import pytest
from types import SimpleNamespace
import inspect


try:
    import torch
except Exception as exc:  # pragma: no cover - environment-dependent skip path
    pytest.skip(f"torch unavailable for RL tests: {exc}", allow_module_level=True)

from ai_decisions import DecisionContext, DecisionKind
from rl_train import (
    ObservationEncoder,
    CurriculumMix,
    HybridNeuralPolicy,
    INITIAL_MANAGED_KINDS,
    PolicyValueNet,
    RewardConfig,
    _load_compatible_state_dict,
    _customize_stages,
    _parse_curriculum_mix,
    _training_base_rewards,
    progressive_stages,
    run_smoke_training,
    smoke_checkpoint_reproducibility,
)


class RaisingFallback:
    def decide(self, context):
        raise AssertionError(f"fallback used for managed kind {context.kind.name}")


def test_rl_smoke_training_runs():
    metrics = run_smoke_training()
    assert metrics['episodes'] == 16
    assert 'random_winrate' in metrics
    assert 'default_winrate' in metrics


def test_rl_checkpoint_reproducibility():
    result = smoke_checkpoint_reproducibility()
    assert 'checkpoint' in result
    assert 0.0 <= result['random_winrate'] <= 1.0
    assert 0.0 <= result['default_winrate'] <= 1.0


def test_combat_resolve_logit_depends_on_candidates():
    torch.manual_seed(0)
    encoder = ObservationEncoder()
    model = PolicyValueNet(encoder, hidden_dim=32)

    global_obs = torch.zeros((1, encoder.combat_global_size), dtype=torch.float32)
    candidate_obs = torch.zeros((1, encoder.max_candidates, encoder.candidate_size), dtype=torch.float32)
    candidate_ids = torch.zeros((1, encoder.max_candidates), dtype=torch.int64)
    action_mask = torch.zeros((1, encoder.max_candidates + 1), dtype=torch.float32)
    action_mask[0, 0] = 1.0
    action_mask[0, 1] = 1.0
    action_mask[0, -1] = 1.0

    logits_a, _ = model.forward_combat(global_obs, candidate_obs, candidate_ids, action_mask)

    candidate_obs[0, 0, 0] = 1.0
    candidate_obs[0, 0, 10] = 1.0
    candidate_ids[0, 0] = 1
    logits_b, _ = model.forward_combat(global_obs, candidate_obs, candidate_ids, action_mask)

    assert not torch.allclose(logits_a[:, -1], logits_b[:, -1])


def test_managed_object_encoder_does_not_consume_heuristic_signals():
    class DummyObject:
        intact = True
        actif = False
        pv_bonus = 0
        modificateur_de = 0
        types_tags = []
        puissance_tags = []
        couleur = 1
        gameplay_tags = ()

        @property
        def priorite(self):
            raise AssertionError("priority must not be consumed by PPO encoder")

        def worthit(self, joueur, carte, jeu, log_details):
            raise AssertionError("worthit must not be consumed by PPO encoder")

    actor = SimpleNamespace(
        pv_total=10,
        pv_base=10,
        medailles=0,
        pile_monstres_vaincus=[],
        objets=[DummyObject()],
        vivant=True,
        dans_le_dj=True,
        fuite_reussie=False,
    )
    game = SimpleNamespace(
        donjon=SimpleNamespace(ordre=[0], index=0),
        joueurs=[actor],
        tour=1,
        traquenard_actif=False,
        traquenard_paye=False,
        execute_next_monster=False,
    )
    subject = SimpleNamespace(
        types=[],
        puissance_initiale=3,
        dommages=3,
        event=False,
        is_X=False,
        effet=None,
    )
    context = DecisionContext(
        kind=DecisionKind.CHOOSE_COMBAT_OBJECT,
        actor=actor,
        game=game,
        phase='choose_combat_object',
        subject=subject,
        options=(actor.objets[0],),
        metadata={},
    )

    encoder = ObservationEncoder()
    encoded = encoder.encode(context)

    assert encoded['mode'] == 'combat_object'
    assert encoded['candidate_obs'][0].shape == (encoder.candidate_size,)


def test_managed_object_and_hero_kinds_do_not_use_fallback_and_return_legal_actions():
    class DummyObject:
        def __init__(self, name):
            self.nom = name
            self.intact = True
            self.actif = False
            self.pv_bonus = 0
            self.modificateur_de = 0
            self.types_tags = ()
            self.puissance_tags = ()
            self.couleur = 1
            self.gameplay_tags = ()

    objects = tuple(DummyObject(f"object-{index}") for index in range(3))
    hero = SimpleNamespace(
        nom='hero',
        pv_bonus=2,
        modificateur_de=0,
        effet=None,
        gameplay_tags=(),
    )
    actor = SimpleNamespace(
        pv_total=10,
        pv_base=10,
        medailles=0,
        pile_monstres_vaincus=[],
        objets=list(objects),
        vivant=True,
        dans_le_dj=True,
        fuite_reussie=False,
        perso_obj=hero,
    )
    game = SimpleNamespace(
        donjon=SimpleNamespace(ordre=[0], index=0),
        joueurs=[actor],
        tour=1,
        traquenard_actif=False,
        traquenard_paye=False,
        execute_next_monster=False,
    )
    subject = SimpleNamespace(
        types=[],
        puissance_initiale=3,
        dommages=3,
        event=False,
        is_X=False,
        effet=None,
    )
    encoder = ObservationEncoder()
    model = PolicyValueNet(encoder, hidden_dim=32)
    policy = HybridNeuralPolicy(
        model,
        encoder,
        managed_kinds=INITIAL_MANAGED_KINDS,
        fallback=RaisingFallback(),
        sample=False,
        record=True,
    )

    contexts = [
        DecisionContext(DecisionKind.USE_OBJECT_IN_COMBAT, actor, game, 'object_combat', subject, (objects[0],), {'objet': objects[0]}),
        DecisionContext(DecisionKind.USE_ACTIVE_OBJECT, actor, game, 'enclume_instable_use', subject, (objects[0],), {'objet': objects[0]}),
        DecisionContext(DecisionKind.USE_HERO_ABILITY, actor, game, 'avatar', subject, metadata={'hero': hero}),
        DecisionContext(DecisionKind.CHOOSE_OBJECT, actor, game, 'draw_two_keep_one', subject, objects),
        DecisionContext(DecisionKind.CHOOSE_OBJECT_TO_SACRIFICE, actor, game, 'object_sacrifice', subject, objects),
        DecisionContext(DecisionKind.CHOOSE_OBJECT_TO_REPAIR, actor, game, 'repair_object', subject, objects),
        DecisionContext(DecisionKind.CHOOSE_OBJECTS, actor, game, 'gants_de_gaia_discards', subject, objects, {'count': 2}),
        DecisionContext(DecisionKind.ORDER_OBJECTS, actor, game, 'inventory', options=objects),
    ]

    results = [policy.decide(context) for context in contexts]

    assert type(results[0]) is bool
    assert type(results[1]) is bool
    assert type(results[2]) is bool
    assert results[3] in objects
    assert results[4] in objects
    assert results[5] in objects
    assert len(results[6]) == 2
    assert all(value in objects for value in results[6])
    assert set(map(id, results[7])) == set(map(id, objects))


def test_encoder_source_excludes_heuristic_feature_symbols():
    sources = "\n".join(
        inspect.getsource(member)
        for member in (
            ObservationEncoder._encode_binary,
            ObservationEncoder._encode_object_choice,
            ObservationEncoder._encode_candidate,
        )
    )
    assert 'worthit' not in sources
    assert 'worth_it' not in sources
    assert 'priorite' not in sources


def test_compatible_load_preserves_candidate_embedding_columns_when_tags_expand():
    torch.manual_seed(123)
    encoder = ObservationEncoder()
    source = PolicyValueNet(encoder, hidden_dim=32)
    target = PolicyValueNet(encoder, hidden_dim=32)

    target_initial = target.state_dict()['combat_candidate_encoder.0.weight'].clone()
    source_state = source.state_dict()
    full_weight = source_state['combat_candidate_encoder.0.weight']
    old_candidate_size = 12
    embed_cols = 16
    old_weight = torch.cat((full_weight[:, :old_candidate_size], full_weight[:, -embed_cols:]), dim=1)
    source_state['combat_candidate_encoder.0.weight'] = old_weight

    _load_compatible_state_dict(target, source_state)

    loaded_weight = target.state_dict()['combat_candidate_encoder.0.weight']
    assert torch.allclose(loaded_weight[:, :old_candidate_size], full_weight[:, :old_candidate_size])
    assert torch.allclose(loaded_weight[:, -embed_cols:], full_weight[:, -embed_cols:])
    assert torch.allclose(loaded_weight[:, old_candidate_size:-embed_cols], target_initial[:, old_candidate_size:-embed_cols])


def test_training_customization_overrides_curriculum_and_stage_knobs():
    mix = _parse_curriculum_mix("0,1,0")
    assert mix == CurriculumMix(self_play=0.0, versus_default=1.0, versus_random=0.0)

    stage = _customize_stages(
        progressive_stages(),
        stage_limit=1,
        managed_kind_names=("CHOOSE_COMBAT_OBJECT",),
        reward_shaping=True,
        lr=5e-5,
        entropy_coef=0.03,
    )[0]

    assert stage.managed_kinds == ("CHOOSE_COMBAT_OBJECT",)
    assert stage.reward.enabled is True
    assert stage.reward.placement_mode == "ranked"
    assert stage.ppo.lr == 5e-5
    assert stage.ppo.entropy_coef == 0.03


def test_winner_take_all_training_rewards_only_the_winner():
    players = [
        SimpleNamespace(score_final=5, vivant=True, dans_le_dj=True, pv_total=1),
        SimpleNamespace(score_final=12, vivant=True, dans_le_dj=True, pv_total=1),
        SimpleNamespace(score_final=8, vivant=True, dans_le_dj=True, pv_total=1),
    ]

    rewards = _training_base_rewards(players, RewardConfig(placement_mode="winner_take_all"))

    assert rewards[id(players[1])] == 1.0
    assert rewards[id(players[0])] == 0.0
    assert rewards[id(players[2])] == 0.0
