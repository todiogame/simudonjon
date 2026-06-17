"""Tests for the toy-mode RL diagnostic.

Environment tests run without torch (they exercise rl_toy_env only). The
network / training tests are skipped when torch is unavailable, mirroring
test_rl_train.py.
"""
import pytest

import rl_toy_env as env
from ai_decisions import DecisionContext, DecisionKind
from ai_policy import RandomPolicy
from objets import ArmureEnCuir, HacheDeGlace, MarteauDeGuerre, TorcheBleue
from simu import ordonnanceur


try:
    import torch  # noqa: F401
    HAVE_TORCH = True
except Exception:  # pragma: no cover - environment-dependent
    HAVE_TORCH = False

requires_torch = pytest.mark.skipif(not HAVE_TORCH, reason="torch unavailable for RL toy tests")


class _RecordingRandomPolicy:
    """Random legal choices, but records every decision kind and tracks the key
    skill (spending the one-shot Hache de Glace on a monster the free tools can't
    kill). Stands in for the network so the environment is testable without torch."""

    def __init__(self):
        self._base = RandomPolicy()
        self.kinds = {}
        self.skill = {'hache_uses': 0, 'hache_well_used': 0}

    def decide(self, context):
        self.kinds[context.kind.name] = self.kinds.get(context.kind.name, 0) + 1
        assert context.kind in env.TOY_ALLOWED_KINDS, context.kind.name
        decision = self._base.decide(context)
        if context.kind is DecisionKind.CHOOSE_COMBAT_OBJECT and env.is_hache(decision):
            self.skill['hache_uses'] += 1
            if env.is_hache_worthy(context.subject):
                self.skill['hache_well_used'] += 1
        return decision


def _play_toy_games(seeds):
    seen = {}
    skill = {'hache_uses': 0, 'hache_well_used': 0}
    for seed in seeds:
        joueurs, objets = env.build_toy_match(seed)
        policies = [_RecordingRandomPolicy() for _ in joueurs]
        routed = env.routed_toy_policy({i: policies[i] for i in range(len(joueurs))}, joueurs)
        ordonnanceur(joueurs, env.ToyDonjon(), objets, False, policy=routed)
        for policy in policies:
            for name, count in policy.kinds.items():
                seen[name] = seen.get(name, 0) + count
            for key in skill:
                skill[key] += policy.skill[key]
    return seen, skill


# --- Environment tests (torch-free) ------------------------------------------

def test_toy_match_draws_a_symmetric_hand_from_the_pool():
    joueurs, objets = env.build_toy_match(1)
    assert len(joueurs) == 2
    assert objets == []
    # Each seat gets a hand of HAND_SIZE objects drawn from the pool, at most one
    # Hache (single now), and the two seats get the SAME hand (symmetric).
    hands = []
    for joueur in joueurs:
        assert len(joueur.objets) == env.TOY_HAND_SIZE
        kinds = {type(o) for o in joueur.objets}
        assert kinds.issubset(set(env.TOY_OBJECT_POOL))
        assert sum(isinstance(o, HacheDeGlace) for o in joueur.objets) <= 1
        # PV varies with the hand (objects carry pv_bonus, plus a same-colour
        # "Panoplie" bonus), so just sanity-check it is at least the hero's base.
        assert joueur.pv_total >= env.TOY_HERO_PV
        hands.append(sorted(type(o).__name__ for o in joueur.objets))
    assert hands[0] == hands[1]  # symmetric: both seats share the same hand


def test_toy_hands_vary_across_games():
    # Different seeds should produce different hands (the pool is sampled).
    seen = {tuple(sorted(type(o).__name__ for o in env.build_toy_match(s)[0][0].objets))
            for s in range(40)}
    assert len(seen) > 1  # not a single fixed hand


def test_toy_dungeon_is_shuffled_with_fixed_composition():
    import numpy as np

    n = len(env.TOY_DUNGEON_SEQUENCE)
    a = env.ToyDonjon()
    np.random.seed(1)
    a.melange()
    b = env.ToyDonjon()
    np.random.seed(2)
    b.melange()
    # Every game draws all cards (a permutation), but the order is shuffled, not
    # fixed -- different seeds give different orders (so no sequence to memorise).
    assert sorted(a.ordre) == list(range(n))
    assert list(a.ordre) != list(b.ordre)
    # The composition is fixed regardless of order.
    assert sorted(c.titre for c in a.cartes) == sorted(nom for nom, _, _, _ in env.TOY_DUNGEON_SEQUENCE)


def test_toy_games_only_raise_allowed_kinds():
    seen, _ = _play_toy_games(range(200))
    allowed = {k.name for k in env.TOY_ALLOWED_KINDS}
    assert set(seen).issubset(allowed)
    # The core turn/combat decisions must actually be exercised.
    assert seen.get('SHOULD_FLEE', 0) > 0
    assert seen.get('SHOULD_REPLAY', 0) > 0
    assert seen.get('CHOOSE_COMBAT_OBJECT', 0) > 0
    assert seen.get('ORDER_OBJECTS', 0) > 0


def test_toy_key_skill_is_reachable_by_a_competent_line():
    """Random play dies at the early monsters, so to show the planted skill is
    reachable (hence learnable) we play the intended clearing line: execute free
    monsters for zero damage, spend the one-shot Hache on a monster the free
    tools cannot kill, never flee, keep drawing."""
    from ai_decisions import CombatObjectChoice

    class _ClearingPolicy:
        def __init__(self):
            self.skill = {'hache_uses': 0, 'hache_well_used': 0}

        def decide(self, context):
            kind = context.kind
            if kind is DecisionKind.SHOULD_FLEE:
                return False
            if kind is DecisionKind.SHOULD_REPLAY:
                return True
            if kind is DecisionKind.ORDER_OBJECTS:
                return tuple(context.options)
            if kind is DecisionKind.CHOOSE_COMBAT_OBJECT:
                free = [o for o in context.options if not env.is_hache(o)]
                if free:
                    return free[0]  # never waste the Hache on a free kill
                hache = [o for o in context.options if env.is_hache(o)]
                if hache:
                    self.skill['hache_uses'] += 1
                    if env.is_hache_worthy(context.subject):
                        self.skill['hache_well_used'] += 1
                    return hache[0]
                return CombatObjectChoice.RESOLVE_NOW
            # Covers CHOOSE_OBJECT_TO_SACRIFICE (Limon/Bombe) etc.: pick the first
            # option, or None when there is nothing to choose (e.g. no intact object).
            return context.options[0] if context.options else None

    total = {'hache_uses': 0, 'hache_well_used': 0}
    for seed in range(20):
        joueurs, objets = env.build_toy_match(seed)
        policies = [_ClearingPolicy() for _ in joueurs]
        routed = env.routed_toy_policy({i: policies[i] for i in range(len(joueurs))}, joueurs)
        ordonnanceur(joueurs, env.ToyDonjon(), objets, False, policy=routed)
        for p in policies:
            for key in total:
                total[key] += p.skill[key]
    assert total['hache_uses'] > 0
    assert total['hache_well_used'] > 0  # the Hache lands on a hache-worthy monster


def test_structural_policy_orders_identity_and_rejects_gameplay_kinds():
    policy = env.ToyStructuralPolicy()
    options = ('a', 'b', 'c')
    context = DecisionContext(
        kind=DecisionKind.ORDER_OBJECTS, actor=None, game=None,
        phase='inventory', options=options,
    )
    assert policy.decide(context) == options  # identity, not heuristic-sorted

    bad = DecisionContext(
        kind=DecisionKind.SHOULD_FLEE, actor=None, game=None, phase='flee',
    )
    with pytest.raises(AssertionError):
        policy.decide(bad)


def test_routed_toy_policy_default_is_structural_not_heuristic():
    joueurs, _ = env.build_toy_match(3)
    routed = env.routed_toy_policy({0: env.ToyStructuralPolicy(), 1: env.ToyStructuralPolicy()}, joueurs)
    # The fall-through default must never be the heuristic DefaultDungeonPolicy.
    assert isinstance(routed.default_policy, env.ToyStructuralPolicy)


# --- Network / training tests (require torch) --------------------------------

@requires_torch
def test_toy_smoke_trains_and_reports():
    import rl_toy

    result = rl_toy.run_toy_smoke()
    assert result.iterations == 2
    assert 0.0 <= result.final_winrate_vs_random <= 1.0
    assert 0.0 <= result.skill_rate <= 1.0
    assert isinstance(result.optimal_line, bool)
    # Every kind the agent saw must be network-encodable / structural.
    allowed = {k.name for k in env.TOY_ALLOWED_KINDS}
    assert set(result.kinds_seen).issubset(allowed)


@requires_torch
def test_toy_control_policy_routes_managed_to_network_and_guards_unknown_kinds():
    from types import SimpleNamespace

    import rl_toy

    model, encoder = rl_toy.build_toy_model(hidden_dim=32)

    class RaisingFallback:
        def decide(self, context):
            raise AssertionError(f"fallback used for managed kind {context.kind.name}")

    policy = rl_toy.ToyControlPolicy(model, encoder, sample=False, record=False)
    policy.fallback = RaisingFallback()  # managed kinds must not touch the fallback

    actor = SimpleNamespace(
        pv_total=7, pv_base=7, medailles=0, pile_monstres_vaincus=[],
        objets=[], vivant=True, dans_le_dj=True, fuite_reussie=False,
        perso_obj=SimpleNamespace(nom='h', pv_bonus=7, modificateur_de=0, effet=None, gameplay_tags=()),
    )
    game = SimpleNamespace(
        donjon=SimpleNamespace(ordre=[0], index=0), joueurs=[actor], tour=2,
        traquenard_actif=False, traquenard_paye=False, execute_next_monster=False,
    )
    flee = DecisionContext(DecisionKind.SHOULD_FLEE, actor, game, 'flee', metadata={})
    assert type(policy.decide(flee)) is bool  # network handled it, no fallback

    forbidden = DecisionContext(DecisionKind.CHOOSE_MONSTER, actor, game, 'whatever', options=())
    with pytest.raises(AssertionError):
        policy.decide(forbidden)  # allowed-kind guard trips


@requires_torch
def test_toy_imitation_smoke_runs():
    import rl_toy

    result, bc, after_bc = rl_toy.run_toy_imitation_smoke()
    assert bc['binary_samples'] > 0 and bc['combat_samples'] > 0
    assert 'binary' in bc['accuracy'] and 'combat' in bc['accuracy']
    assert 0.0 <= after_bc['vs_default'] <= 1.0
    assert 0.0 <= result.final_winrate_vs_default <= 1.0


@requires_torch
def test_probe_returns_structured_result():
    import rl_toy

    model, encoder = rl_toy.build_toy_model(hidden_dim=32)
    probe = rl_toy.probe_optimal_combat_decision(model, encoder)
    assert set(probe) == {'hache_on_lethal_dragon', 'hache_kept_on_weakling', 'optimal_line'}
    assert all(isinstance(v, bool) for v in probe.values())
