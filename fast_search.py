"""Clone-based ISMCTS (Phase B) -- same algorithm as real_search, but each iteration CLONES a
turn-boundary snapshot and resumes, instead of rebuilding the match and re-simulating from
move 0. Removes the per-iteration match rebuild + whole-game prefix replay.

Mechanism:
  - The live game is driven inline by `ordonnanceur(policy=_LivePolicy, on_turn_start=...)`
    (no thread needed now that the engine is resumable). At each turn boundary we snapshot
    (clone_state, index, RNG-state). Within a turn we record the searcher's decision keys.
  - To search a decision: for each iteration, restore the turn-start RNG, clone the snapshot,
    resume the engine with real_search._ISMCTSPolicy. The policy replays the WITHIN-TURN
    decisions (a handful) to reach the root, determinizes the unseen deck (reseeded per iter,
    identical scheme to real_search), then PUCT-descends / rolls out. Outcome backs up the tree.

Because the root state reconstructed here is identical to the one real_search reaches by full
re-simulation, and the determinization is seeded the same way, fast_search and real_search
produce IDENTICAL searches -- verified in __main__ (same outcomes + same visit dicts), at a
fraction of the wall time.

Usage: python fast_search.py [n_seeds] [iters]   (equivalence + speed vs real_search)
"""
import gc
import math
import random
import sys
import time

import numpy as np

import real_search as rs
from ai_policy import DefaultDungeonPolicy
from fast_engine import clone_state
from simu import ordonnanceur


def fast_ismcts_decide(snapshot, within_prefix, searcher_seat, seed, n_iters, c=1.4, p_heur=0.75,
                       progress=None, deadline=None, return_stats=False):
    """Decide the current searcher decision via n_iters clone+resume re-simulations from a
    turn-boundary snapshot. `within_prefix` = the searcher's tree keys already chosen THIS turn.
    iter_seed scheme matches real_search exactly so the two searches are identical."""
    clone0, turn_index, rng_state = snapshot
    root = rs.Node()
    start = time.perf_counter()
    stats = {
        "iterationsRequested": n_iters,
        "iterationsCompleted": 0,
        "iterationsFailed": 0,
        "lastIteration": 0,
        "lastStage": "start",
        "elapsedMs": 0,
        "timedOut": False,
        "rootEdges": 0,
    }
    progress_every = 1 if n_iters <= 20 else max(10, n_iters // 10)

    def tick(stage, force=False, extra=None):
        stats["lastStage"] = stage
        stats["elapsedMs"] = int((time.perf_counter() - start) * 1000)
        stats["rootEdges"] = len(root.edges)
        if progress is None:
            return
        first_resume = stage == "resume" and stats["lastIteration"] == 1
        if (
            force
            or first_resume
            or stats["iterationsCompleted"] == n_iters
            or (stats["iterationsCompleted"] > 0 and stats["iterationsCompleted"] % progress_every == 0)
        ):
            payload = dict(stats)
            if extra:
                payload.update(extra)
            progress(payload)

    tick("start", force=True)
    _gc_on = gc.isenabled()
    switch_interval = sys.getswitchinterval()
    sys.setswitchinterval(min(switch_interval, 0.001))
    gc.disable()                                       # A4: per-iter clones churn the allocator;
    try:                                               # skip GC scans, free the batch at the end
        for it in range(n_iters):
            if deadline is not None and time.perf_counter() >= deadline:
                stats["timedOut"] = True
                tick("timeout", force=True)
                break
            stats["lastIteration"] = it + 1
            tick("clone")
            random.setstate(rng_state[0])              # turn-start RNG: within-turn replay reproduces live
            np.random.set_state(rng_state[1])
            clone = clone_state(clone0)
            searcher = clone.joueurs[searcher_seat]
            pol = rs._ISMCTSPolicy(searcher, within_prefix, root,
                                   iter_seed=(seed * 1000003 + it + 1), c=c, p_heur=p_heur)
            try:
                tick("resume")
                winner, _ = ordonnanceur(None, None, None, log=False, policy=pol,
                                         resume_state=clone, resume_index=turn_index)
            except Exception:
                stats["iterationsFailed"] += 1
                tick("iteration_failed", extra={"errorIteration": it + 1})
                time.sleep(0)
                continue
            stats["iterationsCompleted"] += 1
            outcome = 1.0 if winner is searcher else (0.0 if winner is None else -1.0)
            for nd, k in pol.path:
                nd.edges[k][0] += 1
                nd.edges[k][1] += outcome
            tick("backup")
            time.sleep(0)
    finally:
        sys.setswitchinterval(switch_interval)
        if _gc_on:
            gc.enable()
        gc.collect()
    tick("done", force=True)
    if not root.edges:
        if return_stats:
            return None, {}, stats
        return None, {}
    best = max(root.edges, key=lambda k: root.edges[k][0])
    visits = {k: e[0] for k, e in root.edges.items()}
    if return_stats:
        return best, visits, stats
    return best, visits


class _LivePolicy:
    """Drives the live game: searcher seat = clone-based ISMCTS, other seat = heuristic.
    Snapshots at each turn start; records the searcher's within-turn keys + (ctx, visits)."""

    def __init__(self, searcher_seat, seed, n_iters, c=1.4, p_heur=0.75, progress=None, max_seconds=None):
        self.seat, self.seed, self.n_iters, self.c, self.p_heur = searcher_seat, seed, n_iters, c, p_heur
        self.heur = DefaultDungeonPolicy()
        self.searcher = None
        self.snapshot = None
        self.within = []
        self.records = []
        self.progress = progress
        self.max_seconds = max_seconds
        self.last_stats = None

    def on_turn_start(self, Jeu, index):
        if self.searcher is None:
            self.searcher = Jeu.joueurs[self.seat]
        self.snapshot = (clone_state(Jeu), index, (random.getstate(), np.random.get_state()))
        self.within = []

    def decide(self, ctx):
        if ctx.actor is not self.searcher or ctx.kind.name not in rs.TREE_KINDS or not rs.legal_keys(ctx):
            return self.heur.decide(ctx)
        rs_state, np_state = random.getstate(), np.random.get_state()      # preserve the live RNG
        deadline = time.perf_counter() + self.max_seconds if self.max_seconds else None
        best, visits, self.last_stats = fast_ismcts_decide(
            self.snapshot,
            list(self.within),
            self.seat,
            self.seed,
            self.n_iters,
            self.c,
            self.p_heur,
            progress=self.progress,
            deadline=deadline,
            return_stats=True,
        )
        random.setstate(rs_state)
        np.random.set_state(np_state)
        if best is None:
            best = rs.action_key(ctx, self.heur.decide(ctx))
        self.records.append((ctx, visits))
        self.within.append(best)
        return rs.action_from_key(ctx, best, self.heur, lambda: self.heur.decide(ctx))


def play_game(seed, searcher_seat, n_iters, c=1.4, p_heur=0.75):
    """Play one real game (searcher=clone ISMCTS, opponent=ai_policy). Returns (outcome, records)."""
    from rl_toy_env import build_toy_match, make_dungeon

    random.seed(seed)
    np.random.seed(seed & 0x7FFFFFFF)
    joueurs, reserve = build_toy_match(seed, deck='toy')
    donjon = make_dungeon('toy')
    live = _LivePolicy(searcher_seat, seed, n_iters, c=c, p_heur=p_heur)
    winner, js = ordonnanceur(joueurs, donjon, reserve, log=False,
                              policy=live, on_turn_start=live.on_turn_start)
    searcher = js[searcher_seat]
    outcome = 1 if winner is searcher else (0 if winner is None else -1)
    return outcome, live.records


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    ITERS = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    print(f"fast_search vs real_search: {N} seeds @ {ITERS} iters, p_heur=0.75\n")

    same_outcome = same_visits = 0
    t_fast = t_real = 0.0
    for s in range(N):
        seat = s % 2
        t0 = time.perf_counter()
        of, rf = play_game(s, seat, ITERS)
        t_fast += time.perf_counter() - t0

        t0 = time.perf_counter()
        orr, rr = rs.play_teacher_game(s, seat, ITERS)
        t_real += time.perf_counter() - t0

        same_outcome += (of == orr)
        vf = [v for _, v in rf]
        vr = [v for _, v in rr]
        same_visits += (vf == vr)
        flag = '' if (of == orr and vf == vr) else '  <-- DIFF'
        print(f"  seed {s}: fast={of} real={orr} | decisions f/r={len(rf)}/{len(rr)} | "
              f"visits match={vf == vr}{flag}")

    print(f"\nsame outcome: {same_outcome}/{N} | same visit dicts: {same_visits}/{N}")
    print(f"wall time: fast {t_fast:.1f}s  real {t_real:.1f}s  -> speedup x{t_real/max(t_fast,1e-9):.2f}")
