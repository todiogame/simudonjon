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
from heros import Perso
from joueurs import Joueur
from monstres import CarteEvent, CarteMonstre
from objets import Objet
from simu import GameState, ordonnanceur

# A1b (lossless): a memo-aware fast __deepcopy__ for the leaf game classes (objects, cards).
# Default deepcopy pays __reduce_ex__/_reconstruct per object; this shares immutables by ref and
# deepcopies the rest THROUGH THE MEMO -- so cross-refs / shared card identities / cycles stay
# correct, just faster. Applied to Objet + the card classes (they hold only scalars + lists, no
# refs to other game objects, but the memo handles it if any ever appear).
_IMMUTABLE = (int, float, bool, str, bytes, type(None))


def _fast_deepcopy(self, memo):
    new = type(self).__new__(type(self))
    memo[id(self)] = new
    nd = new.__dict__
    for k, v in self.__dict__.items():
        nd[k] = v if type(v) in _IMMUTABLE else copy.deepcopy(v, memo)
    return new


for _cls in (Objet, CarteMonstre, CarteEvent, Joueur, Perso, GameState):
    _cls.__deepcopy__ = _fast_deepcopy


def _fast_clone_clean(o):
    """Fast clone of a 'clean' object (undealt reserve item): shallow-copy __dict__ + one level of
    container attrs. Reserve objects hold only scalars (+ a types/tags list), no refs to other
    game objects, so this is independent and correct -- and far cheaper than reflective deepcopy."""
    n = object.__new__(type(o))
    d = o.__dict__.copy()
    for k, v in d.items():
        t = type(v)
        if t is list:
            d[k] = v[:]
        elif t is dict:
            d[k] = dict(v)
        elif t is set:
            d[k] = set(v)
    n.__dict__ = d
    return n


def clone_state(Jeu):
    """Deep-copy the game state, detaching the policy first (don't clone it; it's rebound at
    resume time). deepcopy's memo keeps shared card identities consistent across the deck,
    the players' vaincu piles, and cartes_connues.

    A1: the bulky UNSEEN RESERVE (objets_dispo, ~265 undealt objects) is excluded from the
    reflective deepcopy and cloned fast (its objects are clean), giving an independent copy --
    so a rollout that draws/mutates a reserve object stays isolated, byte-identically."""
    pol = Jeu.policy
    saved_players = [
        (j, getattr(j, 'policy', None), getattr(j, 'decision_provider', None))
        for j in Jeu.joueurs
    ]
    reserve = Jeu.objets_dispo
    event_sink = getattr(Jeu, "event_sink", None)
    decision_provider = getattr(Jeu, "decision_provider", None)
    bot_delay_ms = getattr(Jeu, "bot_delay_ms", 0)
    discard = Jeu.defausse
    deck_on_change = getattr(Jeu.donjon, "on_change", None)
    Jeu.policy = None
    Jeu.event_sink = None
    Jeu.decision_provider = None
    Jeu.bot_delay_ms = 0
    for j in Jeu.joueurs:
        j.policy = None
        j.decision_provider = None
    Jeu.objets_dispo = ()                       # keep the heavy reserve out of the reflective copy
    Jeu.defausse = list(discard)
    Jeu.donjon.on_change = None
    try:
        new = copy.deepcopy(Jeu)
    finally:
        Jeu.policy = pol
        Jeu.event_sink = event_sink
        Jeu.decision_provider = decision_provider
        Jeu.bot_delay_ms = bot_delay_ms
        Jeu.objets_dispo = reserve
        Jeu.defausse = discard
        Jeu.donjon.on_change = deck_on_change
        for j, p, provider in saved_players:
            j.policy = p
            j.decision_provider = provider
    new.objets_dispo = [_fast_clone_clean(o) for o in reserve]
    new.event_sink = None
    new.decision_provider = None
    new.bot_delay_ms = 0
    return new


def _seed(s):
    random.seed(s)
    np.random.seed(s & 0x7FFFFFFF)


def _result(winner, joueurs):
    w = winner.nom if winner is not None else None
    return (w, tuple((j.nom, j.score_final, j.vivant, j.dans_le_dj, j.pv_total,
                      len(j.pile_monstres_vaincus)) for j in joueurs))


def run_normal(seed):
    from rl_toy_env import build_toy_match, make_dungeon

    _seed(seed)
    joueurs, reserve = build_toy_match(seed, deck='toy')
    donjon = make_dungeon('toy')
    winner, js = ordonnanceur(joueurs, donjon, reserve, log=False, policy=DefaultDungeonPolicy())
    return _result(winner, js)


def run_resume_at(seed, snapshot_turn):
    from rl_toy_env import build_toy_match, make_dungeon

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
