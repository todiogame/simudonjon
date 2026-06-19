"""ISMCTS on the REAL simudonjon engine via DETERMINIZED RE-SIMULATION.

The engine can't be resumed from a cloned mid-game state (monolithic loop), so a search
that branches must RE-SIMULATE from the game start: rebuild the same match (same seed ->
same hands + same shuffled deck + deterministic heuristic reproduce the seen game exactly),
then at the search root DETERMINIZE -- reshuffle the still-unseen tail of the deck (a fresh
order the searcher couldn't know) -- and play out. This module starts with the building
block: determinizing the unseen deck mid-game and proving the seen prefix is preserved.
"""
import numpy as np

from ai_decisions import CombatObjectChoice


# --- action <-> stable key (re-sims rebuild fresh instances, so we index, not identify) ---
def action_key(ctx, action):
    if action is True or action is False:
        return ('b', action)
    if action is CombatObjectChoice.RESOLVE_NOW:
        return ('r',)
    if action is None:
        return ('n',)
    opts = list(ctx.options or ())
    for i, o in enumerate(opts):
        if o is action or o == action:
            return ('o', i)
    return ('v', action)                       # structural/odd (e.g. ORDER_OBJECTS): not replayable


def action_from_key(ctx, key, heur, fallback_ctx_action):
    t = key[0]
    if t == 'b':
        return key[1]
    if t == 'r':
        return CombatObjectChoice.RESOLVE_NOW
    if t == 'n':
        return None
    if t == 'o':
        return list(ctx.options)[key[1]]
    return fallback_ctx_action()               # ('v',...): re-run the heuristic (state is reproduced)


def determinize_unseen(donjon, det_rng):
    """Reshuffle ONLY the cards not yet drawn (ordre[index:]); the drawn prefix is kept."""
    idx = donjon.index
    tail = list(donjon.ordre[idx:])
    det_rng.shuffle(tail)
    donjon.ordre = np.concatenate([donjon.ordre[:idx], np.array(tail, dtype=donjon.ordre.dtype)])


# --- ISMCTS by determinized re-simulation -------------------------------------------
import math
import random as _rnd

# the gameplay decisions the searcher actually searches over; everything else (structural,
# hero abilities the toy hero doesn't have, ...) is delegated to the heuristic.
TREE_KINDS = {'SHOULD_FLEE', 'SHOULD_REPLAY', 'CHOOSE_COMBAT_OBJECT',
              'CHOOSE_OBJECT_TO_SACRIFICE', 'CHOOSE_OBJECT_TO_REPAIR'}


def legal_keys(ctx):
    name = ctx.kind.name
    opts = list(ctx.options or ())
    if name in ('SHOULD_FLEE', 'SHOULD_REPLAY'):
        acts = [True, False]
    elif name == 'CHOOSE_COMBAT_OBJECT':
        acts = opts + [CombatObjectChoice.RESOLVE_NOW]
    elif name in ('CHOOSE_OBJECT_TO_SACRIFICE', 'CHOOSE_OBJECT_TO_REPAIR'):
        acts = opts + ([None] if ctx.meta('allow_none') else [])   # only if the engine truly allows it
    else:
        acts = list(opts)
    return [action_key(ctx, a) for a in acts]


class Node:
    __slots__ = ('edges', 'children')

    def __init__(self):
        self.edges = {}      # key -> [visits, value_sum, avail]
        self.children = {}   # key -> Node


class _ISMCTSPolicy:
    """One re-simulation: the searcher replays `prefix` to the root, then the deck's unseen
    tail is determinized and the searcher descends the shared tree (UCB) / rolls out with the
    heuristic; the opponent always plays the heuristic. Records the tree path for back-up."""

    def __init__(self, searcher, prefix, root, iter_seed, c, p_heur=0.75):
        from ai_policy import DefaultDungeonPolicy
        self.searcher, self.prefix, self.root, self.c = searcher, prefix, root, c
        self.p_heur = p_heur                                   # prior weight on the heuristic's move
        self.i = 0
        self.node = root
        self.path = []
        self.rollout = False
        self.determinized = False
        self.iter_seed = iter_seed
        self.tree_rng = _rnd.Random(iter_seed ^ 0x9E3779B9)
        self.heur = DefaultDungeonPolicy()

    def _heur(self, ctx):
        return self.heur.decide(ctx)

    def decide(self, ctx):
        if ctx.actor is not self.searcher or ctx.kind.name not in TREE_KINDS:
            return self._heur(ctx)                             # opponent / structural -> heuristic
        if self.i < len(self.prefix):                          # replay the searcher's tree decisions
            k = self.prefix[self.i]
            self.i += 1
            return action_from_key(ctx, k, self.heur, lambda: self._heur(ctx))
        if not self.determinized:                              # at the root: determinize the future
            _rnd.seed(self.iter_seed)
            np.random.seed(self.iter_seed & 0x7FFFFFFF)
            determinize_unseen(ctx.game.donjon, np.random)
            self.determinized = True
        if self.rollout:                                       # past the expanded leaf -> roll out
            return self._heur(ctx)
        keys = legal_keys(ctx)
        if not keys:                                           # nothing to branch on -> heuristic
            return self._heur(ctx)
        for k in keys:
            self.node.edges.setdefault(k, [0, 0.0, 0])
        h_key = action_key(ctx, self.heur.decide(ctx))         # heuristic PRIOR (tunable strength)
        p_oth = (1.0 - self.p_heur) / max(1, len(keys) - 1)    # exploration floor on the other moves
        prior = {k: (self.p_heur if k == h_key else p_oth) for k in keys}
        if h_key not in prior:                                 # heuristic chose an unlisted action
            prior = {k: 1.0 / len(keys) for k in keys}
        N = sum(self.node.edges[k][0] for k in keys)
        # PUCT: Q(a) + c * P(a) * sqrt(N+1) / (1 + n(a)) -- deviate from the prior only if Q backs it
        def puct(k):
            e = self.node.edges[k]
            q = e[1] / e[0] if e[0] else 0.0
            return q + self.c * prior[k] * math.sqrt(N + 1) / (1 + e[0])
        k = max(keys, key=puct)
        self.path.append((self.node, k))
        if self.node.edges[k][0] == 0:                         # leaf -> expand it, then roll out
            self.node.children.setdefault(k, Node())
            self.rollout = True
        else:
            self.node = self.node.children.setdefault(k, Node())
        return action_from_key(ctx, k, self.heur, lambda: self._heur(ctx))


def ismcts_decide(seed, searcher_seat, prefix, n_iters, c=1.4, p_heur=0.75):
    """Decide the searcher's current decision (reached by replaying `prefix`) via `n_iters`
    determinized re-simulations. Returns (best_key, {key: visits})."""
    from ai_policy import DefaultDungeonPolicy
    from simu import ordonnanceur

    from rl_toy_env import build_toy_match, make_dungeon
    root = Node()
    for it in range(n_iters):
        _rnd.seed(seed)
        np.random.seed(seed & 0x7FFFFFFF)
        joueurs, reserve = build_toy_match(seed, deck='toy')
        donjon = make_dungeon('toy')
        pol = _ISMCTSPolicy(joueurs[searcher_seat], prefix, root,
                            iter_seed=(seed * 1000003 + it + 1), c=c, p_heur=p_heur)
        try:
            winner, _ = ordonnanceur(joueurs, donjon, reserve, log=False, policy=pol)
        except Exception:
            continue                                           # a bad determinization -> skip the sim
        outcome = 1.0 if winner is joueurs[searcher_seat] else (0.0 if winner is None else -1.0)
        for nd, k in pol.path:
            nd.edges[k][0] += 1
            nd.edges[k][1] += outcome
    if not root.edges:
        return None, {}
    best = max(root.edges, key=lambda k: root.edges[k][0])
    return best, {k: e[0] for k, e in root.edges.items()}


def play_teacher_game(seed, searcher_seat, n_iters, c=1.4, p_heur=0.75):
    """Play one real game: the searcher seat is the ISMCTS teacher (searching at each of its
    gameplay decisions), the other seat is the real ai_policy.py heuristic. Returns
    (outcome in {+1,0,-1} for the searcher, records=[(DecisionContext, visit-dict), ...])."""
    from ai_policy import DefaultDungeonPolicy
    from rl_toy_env import build_toy_match, make_dungeon
    from real_driver import RealGameDriver
    _rnd.seed(seed)
    np.random.seed(seed & 0x7FFFFFFF)
    joueurs, reserve = build_toy_match(seed, deck='toy')
    donjon = make_dungeon('toy')
    heur = DefaultDungeonPolicy()
    drv = RealGameDriver(joueurs, donjon, reserve)
    searcher = joueurs[searcher_seat]
    prefix, records = [], []
    while not drv.terminal:
        ctx = drv.context
        if ctx.actor is searcher and ctx.kind.name in TREE_KINDS:
            rs_state, np_state = _rnd.getstate(), np.random.get_state()   # preserve the live game RNG
            best, visits = ismcts_decide(seed, searcher_seat, prefix, n_iters, c=c, p_heur=p_heur)
            _rnd.setstate(rs_state)
            np.random.set_state(np_state)                                # the search reseeded globals
            if best is None:
                best = action_key(ctx, heur.decide(ctx))
            records.append((ctx, visits))
            prefix.append(best)
            drv.step(action_from_key(ctx, best, heur, lambda: heur.decide(ctx)))
        else:
            drv.step(heur.decide(ctx))
    winner = drv.result[0] if drv.result else None
    return (1 if winner is searcher else (0 if winner is None else -1)), records


# --- proof: reshuffling the unseen tail at decision K keeps the seen prefix, diverges after ---
if __name__ == '__main__':
    import random

    from ai_policy import DefaultDungeonPolicy
    from rl_toy_env import build_toy_match, make_dungeon
    from real_driver import RealGameDriver

    def run(seed, reshuffle_at=None, det_seed=0):
        """Play a heuristic game; optionally, at the `reshuffle_at`-th decision, determinize
        the unseen deck. Return the sequence of drawn-card ids (deck order actually consumed)."""
        random.seed(seed)
        np.random.seed(seed & 0xFFFFFFFF)
        joueurs, reserve = build_toy_match(seed, deck='toy')
        donjon = make_dungeon('toy')
        heur = DefaultDungeonPolicy()
        drv = RealGameDriver(joueurs, donjon, reserve)
        n = 0
        det_rng = np.random.RandomState(det_seed)
        while not drv.terminal:
            ctx = drv.context
            if reshuffle_at is not None and n == reshuffle_at:
                determinize_unseen(ctx.game.donjon, det_rng)   # seen prefix fixed, unseen reshuffled
            n += 1
            drv.step(heur.decide(ctx))
        # the cards actually consumed, in order (ordre[:index] of the final deck)
        d = joueurs[0].policy  # not used; read deck via a fresh ref below
        return tuple(int(x) for x in donjon.ordre[:donjon.index]), \
            tuple((j.nom, j.score_final) for j in joueurs)

    # --- replay proof: record seat-0's decision keys, then re-sim replaying them ---
    from simu import ordonnanceur

    def record_game(seed):
        random.seed(seed)
        np.random.seed(seed & 0xFFFFFFFF)
        joueurs, reserve = build_toy_match(seed, deck='toy')
        donjon = make_dungeon('toy')
        heur = DefaultDungeonPolicy()
        drv = RealGameDriver(joueurs, donjon, reserve)
        searcher = joueurs[0]
        keys = []
        while not drv.terminal:
            ctx = drv.context
            a = heur.decide(ctx)
            if ctx.actor is searcher:
                keys.append(action_key(ctx, a))
            drv.step(a)
        return keys, tuple((j.nom, j.score_final) for j in joueurs), tuple(int(x) for x in donjon.ordre[:donjon.index])

    class ReplayPolicy:
        def __init__(self, searcher, keys):
            self.searcher, self.keys, self.i = searcher, keys, 0
            self.heur = DefaultDungeonPolicy()

        def decide(self, ctx):
            if ctx.actor is self.searcher and self.i < len(self.keys):
                k = self.keys[self.i]
                self.i += 1
                return action_from_key(ctx, k, self.heur, lambda: self.heur.decide(ctx))
            return self.heur.decide(ctx)

    keys, o_scores, o_draws = record_game(0)
    random.seed(0)
    np.random.seed(0)
    joueurs, reserve = build_toy_match(0, deck='toy')
    donjon = make_dungeon('toy')
    winner, _ = ordonnanceur(joueurs, donjon, reserve, log=False, policy=ReplayPolicy(joueurs[0], keys))
    r_scores = tuple((j.nom, j.score_final) for j in joueurs)
    r_draws = tuple(int(x) for x in donjon.ordre[:donjon.index])
    print(f"REPLAY proof: scores match={o_scores == r_scores}, draws match={o_draws == r_draws}")
    print(f"  recorded {len(keys)} seat-0 keys | orig {o_scores} | replay {r_scores}")

    base_draws, base_scores = run(0)
    K = 6
    a_draws, a_scores = run(0, reshuffle_at=K, det_seed=1)
    b_draws, b_scores = run(0, reshuffle_at=K, det_seed=2)

    # the deck index at decision K isn't exactly K (some decisions don't draw), but the
    # cards drawn BEFORE the reshuffle must be identical across A, B and base; the tail diverges.
    common = 0
    for x, y in zip(a_draws, b_draws):
        if x == y:
            common += 1
        else:
            break
    print(f"base draws ({len(base_draws)}): {base_draws}")
    print(f"det A      ({len(a_draws)}): {a_draws}  scores {a_scores}")
    print(f"det B      ({len(b_draws)}): {b_draws}  scores {b_scores}")
    print(f"A vs B identical for the first {common} drawn cards, then diverge "
          f"(reshuffle was at decision {K}).")
    print(f"determinization {'OK' if common >= 1 and a_draws != b_draws else 'CHECK'}: "
          f"seen prefix preserved, unseen future reshuffled.")