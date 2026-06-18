"""Rollout-search player on the REAL engine -- learns every object by SIMULATING
its real consequences, with zero per-object code.

At each decision it asks, for every legal option the engine offers: "if I take
this, replay this game from its seed (deterministic) and then let the heuristic
play out -- how do I end up?" and keeps the best option. That is rollout policy
improvement (one step of policy iteration over the heuristic). It is general:
candidates come from context.options, outcomes come from the engine, so it handles
all 12 toy objects (or all 271) the same way -- nothing is hand-coded per object.

We then measure an object's VALUE = (outcome with it in hand) - (without it),
under the heuristic vs under this search player. If search lifts a hard object's
value much more than an easy one's, it shows a stronger player de-biases the
per-object stats -- the whole point of the balancing simulator.

Usage: python rollout_search.py [n_games]
"""
import contextlib
import io
import random
import sys

import numpy as np

import rl_toy_env as env
from ai_decisions import CombatObjectChoice, DecisionKind, require_permutation
from ai_policy import default_dungeon_policy
from joueurs import Joueur
from objets import (ArmureEnCuir, KebabRevigorant, MarteauDeGuerre,
                    OsseletsDeResurrection, TorcheBleue, HacheDeGlace)
from rl_train import BINARY_KINDS, SINGLE_OBJECT_KINDS
from simu import ordonnanceur

DECK = 'toy'
BINARY = set(BINARY_KINDS)
SINGLE = set(SINGLE_OBJECT_KINDS)


def build_forced(seed, hand_classes):
    """Deterministic 2-player toy match where both seats get hand_classes."""
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)
    joueurs = [Joueur(nom, env.make_toy_hero(), [c() for c in hand_classes])
               for nom in env.TOY_PLAYER_NAMES]
    return joueurs, []


# --- replay tokens: reconstruct an action in a fresh (deterministic) re-sim ----
def _decode(token, context):
    tag = token[0]
    if tag == 'B':
        return token[1]
    if tag == 'I':
        return context.options[token[1]]
    if tag == 'R':
        return CombatObjectChoice.RESOLVE_NOW
    if tag == 'N':
        return None
    return require_permutation(tuple(context.options), context.options, decision_name='rs')


def _candidates(context):
    """(action, replay-token) pairs for this decision -- straight from the engine's
    options, so no object is treated specially."""
    k = context.kind
    if k in BINARY:
        return [(True, ('B', True)), (False, ('B', False))]
    if k is DecisionKind.CHOOSE_COMBAT_OBJECT:
        cs = [(o, ('I', i)) for i, o in enumerate(context.options)]
        cs.append((CombatObjectChoice.RESOLVE_NOW, ('R',)))
        return cs
    if k in SINGLE:
        cs = [(o, ('I', i)) for i, o in enumerate(context.options)]
        if context.meta('allow_none', False):
            cs.append((None, ('N',)))
        return cs
    return [(_decode(('O',), context), ('O',))]  # order / other -> identity


class ReplayProbeRollout:
    """Re-sim seat policy: replay `committed` for decisions 0..k-1, force `probe`
    at decision k, defer to the heuristic afterwards."""

    def __init__(self, committed, probe):
        self.committed = committed
        self.probe = probe
        self.rollout = default_dungeon_policy()
        self.n = 0

    def decide(self, context):
        i = self.n
        self.n += 1
        if i < len(self.committed):
            return _decode(self.committed[i], context)
        if i == len(self.committed):
            return _decode(self.probe, context)
        return self.rollout.decide(context)


def _outcome(jf, seat, winner):
    # Objective = monsters defeated. Dying ends your run, so survival is valued
    # INSTRUMENTALLY (to keep killing) rather than as a gameable proxy -- this is
    # exactly "how much did my objects let me accomplish", the value signal we want.
    return len(jf[seat].pile_monstres_vaincus)


class RolloutSearchAgent:
    def __init__(self, seed, seat, hand_classes):
        self.seed, self.seat, self.hand = seed, seat, hand_classes
        self.committed = []

    def decide(self, context):
        cands = _candidates(context)
        if len(cands) == 1:
            self.committed.append(cands[0][1])
            return cands[0][0]
        best_action = best_token = None
        best_score = None
        for action, token in cands:
            s = self._score(token)
            if best_score is None or s > best_score:
                best_score, best_action, best_token = s, action, token
        self.committed.append(best_token)
        return best_action

    def _score(self, probe_token):
        # Isolate the re-sim's RNG so the live game's stream is untouched.
        rstate, npstate = random.getstate(), np.random.get_state()
        try:
            joueurs, objets = build_forced(self.seed, self.hand)
            agent = ReplayProbeRollout(list(self.committed), probe_token)
            pols = {self.seat: agent, 1 - self.seat: default_dungeon_policy()}
            routed = env.routed_toy_policy(pols, joueurs)
            with contextlib.redirect_stdout(io.StringIO()):
                winner, jf = ordonnanceur(joueurs, env.make_dungeon(DECK), objets, False, policy=routed)
            return _outcome(jf, self.seat, winner)
        finally:
            random.setstate(rstate)
            np.random.set_state(npstate)


def measure(player, hand, n):
    kills = survived = 0
    for s in range(n):
        seat = s % 2
        joueurs, objets = build_forced(s, hand)
        agent = (RolloutSearchAgent(s, seat, hand) if player == 'search'
                 else default_dungeon_policy())
        pols = {seat: agent, 1 - seat: default_dungeon_policy()}
        routed = env.routed_toy_policy(pols, joueurs)
        with contextlib.redirect_stdout(io.StringIO()):
            winner, jf = ordonnanceur(joueurs, env.make_dungeon(DECK), objets, False, policy=routed)
        j = jf[seat]
        kills += len(j.pile_monstres_vaincus)
        survived += int(j.vivant or j.fuite_reussie)
    return kills / n, survived / n


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    BASE = [KebabRevigorant, MarteauDeGuerre, ArmureEnCuir, TorcheBleue]
    HARD = [OsseletsDeResurrection] + BASE   # technical (needs heal-to-re-arm)
    EASY = [HacheDeGlace] + BASE             # one-shot any-kill, hard to misplay
    print(f"toy deck, {N} games/cell. VALUE = (metric with object) - (without).\n")
    for label, hand in (("Osselets (hard)", HARD), ("Hache (easy)", EASY)):
        for player in ('heuristic', 'search'):
            k1, s1 = measure(player, hand, N)
            k0, s0 = measure(player, BASE, N)
            print(f"  {label:16} [{player:9}]  kills {k0:.2f}->{k1:.2f} (val {k1-k0:+.2f})   "
                  f"survival {s0:.2f}->{s1:.2f} (val {s1-s0:+.2f})")
        print()
