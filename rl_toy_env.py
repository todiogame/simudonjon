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
from objets import ArmureEnCuir, HacheDeGlace, MarteauDeGuerre, TorcheBleue


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


def make_toy_objects():
    """Fresh instances of the fixed toy objects (objects carry game state).

    - Marteau de Guerre : type executor (Golem / Squelette), free, reusable.
    - Torche Bleue      : power executor (<= 2), free, reusable.
    - Hache de Glace x2 : two active one-shot executors of ANY monster (incl.
                          Dragon), each consumed on use. Two of them for the two
                          Dragons removes the "dealt both Dragons => unavoidable
                          death" structure, so skill (allocating the two one-shots
                          across the two Dragons vs spending them early) decides
                          and can be discovered by RL rather than hand-coded.
    - Armure en cuir    : pure passive +5 PV buffer.
    """
    return [MarteauDeGuerre(), TorcheBleue(), HacheDeGlace(), HacheDeGlace(), ArmureEnCuir()]


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


def build_toy_match(seed):
    """Build a fixed 2-player toy match. Returns (joueurs, objets_dispo).

    The only randomness consumed downstream is the flee die roll; seeding here
    keeps each (seed) reproducible while varying across the rollout batch. torch
    is seeded in rl_toy where it is imported; here we seed the stdlib/numpy RNGs.
    """
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)

    from joueurs import Joueur

    return [Joueur(nom, make_toy_hero(), make_toy_objects()) for nom in TOY_PLAYER_NAMES], []


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
