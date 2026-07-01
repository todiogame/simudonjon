import time

import pytest

from heros import Avatar, ChevalierDragon, Perso
from joueurs import Joueur
from monstres import CarteEvent, CarteMonstre, DonjonDeck
from objets import Objet, OiseauDeMauvaisAugure
from simu import _basic_log, _emit_dungeon_state
from ui_runtime import (
    GameSession,
    HEURISTIC_STRATEGY_NAME,
    TEACHER_STRATEGY_NAME,
    fresh_item_pool,
    normalize_bot_strategies,
    serialize_object,
)


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


def test_bot_strategies_are_configured_per_ai_player():
    config = {
        "mode": "random",
        "playerName": "Tester",
        "playerCount": 4,
        "seed": 13,
        "botDelayMs": 0,
        "botStrategies": [
            HEURISTIC_STRATEGY_NAME,
            TEACHER_STRATEGY_NAME,
            "not-a-strategy",
        ],
    }
    assert normalize_bot_strategies(config, 4) == [
        HEURISTIC_STRATEGY_NAME,
        TEACHER_STRATEGY_NAME,
        TEACHER_STRATEGY_NAME,
    ]
    session = GameSession(config)
    session.start()

    _, snap = drive_defaults(session)

    assert [player["strategy"] for player in snap["players"][1:]] == [
        HEURISTIC_STRATEGY_NAME,
        TEACHER_STRATEGY_NAME,
        TEACHER_STRATEGY_NAME,
    ]
    assert [player["control"] for player in snap["players"][1:]] == [
        "heuristic ai",
        "teacher ai",
        "teacher ai",
    ]


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


class _Jeu:
    traquenard_actif = False


def test_human_combat_perso_does_not_prompt_when_rules_cannot_work():
    provider = _Provider("yes")
    hero = ChevalierDragon()
    joueur = Joueur(
        "Tester",
        hero,
        [],
        strategy="baseline",
        control="human",
        decision_provider=provider,
    )
    card = CarteMonstre("Orc", 3, ["Orc"])
    card.dommages = 3

    hero.en_combat(joueur, card, _Jeu(), [])

    assert provider.calls == []
    assert not card.executed

    provider = _Provider("yes")
    avatar = Avatar()
    avatar.capacite_utilisee = True
    joueur = Joueur(
        "Tester",
        avatar,
        [],
        strategy="baseline",
        control="human",
        decision_provider=provider,
    )
    card = CarteMonstre("Dragon", 9, ["Dragon"])
    card.dommages = 9

    avatar.en_combat_late(joueur, card, _Jeu(), [])

    assert provider.calls == []
    assert not card.executed


def test_serialized_items_expose_color_and_description_for_ui():
    item = next(obj for obj in fresh_item_pool() if getattr(obj, "couleur", None))
    payload = serialize_object(item)

    assert payload["colorCode"] in {1, 2, 3, 4, 5}
    assert payload["colorName"]
    assert payload["color"].startswith("#")
    assert payload["description"]


def test_human_item_choice_options_hide_zero_pv_and_expose_color():
    item = Objet("Zero PV Test", actif=True, pv_bonus=0, modificateur_de=0)
    item.couleur = 1
    provider = _Provider("0")
    joueur = Joueur(
        "Tester",
        Perso("Tester Hero", 10),
        [item],
        strategy="baseline",
        control="human",
        decision_provider=provider,
    )

    assert joueur.demander_choix("pick", "Pick one", [item], default=item) is item

    option = provider.calls[0]["options"][0]
    assert "PV +0" not in option["description"]
    assert option["colorCode"] == 1
    assert option["colorName"] == "rouge"


def test_dungeon_state_hides_deck_order_but_orders_discard():
    events = []
    donjon = DonjonDeck()
    donjon.ordre = list(range(4))
    donjon.index = 0

    class Jeu:
        pass

    Jeu.donjon = donjon
    Jeu.defausse = [
        CarteMonstre("Bottom", 1),
        CarteEvent("Top", "top card"),
    ]

    _emit_dungeon_state(events.append, Jeu)

    payload = events[-1]["payload"]
    assert set(payload) == {
        "remainingCount",
        "remainingSummary",
        "discardCount",
        "discard",
        "discardOrder",
    }
    assert payload["remainingCount"] == 4
    assert payload["remainingSummary"][0]["count"] >= 1
    assert payload["discardOrder"] == "top-first"
    assert [card["title"] for card in payload["discard"]] == ["Top", "Bottom"]


def test_bad_omen_bird_asks_human_before_moving_card_under_dungeon():
    bird = OiseauDeMauvaisAugure()
    provider = _Provider("yes")
    owner = Joueur(
        "Owner",
        Perso("Hero", 5),
        [bird],
        control="human",
        decision_provider=provider,
    )
    opponent = Joueur("Other", Perso("Other", 5), [])
    donjon = DonjonDeck()
    dragon_idx = next(i for i, card in enumerate(donjon.cartes) if card.titre == "Dragon")
    donjon.ordre = [dragon_idx]
    donjon.nb_cartes = 1
    donjon.index = 0

    class Jeu:
        joueurs = [owner, opponent]
        defausse = []

    Jeu.donjon = donjon
    log = []

    bird.fin_tour(owner, Jeu, log)

    assert provider.calls[0]["kind"] == "bad_omen_bird_bottom"
    assert provider.calls[0]["context"]["card"] == "Dragon"
    assert provider.calls[0]["context"]["recommended"] == "leave"
    assert any("envoie Dragon sous le Donjon" in row for row in log)
    assert donjon.index == 1
    assert int(donjon.ordre[-1]) == dragon_idx


def test_bad_omen_bird_human_can_leave_card_on_top():
    bird = OiseauDeMauvaisAugure()
    provider = _Provider("no")
    owner = Joueur(
        "Owner",
        Perso("Hero", 5),
        [bird],
        control="human",
        decision_provider=provider,
    )
    opponent = Joueur("Other", Perso("Other", 5), [])
    donjon = DonjonDeck()
    dragon_idx = next(i for i, card in enumerate(donjon.cartes) if card.titre == "Dragon")
    donjon.ordre = [dragon_idx]
    donjon.nb_cartes = 1
    donjon.index = 0

    class Jeu:
        joueurs = [owner, opponent]
        defausse = []

    Jeu.donjon = donjon
    log = []

    bird.fin_tour(owner, Jeu, log)

    assert provider.calls[0]["kind"] == "bad_omen_bird_bottom"
    assert any("voit Dragon" in row for row in log)
    assert any(_basic_log(row) for row in log)
    assert donjon.index == 0
    assert donjon.cartes[dragon_idx] in owner.cartes_connues
