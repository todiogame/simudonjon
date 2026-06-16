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
from objets import CouronneEnMousse, MarteauDeGuerre, TorcheBleue


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

# Fixed dungeon, drawn in this exact order every game. Plain monsters only.
#   Squelette(2): executable by BOTH Marteau (type) and Torche (power)  -> real choice
#   Gobelin(1)  : executable by Torche only (power)                     -> single tool
#   Dragon(9)   : executable by NEITHER -> must be tanked; the combo (two -2
#                 reducers) is the only way to survive it at the tuned HP.
TOY_DUNGEON_SEQUENCE = (
    ("Squelette", 2, ("Squelette",)),
    ("Gobelin", 1, ("Gobelin",)),
    ("Dragon", 9, ("Dragon",)),
    ("Squelette", 2, ("Squelette",)),
    ("Gobelin", 1, ("Gobelin",)),
    ("Dragon", 9, ("Dragon",)),
    ("Squelette", 2, ("Squelette",)),
    ("Gobelin", 1, ("Gobelin",)),
)

TOY_HERO_PV = 7  # MercenaireOrc level 2: pure passive HP, no dice, no decisions.


def make_toy_objects():
    """Fresh instances of the four fixed toy objects (objects carry game state)."""
    return [MarteauDeGuerre(), TorcheBleue(), CouronneEnMousse(), CouronneEnMousse()]


def make_toy_hero():
    return MercenaireOrc(2)


class ToyDonjon(DonjonDeck):
    """DonjonDeck with a fixed card list and a fixed (identity) draw order."""

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

    def melange(self):
        # No shuffle: the toy dungeon order is fixed and reproducible.
        self.ordre = np.arange(self.nb_cartes)
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


def is_dragon_combat_context(context):
    return (
        context.kind is DecisionKind.CHOOSE_COMBAT_OBJECT
        and 'Dragon' in (getattr(context.subject, 'types', ()) or ())
    )


def is_reducer(objet):
    return isinstance(objet, CouronneEnMousse)
