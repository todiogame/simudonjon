import time

import pytest

from heros import Avatar, ChevalierDragon, Perso
from joueurs import Joueur
from monstres import CarteEvent, CarteMonstre, DonjonDeck
from objets import (
    AllianceSanguine,
    AnneauDesSquelettes,
    BarbecueDuPonceur,
    BouleDeCristal,
    CoeurDeGolem,
    Egide,
    FilDuDestin,
    FruitDuDestin,
    LameDraconique,
    LinceulDeResurrection,
    Objet,
    OeilDHorus,
    OiseauDeMauvaisAugure,
    OsseletsDeResurrection,
    PotionDeGlace,
)
from simu import _basic_log, _emit_current_card, _emit_dungeon_state, _reset_temporary_card_modifiers
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


def test_human_next_action_does_not_expose_unknown_next_card():
    provider = _Provider("draw")
    joueur = Joueur(
        "Tester",
        Perso("Tester Hero", 10),
        [],
        control="human",
        decision_provider=provider,
    )
    joueur.tour = 2

    class Jeu:
        joueurs = [joueur]
        carte_courante = None
        donjon = DonjonDeck()

    Jeu.donjon.ordre = [0]
    Jeu.donjon.nb_cartes = 1
    Jeu.donjon.index = 0

    assert joueur.choisir_action_suivante(Jeu, []) == "draw"

    call = provider.calls[0]
    assert call["kind"] == "next_action"
    assert call["prompt"] == "Choisissez votre prochaine action."
    assert [option["id"] for option in call["options"]] == ["flee", "draw"]
    assert "card" not in call["context"]
    assert "power" not in call["context"]


def test_human_next_action_exposes_passed_monster():
    provider = _Provider("draw")
    joueur = Joueur(
        "Tester",
        Perso("Tester Hero", 10),
        [],
        control="human",
        decision_provider=provider,
    )
    joueur.tour = 2
    dragon = CarteMonstre("Dragon", 9, ["Dragon"])

    class Jeu:
        joueurs = [joueur]
        carte_courante = dragon
        donjon = DonjonDeck()

    Jeu.donjon.ordre = [0]
    Jeu.donjon.nb_cartes = 1
    Jeu.donjon.index = 0

    assert joueur.choisir_action_suivante(Jeu, []) == "draw"

    call = provider.calls[0]
    assert call["prompt"] == "Choisissez votre prochaine action."
    assert call["context"]["card"] == "Dragon"
    assert call["context"]["power"] == 9


def test_human_next_action_can_offer_pass_after_a_resolved_card():
    provider = _Provider("pass")
    joueur = Joueur(
        "Tester",
        Perso("Tester Hero", 10),
        [],
        control="human",
        decision_provider=provider,
    )
    joueur.tour = 2

    class Jeu:
        joueurs = [joueur]
        carte_courante = None
        donjon = DonjonDeck()

    Jeu.donjon.ordre = [0]
    Jeu.donjon.nb_cartes = 1
    Jeu.donjon.index = 0

    assert joueur.choisir_action_suivante(Jeu, [], can_pass=True) == "pass"
    assert [option["id"] for option in provider.calls[0]["options"]] == ["flee", "draw", "pass"]


def test_current_card_update_can_refresh_resolved_x_power_without_log_event():
    session = GameSession({"mode": "random"})
    dragon = CarteMonstre("Dragon endormi", 0, ["Dragon"], effet="SLEEPING", is_X=True)
    dragon.puissance = 9
    dragon.dommages = 9

    _emit_current_card(session.emit, dragon, "Human")

    snap = session.snapshot()
    assert snap["currentCard"]["title"] == "Dragon endormi"
    assert snap["currentCard"]["power"] == 9
    assert snap["currentCard"]["damage"] == 9
    assert session.events_after() == []


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


class _SequenceProvider:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def choose(self, joueur, kind, prompt, options, default_id, context=None):
        self.calls.append({
            "kind": kind,
            "prompt": prompt,
            "options": options,
            "default_id": default_id,
            "context": context or {},
        })
        if self.answers:
            return self.answers.pop(0)
        return default_id


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
    assert provider.calls[0]["options"][0]["itemId"] == str(id(first))
    assert provider.calls[0]["options"][1]["itemId"] == str(id(second))


def test_human_resolves_combat_manually_without_legal_item():
    provider = _Provider("resolve")
    joueur = Joueur(
        "Tester",
        Perso("Tester Hero", 10),
        [],
        strategy="baseline",
        control="human",
        decision_provider=provider,
    )

    assert joueur.choisir_source_combat([], _Card(), object(), []) is None
    assert provider.calls[0]["kind"] == "choose_combat_source"
    assert [option["id"] for option in provider.calls[0]["options"]] == ["resolve"]


def test_ice_potion_power_change_is_temporary():
    potion = PotionDeGlace()
    joueur = Joueur("Tester", Perso("Tester Hero", 10), [potion], control="human")
    dragon = CarteMonstre("Dragon", 9, ["Dragon"])
    dragon.dommages = 9

    potion.combat_effet(joueur, dragon, _Jeu(), [])

    assert dragon.puissance == 0
    assert dragon.dommages == 0
    assert dragon.puissance_modifiee_temporairement is True

    _reset_temporary_card_modifiers(dragon)

    assert dragon.puissance == 9
    assert dragon.dommages == 0
    assert dragon.puissance_modifiee_temporairement is False


class _Jeu:
    traquenard_actif = False

    def __init__(self, joueurs=None):
        self.joueurs = joueurs or []
        self.defausse = []


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


def _survival_card(damage=5, pv_before=3):
    card = CarteMonstre("Orc", 3, ["Orc"])
    card.dommages = damage
    card.pv_cible_avant_dommages = pv_before
    return card


def test_human_can_decline_survival_item():
    egide = Egide()
    provider = _Provider("no")
    joueur = Joueur(
        "Tester",
        Perso("Tester Hero", 3),
        [egide],
        control="human",
        decision_provider=provider,
    )
    jeu = _Jeu([joueur])
    joueur.pv_total = -2

    egide.en_survie(joueur, _survival_card(), jeu, [])

    assert joueur.pv_total == -2
    assert egide.intact
    assert provider.calls[0]["kind"] == "survival_item"
    assert provider.calls[0]["context"]["pvBeforeDamage"] == 3


def test_human_can_accept_survival_item():
    egide = Egide()
    provider = _Provider("yes")
    joueur = Joueur(
        "Tester",
        Perso("Tester Hero", 3),
        [egide],
        control="human",
        decision_provider=provider,
    )
    jeu = _Jeu([joueur])
    card = _survival_card()
    joueur.pv_total = -2

    egide.en_survie(joueur, card, jeu, [])

    assert joueur.pv_total == 3
    assert not egide.intact
    assert card in joueur.pile_monstres_vaincus


def test_survival_item_requires_monster_damage_to_be_lethal():
    egide = Egide()
    provider = _Provider("yes")
    joueur = Joueur(
        "Tester",
        Perso("Tester Hero", 3),
        [egide],
        control="human",
        decision_provider=provider,
    )
    jeu = _Jeu([joueur])
    joueur.pv_total = -1

    egide.en_survie(joueur, _survival_card(damage=2, pv_before=3), jeu, [])

    assert provider.calls == []
    assert joueur.pv_total == -1
    assert egide.intact


def test_linceul_survival_requires_discardable_monster():
    linceul = LinceulDeResurrection()
    provider = _Provider("yes")
    joueur = Joueur(
        "Tester",
        Perso("Tester Hero", 3),
        [linceul],
        control="human",
        decision_provider=provider,
    )
    jeu = _Jeu([joueur])
    joueur.pv_total = -2

    linceul.en_survie(joueur, _survival_card(), jeu, [])

    assert provider.calls == []
    assert joueur.pv_total == -2
    assert linceul.intact


def test_conditional_combat_items_do_not_pass_rules_when_effect_cannot_apply():
    joueur = Joueur("Tester", Perso("Tester Hero", 3), [], control="human")
    jeu = _Jeu([joueur])
    orc = CarteMonstre("Orc", 3, ["Orc"])
    orc.dommages = 3

    joueur.pv_total = 2
    assert not OsseletsDeResurrection().rules(joueur, orc, jeu, [])
    assert not CoeurDeGolem().rules(joueur, orc, jeu, [])
    assert not LameDraconique().rules(joueur, orc, jeu, [])
    joueur.pv_total = 5
    assert not AllianceSanguine().rules(joueur, orc, jeu, [])
    assert not AnneauDesSquelettes().rules(joueur, orc, jeu, [])
    assert not BarbecueDuPonceur().rules(joueur, orc, jeu, [])
    assert not FruitDuDestin().rules(joueur, orc, jeu, [])

    joueur.pv_total = 3
    assert OsseletsDeResurrection().rules(joueur, orc, jeu, [])
    joueur.pv_total = 4
    assert AllianceSanguine().rules(joueur, orc, jeu, [])

    joueur.pile_monstres_vaincus.append(CarteMonstre("Golem", 5, ["Golem"]))
    assert CoeurDeGolem().rules(joueur, orc, jeu, [])
    assert BarbecueDuPonceur().rules(joueur, orc, jeu, [])

    dragon = CarteMonstre("Dragon", 9, ["Dragon"])
    dragon.dommages = 9
    assert LameDraconique().rules(joueur, dragon, jeu, [])

    squelette = CarteMonstre("Squelette", 2, ["Squelette"])
    squelette.dommages = 2
    assert AnneauDesSquelettes().rules(joueur, squelette, jeu, [])

    jeu.defausse.append(CarteMonstre("Gobelin", 1, ["Gobelin"]))
    assert FruitDuDestin().rules(joueur, orc, jeu, [])


def test_serialized_items_expose_color_and_description_for_ui():
    item = next(obj for obj in fresh_item_pool() if getattr(obj, "couleur", None))
    payload = serialize_object(item)

    assert payload["colorCode"] in {1, 2, 3, 4, 5}
    assert payload["colorName"]
    assert payload["color"].startswith("#")
    assert payload["description"]
    assert payload["itemId"] == str(id(item))


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
        "knownCards",
        "discardCount",
        "discard",
        "discardOrder",
    }
    assert payload["remainingCount"] == 4
    assert payload["remainingSummary"][0]["count"] >= 1
    assert payload["knownCards"] == []
    assert payload["discardOrder"] == "top-first"
    assert [card["title"] for card in payload["discard"]] == ["Top", "Bottom"]


def test_dungeon_state_exposes_human_known_cards_in_order():
    events = []
    donjon = DonjonDeck()
    dragon_idx = next(i for i, card in enumerate(donjon.cartes) if card.titre == "Dragon")
    orc_idx = next(i for i, card in enumerate(donjon.cartes) if card.titre == "Orc")
    donjon.ordre = [dragon_idx, orc_idx]
    donjon.nb_cartes = 2
    donjon.index = 0
    human = Joueur("Human", Perso("Hero", 10), [], control="human")
    bot = Joueur("Bot", Perso("Bot Hero", 10), [], control="teacher ai")
    human.cartes_connues.add(donjon.cartes[orc_idx])
    bot.cartes_connues.add(donjon.cartes[dragon_idx])

    class Jeu:
        defausse = []
        joueurs = [human, bot]

    Jeu.donjon = donjon

    _emit_dungeon_state(events.append, Jeu)

    known = events[-1]["payload"]["knownCards"]
    assert len(known) == 1
    assert known[0]["player"] == "Human"
    assert [(card["title"], card["position"]) for card in known[0]["cards"]] == [("Orc", 2)]


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


def test_crystal_ball_human_chooses_announced_power():
    crystal = BouleDeCristal()
    provider = _Provider("1")
    owner = Joueur(
        "Owner",
        Perso("Hero", 10),
        [crystal],
        control="human",
        decision_provider=provider,
    )
    donjon = DonjonDeck()
    orc_idx = next(i for i, card in enumerate(donjon.cartes) if card.titre == "Orc")
    dragon_idx = next(i for i, card in enumerate(donjon.cartes) if card.titre == "Dragon")
    donjon.ordre = [orc_idx, dragon_idx]
    donjon.nb_cartes = 2
    donjon.index = 0

    class Jeu:
        pass

    Jeu.donjon = donjon

    crystal.debut_tour(owner, Jeu, [])

    assert provider.calls[0]["kind"] == "crystal_ball_power"
    assert [option["label"] for option in provider.calls[0]["options"]] == ["Power 3", "Power 9"]
    assert crystal.annonce == 9


def test_eye_of_horus_human_decides_whether_to_bottom_card():
    eye = OeilDHorus()
    provider = _Provider("yes")
    owner = Joueur(
        "Owner",
        Perso("Hero", 10),
        [eye],
        control="human",
        decision_provider=provider,
    )
    defeated = CarteMonstre("Defeated", 1)
    defeated.executed = True
    donjon = DonjonDeck()
    dragon_idx = next(i for i, card in enumerate(donjon.cartes) if card.titre == "Dragon")
    donjon.ordre = [dragon_idx]
    donjon.nb_cartes = 1
    donjon.index = 0

    class Jeu:
        pass

    Jeu.donjon = donjon
    Jeu.joueurs = [owner]
    log = []

    eye.vaincu_effet(owner, owner, defeated, Jeu, log)

    assert provider.calls[0]["kind"] == "eye_of_horus_bottom"
    assert provider.calls[0]["context"]["card"] == "Dragon"
    assert donjon.index == 1
    assert int(donjon.ordre[-1]) == dragon_idx


def test_thread_of_fate_human_orders_four_cards():
    thread = FilDuDestin()
    provider = _SequenceProvider(["yes", "3", "2", "1", "0"])
    owner = Joueur(
        "Owner",
        Perso("Hero", 10),
        [thread],
        control="human",
        decision_provider=provider,
    )
    owner.tour = 2
    donjon = DonjonDeck()
    names = ["Orc", "Dragon", "Gobelin", "Vampire"]
    indices = [next(i for i, card in enumerate(donjon.cartes) if card.titre == name) for name in names]
    donjon.ordre = indices[:]
    donjon.nb_cartes = len(indices)
    donjon.index = 0

    class Jeu:
        pass

    Jeu.donjon = donjon
    Jeu.joueurs = [owner]
    log = []

    thread.debut_tour(owner, Jeu, log)

    assert [call["kind"] for call in provider.calls] == [
        "thread_of_fate_use",
        "thread_of_fate_order",
        "thread_of_fate_order",
        "thread_of_fate_order",
        "thread_of_fate_order",
    ]
    assert [donjon.cartes[int(idx)].titre for idx in donjon.ordre[:4]] == [
        "Vampire",
        "Gobelin",
        "Dragon",
        "Orc",
    ]
    assert all(donjon.cartes[idx] in owner.cartes_connues for idx in indices)
    assert not thread.intact
