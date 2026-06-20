"""Fix the collapsed student: behavior-clone the heuristic (cheap, balanced data) so the net
plays at least at heuristic level without collapsing to 'never flee', THEN learn the teacher's
edge on top. Reuses full_distill (encoder, vocab, net, eval) and the CACHED teacher data.

- gen_heuristic_data: many heuristic-vs-heuristic full games, recording at each searched decision
  (encode_ctx, the heuristic's chosen action as a one-hot policy target, legal mask, seat outcome).
- combine with the cached teacher data (visit-distribution policy), teacher upweighted.
- train with a held-out val split + best-checkpoint, then eval BOTH a heuristic-clone-only net
  (sanity: can the net represent the heuristic? -> no pipeline bug) and the combined student.

Usage: python full_warmstart.py [heur_games] [epochs] [teacher_cache]
"""
import os

# single training process -> let BLAS use all cores (set BEFORE importing full_distill/torch,
# so full_distill's setdefault(...,'1') no-ops and torch's MKL/OpenMP backend sees the high count)
_THREADS = str(min(10, os.cpu_count() or 4))
for _v in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_v] = _THREADS

import pickle
import random
import sys
import time

import numpy as np

import full_distill as fd
import real_search as rs
from ai_policy import DefaultDungeonPolicy
from full_env import build_full_match, make_full_dungeon
from simu import ordonnanceur


class _CloneRec:
    """Heuristic policy that records (encode, heuristic-action one-hot, mask) at searched
    decisions of one seat -- behavior-cloning targets."""

    def __init__(self, searcher):
        self.searcher = searcher
        self.heur = DefaultDungeonPolicy()
        self.records = []

    def decide(self, ctx):
        if ctx.actor is not self.searcher or ctx.kind.name not in rs.TREE_KINDS or not rs.legal_keys(ctx):
            return self.heur.decide(ctx)
        action = self.heur.decide(ctx)
        v = fd.key_to_vocab(ctx, rs.action_key(ctx, action))
        if v in fd.VIDX:
            pol = np.zeros(fd.NACT, dtype=np.float32)
            mask = np.zeros(fd.NACT, dtype=bool)
            for _, vv in fd.legal_pairs(ctx):
                mask[fd.VIDX[vv]] = True
            pol[fd.VIDX[v]] = 1.
            self.records.append([fd.encode_ctx(ctx), pol, mask])
        return action


def gen_heuristic_data(games, seed0=300000):
    data = []
    t0 = time.perf_counter()
    for g in range(games):
        seed = seed0 + g
        random.seed(seed)
        np.random.seed(seed & 0x7FFFFFFF)
        joueurs, reserve = build_full_match(seed)
        seat = seed % len(joueurs)
        pol = _CloneRec(joueurs[seat])
        winner, js = ordonnanceur(joueurs, make_full_dungeon(), reserve, log=False, policy=pol)
        z = 1.0 if winner is js[seat] else -1.0
        data += [(f, p, m, z) for f, p, m in pol.records]
        if (g + 1) % 500 == 0:
            print(f"    heuristic gen {g+1}/{games} | {len(data)} decisions | {time.perf_counter()-t0:.0f}s", flush=True)
    return data


if __name__ == '__main__':
    import torch
    torch.set_num_threads(min(10, os.cpu_count() or 4))   # single training process -> use all cores
    HG = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    EPOCHS = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    CACHE = sys.argv[3] if len(sys.argv) > 3 else 'artifacts/full_gen_300_500.pkl'

    print(f"[1] heuristic behavior-clone data: {HG} games...", flush=True)
    heur_data = gen_heuristic_data(HG)
    print(f"    {len(heur_data)} heuristic decisions", flush=True)

    teach = pickle.load(open(CACHE, 'rb'))['data']
    print(f"    teacher data (cached): {len(teach)} decisions", flush=True)

    # --- sanity: clone-only net should reproduce the heuristic (~28%), proving no pipeline bug
    print("[2] train heuristic-clone-only net (sanity)...", flush=True)
    net_h = fd.make_net()
    fd.train(net_h, heur_data, EPOCHS)
    sw_h, hw_h = fd.eval_net_and_baseline(net_h, 400)
    print(f"  CLONE-ONLY student: {sw_h:.1%}  | heuristic baseline {hw_h:.1%}", flush=True)

    # --- student: heuristic (broad, anti-collapse) + teacher upweighted (the edge)
    print("[3] train combined (heuristic + teacher x4)...", flush=True)
    combined = heur_data + teach * 4
    net = fd.make_net()
    fd.train(net, combined, EPOCHS)
    torch.save(net.state_dict(), 'artifacts/full_warmstart.pt')
    sw, hw = fd.eval_net_and_baseline(net, 400)
    print(f"\n  WARMSTART student: {sw:.1%}")
    print(f"  HEURISTIC baseline (same seeds): {hw:.1%}")
    print(f"  -> student edge: {sw-hw:+.1%}")
    print(f"  (teacher@300 was ~41% on its gen bank)")
