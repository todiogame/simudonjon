"""Determinised DEEP search (PIMC) on the toy -- the proper test of whether
looking MORE than one ply ahead beats the heuristic (the 1-ply search only
reached parity).

Idea (Perfect-Information Monte Carlo): at a decision, sample N "worlds" (deck
orders consistent with what's been revealed). In each world the future is KNOWN,
so we run an exhaustive depth-d search for the best line. Average each candidate's
value across worlds, pick the best. Depth captures multi-step play (e.g. milking
the Osselets); averaging over worlds keeps it honest (no single-future foresight).

Search access to the engine is by RE-SIMULATION: a node = the action path from
the start; we reach it by replaying that path (deterministically), determinising
the unseen deck at the current decision so every re-sim of one world sees the SAME
sampled future. Slow (no steppable engine yet) but correct -- enough to test the
hypothesis before investing in the engine refactor + AlphaZero.

Usage: python pimc_search.py [n_games] [depth] [n_worlds]
"""
import contextlib
import io
import random
import sys

import numpy as np

import rl_toy_env as env
from ai_policy import default_dungeon_policy
from rollout_search import _candidates, _decode, outcome_win
from simu import ordonnanceur

DECK = 'toy'


class _Stop(Exception):
    def __init__(self, context):
        self.context = context


def _determinize(context, world_seed):
    """Reshuffle the UNSEEN deck (ordre[index:]) and reseed the dice, so this re-sim
    plays one sampled future. Deterministic in world_seed => every re-sim of the
    same world reaches the same future."""
    d = getattr(context.game, 'donjon', None)
    if d is not None and getattr(d, 'ordre', None) is not None:
        idx = d.index
        rem = list(d.ordre[idx:])
        random.Random(world_seed).shuffle(rem)
        d.ordre = np.concatenate([np.asarray(d.ordre[:idx]),
                                  np.asarray(rem, dtype=d.ordre.dtype)])
    random.seed(world_seed)
    np.random.seed(world_seed & 0xFFFFFFFF)


class _WorldDriver:
    """Replays `tokens`; determinises the world at decision index `boundary`. After
    `tokens` are exhausted: if `probe_node` it raises _Stop with the next decision's
    context (to read its legal moves); else the heuristic plays the rollout tail."""

    def __init__(self, tokens, boundary, world_seed, probe_node):
        self.tokens = tokens
        self.boundary = boundary
        self.world_seed = world_seed
        self.probe_node = probe_node
        self.heur = default_dungeon_policy()
        self.n = 0

    def decide(self, context):
        i = self.n
        self.n += 1
        if i == self.boundary:
            _determinize(context, self.world_seed)
        if i < len(self.tokens):
            return _decode(self.tokens[i], context)
        if self.probe_node:
            raise _Stop(context)
        return self.heur.decide(context)


def _resim(seed, seat, tokens, boundary, world_seed, probe_node):
    """Run one re-sim. Returns ('node', context) at the next decision after tokens
    (if probe_node), or ('end', outcome) if the game finished."""
    rstate, npstate = random.getstate(), np.random.get_state()
    try:
        joueurs, objets = env.build_toy_match(seed, deck=DECK)
        agent = _WorldDriver(tokens, boundary, world_seed, probe_node)
        routed = env.routed_toy_policy({seat: agent, 1 - seat: default_dungeon_policy()}, joueurs)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                winner, jf = ordonnanceur(joueurs, env.make_dungeon(DECK), objets, False, policy=routed)
        except _Stop as stop:
            return 'node', stop.context
        return 'end', outcome_win(jf, seat, winner)
    finally:
        random.setstate(rstate)
        np.random.set_state(npstate)


def _world_value(seed, seat, tokens, boundary, world_seed, depth):
    """Best outcome the agent can get from node `tokens` with `depth` more searched
    moves, in the FIXED world (world_seed). Exhaustive max over the agent's moves;
    heuristic plays everything else."""
    if depth <= 0:
        kind, payload = _resim(seed, seat, tokens, boundary, world_seed, probe_node=False)
        return payload  # heuristic-tail outcome
    kind, payload = _resim(seed, seat, tokens, boundary, world_seed, probe_node=True)
    if kind == 'end':
        return payload
    cands = _candidates(payload)
    if not cands:
        return _resim(seed, seat, tokens, boundary, world_seed, probe_node=False)[1]
    if len(cands) == 1:
        return _world_value(seed, seat, tokens + [cands[0][1]], boundary, world_seed, depth)
    return max(_world_value(seed, seat, tokens + [tok], boundary, world_seed, depth - 1)
               for _, tok in cands)


class PimcSearch:
    def __init__(self, seed, seat, depth=2, n_worlds=8):
        self.seed, self.seat, self.depth, self.n_worlds = seed, seat, depth, n_worlds
        self.committed = []
        self.heur = default_dungeon_policy()

    def decide(self, context):
        cands = _candidates(context)
        if cands is None:
            a = self.heur.decide(context)
            from rollout_search import _encode
            self.committed.append(_encode(a, context))
            return a
        if len(cands) == 1:
            self.committed.append(cands[0][1])
            return cands[0][0]
        boundary = len(self.committed)
        base = self.seed * 1_000_003 + boundary * 97
        best_action = best_token = None
        best_score = None
        for action, token in cands:
            total = 0.0
            for w in range(self.n_worlds):
                total += _world_value(self.seed, self.seat, self.committed + [token],
                                      boundary, base + w, self.depth - 1)
            avg = total / self.n_worlds
            if best_score is None or avg > best_score:
                best_score, best_action, best_token = avg, action, token
        self.committed.append(best_token)
        return best_action


def winrate(n, depth, n_worlds):
    w = l = d = 0
    for s in range(n):
        seat = s % 2
        joueurs, objets = env.build_toy_match(s, deck=DECK)
        agent = PimcSearch(s, seat, depth=depth, n_worlds=n_worlds)
        routed = env.routed_toy_policy({seat: agent, 1 - seat: default_dungeon_policy()}, joueurs)
        with contextlib.redirect_stdout(io.StringIO()):
            winner, jf = ordonnanceur(joueurs, env.make_dungeon(DECK), objets, False, policy=routed)
        t = jf[seat]
        if t is winner:
            w += 1
        elif winner is None:
            d += 1
        else:
            l += 1
    return w / n, l / n, d / n


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    DEPTH = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    WORLDS = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    a, b, c = winrate(N, DEPTH, WORLDS)
    print(f"PIMC depth={DEPTH} worlds={WORLDS} vs heuristic: "
          f"agent {a:.1%} / opp {b:.1%} / draw {c:.1%}   (N={N})")
