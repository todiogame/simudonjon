"""Minimal, CLONEABLE, STEPPABLE toy engine -- a clean state machine so MCTS/ISMCTS
can explore fast (no re-simulation).

Deliberately simple (per the brief): plain monsters (power + type, NO special
effects), a small set of faithful objects, and the core decisions where skill
lives: heal / flee / which combat object / replay. Two players share a shuffled
deck (the hidden info); each turn a player faces cards, fighting or fleeing, and
may keep replaying (facing the next card) or stop. Winner = top score among the
non-dead.

API for search:
    s = new_game(seed, hand)            # initial State (at the first decision)
    kind, options = legal(s)            # current decision
    s2 = step(s, action)                # -> next State (advanced to next decision
                                        #    or terminal); s is unchanged (returns a copy)
    s.terminal, s.winner                # terminal flag + winner seat (or None=draw)
States are plain dataclasses -> copy.deepcopy clones them for tree search.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

PV_START = 10
PV_MAX = 10
HEAL = 7
OSSELETS_THRESHOLD = 3

# --- objects (faithful but minimal; rules are GAME rules, not AI) ------------
KILLERS = ('marteau', 'torche', 'hache')        # used in combat to negate damage + defeat
ONE_SHOT = ('hache', 'kebab')                    # consumed on use (intact -> broken)


def _can_kill(name, power, mtype):
    if name == 'marteau':
        return mtype in ('Golem', 'Squelette')
    if name == 'torche':
        return power <= 2
    if name == 'hache':
        return True
    return False


# --- the (plain) dungeon -----------------------------------------------------
DECK = (
    (1, 'Gobelin'), (1, 'Gobelin'), (1, 'Gobelin'), (1, 'Gobelin'),
    (2, 'Squelette'), (2, 'Squelette'), (2, 'Squelette'), (2, 'Squelette'),
    (3, 'Orc'), (3, 'Orc'), (3, 'Orc'), (3, 'Orc'),
    (4, 'Vampire'), (4, 'Vampire'), (4, 'Vampire'), (4, 'Vampire'),
    (5, 'Golem'), (5, 'Golem'), (5, 'Golem'), (5, 'Golem'),
    (6, 'Liche'), (6, 'Liche'),
    (7, 'Demon'), (7, 'Demon'),
    (9, 'Dragon'), (9, 'Dragon'),
)  # 26 cards: 4x power 1-5, 2x Liche(6) / Demon(7) / Dragon(9)


@dataclass
class Player:
    pv: int
    pv_max: int
    objs: dict           # name -> intact(bool)
    score: int = 0
    status: str = 'in'   # 'in' | 'fled' | 'dead'


@dataclass
class State:
    order: tuple                 # draw order = permutation of DECK indices (hidden)
    idx: int                     # next card to draw
    players: list                # [Player, Player]
    to_move: int
    phase: str                   # 'heal'|'flee'|'object'|'replay'|'terminal'
    current: tuple = None        # (power, type) being faced, or None
    terminal: bool = False
    winner: int = None           # seat, or None (draw)
    rng: object = None           # random.Random for the flee dice (in-state -> cloneable)

    def clone(self):
        return copy.deepcopy(self)


def new_game(seed, hand):
    """hand = list of object names both seats start with (e.g. ['marteau','osselets',...])."""
    rng = random.Random(seed)
    order = list(range(len(DECK)))
    rng.shuffle(order)
    armure = hand.count('armure')
    players = [Player(pv=PV_START + 5 * armure, pv_max=PV_MAX + 5 * armure,
                      objs={n: True for n in hand}) for _ in range(2)]
    s = State(order=tuple(order), idx=0, players=players, to_move=0, phase='descend', rng=rng)
    return _advance(s)


def _holds(p, name):
    return p.objs.get(name, False)


def legal(s):
    """(kind, options) for the current decision. options are concrete action values."""
    p = s.players[s.to_move]
    if s.phase == 'descend':
        return 'descend', [True, False]   # True = face the next card; False = stop & bank
    if s.phase == 'heal':
        return 'heal', [True, False]
    if s.phase == 'flee':
        return 'flee', [True, False]
    if s.phase == 'object':
        power, mtype = s.current
        opts = [n for n in KILLERS if _holds(p, n) and _can_kill(n, power, mtype)]
        opts.append('none')
        return 'object', opts
    return 'terminal', []


def _next_player(s):
    """The current player's run just ended (stopped / fled / died). Hand the rest
    of the deck to the other player if they still have a run to take, else finish.
    (Sequential runs: player A descends, then player B descends what's left.)"""
    s.current = None
    other = 1 - s.to_move
    if s.players[other].status == 'in' and s.idx < len(s.order):
        s.to_move = other
        s.phase = 'descend'
        return s
    return _finish(s)


def _finish(s):
    s.phase = 'terminal'
    s.terminal = True
    alive = [(pl.score, i) for i, pl in enumerate(s.players) if pl.status != 'dead']
    if not alive:
        s.winner = None
    else:
        top = max(sc for sc, _ in alive)
        winners = [i for sc, i in alive if sc == top]
        s.winner = winners[0] if len(winners) == 1 else None  # tie -> draw
    return s


def _advance(s):
    """Resolve auto-steps until the next decision or terminal. Currently every
    phase is a decision, so this just ensures terminal/empty-deck handling."""
    if s.terminal:
        return s
    if s.phase == 'heal':
        p = s.players[s.to_move]
        if not _holds(p, 'kebab'):                  # no heal -> skip to drawing
            return _draw(s)
    return s


def _draw(s):
    """Draw the top card -> the player must flee/fight it. Deck empty -> run ends."""
    if s.idx >= len(s.order):
        s.players[s.to_move].status = 'done'        # nothing left -> banked
        return _next_player(s)
    s.current = DECK[s.order[s.idx]]
    s.idx += 1
    s.phase = 'flee'
    return s


def step(s, action):
    """Apply `action` IN PLACE; advance to the next decision/terminal and return s.
    Callers that need to preserve a state (e.g. MCTS at the root) clone first via
    s.clone(); within a simulation we mutate freely -- far faster than cloning every
    step (deepcopy per call was the bottleneck)."""
    p = s.players[s.to_move]
    if s.phase == 'descend':
        if not action:                              # STOP: bank the score, run ends
            p.status = 'done'
            return _next_player(s)
        s.phase = 'heal'                            # keep descending: heal? then draw
        return _advance(s)
    if s.phase == 'heal':
        if action and _holds(p, 'kebab'):
            p.pv = min(p.pv_max, p.pv + HEAL)
            p.objs['kebab'] = False
        return _draw(s)
    if s.phase == 'flee':
        if action:                                  # attempt to flee: d6 vs monster power
            power, _ = s.current
            if s.rng.randint(1, 6) >= power:        # escaped -> leave the dungeon (banked)
                p.status = 'done'
                return _next_player(s)
            # flee FAILED -> forced to fight this monster (power 7/9 always fail)
        s.phase = 'object'
        return s
    if s.phase == 'object':
        power, mtype = s.current
        if action in KILLERS and _holds(p, action) and _can_kill(action, power, mtype):
            if action in ONE_SHOT:
                p.objs[action] = False
            p.score += 1                            # executed: defeat, no damage
        elif power >= p.pv:                         # lethal hit, no killing object
            if _holds(p, 'osselets') and p.pv >= OSSELETS_THRESHOLD:
                p.pv = 1                            # death-save (reusable), defeat
                p.score += 1
            else:
                p.status = 'dead'
                return _next_player(s)
        else:
            p.pv -= power                           # survive the hit, defeat
            p.score += 1
        s.phase = 'descend'                         # survived -> keep descending or stop
        return s
    return s


# --- a reasonable baseline heuristic for this engine -------------------------
def heuristic_action(s):
    kind, opts = legal(s)
    p = s.players[s.to_move]
    if kind == 'descend':
        # keep descending only while we could survive a FORCED Dragon (9): tank it,
        # hache it, or osselets-save it. Otherwise stop & bank (a drawn Dragon is
        # unfleeable). This is the push-your-luck lever.
        backstop = (p.pv > 9 or _holds(p, 'hache')
                    or (_holds(p, 'osselets') and p.pv >= OSSELETS_THRESHOLD))
        return bool(backstop)
    if kind == 'heal':
        return bool(p.pv <= 6 and _holds(p, 'kebab'))          # heal when low-ish
    if kind == 'flee':
        power, mtype = s.current
        killers = [n for n in KILLERS if _holds(p, n) and _can_kill(n, power, mtype)]
        save = _holds(p, 'osselets') and p.pv >= OSSELETS_THRESHOLD
        # attempt to flee a monster we can't kill and don't want to tank (osselets
        # would save a lethal hit -> rather fight + score). Power 7/9 will fail anyway.
        return bool(not killers and not save and power >= 4)
    if kind == 'object':
        power, mtype = s.current
        free = [n for n in ('marteau', 'torche') if n in opts]
        if power < p.pv:
            return free[0] if free else 'none'                 # survivable: save pv if free kill
        if free:
            return free[0]
        if 'hache' in opts:
            return 'hache'
        return 'none'                                          # osselets saves, or die
    return opts[0] if opts else None


def play(seed, hand, pol0, pol1):
    """Play one game; policies are functions State->action. Returns the final State."""
    s = new_game(seed, hand)
    pols = (pol0, pol1)
    while not s.terminal:
        s = step(s, pols[s.to_move](s))
    return s
