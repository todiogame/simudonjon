import time

import pytest

from heros import Perso
from joueurs import Joueur
from objets import Objet
from ui_runtime import GameSession


def drive_defaults(session, timeout=30):
    deadline = time.time() + timeout
    decisions = 0
    while time.time() < deadline:
        snap = session.snapshot()
        if snap["pendingDecision"]:
            decision = snap["pendingDecision"]
            session.submit_decision(decision["id"], decision["defaultId"])
            decisions += 1
        if snap["status"] in {"finished", "error", "cancelled"}:
            break
        time.sleep(0.005)
    snap = session.snapshot()
    assert snap["status"] == "finished", snap.get("error")
    assert snap["result"]["winner"] is not None
    return decisions, snap


@pytest.mark.parametrize(
    ("mode", "extra"),
    [
        ("random", {}),
        ("draft", {}),
        ("party", {"partyRounds": 1}),
    ],
)
def test_ui_sessions_finish_with_default_human_choices(mode, extra):
    config = {
        "mode": mode,
        "playerName": "Tester",
        "playerCount": 3,
        "seed": 11,
        "botDelayMs": 0,
        **extra,
    }
    session = GameSession(config)
    session.start()

    decisions, snap = drive_defaults(session)

    assert decisions > 0
    assert snap["lastEventId"] > 0
    assert len(snap["players"]) in {0, 3}


def test_decision_validation_rejects_illegal_option():
    session = GameSession({"mode": "random"})
    with session.condition:
        session.pending_decision = {
            "id": "decision-1",
            "player": "Tester",
            "kind": "test",
            "prompt": "Pick one",
            "options": [{"id": "a", "label": "A"}],
            "defaultId": "a",
            "context": {},
        }

    with pytest.raises(ValueError):
        session.submit_decision("decision-1", "b")

    session.submit_decision("decision-1", "a")
    assert session._decision_answer == "a"


class _Provider:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def choose(self, joueur, kind, prompt, options, default_id, context=None):
        self.calls.append({
            "kind": kind,
            "prompt": prompt,
            "options": options,
            "default_id": default_id,
            "context": context or {},
        })
        return self.answer


class _CombatItem(Objet):
    def __init__(self, name, worth):
        super().__init__(name, actif=True)
        self._worth = worth

    def worthit(self, joueur, carte, Jeu, log_details):
        return self._worth


class _Card:
    titre = "Test Monster"
    dommages = 6
    puissance = 6
    types = ["Golem"]


def test_human_can_choose_any_legal_combat_item_directly():
    first = _CombatItem("First legal item", False)
    second = _CombatItem("Second legal item", True)
    provider = _Provider("1")
    joueur = Joueur(
        "Tester",
        Perso("Tester Hero", 10),
        [first, second],
        strategy="baseline",
        control="human",
        decision_provider=provider,
    )

    choice = joueur.choisir_source_combat([first, second], _Card(), object(), [])

    assert choice is second
    assert provider.calls[0]["kind"] == "choose_combat_source"
    assert [option["label"] for option in provider.calls[0]["options"]] == [
        "First legal item",
        "Second legal item",
        "Resolve now",
    ]
