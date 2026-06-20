"""Benchmark + identical-result validator for teacher-gen speedups.

Plays K full clone-based ISMCTS teacher games at a modest iter count, records a SIGNATURE
(per searcher decision: kind + the full visit dict) hashed to md5, plus the wall time. A
lossless optimization MUST keep SIG identical to the baseline while lowering the time.

Usage: python bench_opt.py [iters] [n_games] [seed0]
"""
import os

for _v in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(_v, '1')

import hashlib
import json
import random
import sys
import time

import numpy as np

import fast_search
import real_search as rs
from full_env import build_full_match, make_full_dungeon
from simu import ordonnanceur


class _BenchPol(fast_search._LivePolicy):
    def __init__(self, seat, seed, n_iters):
        super().__init__(seat, seed, n_iters)
        self.sig = []

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
        self.sig.append((ctx.kind.name, sorted((str(k), int(v)) for k, v in visits.items())))
        self.within.append(best)
        return rs.action_from_key(ctx, best, self.heur, lambda: self.heur.decide(ctx))


def run(iters, n, seed0):
    sigs = []
    t0 = time.perf_counter()
    for g in range(n):
        seed = seed0 + g
        random.seed(seed)
        np.random.seed(seed & 0x7FFFFFFF)
        j, r = build_full_match(seed)
        seat = seed % len(j)
        pol = _BenchPol(seat, seed, iters)
        w, js = ordonnanceur(j, make_full_dungeon(), r, log=False, policy=pol, on_turn_start=pol.on_turn_start)
        out = 1 if w is js[seat] else (0 if w is None else -1)
        sigs.append((seed, out, pol.sig))
    el = time.perf_counter() - t0
    h = hashlib.md5(json.dumps(sigs, default=str).encode()).hexdigest()
    return el, h, sum(1 for s in sigs if s[1] == 1)


if __name__ == '__main__':
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 950000
    el, h, wins = run(iters, n, seed0)
    print(f"games={n} iters={iters} seed0={seed0} | time={el:.2f}s ({el/n:.2f}s/game) | "
          f"teacher_wins={wins}/{n} | SIG={h}")
