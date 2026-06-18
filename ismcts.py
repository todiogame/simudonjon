"""Information-Set MCTS on the steppable toy engine -- the SOUND search for hidden
info (no strategy fusion, unlike PIMC).

One shared tree over the searching player's decisions. Each iteration samples a
fresh determinization (reshuffle the unseen deck), descends the tree with UCB
(only over actions legal in that determinization, with availability counts),
expands, rolls out with the heuristic, and backs up the agent's result. Because
the tree is shared across determinizations, the agent's strategy can't depend on
the specific future -> no strategy fusion. The opponent plays the heuristic (we
want to beat the heuristic).

Usage: python ismcts.py [n_games] [iters_per_move]
"""
import math
import random
import sys

import toy_engine as te

C = 1.4


class Node:
    __slots__ = ('edges', 'children')

    def __init__(self):
        self.edges = {}      # action -> [visits, value_sum, avail]
        self.children = {}   # action -> Node


def _determinize(root, rng):
    s = root.clone()
    rem = list(s.order[s.idx:])
    rng.shuffle(rem)
    s.order = tuple(s.order[:s.idx]) + tuple(rem)
    return s


def _outcome(s, seat):
    if s.winner == seat:
        return 1.0
    if s.winner is None:
        return 0.0
    return -1.0


def _rollout(s, seat):
    while not s.terminal:
        s = te.step(s, te.heuristic_action(s))
    return _outcome(s, seat)


def ismcts_decide(root, seat, n_iters):
    rootnode = Node()
    rng = random.Random(root.idx * 7919 + seat * 31 + 1)
    for _ in range(n_iters):
        s = _determinize(root, rng)
        node = rootnode
        path = []
        while not s.terminal:
            if s.to_move == seat:
                _, actions = te.legal(s)
                for a in actions:                       # ensure edges + availability
                    node.edges.setdefault(a, [0, 0.0, 0])
                    node.edges[a][2] += 1
                untried = [a for a in actions if node.edges[a][0] == 0]
                if untried:
                    a = rng.choice(untried)
                    path.append((node, a))
                    s = te.step(s, a)
                    node.children.setdefault(a, Node())
                    break                                # expand -> then rollout
                a = max(actions, key=lambda x: (node.edges[x][1] / node.edges[x][0]
                                                 + C * math.sqrt(math.log(node.edges[x][2]) / node.edges[x][0])))
                path.append((node, a))
                s = te.step(s, a)
                node = node.children.setdefault(a, Node())
            else:
                s = te.step(s, te.heuristic_action(s))
        outcome = _outcome(s, seat) if s.terminal else _rollout(s, seat)
        for nd, a in path:
            nd.edges[a][0] += 1
            nd.edges[a][1] += outcome
    if not rootnode.edges:
        return te.heuristic_action(root)
    return max(rootnode.edges, key=lambda a: rootnode.edges[a][0])   # most-visited


def winrate(n, iters, hand):
    w = l = d = 0
    for g in range(n):
        seat = g % 2                                    # seat-rotate to cancel first-player edge
        s = te.new_game(g, hand)
        while not s.terminal:
            if s.to_move == seat:
                a = ismcts_decide(s, seat, iters)
            else:
                a = te.heuristic_action(s)
            s = te.step(s, a)
        if s.winner == seat:
            w += 1
        elif s.winner is None:
            d += 1
        else:
            l += 1
    return w / n, l / n, d / n


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    ITERS = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    HAND = ['marteau', 'torche', 'hache', 'osselets', 'kebab']
    a, b, c = winrate(N, ITERS, HAND)
    print(f"ISMCTS ({ITERS} iters/move) vs heuristic, seat-rotated: "
          f"agent {a:.1%} / opp {b:.1%} / draw {c:.1%}   (N={N})")
