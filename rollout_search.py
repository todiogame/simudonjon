"""Depth-parameterised rollout-search player on the REAL engine -- learns every
object by SIMULATING its real consequences, zero per-object code.

  depth=0 : the heuristic itself (base case).
  depth=d : at each decision, score every option the engine offers by replaying
            this game from its seed (deterministic), forcing the option, then
            letting a depth-(d-1) search play out -- keep the best option.

The objective is swappable: outcome_kills (how much an object lets you accomplish)
or outcome_win (the actual 1v1 result, for winrate tests). The match builder is
swappable too (forced hand vs random hand), so the re-sim rebuilds the same game.
Candidates come from context.options and outcomes from the engine -> all objects
are handled the same way, nothing hand-coded per object.
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
from objets import (ArmureEnCuir, HacheDeGlace, KebabRevigorant, MarteauDeGuerre,
                    OsseletsDeResurrection, TorcheBleue)
from rl_train import BINARY_KINDS, ORDER_OBJECT_KINDS, SINGLE_OBJECT_KINDS
from simu import ordonnanceur

DECK = 'toy'
BINARY = set(BINARY_KINDS)
SINGLE = set(SINGLE_OBJECT_KINDS)
ORDER = set(ORDER_OBJECT_KINDS)


def build_forced(seed, hand_classes):
    """Deterministic 2-player toy match where both seats get hand_classes."""
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)
    joueurs = [Joueur(nom, env.make_toy_hero(), [c() for c in hand_classes])
               for nom in env.TOY_PLAYER_NAMES]
    return joueurs, []


def outcome_kills(jf, seat, winner):
    # Monsters defeated; dying ends the run, so survival is valued instrumentally.
    return len(jf[seat].pile_monstres_vaincus)


def outcome_win(jf, seat, winner):
    # The actual duel result: +1 win / 0 draw / -1 loss, with a tiny score-margin
    # tie-break so the search ranks decisively between equal-result actions.
    me = jf[seat]
    opp = max((len(o.pile_monstres_vaincus) for o in jf if o is not me), default=0)
    margin = len(me.pile_monstres_vaincus) - opp
    base = 1.0 if me is winner else (0.0 if winner is None else -1.0)
    return base + 0.001 * margin


def outcome_margin(jf, seat, winner):
    # Denser objective: out-score the opponent (you win the duel by being a
    # surviving finalist with the top score). Less risk-averse than +1/-1, so the
    # search plays to SCORE rather than just survive. Dying is penalised (a corpse
    # can't be the finalist).
    me = jf[seat]
    opp = max((len(o.pile_monstres_vaincus) for o in jf if o is not me), default=0)
    margin = float(len(me.pile_monstres_vaincus) - opp)
    if not (me.vivant or me.fuite_reussie):
        margin -= 5.0
    return margin


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
    if tag == 'P':                              # a permutation / subset, by indices
        return [context.options[i] for i in token[1]]
    return require_permutation(tuple(context.options), context.options, decision_name='rs')


def _encode(action, context):
    """Encode an arbitrary (heuristic) action into a replay token."""
    if action is True or action is False:
        return ('B', action)
    if action is CombatObjectChoice.RESOLVE_NOW:
        return ('R',)
    if action is None:
        return ('N',)
    opts = list(context.options)
    if isinstance(action, (list, tuple)):
        idx = [i for x in action for i, o in enumerate(opts) if o is x]
        return ('P', idx)
    for i, o in enumerate(opts):
        if o is action or o == action:
            return ('I', i)
    return ('N',)


def _candidates(context):
    """Searchable (action, token) options, or None to defer to the heuristic for
    kinds we don't cleanly search (empty options, multi-object, exotic, ...)."""
    k = context.kind
    if k in BINARY:
        return [(True, ('B', True)), (False, ('B', False))]
    if k is DecisionKind.CHOOSE_COMBAT_OBJECT:
        cs = [(o, ('I', i)) for i, o in enumerate(context.options)]
        cs.append((CombatObjectChoice.RESOLVE_NOW, ('R',)))
        return cs
    if k in SINGLE and context.options:
        cs = [(o, ('I', i)) for i, o in enumerate(context.options)]
        if context.meta('allow_none', False):
            cs.append((None, ('N',)))
        return cs
    if k in ORDER:
        return [(_decode(('O',), context), ('O',))]   # identity ordering
    return None                                       # -> defer to heuristic


def play_out_score(seed, seat, build_fn, prefix, tail_depth, objective):
    """Re-sim: seat replays `prefix`, then a depth-`tail_depth` search takes over;
    return the seat's objective. RNG is saved/restored so the caller's stream (and
    any outer re-sim) is untouched."""
    rstate, npstate = random.getstate(), np.random.get_state()
    try:
        joueurs, objets = build_fn(seed)
        tail = SearchPolicy(seed, seat, tail_depth, build_fn, objective, prefix=prefix)
        pols = {seat: tail, 1 - seat: default_dungeon_policy()}
        routed = env.routed_toy_policy(pols, joueurs)
        with contextlib.redirect_stdout(io.StringIO()):
            winner, jf = ordonnanceur(joueurs, env.make_dungeon(DECK), objets, False, policy=routed)
        return objective(jf, seat, winner)
    finally:
        random.setstate(rstate)
        np.random.set_state(npstate)


class SearchPolicy:
    def __init__(self, seed, seat, depth, build_fn, objective=outcome_kills, prefix=None):
        self.seed, self.seat, self.depth = seed, seat, depth
        self.build_fn, self.objective = build_fn, objective
        self.prefix = list(prefix or [])
        self.my = []
        self.n = 0
        self.heur = default_dungeon_policy()

    def decide(self, context):
        i = self.n
        self.n += 1
        if i < len(self.prefix):
            return _decode(self.prefix[i], context)
        if self.depth == 0:
            return self.heur.decide(context)       # final rollout: no recording
        cands = _candidates(context)
        if cands is None:                          # defer exotic kinds to heuristic
            action = self.heur.decide(context)
            self.my.append(_encode(action, context))
            return action
        if len(cands) == 1:
            self.my.append(cands[0][1])
            return cands[0][0]
        best_action = best_token = None
        best_score = None
        for action, token in cands:
            s = play_out_score(self.seed, self.seat, self.build_fn,
                               self.prefix + self.my + [token], self.depth - 1, self.objective)
            if best_score is None or s > best_score:
                best_score, best_action, best_token = s, action, token
        self.my.append(best_token)
        return best_action


class _ReplayReshuffleRollout:
    """Re-sim seat policy for DETERMINIZED 1-ply search. Replays `prefix` on the
    real deck/dice (so the pre-decision state is reproduced exactly); AT the probed
    decision it reshuffles the UNSEEN deck (ordre[index:]) and re-seeds the dice
    with `sample_seed`, then forces the probe; afterwards the heuristic plays out.
    => the search never sees the true future, only one plausible sampled future."""

    def __init__(self, prefix, probe, sample_seed, tail_factory=None):
        self.prefix = prefix
        self.probe = probe
        self.sample_seed = sample_seed
        self.tail = (tail_factory or default_dungeon_policy)()   # rollout policy after the probe
        self.n = 0

    def decide(self, context):
        i = self.n
        self.n += 1
        if i < len(self.prefix):
            return _decode(self.prefix[i], context)
        if i == len(self.prefix):
            self._determinize(context)
            return _decode(self.probe, context)
        return self.tail.decide(context)

    def _determinize(self, context):
        d = getattr(context.game, 'donjon', None)
        if d is not None and getattr(d, 'ordre', None) is not None:
            idx = d.index
            rem = list(d.ordre[idx:])
            random.Random(self.sample_seed).shuffle(rem)
            d.ordre = np.concatenate([np.asarray(d.ordre[:idx]),
                                      np.asarray(rem, dtype=d.ordre.dtype)])
        random.seed(self.sample_seed)
        np.random.seed(self.sample_seed & 0xFFFFFFFF)


def play_out_det(seed, seat, build_fn, prefix, probe, sample_seed, objective,
                 tail_factory=None, opp_factory=None):
    rstate, npstate = random.getstate(), np.random.get_state()
    try:
        joueurs, objets = build_fn(seed)
        agent = _ReplayReshuffleRollout(prefix, probe, sample_seed, tail_factory)
        opp = (opp_factory or default_dungeon_policy)()
        pols = {seat: agent, 1 - seat: opp}
        routed = env.routed_toy_policy(pols, joueurs)
        with contextlib.redirect_stdout(io.StringIO()):
            winner, jf = ordonnanceur(joueurs, env.make_dungeon(DECK), objets, False, policy=routed)
        return objective(jf, seat, winner)
    finally:
        random.setstate(rstate)
        np.random.set_state(npstate)


class DetSearchPolicy:
    """Realistic (non-clairvoyant) 1-ply search: each option is scored as the MEAN
    over k_samples determinized futures, so it decides on expectation without
    knowing the deck order."""

    def __init__(self, seed, seat, build_fn, objective=outcome_win, k_samples=8,
                 tail_factory=None, opp_factory=None):
        self.seed, self.seat, self.build_fn, self.objective = seed, seat, build_fn, objective
        self.k = k_samples
        self.tail_factory = tail_factory      # rollout policy after the probe (None=heuristic)
        self.opp_factory = opp_factory        # opponent in re-sims (None=heuristic)
        self.committed = []
        self.heur = default_dungeon_policy()

    def decide(self, context):
        cands = _candidates(context)
        if cands is None:
            action = self.heur.decide(context)
            self.committed.append(_encode(action, context))
            return action
        if len(cands) == 1:
            self.committed.append(cands[0][1])
            return cands[0][0]
        base = (self.seed * 1_000_003 + len(self.committed) * 97)  # shared futures across candidates
        best_action = best_token = None
        best_score = None
        for action, token in cands:
            total = 0.0
            for j in range(self.k):
                total += play_out_det(self.seed, self.seat, self.build_fn,
                                      self.committed, token, base + j, self.objective,
                                      self.tail_factory, self.opp_factory)
            avg = total / self.k
            if best_score is None or avg > best_score:
                best_score, best_action, best_token = avg, action, token
        self.committed.append(best_token)
        return best_action


def measure(depth, hand, n):
    build = lambda s: build_forced(s, hand)
    kills = 0
    for s in range(n):
        seat = s % 2
        joueurs, objets = build(s)
        agent = SearchPolicy(s, seat, depth, build, outcome_kills)
        pols = {seat: agent, 1 - seat: default_dungeon_policy()}
        routed = env.routed_toy_policy(pols, joueurs)
        with contextlib.redirect_stdout(io.StringIO()):
            winner, jf = ordonnanceur(joueurs, env.make_dungeon(DECK), objets, False, policy=routed)
        kills += len(jf[seat].pile_monstres_vaincus)
    return kills / n


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    DEPTH = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    BASE = [KebabRevigorant, MarteauDeGuerre, ArmureEnCuir, TorcheBleue]
    for label, hand in (("Osselets (hard)", [OsseletsDeResurrection] + BASE),
                        ("Hache (easy)", [HacheDeGlace] + BASE)):
        k1 = measure(DEPTH, hand, N)
        k0 = measure(DEPTH, BASE, N)
        print(f"  {label:16} kills {k0:.2f}->{k1:.2f} (value {k1-k0:+.2f})")
