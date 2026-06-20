"""Full-game student with the v2 (full visible state) encoder.

Re-generates teacher (clone-based ISMCTS) games recording the v2 encoding + visit policy, trains
the v2 embedding net, evaluates teacher and student vs the heuristic on the same seeds/seats.
(The cached v1 data can't be reused -- different feature layout.)

Usage: python full_student_v2.py [iters] [games] [workers] [epochs] [p_heur]
"""
import os

_THREADS = str(min(10, os.cpu_count() or 4))
for _v in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(_v, _THREADS)                # set BEFORE importing torch so TRAINING is
# multi-threaded. Gen workers are pure-Python (engine + np.shuffle/indexing, no heavy BLAS), so a
# high thread count doesn't oversubscribe them.

import multiprocessing as mp
import pickle
import random
import sys
import time

import numpy as np

import fast_search
import full_encoder as fe
import real_search as rs
from ai_policy import DefaultDungeonPolicy
from full_distill import train                         # generic (net + data), encoder-agnostic
from full_env import build_full_match, make_full_dungeon
from simu import ordonnanceur


class _RecPolicy(fast_search._LivePolicy):
    def __init__(self, seat, seed, n_iters, c=1.4, p_heur=0.75):
        super().__init__(seat, seed, n_iters, c=c, p_heur=p_heur)
        self.records = []

    def decide(self, ctx):
        if ctx.actor is not self.searcher or ctx.kind.name not in rs.TREE_KINDS or not rs.legal_keys(ctx):
            return self.heur.decide(ctx)
        st1, st2 = random.getstate(), np.random.get_state()
        best, visits = fast_search.fast_ismcts_decide(self.snapshot, list(self.within), self.seat,
                                                       self.seed, self.n_iters, self.c, self.p_heur)
        random.setstate(st1)
        np.random.set_state(st2)
        if best is None:
            best = rs.action_key(ctx, self.heur.decide(ctx))
        pol = np.zeros(fe.NACT, dtype=np.float32)
        mask = np.zeros(fe.NACT, dtype=bool)
        for _, v in fe.legal_pairs(ctx):
            mask[fe.VIDX[v]] = True
        tot = sum(visits.values()) or 1
        for k, cnt in visits.items():
            v = fe.key_to_vocab(ctx, k)
            if v in fe.VIDX:
                pol[fe.VIDX[v]] += cnt / tot
        self.records.append([fe.encode_ctx(ctx), pol, mask])
        self.within.append(best)
        return rs.action_from_key(ctx, best, self.heur, lambda: self.heur.decide(ctx))


def _gen_game(seed, iters, p_heur):
    random.seed(seed)
    np.random.seed(seed & 0x7FFFFFFF)
    j, r = build_full_match(seed)
    seat = seed % len(j)
    live = _RecPolicy(seat, seed, iters, p_heur=p_heur)
    w, js = ordonnanceur(j, make_full_dungeon(), r, log=False, policy=live, on_turn_start=live.on_turn_start)
    return [(f, p, m, 1.0 if w is js[seat] else -1.0) for f, p, m in live.records], (1 if w is js[seat] else 0)


def _gen_worker(arg):
    lo, hi, iters, p_heur = arg
    out, w, n = [], 0, 0
    for seed in range(lo, hi):
        recs, win = _gen_game(seed, iters, p_heur)
        out += recs
        w += win
        n += 1
    return out, w, n, (lo, hi)


def gen_data(games, iters, workers, p_heur, cache_path):
    chunk = max(1, min(5, games // (workers * 4) or 1))
    chunks = [(lo, min(lo + chunk, games), iters, p_heur) for lo in range(0, games, chunk)]
    data, w, n, done = [], 0, 0, set()
    if os.path.exists(cache_path):
        ck = pickle.load(open(cache_path, 'rb'))
        data, w, n, done = ck['data'], ck['w'], ck['n'], set(ck['done'])
        print(f"    resume: {n} games / {len(data)} decisions cached", flush=True)
    todo = [c for c in chunks if (c[0], c[1]) not in done]
    t0 = time.perf_counter()
    n0 = n

    def absorb(res):
        nonlocal w, n
        out, cw, cn, key = res
        data.extend(out)
        w += cw
        n += cn
        done.add(key)
        tmp = cache_path + '.tmp'
        pickle.dump({'data': data, 'w': w, 'n': n, 'done': list(done)}, open(tmp, 'wb'))
        os.replace(tmp, cache_path)
        el = time.perf_counter() - t0
        eta = el / max(1, n - n0) * (games - n)
        print(f"    ... {n}/{games} games | teacher {w}/{n}={w/max(1,n):.0%} | {len(data)} dec | "
              f"{el:.0f}s | ETA {eta:.0f}s", flush=True)

    if todo:
        with mp.get_context('spawn').Pool(workers) as pool:
            for res in pool.imap_unordered(_gen_worker, todo):
                absorb(res)
    return data, w, n


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


def eval_student(net, n, seed0=800000):
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
    os.makedirs('artifacts', exist_ok=True)            # fresh machine may not have it
    ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    GAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    WORKERS = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    EPOCHS = int(sys.argv[4]) if len(sys.argv) > 4 else 80
    P_HEUR = float(sys.argv[5]) if len(sys.argv) > 5 else 0.75
    print(f"v2 student: {fe.NFEAT} features. [1] gen {GAMES} teacher games @ {ITERS} iters...", flush=True)
    cache = f'artifacts/full_v2_gen_{ITERS}_{GAMES}.pkl'
    data, w, n = gen_data(GAMES, ITERS, WORKERS, P_HEUR, cache)
    print(f"    {len(data)} decisions; TEACHER@{ITERS} seat-win {w}/{n}={w/n:.1%}", flush=True)
    print("[2] training v2 net...", flush=True)
    net = fe.make_net()
    train(net, data, EPOCHS)
    torch.save(net.state_dict(), 'artifacts/full_student_v2.pt')
    print("[3] eval student vs heuristic (same seeds/seats)...", flush=True)
    sw, hw = eval_student(net, 400)
    print(f"\n  STUDENT v2: {sw:.1%}  | HEURISTIC {hw:.1%}  | edge {sw-hw:+.1%}")
    print(f"  TEACHER@{ITERS}: {w/n:.1%}")
