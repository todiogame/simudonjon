"""Decisive test: can a net CLONE the heuristic with the v2 (full visible state) encoder?
v1 encoder clone was 17.8% (vs heuristic 30.2%) -- if v2 lifts it toward ~30%, the wall was
missing features (representation); if it stays low, it's the object embeddings starved of data.

Trains a net to copy the heuristic on free heuristic-vs-heuristic full games (v2 encoder), then
measures its seat-win vs the heuristic baseline on the same held-out seeds/seats.

Usage: python full_clone_test.py [heur_games] [epochs]
"""
import os

_THREADS = str(min(10, os.cpu_count() or 4))
for _v in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_v] = _THREADS                          # before importing full_distill/torch

import random
import sys
import time

import numpy as np

import full_distill as fd
import full_encoder as fe
import real_search as rs
from ai_policy import DefaultDungeonPolicy
from full_env import build_full_match, make_full_dungeon
from simu import ordonnanceur


class _CloneRec:
    def __init__(self, searcher):
        self.searcher = searcher
        self.h = DefaultDungeonPolicy()
        self.records = []

    def decide(self, ctx):
        if ctx.actor is not self.searcher or ctx.kind.name not in rs.TREE_KINDS or not rs.legal_keys(ctx):
            return self.h.decide(ctx)
        a = self.h.decide(ctx)
        v = fe.key_to_vocab(ctx, rs.action_key(ctx, a))
        if v in fe.VIDX:
            pol = np.zeros(fe.NACT, dtype=np.float32)
            mask = np.zeros(fe.NACT, dtype=bool)
            for _, vv in fe.legal_pairs(ctx):
                mask[fe.VIDX[vv]] = True
            pol[fe.VIDX[v]] = 1.
            self.records.append([fe.encode_ctx(ctx), pol, mask])
        return a


def gen(games, seed0=300000):
    data = []
    t0 = time.perf_counter()
    for g in range(games):
        seed = seed0 + g
        random.seed(seed)
        np.random.seed(seed & 0x7FFFFFFF)
        j, r = build_full_match(seed)
        seat = seed % len(j)
        pol = _CloneRec(j[seat])
        w, js = ordonnanceur(j, make_full_dungeon(), r, log=False, policy=pol)
        z = 1.0 if w is js[seat] else -1.0
        data += [(f, p, m, z) for f, p, m in pol.records]
        if (g + 1) % 500 == 0:
            print(f"  gen {g+1}/{games} | {len(data)} decisions | {time.perf_counter()-t0:.0f}s", flush=True)
    return data


def _net_action(net, ctx, heur):
    import torch
    pairs = fe.legal_pairs(ctx)
    if not pairs:
        return heur.decide(ctx)
    with torch.no_grad():
        logits, _ = net(torch.from_numpy(fe.encode_ctx(ctx)).unsqueeze(0))
    logits = logits[0].numpy()
    bk, _ = max(pairs, key=lambda kv: logits[fe.VIDX[kv[1]]])
    return rs.action_from_key(ctx, bk, heur, lambda: heur.decide(ctx))


def eval_clone(net, n, seed0=800000):
    class NP:
        def __init__(s, searcher):
            s.searcher, s.h = searcher, DefaultDungeonPolicy()

        def decide(s, ctx):
            use = ctx.actor is s.searcher and ctx.kind.name in rs.TREE_KINDS and rs.legal_keys(ctx)
            return _net_action(net, ctx, s.h) if use else s.h.decide(ctx)

    sw = hw = 0
    for g in range(n):
        seed = seed0 + g
        random.seed(seed)
        np.random.seed(seed & 0x7FFFFFFF)
        j, r = build_full_match(seed)
        seat = seed % len(j)
        w, js = ordonnanceur(j, make_full_dungeon(), r, log=False, policy=NP(j[seat]))
        sw += w is js[seat]
        random.seed(seed)
        np.random.seed(seed & 0x7FFFFFFF)
        j, r = build_full_match(seed)
        w, js = ordonnanceur(j, make_full_dungeon(), r, log=False, policy=DefaultDungeonPolicy())
        hw += w is js[seat]
    return sw / n, hw / n


if __name__ == '__main__':
    import torch
    torch.set_num_threads(min(10, os.cpu_count() or 4))
    HG = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    EP = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    print(f"clone test, v2 encoder ({fe.NFEAT} features). gen {HG} heuristic games...", flush=True)
    data = gen(HG)
    print(f"{len(data)} decisions; training {EP} epochs...", flush=True)
    net = fe.make_net()
    fd.train(net, data, EP)
    torch.save(net.state_dict(), 'artifacts/full_clone_v2.pt')
    sw, hw = eval_clone(net, 400)
    print(f"\nCLONE v2 student: {sw:.1%}  | heuristic baseline {hw:.1%}  | edge {sw-hw:+.1%}")
    print("(reference: v1 encoder clone was 17.8% vs 30.2%)")
