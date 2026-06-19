"""Minimal, CLONEABLE, STEPPABLE toy engine -- a clean state machine so MCTS/ISMCTS
can explore fast (no re-simulation).

Faithful to the REAL simudonjon (simu.py `ordonnanceur`):
  - Players ALTERNATE turns. A turn = face one card. After defeating it, the player
    decides to REPLAY (keep the turn) or PASS. A player stays IN the dungeon across
    turns; they only leave by fleeing successfully or dying.
  - MONSTER-PASSING: fleeing/dying hands the monster to the next player. Fleeing is
    OFFENSIVE.
  - Round ends on deck-empty (poncé) or all-out. Scoring: poncéurs (still IN) count and
    exclude fleers; else the alive fleers count; the dead never count. Top score wins.
  - NO native "heal" or "save" action: using ANY object (kill, heal, survive) is the
    SAME decision -- the "use an object" phase, which is a LOOP (you may use several
    objects in a row, e.g. heal then execute). Death-saves are just objects you may
    play when the monster's damage >= your PV. You may also resolve and die on purpose.
  - PV has NO ceiling (the real game: pv_total is uncapped; heals can overheal).

OBJECT POOL (11 real game objects, faithful rules; a game draws 5 symmetric).
Executors (defeat the monster, no damage taken):
  marteau  : kills Golem/Squelette, free, reusable.
  torche   : kills power<=2, free, reusable.
  hache    : kills ANY, one-shot, then discarded (not repairable).
  midas    : kills power<=4, one-shot, AND heals you by the monster's power.
  barde    : passive +3 PV; may be broken to kill ANY (you lose the +3 PV).
  calumet  : kills ANY, one-shot, then your current turn ends immediately.
Heal:
  kebab    : +7 PV, one-shot, usable only from your 3rd turn on (does NOT end the fight
             -> you keep choosing objects).
Death-saves (playable only when the monster's damage >= your PV; defeat the monster):
  osselets : survive at 1 PV, reusable.
  coquille : survive at 3 PV, one-shot.
Passive PV (applied at game start):
  armure   : +5 PV.
  coeur    : +3 PV; +1 PV each time you defeat a monster while already >=2 kills this turn.
(Excluded for now -- need a learned decision the toy doesn't model yet: pomme=see next
 3 cards, couteau=repair, bombe=break-another-object.)

API: s=new_game(seed,hand); kind,opts=legal(s); s=step(s,action); s.terminal,s.winner.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass

PV_START = 10
HEAL = 7
KEBAB_MIN_TURN = 3
OSSELETS_PV = 1
COQUILLE_PV = 3

POOL = ('marteau', 'torche', 'hache', 'midas', 'barde', 'calumet',
        'osselets', 'coquille', 'kebab', 'armure', 'coeur')

EXECUTORS = ('marteau', 'torche', 'hache', 'midas', 'barde', 'calumet')
_EXEC_PRED = {
    'marteau': lambda q, t: t in ('Golem', 'Squelette'),
    'torche':  lambda q, t: q <= 2,
    'hache':   lambda q, t: True,
    'midas':   lambda q, t: q <= 4,
    'barde':   lambda q, t: True,
    'calumet': lambda q, t: True,
}
_ONESHOT_EXEC = ('hache', 'midas', 'barde', 'calumet')   # consumed/broken on use
_PASSIVE_PV = {'armure': 5, 'coeur': 3, 'barde': 3}      # +PV at game start


def sample_hand(seed, k=5):
    return random.Random(seed).sample(POOL, k)


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
)  # 26 cards
TYPES = ('Gobelin', 'Squelette', 'Orc', 'Vampire', 'Golem', 'Liche', 'Demon', 'Dragon')


@dataclass
class Player:
    pv: int
    objs: dict           # name -> intact(bool)
    score: int = 0
    status: str = 'in'   # 'in' | 'fled' | 'dead'
    turn: int = 0        # turns begun (kebab gated at >=3)
    kills_turn: int = 0  # defeats this turn (coeur bonus)


@dataclass
class State:
    order: tuple
    idx: int
    players: list
    to_move: int
    phase: str                   # 'flee' | 'object' | 'replay' | 'terminal'
    current: tuple = None        # (power, type) being faced (drawn or PASSED), or None
    terminal: bool = False
    winner: int = None
    rng: object = None

    def clone(self):
        return copy.deepcopy(self)


def new_game(seed, hand):
    rng = random.Random(seed)
    order = list(range(len(DECK)))
    rng.shuffle(order)
    pv0 = PV_START + sum(_PASSIVE_PV.get(n, 0) for n in hand)
    players = [Player(pv=pv0, objs={n: True for n in hand}) for _ in range(2)]
    s = State(order=tuple(order), idx=0, players=players, to_move=0, phase='flee', rng=rng)
    return _begin_fresh_turn(s, 0)


def _holds(p, name):
    return p.objs.get(name, False)


def _object_options(s, p):
    """Usable held objects + 'resolve', for the combat object loop."""
    q, t = s.current
    opts = []
    for n in EXECUTORS:
        if _holds(p, n) and _EXEC_PRED[n](q, t) and not (n == 'barde' and p.pv <= 3):
            opts.append(n)
    if _holds(p, 'kebab') and p.turn >= KEBAB_MIN_TURN:
        opts.append('kebab')
    if q >= p.pv:                                    # lethal -> death-saves are usable
        if _holds(p, 'osselets'):
            opts.append('osselets')
        if _holds(p, 'coquille'):
            opts.append('coquille')
    opts.append('resolve')                           # take the hit (tank, or die if lethal)
    return opts


def legal(s):
    p = s.players[s.to_move]
    if s.phase == 'flee':
        return 'flee', [True, False]
    if s.phase == 'object':
        return 'object', _object_options(s, p)
    if s.phase == 'replay':
        return 'replay', [True, False]
    return 'terminal', []


# --- turn plumbing -----------------------------------------------------------
def _next_in_after(s, start):
    n = len(s.players)
    for k in range(1, n + 1):
        cand = (start + k) % n
        if s.players[cand].status == 'in':
            return cand
    return None


def _setup_facing(s):
    if s.current is None:
        if s.idx >= len(s.order):
            return _finish(s)
        s.current = DECK[s.order[s.idx]]
        s.idx += 1
    s.phase = 'flee'
    return s


def _begin_fresh_turn(s, seat):
    if seat is None or s.players[seat].status != 'in':
        seat = _next_in_after(s, s.to_move)
        if seat is None:
            return _finish(s)
    s.to_move = seat
    p = s.players[seat]
    p.turn += 1
    p.kills_turn = 0
    s.current = None
    return _setup_facing(s)


def _begin_carried_turn(s, seat):
    s.to_move = seat
    p = s.players[seat]
    p.turn += 1
    p.kills_turn = 0
    s.phase = 'flee'
    return s


def _pass_carried(s):
    nxt = _next_in_after(s, s.to_move)
    return _begin_carried_turn(s, nxt) if nxt is not None else _finish(s)


def _pass_turn(s):
    s.current = None
    nxt = _next_in_after(s, s.to_move)
    return _begin_fresh_turn(s, nxt if nxt is not None else s.to_move)


def _continue_same(s):
    s.current = None
    return _setup_facing(s)


def _defeat(s, p):
    p.score += 1
    p.kills_turn += 1
    if _holds(p, 'coeur') and p.kills_turn >= 2:
        p.pv += 1


def _finish(s):
    s.phase = 'terminal'
    s.terminal = True
    ins = [i for i, pl in enumerate(s.players) if pl.status == 'in']
    finalists = ins if ins else [i for i, pl in enumerate(s.players) if pl.status == 'fled']
    if not finalists:
        s.winner = None
    else:
        top = max(s.players[i].score for i in finalists)
        winners = [i for i in finalists if s.players[i].score == top]
        s.winner = winners[0] if len(winners) == 1 else None
    return s


def step(s, action):
    p = s.players[s.to_move]
    if s.phase == 'flee':
        power, _ = s.current
        if action and s.rng.randint(1, 6) >= power:
            p.status = 'fled'
            return _pass_carried(s)
        s.phase = 'object'
        return s
    if s.phase == 'object':
        q, t = s.current
        if action == 'kebab' and _holds(p, 'kebab') and p.turn >= KEBAB_MIN_TURN:
            p.pv += HEAL                              # uncapped; stay in the loop
            p.objs['kebab'] = False
            return s
        if action == 'osselets' and _holds(p, 'osselets') and q >= p.pv:
            p.pv = OSSELETS_PV                        # reusable
            _defeat(s, p)
            s.phase = 'replay'
            return s
        if action == 'coquille' and _holds(p, 'coquille') and q >= p.pv:
            p.objs['coquille'] = False
            p.pv = COQUILLE_PV
            _defeat(s, p)
            s.phase = 'replay'
            return s
        if action in EXECUTORS and _holds(p, action) and _EXEC_PRED[action](q, t):
            if action == 'midas':
                p.pv += q                             # heals by the monster's power (uncapped)
                p.objs['midas'] = False
            elif action == 'barde':
                p.objs['barde'] = False
                p.pv -= 3                             # lose the passive +3
            elif action in _ONESHOT_EXEC:             # hache / calumet
                p.objs[action] = False
            _defeat(s, p)
            if action == 'calumet':
                return _pass_turn(s)                  # ends the current turn
            s.phase = 'replay'
            return s
        # 'resolve' (or anything illegal) -> take the hit
        if q >= p.pv:                                 # lethal, no save chosen -> die on purpose
            p.status = 'dead'
            return _pass_carried(s)
        p.pv -= q
        _defeat(s, p)
        s.phase = 'replay'
        return s
    if s.phase == 'replay':
        return _continue_same(s) if action else _pass_turn(s)
    return s


# --- a reasonable baseline heuristic (returns one action per call; the object phase
#     is a loop, so it is re-queried until the monster is resolved) -------------------
def heuristic_action(s):
    kind, opts = legal(s)
    p = s.players[s.to_move]
    opp = s.players[1 - s.to_move]

    if kind == 'object':
        q, t = s.current
        free = [n for n in ('marteau', 'torche') if n in opts]
        if free:
            return free[0]                            # free reusable kill: always good
        if q < p.pv:
            return 'resolve'                          # survivable: tank, save the objects
        # lethal, no free kill:
        if 'osselets' in opts:
            return 'osselets'                         # reusable save (-> 1 PV)
        for n in ('midas', 'hache', 'calumet', 'barde'):   # spend a one-shot executor
            if n in opts:
                return n
        if 'coquille' in opts:
            return 'coquille'                         # one-shot save (-> 3 PV)
        if 'kebab' in opts and p.pv + HEAL > q:
            return 'kebab'                            # heal enough to survive, then tank
        return 'resolve'                              # nothing left -> die

    # flee / replay: danger read over the remaining deck (composition is legal info)
    def free_kill(q, t):
        return ((t in ('Golem', 'Squelette') and _holds(p, 'marteau'))
                or (q <= 2 and _holds(p, 'torche')))
    n_deadly = sum(1 for q, t in (DECK[i] for i in s.order[s.idx:])
                   if q >= p.pv and not free_kill(q, t))
    covers = (sum(1 for n in ('hache', 'calumet', 'barde') if _holds(p, n))
              + (1 if _holds(p, 'osselets') else 0) + (1 if _holds(p, 'coquille') else 0))

    if kind == 'replay':
        return n_deadly <= covers

    if kind == 'flee':
        q, t = s.current
        if free_kill(q, t) or q < p.pv:
            return False
        fleeable = q <= 6
        if fleeable and opp.status == 'dead':
            return True
        if fleeable and opp.status == 'fled' and p.score > opp.score:
            return True
        killers = [n for n in EXECUTORS if _holds(p, n) and _EXEC_PRED[n](q, t)]
        save = _holds(p, 'osselets') or _holds(p, 'coquille')
        heal = _holds(p, 'kebab') and p.turn >= KEBAB_MIN_TURN and p.pv + HEAL > q
        return bool(q >= p.pv and not killers and not save and not heal)
    return opts[0] if opts else None


def play(seed, hand, pol0, pol1):
    s = new_game(seed, hand)
    pols = (pol0, pol1)
    while not s.terminal:
        s = step(s, pols[s.to_move](s))
    return s
