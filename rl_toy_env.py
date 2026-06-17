"""Torch-free toy environment for the RL diagnostic (see rl_toy.py for the why).

This module owns everything about the toy *match* that does not depend on
PyTorch: the fixed object set, the fixed dungeon, the duel match builder, the
guardrail decision-kind set and the structural (identity) fallback policy.

Keeping it torch-free means the environment -- the part most likely to silently
break the "only encodable kinds are raised / nothing hits the heuristic policy"
guarantees -- can be tested on its own. ``rl_toy.py`` adds the network, the PPO
training loop and the success-criterion probes on top.
"""
from __future__ import annotations

import random

import numpy as np

from ai_decisions import CombatObjectChoice, DecisionKind, require_permutation
from ai_policy import RoutedDungeonPolicy
from heros import MercenaireOrc
from monstres import CarteMonstre, DonjonDeck
from objets import (ArmureEnCuir, CalumetDeLaPaix, CoquilleSalvatrice, CouteauSuisse,
                    HacheDeGlace, KebabRevigorant, MarteauDeGuerre, TorcheBleue)


TOY_PLAYER_NAMES = ("Alice", "Bob")

# The network must control exactly these decision kinds in the toy. SHOULD_FLEE
# and SHOULD_REPLAY are raised every turn; the combat kinds when fighting.
# USE_OBJECT_IN_COMBAT / USE_ACTIVE_OBJECT are listed for safety -- harmless if
# the fixed object set never raises them.
TOY_MANAGED_KINDS = (
    DecisionKind.SHOULD_FLEE,
    DecisionKind.SHOULD_REPLAY,
    DecisionKind.USE_OBJECT_IN_COMBAT,
    DecisionKind.USE_ACTIVE_OBJECT,
    DecisionKind.CHOOSE_COMBAT_OBJECT,
    # Couteau Suisse: pick which broken object to repair. A new decision *kind*,
    # but the SAME shape as CHOOSE_COMBAT_OBJECT (1-of-N over objects) -- the
    # encoder routes it to the existing candidate/pointer head, no new machinery.
    # The heuristic is provably lazy here (repairs max-by-pv_bonus, which ties at
    # 0 for our one-shots -> just the first one), so it is real headroom to learn.
    DecisionKind.CHOOSE_OBJECT_TO_REPAIR,
)

# ORDER_OBJECTS is a structural, non-strategic inventory call the engine makes at
# setup. It is resolved as identity -- not by the network (ordering head is out
# of v0 scope) and not by any heuristic.
TOY_STRUCTURAL_KINDS = (DecisionKind.ORDER_OBJECTS,)
TOY_ALLOWED_KINDS = frozenset(TOY_MANAGED_KINDS) | frozenset(TOY_STRUCTURAL_KINDS)

# Fixed *composition* (re-shuffled each game): the full set of "standard"
# monsters (no rats, no special-rule / effect / X cards). Listed here ascending
# by power for readability only -- the order is randomised per game (see
# ToyDonjon), so the agent cannot memorise a sequence. Plain monsters only =>
# the only decisions raised stay the encodable binary / 1-of-N kinds.
#   Gobelin(1)/Squelette(2) : free kills (Torche; Marteau also kills Squelette)
#   Golem(5)                : Marteau (type) or Hache
#   Orc/Vampire/Liche/Demon : Hache-only (or tank); not coverable by Marteau/Torche
#   Dragon(9)               : Hache-only (biggest threat) -> the scarce Hache is
#                             best spent here; the rest must be tanked or fled.
_STANDARD_MONSTERS = (
    # (nom, puissance, types, count) -- matches the base DonjonDeck composition.
    ("Gobelin", 1, ("Gobelin",), 4),
    ("Squelette", 2, ("Squelette",), 4),
    ("Orc", 3, ("Orc",), 4),
    ("Vampire", 4, ("Vampire",), 4),
    ("Golem", 5, ("Golem",), 4),
    ("Liche", 6, ("Liche",), 2),
    ("Démon", 7, ("Démon",), 2),
    ("Dragon", 9, ("Dragon",), 2),
)
TOY_DUNGEON_SEQUENCE = tuple(
    (nom, puissance, types)
    for nom, puissance, types, count in _STANDARD_MONSTERS
    for _ in range(count)
)

TOY_HERO_PV = 7   # MercenaireOrc level 2: pure passive HP, no dice, no decisions.
TOY_ARMOR_PV = 5  # Armure en cuir: pure passive +5 PV.
TOY_START_PV = TOY_HERO_PV + TOY_ARMOR_PV  # 12 PV: enough to tank one Dragon (->3).

# Distinct monster power levels and deck size, for the exact remaining-deck
# histogram fed to the network (full information, not a coarse summary).
TOY_POWER_LEVELS = tuple(sorted({puissance for _, puissance, _ in TOY_DUNGEON_SEQUENCE}))
TOY_DECK_SIZE = len(TOY_DUNGEON_SEQUENCE)


# The object POOL the toy draws hands from. All are real game objects, all are in
# the encoder's object vocabulary, and (verified) they only ever raise the
# network-controlled decision kinds. The variety forces the agent to value scarce
# *consumables* against each other across many hand compositions:
#   - Marteau de Guerre   : type executor (Golem / Squelette), free, reusable.
#   - Torche Bleue        : power executor (<= 2), free, reusable.
#   - Hache de Glace      : one-shot, executes ANY monster (the scarce premium).
#   - Armure en cuir      : passive +5 PV buffer.
#   - Calumet de la Paix  : one-shot, executes ANY monster but FORCES a skipped
#                           turn (a second executor with a tempo cost).
#   - Coquille Salvatrice : one-shot death-save -- a lethal hit leaves you at 3 PV
#                           instead of dead (auto; changes the risk calculus).
#   - Kebab revigorant    : one-shot heal of +7 PV (from turn 3 on).
TOY_OBJECT_POOL = (
    MarteauDeGuerre, TorcheBleue, HacheDeGlace, ArmureEnCuir,
    CalumetDeLaPaix, CoquilleSalvatrice, KebabRevigorant,
    # Couteau Suisse: one-shot, repairs ONE broken object of your choice. Our
    # one-shots (Calumet / Coquille / Kebab) break (intact=False) on use rather
    # than vanish, so the Couteau gives them a second life -- and *which* one to
    # repair (given the remaining deck) is the new skill to learn.
    CouteauSuisse,
)
TOY_HAND_SIZE = 5  # each game draws this many from the pool (symmetric for both seats)


def make_toy_objects():
    """A FIXED reference hand (1 Hache, no second any-executor) -- used only by the
    optimal-line probe, where the Hache must be the unique any-monster executor so
    the 'use it on the lethal Dragon / keep it on the weakling' test is unambiguous.
    Real matches draw a varied hand from TOY_OBJECT_POOL (see build_toy_match)."""
    return [MarteauDeGuerre(), TorcheBleue(), HacheDeGlace(), ArmureEnCuir()]


def make_toy_hand(rng):
    """Draw a symmetric hand of TOY_HAND_SIZE object *classes* from the pool, using
    the given stdlib Random instance (so it is reproducible per game seed)."""
    return rng.sample(TOY_OBJECT_POOL, TOY_HAND_SIZE)


def make_toy_hero():
    return MercenaireOrc(2)


class ToyDonjon(DonjonDeck):
    """DonjonDeck restricted to the fixed toy *composition*. The draw order is
    shuffled every game (inherited DonjonDeck.melange), so the agent must learn a
    state-based policy -- decide from the current card, its HP and the number of
    cards left -- rather than memorise a fixed sequence. The shuffle is seeded in
    build_toy_match, so each (seed) is reproducible and the eval bank is fixed."""

    def __init__(self):
        self.cartes = [
            CarteMonstre(nom, power, list(types))
            for nom, power, types in TOY_DUNGEON_SEQUENCE
        ]
        for index, carte in enumerate(self.cartes):
            carte.index = index
            carte.ordre = index
        self.nb_cartes = len(self.cartes)
        self.ordre = None
        self.index = 0


def build_toy_match(seed, shuffle_objects=False):
    """Build a 2-player toy match. Returns (joueurs, objets_dispo).

    Each game draws a SYMMETRIC hand of TOY_HAND_SIZE objects from TOY_OBJECT_POOL
    -- the two seats get the *same* hand (fairness preserved), but the hand varies
    across games, so the agent must handle different object *combinations* rather
    than one fixed set. Reproducible per seed.

    The only randomness consumed downstream is the flee die roll; seeding here
    keeps each (seed) reproducible while varying across the rollout batch. torch
    is seeded in rl_toy where it is imported; here we seed the stdlib/numpy RNGs.

    ``shuffle_objects`` additionally permutes each seat's inventory order. The hand
    (set) stays identical between seats; only the presentation order differs. A
    policy that decides by object *identity* rather than slot position is invariant
    to this -- a robustness check, mirroring the real game's arbitrary item order.
    """
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)

    from joueurs import Joueur

    hand_classes = make_toy_hand(random)  # the shared hand (symmetric across seats)
    joueurs = []
    for nom in TOY_PLAYER_NAMES:
        objets = [cls() for cls in hand_classes]  # fresh instances per seat
        if shuffle_objects:
            random.shuffle(objets)
        joueurs.append(Joueur(nom, make_toy_hero(), objets))
    return joueurs, []


class ToyStructuralPolicy:
    """Resolves the engine's structural calls without any heuristic or network.

    Only ``ORDER_OBJECTS`` is allowed (resolved as identity). Any other kind
    reaching here means a gameplay decision escaped the network -> hard failure,
    which is exactly the guardrail the brief asks for.
    """

    def decide(self, context):
        if context.kind in TOY_STRUCTURAL_KINDS:
            return require_permutation(
                tuple(context.options), context.options, decision_name='toy_order_objects'
            )
        raise AssertionError(
            f"toy: decision {context.kind.name} (phase={context.phase!r}) reached the "
            f"structural fallback -- it must be network-controlled"
        )


def routed_toy_policy(seat_policies, joueurs):
    """A RoutedDungeonPolicy whose *default* is the strict structural policy, so
    no decision can ever fall through to DefaultDungeonPolicy."""
    routed = RoutedDungeonPolicy(ToyStructuralPolicy())
    routed.set_assignments({joueurs[i]: pol for i, pol in seat_policies.items()})
    return routed


def is_hache(objet):
    """The scarce one-shot executor whose use is the toy's key strategic skill."""
    return isinstance(objet, HacheDeGlace)


def is_hache_worthy(carte):
    """True if the free reusable tools cannot execute this monster, so spending
    the one-shot Hache on it is justified rather than a waste: not power <= 2
    (Torche) and not Golem / Squelette (Marteau de Guerre)."""
    power = getattr(carte, 'puissance', getattr(carte, 'puissance_initiale', 0))
    types = getattr(carte, 'types', ()) or ()
    return power > 2 and 'Golem' not in types and 'Squelette' not in types
