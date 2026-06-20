"""Value-net truncated ISMCTS (POC) -- the only structural speed lever left.

Same clone-based PUCT search as fast_search, BUT instead of rolling the playout out to a
terminal, we truncate: take the leaf edge, let the heuristic play just until the NEXT searcher
decision, then evaluate that state with the distilled net's VALUE head (one forward) and back
that up. No rollout to the end. The leaf state is always a searcher decision (the tree only
branches on searcher decisions), so encode_ctx is from the searcher's perspective and the net
value = P(searcher wins) -- backed up directly. If the game ends before the next searcher
decision, the real terminal outcome is used.

This isolates the value-head idea: measures (1) wall-time per game and (2) does the truncated
teacher still beat ai_policy on a common bank, vs the rollout teacher.

Usage: python value_search.py [n_seeds] [iters] [seed0]
"""
import math
import random
import sys
import time

import numpy as np
import torch

import real_distill as rd
import real_search as rs
from ai_policy import DefaultDungeonPolicy
from fast_engine import clone_state
from rl_toy_env import build_toy_match, make_dungeon
from simu import ordonnanceur

torch.set_num_threads(1)
_NET = None


def get_net(path='artifacts/real_distill.pt'):
    global _NET
    if _NET is None:
        _NET = rd.make_net()
        _NET.load_state_dict(torch.load(path))
        _NET.eval()
    return _NET


def make_value_fn(net):
    def vf(ctx):
        x = torch.from_numpy(rd.encode_ctx(ctx)).unsqueeze(0)
        with torch.no_grad():
            _, v = net(x)
        return float(v[0])
    return vf


class _LeafReached(BaseException):
    def __init__(self, value):
        self.value = value


class _TruncPolicy:
    """real_search._ISMCTSPolicy with the rollout replaced by a value-head eval at the next
    searcher decision after the leaf edge."""

    def __init__(self, searcher, prefix, root, iter_seed, c, p_heur, value_fn):
        self.searcher, self.prefix, self.root, self.c, self.p_heur = searcher, prefix, root, c, p_heur
        self.value_fn = value_fn
        self.i = 0
        self.node = root
        self.path = []
        self.determinized = False
        self.eval_pending = False
        self.iter_seed = iter_seed
        self.heur = DefaultDungeonPolicy()

    def _heur(self, ctx):
        return self.heur.decide(ctx)

    def decide(self, ctx):
        if ctx.actor is not self.searcher or ctx.kind.name not in rs.TREE_KINDS:
            return self._heur(ctx)
        keys = rs.legal_keys(ctx)
        if not keys:
            return self._heur(ctx)
        if self.i < len(self.prefix):
            k = self.prefix[self.i]
            self.i += 1
            return rs.action_from_key(ctx, k, self.heur, lambda: self._heur(ctx))
        if not self.determinized:
            random.seed(self.iter_seed)
            np.random.seed(self.iter_seed & 0x7FFFFFFF)
            rs.determinize_unseen(ctx.game.donjon, np.random)
            self.determinized = True
        if self.eval_pending:                              # leaf edge taken -> evaluate here, stop
            raise _LeafReached(self.value_fn(ctx))
        for k in keys:
            self.node.edges.setdefault(k, [0, 0.0, 0])
        h_key = rs.action_key(ctx, self.heur.decide(ctx))
        p_oth = (1.0 - self.p_heur) / max(1, len(keys) - 1)
        prior = {k: (self.p_heur if k == h_key else p_oth) for k in keys}
        if h_key not in prior:
            prior = {k: 1.0 / len(keys) for k in keys}
        N = sum(self.node.edges[k][0] for k in keys)

        def puct(k):
            e = self.node.edges[k]
            q = e[1] / e[0] if e[0] else 0.0
            return q + self.c * prior[k] * math.sqrt(N + 1) / (1 + e[0])
        k = max(keys, key=puct)
        self.path.append((self.node, k))
        if self.node.edges[k][0] == 0:
            self.node.children.setdefault(k, rs.Node())
            self.eval_pending = True                       # truncate at the next searcher decision
        else:
            self.node = self.node.children.setdefault(k, rs.Node())
        return rs.action_from_key(ctx, k, self.heur, lambda: self._heur(ctx))


def trunc_decide(snapshot, within_prefix, seat, seed, n_iters, value_fn, c=1.4, p_heur=0.75):
    clone0, turn_index, rng_state = snapshot
    root = rs.Node()
    for it in range(n_iters):
        random.setstate(rng_state[0])
        np.random.set_state(rng_state[1])
        clone = clone_state(clone0)
        searcher = clone.joueurs[seat]
        pol = _TruncPolicy(searcher, within_prefix, root, seed * 1000003 + it + 1, c, p_heur, value_fn)
        try:
            winner, _ = ordonnanceur(None, None, None, log=False, policy=pol,
                                     resume_state=clone, resume_index=turn_index)
            outcome = 1.0 if winner is searcher else (0.0 if winner is None else -1.0)
        except _LeafReached as lr:
            outcome = lr.value
        except Exception:
            continue
        for nd, k in pol.path:
            nd.edges[k][0] += 1
            nd.edges[k][1] += outcome
    if not root.edges:
        return None, {}
    best = max(root.edges, key=lambda k: root.edges[k][0])
    return best, {k: e[0] for k, e in root.edges.items()}


class _LivePolicy:
    def __init__(self, seat, seed, n_iters, value_fn, c=1.4, p_heur=0.75):
        self.seat, self.seed, self.n_iters, self.c, self.p_heur = seat, seed, n_iters, c, p_heur
        self.value_fn = value_fn
        self.heur = DefaultDungeonPolicy()
        self.searcher = None
        self.snapshot = None
        self.within = []

    def on_turn_start(self, Jeu, index):
        if self.searcher is None:
            self.searcher = Jeu.joueurs[self.seat]
        self.snapshot = (clone_state(Jeu), index, (random.getstate(), np.random.get_state()))
        self.within = []

    def decide(self, ctx):
        if ctx.actor is not self.searcher or ctx.kind.name not in rs.TREE_KINDS or not rs.legal_keys(ctx):
            return self.heur.decide(ctx)
        st1, st2 = random.getstate(), np.random.get_state()
        best, _ = trunc_decide(self.snapshot, list(self.within), self.seat, self.seed,
                               self.n_iters, self.value_fn, self.c, self.p_heur)
        random.setstate(st1)
        np.random.set_state(st2)
        if best is None:
            best = rs.action_key(ctx, self.heur.decide(ctx))
        self.within.append(best)
        return rs.action_from_key(ctx, best, self.heur, lambda: self.heur.decide(ctx))


def play_game(seed, seat, n_iters, value_fn, c=1.4, p_heur=0.75):
    random.seed(seed)
    np.random.seed(seed & 0x7FFFFFFF)
    joueurs, reserve = build_toy_match(seed, deck='toy')
    donjon = make_dungeon('toy')
    live = _LivePolicy(seat, seed, n_iters, value_fn, c=c, p_heur=p_heur)
    winner, js = ordonnanceur(joueurs, donjon, reserve, log=False,
                              policy=live, on_turn_start=live.on_turn_start)
    s = js[seat]
    return 1 if winner is s else (0 if winner is None else -1)


if __name__ == '__main__':
    import fast_search

    N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    ITERS = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    SEED0 = int(sys.argv[3]) if len(sys.argv) > 3 else 600000
    vf = make_value_fn(get_net())
    print(f"value-net TRUNCATED vs ROLLOUT teacher @ {ITERS} iters, seeds {SEED0}..{SEED0+N-1}\n")

    tw = tl = td = 0
    t_trunc = 0.0
    for g in range(N):
        seat = g % 2
        t0 = time.perf_counter()
        o = play_game(SEED0 + g, seat, ITERS, vf)
        t_trunc += time.perf_counter() - t0
        tw += o == 1
        td += o == 0
        tl += o == -1
    print(f"TRUNCATED teacher vs ai_policy: win {tw/N:.0%} lose {tl/N:.0%} draw {td/N:.0%} "
          f"| {t_trunc/N:.2f}s/game")

    rw = rl = rd_ = 0
    t_roll = 0.0
    for g in range(N):
        seat = g % 2
        t0 = time.perf_counter()
        o, _ = fast_search.play_game(SEED0 + g, seat, ITERS)
        t_roll += time.perf_counter() - t0
        rw += o == 1
        rd_ += o == 0
        rl += o == -1
    print(f"ROLLOUT   teacher vs ai_policy: win {rw/N:.0%} lose {rl/N:.0%} draw {rd_/N:.0%} "
          f"| {t_roll/N:.2f}s/game")

    print(f"\nspeedup (truncated vs rollout): x{t_roll/max(t_trunc,1e-9):.2f}")
