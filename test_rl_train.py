import pytest
from types import SimpleNamespace


try:
    import torch
except Exception as exc:  # pragma: no cover - environment-dependent skip path
    pytest.skip(f"torch unavailable for RL tests: {exc}", allow_module_level=True)

from ai_decisions import DecisionContext, DecisionKind
from rl_train import ObservationEncoder, PolicyValueNet, run_smoke_training, smoke_checkpoint_reproducibility


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


def test_combat_encoder_exposes_worthit_signal():
    class DummyObject:
        intact = True
        actif = False
        pv_bonus = 0
        modificateur_de = 0
        priorite = 42
        types_tags = []
        puissance_tags = []
        couleur = 1

        def worthit(self, joueur, carte, jeu, log_details):
            return True

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

    assert encoded['candidate_obs'][0, -1] == 1.0
    assert encoded['global_obs'][-4] == 1.0 / encoder.max_candidates
