"""Cloneable / resumable real engine -- Phase A of the linear-cost search refactor.

`simu.ordonnanceur` now accepts (resume_state, resume_index, on_turn_start). This module adds:
  - clone_state(Jeu): a deep-copy of the full game state, EXCLUDING the policy (which is
    swapped in at resume time). A turn-boundary clone + ordonnanceur(resume_state=clone, ...)
    continues the game with zero re-setup and zero prefix re-simulation.
  - an EQUIVALENCE HARNESS proving the resume path is byte-identical to a normal run:
      * determinism: same seed -> same result (twice).
      * mid-game resume: snapshot at turn N (clone + RNG state), let the original finish, then
        restore RNG and resume from the clone -> must reproduce the original's final result.

This is the foundation for clone-based ISMCTS (snapshot at a turn boundary, branch from the
clone) instead of re-simulating from move 0 every iteration.

Usage: python fast_engine.py [n_seeds]
"""
import copy
import random
import sys

import numpy as np

from ai_policy import DefaultDungeonPolicy
from rl_toy_env import build_toy_match, make_dungeon
from simu import ordonnanceur


def clone_state(Jeu):
    """Deep-copy the game state, detaching the policy first (don't clone it; it's rebound at
    resume time). deepcopy's memo keeps shared card identities consistent across the deck,
    the players' vaincu piles, and cartes_connues."""
    pol = Jeu.policy
    saved = [(j, getattr(j, 'policy', None)) for j in Jeu.joueurs]
    Jeu.policy = None
    for j in Jeu.joueurs:
        j.policy = None
    try:
        new = copy.deepcopy(Jeu)
    finally:
        Jeu.policy = pol
        for j, p in saved:
            j.policy = p
    return new


def _seed(s):
    random.seed(s)
    np.random.seed(s & 0x7FFFFFFF)


def _result(winner, joueurs):
    w = winner.nom if winner is not None else None
    return (w, tuple((j.nom, j.score_final, j.vivant, j.dans_le_dj, j.pv_total,
                      len(j.pile_monstres_vaincus)) for j in joueurs))


def run_normal(seed):
    _seed(seed)
    joueurs, reserve = build_toy_match(seed, deck='toy')
    donjon = make_dungeon('toy')
    winner, js = ordonnanceur(joueurs, donjon, reserve, log=False, policy=DefaultDungeonPolicy())
    return _result(winner, js)


def run_resume_at(seed, snapshot_turn):
    """Run normally but snapshot at the `snapshot_turn`-th turn boundary; then resume from the
    clone with the SAME RNG. Returns (original_result, resumed_result) or (orig, None) if the
    game had fewer turns than snapshot_turn."""
    _seed(seed)
    joueurs, reserve = build_toy_match(seed, deck='toy')
    donjon = make_dungeon('toy')
    snap = {}
    cnt = [0]

    def on_ts(Jeu, idx):
        cnt[0] += 1
        if cnt[0] == snapshot_turn and 'state' not in snap:
            snap['state'] = clone_state(Jeu)
            snap['idx'] = idx
            snap['rng'] = (random.getstate(), np.random.get_state())

    winner, js = ordonnanceur(joueurs, donjon, reserve, log=False,
                              policy=DefaultDungeonPolicy(), on_turn_start=on_ts)
    orig = _result(winner, js)
    if 'state' not in snap:
        return orig, None

    random.setstate(snap['rng'][0])
    np.random.set_state(snap['rng'][1])
    w2, js2 = ordonnanceur(None, None, None, log=False, policy=DefaultDungeonPolicy(),
                           resume_state=snap['state'], resume_index=snap['idx'])
    return orig, _result(w2, js2)


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    print(f"Equivalence harness over {N} seeds\n")

    # 1) determinism
    det_ok = 0
    for s in range(N):
        if run_normal(s) == run_normal(s):
            det_ok += 1
    print(f"[determinism] same seed -> same result: {det_ok}/{N}")

    # 2) mid-game resume fidelity, at several turn boundaries
    SNAP_TURNS = [1, 2, 3, 5, 8, 12]
    tested = match = skipped = 0
    mismatches = []
    for s in range(N):
        for t in SNAP_TURNS:
            orig, resumed = run_resume_at(s, t)
            if resumed is None:
                skipped += 1
                continue
            tested += 1
            if orig == resumed:
                match += 1
            elif len(mismatches) < 5:
                mismatches.append((s, t, orig, resumed))
    print(f"[resume] mid-game clone+resume == original: {match}/{tested} "
          f"({skipped} skipped: game shorter than snapshot turn)")
    for s, t, o, r in mismatches:
        print(f"  MISMATCH seed {s} turn {t}:\n    orig={o}\n    resumed={r}")

    print("\nPASS" if det_ok == N and match == tested and tested > 0 else "\nFAIL")
