"""Minimal, CLONEABLE, STEPPABLE toy engine -- a clean state machine so MCTS/ISMCTS
can explore fast (no re-simulation).

Faithful to the REAL simudonjon (simu.py `ordonnanceur`): players ALTERNATE turns; a
turn = face one card; after defeating it you REPLAY or PASS; you stay IN the dungeon
across turns and only leave by fleeing (a d6 roll >= power) or dying; fleeing/dying
HANDS the monster to the next player (offensive); the round ends on deck-empty (poncé)
or all-out; scoring = poncéurs (still IN) count and exclude fleers, else the alive
fleers count, the dead never count; PV is UNCAPPED.

ONE looping "use an object" decision (no native heal/save): heal, death-saves and
executors are all objects you may use, several in a row. Two sub-decisions reuse it:
choosing WHICH object to break (bombe / Limon) and WHICH to repair (couteau).

OBJECT POOL (14):
  marteau  : kills Golem/Squelette, free, reusable.
  torche   : kills power<=2, free, reusable.
  hache    : kills ANY, one-shot, discarded (NOT repairable).
  midas    : kills power<=4, one-shot, AND heals by the monster's power.
  barde    : passive +3 PV; broken to kill ANY (you lose the +3 PV; repairable).
  calumet  : kills ANY, one-shot, then your current turn ends.
  bombe    : kills ANY, REUSABLE, but each use BREAKS another of your objects (your
             choice; breaking a passive-PV object loses those PV).
  couteau  : one-shot; REPAIR one broken object (your choice; not the hache).
  kebab    : +7 PV, one-shot, only from your 3rd turn on.
  pomme    : +3 PV AND reveal the next 3 cards (to you), one-shot.
  osselets : survive a lethal hit at 1 PV; reusable but only ARMS at PV>=3.
  coquille : survive a lethal hit at 3 PV; one-shot.
  armure   : passive +5 PV.
  coeur    : passive +3 PV; +1 PV per defeat once you have >=2 kills this turn.

DUNGEON: plain monsters + the LIMON event (power 0): if you FIGHT it you must eat
(break) one of your objects; if you EXECUTE it with an object, no loss.

API: s=new_game(seed,hand); kind,opts=legal(s); s=step(s,action); s.terminal,s.winner.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

PV_START = 10
HEAL = 7
KEBAB_MIN_TURN = 3
OSSELETS_PV = 1
OSSELETS_THRESHOLD = 3
COQUILLE_PV = 3
POMME_HEAL = 3
POMME_LOOKAHEAD = 3

POOL = ('marteau', 'torche', 'hache', 'midas', 'barde', 'calumet', 'bombe',
        'couteau', 'kebab', 'pomme', 'osselets', 'coquille', 'armure', 'coeur')

EXECUTORS = ('marteau', 'torche', 'hache', 'midas', 'barde', 'calumet', 'bombe')
_EXEC_PRED = {
    'marteau': lambda q, t: t in ('Golem', 'Squelette'),
    'torche':  lambda q, t: q <= 2,
    'hache':   lambda q, t: True,
    'midas':   lambda q, t: q <= 4,
    'barde':   lambda q, t: True,
    'calumet': lambda q, t: True,
    'bombe':   lambda q, t: True,
}
_ONESHOT_EXEC = ('hache', 'midas', 'barde', 'calumet')   # consumed/broken on use (bombe is reusable)
_PASSIVE_PV = {'armure': 5, 'coeur': 3, 'barde': 3}      # +PV at game start (lost if broken)

DECK = (
    (1, 'Gobelin'), (1, 'Gobelin'), (1, 'Gobelin'), (1, 'Gobelin'),
    (2, 'Squelette'), (2, 'Squelette'), (2, 'Squelette'), (2, 'Squelette'),
    (3, 'Orc'), (3, 'Orc'), (3, 'Orc'), (3, 'Orc'),
    (4, 'Vampire'), (4, 'Vampire'), (4, 'Vampire'), (4, 'Vampire'),
    (5, 'Golem'), (5, 'Golem'), (5, 'Golem'), (5, 'Golem'),
    (6, 'Liche'), (6, 'Liche'),
    (7, 'Demon'), (7, 'Demon'),
    (9, 'Dragon'), (9, 'Dragon'),
    (0, 'Limon'), (0, 'Limon'),                          # event: fight it -> eat an object
)  # 28 cards
TYPES = ('Gobelin', 'Squelette', 'Orc', 'Vampire', 'Golem', 'Liche', 'Demon', 'Dragon', 'Limon')


@dataclass
class Player:
    pv: int
    objs: dict
    score: int = 0
    status: str = 'in'
    turn: int = 0
    kills_turn: int = 0


@dataclass
class State:
    order: tuple
    idx: int
    players: list
    to_move: int
    phase: str                   # 'flee'|'object'|'break'|'repair'|'replay'|'terminal'
    current: tuple = None        # (power, type) faced (drawn or PASSED), or None
    terminal: bool = False
    winner: int = None
    rng: object = None
    known_until: list = field(default_factory=lambda: [0, 0])   # per-seat: order known up to here
    break_then: str = None       # why we're in 'break' ('bombe' -> still must defeat; 'limon' -> done)

    def clone(self):
        return copy.deepcopy(self)


def sample_hand(seed, k=5):
    return random.Random(seed).sample(POOL, k)


def new_game(seed, hand):
    rng = random.Random(seed)
    order = list(range(len(DECK)))
    rng.shuffle(order)
    pv0 = PV_START + sum(_PASSIVE_PV.get(n, 0) for n in hand)
    players = [Player(pv=pv0, objs={n: True for n in hand}) for _ in range(2)]
    s = State(order=tuple(order), idx=0, players=players, to_move=0, phase='flee', rng=rng,
              known_until=[0, 0])
    return _begin_fresh_turn(s, 0)


def _holds(p, name):
    return p.objs.get(name, False)


def _break_targets(p, exclude=None):
    """Intact objects whose breaking won't kill us (passives gated by their PV)."""
    return [n for n, ok in p.objs.items()
            if ok and n != exclude and _PASSIVE_PV.get(n, 0) < p.pv]


def _repair_targets(p):
    """Broken objects we may repair (not the discarded hache, not the couteau itself)."""
    return [n for n, ok in p.objs.items() if not ok and n not in ('hache', 'couteau')]


def _object_options(s, p):
    q, t = s.current
    opts = []
    for n in EXECUTORS:
        if not _holds(p, n) or not _EXEC_PRED[n](q, t):
            continue
        if n == 'barde' and p.pv <= 3:
            continue
        if n == 'bombe' and not _break_targets(p, exclude='bombe'):
            continue
        opts.append(n)
    if _holds(p, 'kebab') and p.turn >= KEBAB_MIN_TURN:
        opts.append('kebab')
    if _holds(p, 'pomme'):
        opts.append('pomme')
    if _holds(p, 'couteau') and _repair_targets(p):
        opts.append('couteau')
    if q >= p.pv:
        if _holds(p, 'osselets') and p.pv >= OSSELETS_THRESHOLD:
            opts.append('osselets')
        if _holds(p, 'coquille'):
            opts.append('coquille')
    opts.append('resolve')
    return opts


def legal(s):
    p = s.players[s.to_move]
    if s.phase == 'flee':
        return 'flee', [True, False]
    if s.phase == 'object':
        return 'object', _object_options(s, p)
    if s.phase == 'break':
        excl = 'bombe' if s.break_then == 'bombe' else None
        return 'break', _break_targets(p, exclude=excl)
    if s.phase == 'repair':
        return 'repair', _repair_targets(p)
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


def _face_next(s):
    """Set the to_move player to face a card. A CARRIED monster (s.current set) is known.
    A FRESH draw stays HIDDEN (s.current is None) until the flee decision is made -> the
    flee gamble is BLIND, per the rules: announce flee + roll the d6, THEN draw the card.
    (The reveal happens inside step()'s flee phase, after the roll / on a no-flee.)"""
    if s.current is None and s.idx >= len(s.order):
        return _finish(s)                       # deck empty, nothing to draw -> poncé
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
    return _face_next(s)


def _begin_carried_turn(s, seat):
    s.to_move = seat
    p = s.players[seat]
    p.turn += 1
    p.kills_turn = 0
    return _face_next(s)                         # current stays (carried = known monster)


def _pass_carried(s):
    nxt = _next_in_after(s, s.to_move)
    return _begin_carried_turn(s, nxt) if nxt is not None else _finish(s)


def _pass_turn(s):
    s.current = None
    nxt = _next_in_after(s, s.to_move)
    return _begin_fresh_turn(s, nxt if nxt is not None else s.to_move)


def _continue_same(s):
    s.current = None
    return _face_next(s)


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


def _resolve_hit(s, p):
    """The player takes the faced card's hit (chose 'resolve' / no object)."""
    q, t = s.current
    if q >= p.pv:                                # lethal, no save chosen -> die on purpose
        p.status = 'dead'
        return _pass_carried(s)
    p.pv -= q
    _defeat(s, p)
    if t == 'Limon' and _break_targets(p):       # fighting the Limon -> it eats one of your objects
        s.break_then = 'limon'
        s.phase = 'break'
        return s
    s.phase = 'replay'
    return s


def step(s, action):
    p = s.players[s.to_move]
    if s.phase == 'flee':
        if action:                                      # announce flee, roll the d6, THEN reveal
            roll = s.rng.randint(1, 6)
            if s.current is None:                        # fresh draw -> revealed only now
                s.current = DECK[s.order[s.idx]]
                s.idx += 1
            if roll >= s.current[0]:
                p.status = 'fled'
                return _pass_carried(s)
            # flee failed -> must fight the (now revealed) monster
        elif s.current is None:                          # no flee on a fresh draw -> reveal to fight
            s.current = DECK[s.order[s.idx]]
            s.idx += 1
        s.phase = 'object'
        return s

    if s.phase == 'object':
        q, t = s.current
        if action == 'kebab' and _holds(p, 'kebab') and p.turn >= KEBAB_MIN_TURN:
            p.pv += HEAL
            p.objs['kebab'] = False
            return s                                       # stay in the loop
        if action == 'pomme' and _holds(p, 'pomme'):
            p.pv += POMME_HEAL
            p.objs['pomme'] = False
            s.known_until[s.to_move] = max(s.known_until[s.to_move], s.idx + POMME_LOOKAHEAD)
            return s                                       # stay in the loop
        if action == 'couteau' and _holds(p, 'couteau') and _repair_targets(p):
            p.objs['couteau'] = False
            s.phase = 'repair'
            return s
        if action == 'bombe' and _holds(p, 'bombe') and _break_targets(p, exclude='bombe'):
            s.break_then = 'bombe'                         # break first, then the kill
            s.phase = 'break'
            return s
        if action == 'osselets' and _holds(p, 'osselets') and q >= p.pv and p.pv >= OSSELETS_THRESHOLD:
            p.pv = OSSELETS_PV
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
                p.pv += q
                p.objs['midas'] = False
            elif action == 'barde':
                p.objs['barde'] = False
                p.pv -= 3
            elif action in _ONESHOT_EXEC:                  # hache / calumet
                p.objs[action] = False
            _defeat(s, p)
            if action == 'calumet':
                return _pass_turn(s)
            s.phase = 'replay'
            return s
        return _resolve_hit(s, p)                          # 'resolve' (or anything illegal)

    if s.phase == 'break':
        if action in p.objs and p.objs[action]:
            p.objs[action] = False
            p.pv -= _PASSIVE_PV.get(action, 0)             # lose passive PV if it gave any
        if s.break_then == 'bombe':                        # bombe's kill happens after the break
            _defeat(s, p)
        s.break_then = None
        s.phase = 'replay'
        return s

    if s.phase == 'repair':
        if action in p.objs and not p.objs[action]:
            p.objs[action] = True
            p.pv += _PASSIVE_PV.get(action, 0)             # regain passive PV
        s.phase = 'object'                                 # back to the loop, same monster
        return s

    if s.phase == 'replay':
        return _continue_same(s) if action else _pass_turn(s)
    return s


# --- baseline heuristic (one action per call; the object loop re-queries it) ---
def heuristic_action(s):
    kind, opts = legal(s)
    p = s.players[s.to_move]
    opp = s.players[1 - s.to_move]

    if kind == 'break':
        # eat/sacrifice the least valuable: spend passives last, then by a rough order
        order = ['pomme', 'kebab', 'couteau', 'midas', 'torche', 'marteau', 'calumet',
                 'bombe', 'hache', 'coquille', 'osselets', 'coeur', 'barde', 'armure']
        return next((n for n in order if n in opts), opts[0])

    if kind == 'repair':
        # restore the most valuable broken object
        order = ['osselets', 'coquille', 'bombe', 'calumet', 'barde', 'marteau', 'torche',
                 'midas', 'armure', 'coeur', 'kebab', 'pomme', 'couteau']
        return next((n for n in order if n in opts), opts[0])

    if kind == 'object':
        q, t = s.current
        free = [n for n in ('marteau', 'torche') if n in opts]
        if free:
            return free[0]                                 # free reusable kill (also dodges Limon's eat)
        if q < p.pv:
            return 'resolve'                               # survivable: tank, keep objects
        if 'osselets' in opts:
            return 'osselets'
        for n in ('midas', 'hache', 'calumet'):            # cheap one-shot executors
            if n in opts:
                return n
        if 'coquille' in opts:
            return 'coquille'
        if 'bombe' in opts:
            return 'bombe'                                 # kill any, at the cost of an object
        if 'barde' in opts:
            return 'barde'
        if 'kebab' in opts and p.pv + HEAL > q:
            return 'kebab'
        if 'pomme' in opts and p.pv + POMME_HEAL > q:
            return 'pomme'
        return 'resolve'                                   # nothing left -> die

    def free_kill(q, t):
        return ((t in ('Golem', 'Squelette') and _holds(p, 'marteau'))
                or (q <= 2 and _holds(p, 'torche')))
    n_deadly = sum(1 for q, t in (DECK[i] for i in s.order[s.idx:])
                   if q >= p.pv and not free_kill(q, t))
    covers = (sum(1 for n in ('hache', 'calumet', 'barde', 'bombe') if _holds(p, n))
              + (1 if _holds(p, 'osselets') else 0) + (1 if _holds(p, 'coquille') else 0))

    if kind == 'replay':
        # on par with ai_policy.should_replay: PASS as soon as ANY remaining monster deals
        # >2 and isn't FREELY executable (reusable marteau/torche). One-shots/saves are NOT
        # "easy coverage", so it plays one card then passes whenever a real threat remains --
        # it does NOT keep re-drawing early (matches simudonjon's "pass almost every turn").
        return not any(q > 2 and not free_kill(q, t)
                       for q, t in (DECK[i] for i in s.order[s.idx:]))

    if kind == 'flee':
        if s.current is None:                            # BLIND fresh flee (card not revealed yet)
            if opp.status == 'dead':
                return True                              # last alive -> try to exit and lock the win
            if opp.status == 'fled' and p.score > opp.score:
                return True                              # ahead of a fled opponent -> lock it
            n_rem = max(1, len(s.order) - s.idx)
            return bool(p.pv <= 6 and n_deadly > covers and n_deadly / n_rem >= 0.3)  # fragile + risky deck
        q, t = s.current                                 # carried (known) monster -> informed flee
        if free_kill(q, t) or q < p.pv:
            return False
        fleeable = q <= 6
        if fleeable and opp.status == 'dead':
            return True
        if fleeable and opp.status == 'fled' and p.score > opp.score:
            return True
        killers = [n for n in EXECUTORS if _holds(p, n) and _EXEC_PRED[n](q, t)]
        save = (_holds(p, 'osselets') and p.pv >= OSSELETS_THRESHOLD) or _holds(p, 'coquille')
        heal = _holds(p, 'kebab') and p.turn >= KEBAB_MIN_TURN and p.pv + HEAL > q
        return bool(q >= p.pv and not killers and not save and not heal)
    return opts[0] if opts else None


def play(seed, hand, pol0, pol1):
    s = new_game(seed, hand)
    pols = (pol0, pol1)
    while not s.terminal:
        s = step(s, pols[s.to_move](s))
    return s
