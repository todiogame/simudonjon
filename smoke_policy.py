import random

import numpy as np

from ai_policy import DefaultDungeonPolicy, default_draft_policy, default_dungeon_policy
from ai_decisions import DecisionContext, DecisionKind, require_option
from draft import _charger_priors, _draft_rapide
from heros import BeteDeLEvenement, Princesse, SANS_HOOK_PERSO, persos_disponibles
from joueurs import Joueur
from monstres import CarteEvent, CarteMonstre, DonjonDeck
from objets import (
    ArmureEnCuir,
    AttrapeReves,
    ClocheDuDejaVu,
    CouteauSuisse,
    CouteauxDeLancer,
    FilDuDestin,
    FouetDuFourbe,
    HacheDeGlace,
    Objet,
    OeilDHorus,
    OiseauDeMauvaisAugure,
    SANS_HOOK_OBJET,
    TambourDeKui,
    objets_disponibles,
)
from party import draft_soiree
from simu import GameState, _premier_candidat_traquenard, ordonnanceur


def _build_players(seed):
    random.seed(seed)
    np.random.seed(seed)
    objets_simu = list(objets_disponibles)
    for objet in objets_simu:
        objet.repare()
    persos = random.sample(persos_disponibles, 3)
    joueurs = []
    for i, nom in enumerate(("A", "B", "C")):
        objets_joueur = random.sample(objets_simu, 6)
        for objet in objets_joueur:
            objets_simu.remove(objet)
        joueurs.append(Joueur(nom, persos[i], objets_joueur))
    return joueurs, objets_simu


def _state(joueurs, vainqueur):
    return (
        getattr(vainqueur, "nom", None),
        tuple(
            (
                joueur.nom,
                joueur.personnage_nom,
                joueur.pv_total,
                joueur.score_final,
                joueur.vivant,
                joueur.fuite_reussie,
                joueur.dans_le_dj,
                tuple(monstre.titre for monstre in joueur.pile_monstres_vaincus),
            )
            for joueur in joueurs
        ),
    )


def smoke_ordonnanceur_policy_equivalence():
    joueurs_a, objets_a = _build_players(77)
    vainqueur_a, joueurs_a = ordonnanceur(joueurs_a, DonjonDeck(), objets_a, False)

    joueurs_b, objets_b = _build_players(77)
    vainqueur_b, joueurs_b = ordonnanceur(
        joueurs_b, DonjonDeck(), objets_b, False, policy=default_dungeon_policy()
    )

    assert _state(joueurs_a, vainqueur_a) == _state(joueurs_b, vainqueur_b)


def smoke_legacy_wrappers():
    joueurs, objets_simu = _build_players(12)
    donjon = DonjonDeck()
    donjon.melange()
    jeu = GameState(joueurs, donjon, objets_simu, default_dungeon_policy())
    joueur = joueurs[0]

    assert joueur.deciderDeFuir(jeu, []) is False
    assert isinstance(joueur.deciderDeRejouer(jeu, []), bool)
    assert joueur.decideBriseObjet(jeu, []) is not None


def smoke_draft_policy_equivalence():
    priors = _charger_priors()
    assert priors is not None

    random.seed(31)
    np.random.seed(31)
    persos_a = random.sample(persos_disponibles, 3)
    builds_a, restants_a = _draft_rapide(persos_a, [priors] * 3, epsilon=0.15)

    random.seed(31)
    np.random.seed(31)
    persos_b = random.sample(persos_disponibles, 3)
    builds_b, restants_b = _draft_rapide(
        persos_b, [priors] * 3, epsilon=0.15, draft_policy=default_draft_policy()
    )

    assert [[o.nom for o in b] for b in builds_a] == [[o.nom for o in b] for b in builds_b]
    assert [o.nom for o in restants_a] == [o.nom for o in restants_b]

    random.seed(41)
    np.random.seed(41)
    builds_c, restants_c = draft_soiree(persos_a, [0, 1, 0], False)

    random.seed(41)
    np.random.seed(41)
    builds_d, restants_d = draft_soiree(persos_a, [0, 1, 0], False, default_draft_policy())

    assert [[o.nom for o in b] for b in builds_c] == [[o.nom for o in b] for b in builds_d]
    assert [o.nom for o in restants_c] == [o.nom for o in restants_d]


def smoke_hero_policy_can_decline():
    class DeclinePrincessPolicy(DefaultDungeonPolicy):
        def decide_use_hero_ability(self, context):
            if context.phase == 'princess_draw':
                return False
            return super().decide_use_hero_ability(context)

    objets_simu = list(objets_disponibles)
    for objet in objets_simu:
        objet.repare()
    joueur = Joueur("P", Princesse(1), [])
    jeu = GameState([joueur], DonjonDeck(), objets_simu, DeclinePrincessPolicy())

    joueur.perso_obj.debut_tour(joueur, jeu, [])

    assert not joueur.perso_obj.capacite_utilisee
    assert joueur.objets == []


def smoke_unavailable_hero_ability_does_not_call_policy():
    class CountingPolicy(DefaultDungeonPolicy):
        def __init__(self):
            self.hero_calls = 0

        def decide_use_hero_ability(self, context):
            self.hero_calls += 1
            return super().decide_use_hero_ability(context)

    policy = CountingPolicy()
    joueur = Joueur("P", Princesse(1), [])
    joueur.perso_obj.capacite_utilisee = True
    jeu = GameState([joueur], DonjonDeck(), list(objets_disponibles), policy)

    joueur.perso_obj.debut_tour(joueur, jeu, [])

    assert policy.hero_calls == 0


def smoke_object_policy_can_decline_combat_use():
    class DeclineObjectsPolicy(DefaultDungeonPolicy):
        def decide_use_object_in_combat(self, context):
            return False

    hache = HacheDeGlace()
    joueur = Joueur("O", Princesse(1), [hache])
    joueur.pv_total = 5
    carte = CarteMonstre("Dragon test", 9, ["Dragon"])
    carte.dommages = 10
    jeu = GameState([joueur], DonjonDeck(), [], DeclineObjectsPolicy())

    hache.en_combat(joueur, carte, jeu, [])

    assert not carte.executed
    assert hache.intact
    assert joueur.pile_monstres_vaincus == []


def smoke_object_policy_can_choose_target():
    class ChooseHachePolicy(DefaultDungeonPolicy):
        def decide_choose_object_to_repair(self, context):
            if context.phase == 'couteau_suisse_repair':
                return next(o for o in context.options if o.nom == "Hache de Glace")
            return super().decide_choose_object_to_repair(context)

    couteau = CouteauSuisse()
    hache = HacheDeGlace()
    armure = ArmureEnCuir()
    hache.intact = False
    armure.intact = False
    joueur = Joueur("T", Princesse(1), [couteau, hache, armure])
    jeu = GameState([joueur], DonjonDeck(), [], ChooseHachePolicy())
    carte = CarteMonstre("Dragon test", 9, ["Dragon"])

    couteau.combat_effet(joueur, carte, jeu, [])

    assert hache.intact
    assert not armure.intact


def smoke_policy_controls_object_order():
    class ReverseInventoryPolicy(DefaultDungeonPolicy):
        def decide_order_objects(self, context):
            return tuple(reversed(context.options))

    joueur = Joueur("R", Princesse(1), [])
    jeu = GameState([joueur], DonjonDeck(), [], ReverseInventoryPolicy())
    hache = HacheDeGlace()
    armure = ArmureEnCuir()

    joueur.ajouter_objet(hache)
    joueur.ajouter_objet(armure)

    assert joueur.policy is jeu.policy
    assert joueur.objets == [armure, hache]


def smoke_invalid_policy_rejected():
    class InvalidBoolPolicy(DefaultDungeonPolicy):
        def decide_use_object_in_combat(self, context):
            return None

    hache = HacheDeGlace()
    joueur = Joueur("I", Princesse(1), [hache])
    carte = CarteMonstre("Dragon test", 9, ["Dragon"])
    carte.dommages = 10
    jeu = GameState([joueur], DonjonDeck(), [], InvalidBoolPolicy())

    try:
        hache.en_combat(joueur, carte, jeu, [])
    except ValueError:
        pass
    else:
        raise AssertionError("invalid bool policy return was not rejected")

    assert not carte.executed
    assert hache.intact


def smoke_default_policy_normalizes_legacy_worthit():
    class LegacyListWorthitObject(Objet):
        def __init__(self):
            super().__init__("Legacy list worthit", True)

        def worthit(self, joueur, carte, Jeu, log_details):
            return [carte]

    objet = LegacyListWorthitObject()
    joueur = Joueur("L", Princesse(1), [objet])
    carte = CarteMonstre("Rat test", 1, ["Rat"])
    jeu = GameState([joueur], DonjonDeck(), [], default_dungeon_policy())

    assert objet.condition(joueur, carte, jeu, []) is True


def smoke_donjon_worker_batch_runs():
    import donjon

    donjon._simuler_batch((2, 12345))


def smoke_traquenard_legality_independent_from_object_policy():
    class RefuseObjectPayTrapPolicy(DefaultDungeonPolicy):
        def decide_use_object_in_combat(self, context):
            return False

        def decide_pay_traquenard(self, context):
            return True

    hache = HacheDeGlace()
    joueur = Joueur("Q", Princesse(1), [hache])
    carte = CarteMonstre("Dragon test", 9, ["Dragon"])
    carte.dommages = 9
    jeu = GameState([joueur], DonjonDeck(), [], RefuseObjectPayTrapPolicy())
    jeu.traquenard_actif = True

    candidat = _premier_candidat_traquenard(
        joueur,
        carte,
        jeu,
        SANS_HOOK_OBJET['en_combat'],
        SANS_HOOK_PERSO['en_combat'],
        SANS_HOOK_PERSO['en_combat_late'],
    )

    assert candidat is not None
    assert candidat['source'] is hache


def _single_card_deck(card):
    deck = DonjonDeck()
    deck.cartes = [card]
    card.index = 0
    card.ordre = 0
    deck.nb_cartes = 1
    deck.ordre = np.array([0])
    deck.index = 0
    return deck


def _deck_with_cards(*cards):
    deck = DonjonDeck()
    deck.cartes = list(cards)
    for i, card in enumerate(deck.cartes):
        card.index = i
        card.ordre = i
    deck.nb_cartes = len(cards)
    deck.ordre = np.arange(len(cards))
    deck.index = 0
    return deck


def _assert_raises_value_error(callable_):
    try:
        callable_()
    except ValueError:
        return
    raise AssertionError("Expected ValueError")


def smoke_fortune_wheel_policy_can_decline():
    class DeclineWheelPolicy(DefaultDungeonPolicy):
        def decide_use_hero_ability(self, context):
            return False

        def decide_use_event_effect(self, context):
            if context.phase == 'fortune_wheel':
                return False
            return super().decide_use_event_effect(context)

    monstre = CarteMonstre("Golem test", 5, ["Golem"])
    joueur = Joueur("W", Princesse(1), [])
    joueur.pile_monstres_vaincus.append(monstre)
    pv_depart = joueur.pv_total
    event = CarteEvent("Roue test", "", "FORTUNE_WHEEL")

    ordonnanceur([joueur], _single_card_deck(event), [], False, policy=DeclineWheelPolicy())

    assert joueur.pile_monstres_vaincus == [monstre]
    assert joueur.pv_total == pv_depart


def smoke_event_beast_policy_choice_and_decline():
    repair = CarteEvent("Bricoleur test", "", "REPAIR")
    heal = CarteEvent("Heal test", "", "HEAL")

    def add_to_deck(deck, *cards):
        if deck.ordre is None:
            deck.ordre = np.array([], dtype=int)
            deck.index = 0
        for card in cards:
            card.index = len(deck.cartes)
            card.ordre = card.index
            deck.cartes.append(card)

    class DeclineBeastPolicy(DefaultDungeonPolicy):
        def decide_choose_card(self, context):
            if context.phase == 'event_beast_target':
                return None
            return super().decide_choose_card(context)

    joueur = Joueur("B", BeteDeLEvenement(2), [])
    jeu = GameState([joueur], DonjonDeck(), [], DeclineBeastPolicy())
    add_to_deck(jeu.donjon, repair, heal)
    jeu.defausse.extend([repair, heal])
    joueur.perso_obj.debut_tour(joueur, jeu, [])
    assert not joueur.perso_obj.capacite_utilisee
    assert jeu.defausse == [repair, heal]

    class ChooseHealPolicy(DefaultDungeonPolicy):
        def decide_choose_card(self, context):
            if context.phase == 'event_beast_target':
                return next(c for c in context.options if c.effet == 'HEAL')
            return super().decide_choose_card(context)

    joueur = Joueur("B", BeteDeLEvenement(2), [])
    jeu = GameState([joueur], DonjonDeck(), [], ChooseHealPolicy())
    add_to_deck(jeu.donjon, repair, heal)
    jeu.defausse.extend([repair, heal])
    joueur.perso_obj.debut_tour(joueur, jeu, [])
    assert joueur.perso_obj.capacite_utilisee
    assert heal not in jeu.defausse
    assert jeu.donjon.cartes[jeu.donjon.ordre[jeu.donjon.index]] is heal


def smoke_guardian_angel_attrape_reves_confidence():
    joueur = Joueur("G", Princesse(1), [AttrapeReves()])
    carte = CarteMonstre("Ange Gardien test", 8, [], effet="GUARDIAN_ANGEL")
    jeu = GameState([joueur], DonjonDeck(), [], default_dungeon_policy())

    wants = jeu.policy.decide(DecisionContext(
        kind=DecisionKind.SHOULD_FACE_SPECIAL_CARD,
        actor=joueur,
        game=jeu,
        phase="guardian_angel_face_or_discard",
        subject=carte,
    ))
    assert wants is True

    options = tuple(joueur.objets)
    confidence = jeu.policy.decide(DecisionContext(
        kind=DecisionKind.CHOOSE_OBJECT,
        actor=joueur,
        game=jeu,
        phase='guardian_angel_confidence_object',
        subject=carte,
        options=options,
        metadata={'allow_none': True},
    ))
    assert require_option(confidence, options, allow_none=True, decision_name='guardian_angel_confidence_object').nom == "Attrape-Rêves"


def smoke_traquenard_detects_chevalier_dragon_candidate():
    from heros import ChevalierDragon
    from monstres import CarteMonstre, DonjonDeck
    from simu import GameState, _premier_candidat_traquenard
    from objets import SANS_HOOK_OBJET

    joueur = Joueur("D", ChevalierDragon(2), [])
    carte = CarteMonstre("Dragon test", 9, ["Dragon"])
    jeu = GameState([joueur], DonjonDeck(), [], default_dungeon_policy())
    jeu.traquenard_actif = True

    candidat = _premier_candidat_traquenard(
        joueur,
        carte,
        jeu,
        SANS_HOOK_OBJET['en_combat'],
        SANS_HOOK_PERSO['en_combat'],
        SANS_HOOK_PERSO['en_combat_late'],
    )

    assert candidat is not None
    assert candidat["source"] is joueur.perso_obj


def smoke_traquenard_detects_docteur_de_peste_candidate():
    from heros import DocteurDePeste
    from monstres import CarteMonstre, DonjonDeck
    from simu import GameState, _premier_candidat_traquenard
    from objets import SANS_HOOK_OBJET

    joueur = Joueur("E", DocteurDePeste(1), [])
    carte = CarteMonstre("Rat test", 3, ["Rat"])
    jeu = GameState([joueur], DonjonDeck(), [], default_dungeon_policy())
    jeu.traquenard_actif = True

    candidat = _premier_candidat_traquenard(
        joueur,
        carte,
        jeu,
        SANS_HOOK_OBJET['en_combat'],
        SANS_HOOK_PERSO['en_combat'],
        SANS_HOOK_PERSO['en_combat_late'],
    )

    assert candidat is not None
    assert candidat["source"] is joueur.perso_obj


def smoke_traquenard_detects_avatar_late_candidate():
    from heros import Avatar
    from monstres import CarteMonstre, DonjonDeck
    from simu import GameState, _premier_candidat_traquenard
    from objets import SANS_HOOK_OBJET

    joueur = Joueur("F", Avatar(1), [])
    carte = CarteMonstre("Demon test", 7, ["Démon"])
    jeu = GameState([joueur], DonjonDeck(), [], default_dungeon_policy())
    jeu.traquenard_actif = True

    candidat = _premier_candidat_traquenard(
        joueur,
        carte,
        jeu,
        SANS_HOOK_OBJET['en_combat'],
        SANS_HOOK_PERSO['en_combat'],
        SANS_HOOK_PERSO['en_combat_late'],
    )

    assert candidat is not None
    assert candidat["source"] is joueur.perso_obj
    assert candidat["late"] is True


def smoke_defausse_monstre_de_pile_policy_choice():
    from monstres import CarteMonstre, DonjonDeck
    from simu import GameState

    class ChooseSpecificMonsterPolicy(DefaultDungeonPolicy):
        def decide_choose_monster(self, context):
            if context.phase == 'discard_monster_from_pile':
                return max(context.options, key=lambda m: 0 if m.is_X else m.puissance)
            return super().decide_choose_monster(context)

    joueur = Joueur("G", Princesse(1), [])
    faible = CarteMonstre("Rat faible", 2, ["Rat"])
    fort = CarteMonstre("Dragon fort", 9, ["Dragon"])
    joueur.pile_monstres_vaincus = [faible, fort]
    jeu = GameState([joueur], DonjonDeck(), [], ChooseSpecificMonsterPolicy())

    from objets import _defausse_monstre_de_pile
    monstre = _defausse_monstre_de_pile(joueur, jeu, [])
    assert monstre is fort
    assert fort not in joueur.pile_monstres_vaincus
    assert fort in jeu.defausse
    assert faible in joueur.pile_monstres_vaincus


def smoke_barbecue_du_ponceur_policy_target():
    from monstres import CarteMonstre, DonjonDeck
    from simu import GameState

    class ChooseSpecificMonsterPolicy(DefaultDungeonPolicy):
        def decide_choose_monster(self, context):
            if context.phase == 'barbecue_du_ponceur':
                return min(context.options, key=lambda m: 0 if m.is_X else m.puissance)
            return super().decide_choose_monster(context)

    joueur = Joueur("H", Princesse(1), [])
    faible = CarteMonstre("Rat faible", 2, ["Rat"])
    fort = CarteMonstre("Dragon fort", 9, ["Dragon"])
    joueur.pile_monstres_vaincus = [faible, fort]
    jeu = GameState([joueur], DonjonDeck(), [], ChooseSpecificMonsterPolicy())

    from objets import _defausse_monstre_de_pile
    monstre = _defausse_monstre_de_pile(joueur, jeu, [], plus_puissant=True, phase='barbecue_du_ponceur')
    assert monstre is faible
    assert faible not in joueur.pile_monstres_vaincus
    assert faible in jeu.defausse
    assert fort in joueur.pile_monstres_vaincus


def smoke_fruit_du_destin_policy_category():
    from monstres import CarteMonstre, CarteEvent, DonjonDeck
    from simu import GameState

    class ChooseEventCategory(DefaultDungeonPolicy):
        def decide_choose_category(self, context):
            if context.phase == 'fruit_du_destin_category':
                return "event"
            return super().decide_choose_category(context)

    joueur = Joueur("I", Princesse(1), [])
    event = CarteEvent("Heal test", "", "HEAL")
    monstre = CarteMonstre("Orc test", 3, ["Orc"])
    jeu = GameState([joueur], DonjonDeck(), [], ChooseEventCategory())
    jeu.defausse.extend([monstre, event])

    from objets import FruitDuDestin
    fruit = FruitDuDestin()
    pv_pre = joueur.pv_total
    fruit.combat_effet(joueur, monstre, jeu, [])
    assert joueur.pv_total == pv_pre + 1  # 1 event = 1 PV
    assert not fruit.intact


def smoke_fruit_du_destin_invalid_category_rejected():
    from monstres import CarteMonstre, CarteEvent, DonjonDeck
    from simu import GameState

    class BadCategoryPolicy(DefaultDungeonPolicy):
        def decide_choose_category(self, context):
            if context.phase == 'fruit_du_destin_category':
                return "invalid_category"
            return super().decide_choose_category(context)

    joueur = Joueur("J", Princesse(1), [])
    event = CarteEvent("Heal test", "", "HEAL")
    monstre = CarteMonstre("Orc test", 3, ["Orc"])
    jeu = GameState([joueur], DonjonDeck(), [], BadCategoryPolicy())
    jeu.defausse.extend([monstre, event])

    from objets import FruitDuDestin
    fruit = FruitDuDestin()
    pv_pre = joueur.pv_total
    try:
        fruit.combat_effet(joueur, monstre, jeu, [])
        assert False, "Should have raised ValueError for invalid category"
    except ValueError:
        pass
    assert fruit.intact
    assert joueur.pv_total == pv_pre


def smoke_default_policy_couteaux_de_lancer_targets_strongest():
    joueur = Joueur("K", Princesse(1), [])
    jeu = GameState([joueur], DonjonDeck(), [], default_dungeon_policy())
    faible = CarteMonstre("Rat faible", 2, ["Rat"])
    fort = CarteMonstre("Dragon fort", 9, ["Dragon"])
    moyen = CarteMonstre("Golem moyen", 5, ["Golem"])
    haut = CarteMonstre("Demon haut", 7, ["Demon"])

    choix = jeu.policy.decide(DecisionContext(
        kind=DecisionKind.CHOOSE_MONSTERS,
        actor=joueur,
        game=jeu,
        phase='couteaux_de_lancer',
        options=(faible, fort, moyen, haut),
        metadata={'max_count': 3},
    ))

    assert choix == (fort, haut, moyen)


def smoke_default_policy_tambour_de_kui_discards_dangerous_visible_monsters():
    joueur = Joueur("L", Princesse(1), [])
    joueur.pv_total = 4
    jeu = GameState([joueur], DonjonDeck(), [], default_dungeon_policy())
    dangereux = CarteMonstre("Dragon test", 7, ["Dragon"])
    limite_basse = CarteMonstre("Golem test", 6, ["Golem"])
    event = CarteEvent("Heal test", "", "HEAL")

    choix = jeu.policy.decide(DecisionContext(
        kind=DecisionKind.CHOOSE_CARDS,
        actor=joueur,
        game=jeu,
        phase='tambour_de_kui',
        options=(dangereux, limite_basse, event),
        metadata={'pv_total': joueur.pv_total},
    ))

    assert choix == (dangereux,)


def smoke_default_policy_divination_destinations_preserve_keep_bottom_rules():
    joueur = Joueur("M", Princesse(1), [])
    joueur.pv_total = 5
    jeu = GameState([joueur], DonjonDeck(), [], default_dungeon_policy())
    fort = CarteMonstre("Dragon test", 9, ["Dragon"])
    faible = CarteMonstre("Squelette test", 2, ["Squelette"])
    event = CarteEvent("Heal test", "", "HEAL")

    def decide(phase, card):
        return jeu.policy.decide(DecisionContext(
            kind=DecisionKind.CHOOSE_DESTINATION,
            actor=joueur,
            game=jeu,
            phase=phase,
            subject=None,
            options=('keep', 'bottom'),
            metadata={'prochaine': card},
        ))

    assert decide('oeil_d_horus', fort) == 'bottom'
    assert decide('oeil_d_horus', faible) == 'keep'
    assert decide('oiseau_de_mauvais_augure', event) == 'bottom'
    assert decide('oiseau_de_mauvais_augure', faible) == 'bottom'
    assert decide('oiseau_de_mauvais_augure', fort) == 'keep'


def smoke_default_policy_fil_du_destin_orders_by_old_danger_heuristic():
    joueur = Joueur("N", Princesse(1), [])
    jeu = GameState([joueur], DonjonDeck(), [], default_dungeon_policy())
    orc = CarteMonstre("Orc test", 3, ["Orc"])
    dragon = CarteMonstre("Dragon test", 9, ["Dragon"])
    event = CarteEvent("Heal test", "", "HEAL")
    mimic = CarteMonstre("Mimique test", 0, [], effet="MIMIC", is_X=True)

    choix = jeu.policy.decide(DecisionContext(
        kind=DecisionKind.ORDER_CARDS,
        actor=joueur,
        game=jeu,
        phase='fil_du_destin',
        options=(orc, dragon, event, mimic),
    ))

    assert choix == (event, dragon, mimic, orc)


def smoke_default_policy_fouet_du_fourbe_preserves_first_matching_choice():
    joueur = Joueur("O", Princesse(1), [])
    jeu = GameState([joueur], DonjonDeck(), [], default_dungeon_policy())
    premier = CarteMonstre("Squelette faible", 2, ["Squelette"])
    second = CarteMonstre("Dragon squelette", 9, ["Squelette", "Dragon"])

    choix = jeu.policy.decide(DecisionContext(
        kind=DecisionKind.CHOOSE_MONSTER,
        actor=joueur,
        game=jeu,
        phase='fouet_du_fourbe',
        options=(premier, second),
    ))

    assert choix is premier


def smoke_default_policy_cloche_du_deja_vu_split_choices():
    joueur = Joueur("P", Princesse(1), [])
    jeu = GameState([joueur], DonjonDeck(), [], default_dungeon_policy())
    premier_fodder = CarteMonstre("Gobelin premier", 1, ["Gobelin"])
    second_fodder = CarteMonstre("Gobelin second", 1, ["Gobelin"])
    faible = CarteMonstre("Squelette faible", 2, ["Squelette"])
    fort = CarteMonstre("Dragon fort", 9, ["Dragon"])

    fodder = jeu.policy.decide(DecisionContext(
        kind=DecisionKind.CHOOSE_MONSTER,
        actor=joueur,
        game=jeu,
        phase='cloche_du_deja_vu_urgence_defausse',
        options=(premier_fodder, second_fodder),
    ))
    pile = jeu.policy.decide(DecisionContext(
        kind=DecisionKind.CHOOSE_MONSTER,
        actor=joueur,
        game=jeu,
        phase='cloche_du_deja_vu_urgence_pile',
        options=(fort, faible),
    ))

    assert fodder is premier_fodder
    assert pile is faible


def smoke_cloche_du_deja_vu_routes_distinct_fodder_and_pile_phases():
    class RecordingPolicy(DefaultDungeonPolicy):
        def __init__(self):
            self.phases = []

        def decide_choose_monster(self, context):
            self.phases.append(context.phase)
            return super().decide_choose_monster(context)

    policy = RecordingPolicy()
    joueur = Joueur("Q", Princesse(1), [])
    attack = CarteMonstre("Dragon attaque", 9, ["Dragon"])
    attack.dommages = 9
    fodder = CarteMonstre("Gobelin fodder", 1, ["Gobelin"])
    pile_faible = CarteMonstre("Squelette faible", 2, ["Squelette"])
    pile_fort = CarteMonstre("Dragon fort", 9, ["Dragon"])
    deck = _deck_with_cards(attack, fodder, pile_faible, pile_fort)
    jeu = GameState([joueur], deck, [], policy)
    cloche = ClocheDuDejaVu()

    jeu.defausse.append(fodder)
    cloche.combat_effet(joueur, attack, jeu, [])
    assert policy.phases == ['cloche_du_deja_vu_urgence_defausse']
    assert deck.cartes[deck.ordre[deck.index]] is fodder

    policy = RecordingPolicy()
    joueur = Joueur("R", Princesse(1), [])
    joueur.pile_monstres_vaincus = [pile_fort, pile_faible]
    deck = _deck_with_cards(attack, fodder, pile_faible, pile_fort)
    jeu = GameState([joueur], deck, [], policy)
    cloche = ClocheDuDejaVu()

    cloche.combat_effet(joueur, attack, jeu, [])
    assert policy.phases == ['cloche_du_deja_vu_urgence_pile']
    assert deck.cartes[deck.ordre[deck.index]] is pile_faible


def smoke_custom_policy_controls_newly_routed_item_decisions():
    class CustomRoutedPolicy(DefaultDungeonPolicy):
        def decide_choose_monsters(self, context):
            if context.phase == 'couteaux_de_lancer':
                return (min(context.options, key=lambda m: m.puissance_initiale),)
            return super().decide_choose_monsters(context)

        def decide_choose_cards(self, context):
            if context.phase == 'tambour_de_kui':
                return tuple(c for c in context.options if getattr(c, 'event', False))
            return super().decide_choose_cards(context)

        def decide_choose_destination(self, context):
            if context.phase == 'oeil_d_horus':
                return 'bottom'
            if context.phase == 'oiseau_de_mauvais_augure':
                return 'keep'
            return super().decide_choose_destination(context)

        def decide_order_cards(self, context):
            if context.phase == 'fil_du_destin':
                return tuple(reversed(context.options))
            return super().decide_order_cards(context)

        def decide_choose_monster(self, context):
            if context.phase in {'fouet_du_fourbe', 'cloche_du_deja_vu_urgence_defausse'}:
                return context.options[-1]
            return super().decide_choose_monster(context)

    policy = CustomRoutedPolicy()
    joueur = Joueur("S", Princesse(1), [])
    faible = CarteMonstre("Rat faible", 2, ["Rat"])
    moyen = CarteMonstre("Golem moyen", 5, ["Golem"])
    fort = CarteMonstre("Dragon fort", 9, ["Dragon"])
    jeu = GameState([joueur], _deck_with_cards(faible, moyen, fort), [], policy)
    CouteauxDeLancer().combat_effet(joueur, CarteMonstre("Attaque", 3, ["Orc"]), jeu, [])
    assert faible in jeu.defausse
    assert moyen not in jeu.defausse
    assert fort not in jeu.defausse

    joueur = Joueur("T", Princesse(1), [])
    joueur.pv_total = 4
    event = CarteEvent("Event test", "", "HEAL")
    monstre = CarteMonstre("Dragon test", 9, ["Dragon"])
    jeu = GameState([joueur], _deck_with_cards(event, monstre), [], policy)
    pv_pre = joueur.pv_total
    TambourDeKui().combat_effet(joueur, CarteMonstre("Attaque", 3, ["Orc"]), jeu, [])
    assert event in jeu.defausse
    assert monstre not in jeu.defausse
    assert joueur.pv_total == pv_pre + 1

    joueur = Joueur("U", Princesse(1), [])
    faible = CarteMonstre("Squelette faible", 2, ["Squelette"])
    suivant = CarteMonstre("Orc suivant", 3, ["Orc"])
    jeu = GameState([joueur], _deck_with_cards(faible, suivant), [], policy)
    OeilDHorus().vaincu_effet(joueur, joueur, CarteMonstre("Vaincu", 1, ["Rat"]), jeu, [])
    assert jeu.donjon.cartes[jeu.donjon.ordre[jeu.donjon.index]] is suivant

    joueur = Joueur("V", Princesse(1), [])
    autre = Joueur("W", Princesse(1), [])
    event = CarteEvent("Event garde", "", "HEAL")
    jeu = GameState([joueur, autre], _deck_with_cards(event), [], policy)
    OiseauDeMauvaisAugure().fin_tour(joueur, jeu, [])
    assert event in joueur.cartes_connues
    assert jeu.donjon.cartes[jeu.donjon.ordre[jeu.donjon.index]] is event

    joueur = Joueur("X", Princesse(1), [])
    joueur.tour = 2
    cartes = [CarteMonstre(f"Carte {i}", i + 1, ["Orc"]) for i in range(4)]
    jeu = GameState([joueur], _deck_with_cards(*cartes), [], policy)
    FilDuDestin().debut_tour(joueur, jeu, [])
    assert [jeu.donjon.cartes[jeu.donjon.ordre[i]] for i in range(4)] == list(reversed(cartes))

    joueur = Joueur("Y", Princesse(1), [])
    victime = Joueur("Z", Princesse(1), [])
    premier = CarteMonstre("Squelette premier", 2, ["Squelette"])
    second = CarteMonstre("Squelette second", 6, ["Squelette"])
    victime.pile_monstres_vaincus = [premier, second]
    jeu = GameState([joueur, victime], DonjonDeck(), [], policy)
    FouetDuFourbe().combat_effet(joueur, CarteMonstre("Attaque squelette", 3, ["Squelette"]), jeu, [])
    assert second in jeu.defausse
    assert premier in victime.pile_monstres_vaincus

    joueur = Joueur("AA", Princesse(1), [])
    premier = CarteMonstre("Gobelin premier", 1, ["Gobelin"])
    second = CarteMonstre("Gobelin second", 1, ["Gobelin"])
    attaque = CarteMonstre("Attaque", 9, ["Dragon"])
    attaque.dommages = 9
    jeu = GameState([joueur], _deck_with_cards(attaque, premier, second), [], policy)
    jeu.defausse.extend([premier, second])
    ClocheDuDejaVu().combat_effet(joueur, attaque, jeu, [])
    assert jeu.donjon.cartes[jeu.donjon.ordre[jeu.donjon.index]] is second


def smoke_invalid_policy_rejected_for_newly_routed_item_decisions():
    invalid_monster = CarteMonstre("Intrus monstre", 1, ["Rat"])
    invalid_card = CarteEvent("Intrus event", "", "HEAL")

    class InvalidRoutedPolicy(DefaultDungeonPolicy):
        def decide_choose_monsters(self, context):
            if context.phase == 'couteaux_de_lancer':
                return (invalid_monster,)
            return super().decide_choose_monsters(context)

        def decide_choose_cards(self, context):
            if context.phase == 'tambour_de_kui':
                return (invalid_card,)
            return super().decide_choose_cards(context)

        def decide_choose_destination(self, context):
            if context.phase in {'oeil_d_horus', 'oiseau_de_mauvais_augure'}:
                return 'sideways'
            return super().decide_choose_destination(context)

        def decide_order_cards(self, context):
            if context.phase == 'fil_du_destin':
                return (context.options[0], context.options[0], context.options[1], context.options[2])
            return super().decide_order_cards(context)

        def decide_choose_monster(self, context):
            if context.phase in {
                'fouet_du_fourbe',
                'cloche_du_deja_vu_urgence_defausse',
                'cloche_du_deja_vu_urgence_pile',
            }:
                return invalid_monster
            return super().decide_choose_monster(context)

    policy = InvalidRoutedPolicy()

    def game_with(player, *cards):
        return GameState([player], _deck_with_cards(*cards), [], policy)

    joueur = Joueur("AB", Princesse(1), [])
    _assert_raises_value_error(lambda: CouteauxDeLancer().combat_effet(
        joueur,
        CarteMonstre("Attaque", 3, ["Orc"]),
        game_with(joueur, CarteMonstre("Rat option", 1, ["Rat"])),
        [],
    ))

    joueur = Joueur("AC", Princesse(1), [])
    _assert_raises_value_error(lambda: TambourDeKui().combat_effet(
        joueur,
        CarteMonstre("Attaque", 3, ["Orc"]),
        game_with(joueur, CarteMonstre("Rat option", 1, ["Rat"])),
        [],
    ))

    joueur = Joueur("AD", Princesse(1), [])
    _assert_raises_value_error(lambda: OeilDHorus().vaincu_effet(
        joueur,
        joueur,
        CarteMonstre("Vaincu", 1, ["Rat"]),
        game_with(joueur, CarteMonstre("Rat option", 1, ["Rat"])),
        [],
    ))

    joueur = Joueur("AE", Princesse(1), [])
    autre = Joueur("AF", Princesse(1), [])
    _assert_raises_value_error(lambda: OiseauDeMauvaisAugure().fin_tour(
        joueur,
        GameState([joueur, autre], _deck_with_cards(CarteMonstre("Rat option", 1, ["Rat"])), [], policy),
        [],
    ))

    joueur = Joueur("AG", Princesse(1), [])
    joueur.tour = 2
    cards = [CarteMonstre(f"Carte invalid {i}", i + 1, ["Orc"]) for i in range(4)]
    _assert_raises_value_error(lambda: FilDuDestin().debut_tour(
        joueur,
        game_with(joueur, *cards),
        [],
    ))

    joueur = Joueur("AH", Princesse(1), [])
    victime = Joueur("AI", Princesse(1), [])
    victime.pile_monstres_vaincus = [CarteMonstre("Squelette option", 2, ["Squelette"])]
    _assert_raises_value_error(lambda: FouetDuFourbe().combat_effet(
        joueur,
        CarteMonstre("Attaque squelette", 3, ["Squelette"]),
        GameState([joueur, victime], DonjonDeck(), [], policy),
        [],
    ))

    joueur = Joueur("AJ", Princesse(1), [])
    attaque = CarteMonstre("Attaque", 9, ["Dragon"])
    attaque.dommages = 9
    fodder = CarteMonstre("Gobelin fodder", 1, ["Gobelin"])
    jeu = game_with(joueur, attaque, fodder)
    jeu.defausse.append(fodder)
    _assert_raises_value_error(lambda: ClocheDuDejaVu().combat_effet(joueur, attaque, jeu, []))

    joueur = Joueur("AK", Princesse(1), [])
    attaque = CarteMonstre("Attaque", 9, ["Dragon"])
    attaque.dommages = 9
    joueur.pile_monstres_vaincus = [CarteMonstre("Squelette option", 2, ["Squelette"])]
    _assert_raises_value_error(lambda: ClocheDuDejaVu().combat_effet(
        joueur,
        attaque,
        game_with(joueur, attaque),
        [],
    ))


if __name__ == "__main__":
    smoke_traquenard_detects_chevalier_dragon_candidate()
    smoke_traquenard_detects_docteur_de_peste_candidate()
    smoke_traquenard_detects_avatar_late_candidate()
    smoke_defausse_monstre_de_pile_policy_choice()
    smoke_barbecue_du_ponceur_policy_target()
    smoke_fruit_du_destin_policy_category()
    smoke_fruit_du_destin_invalid_category_rejected()
    smoke_default_policy_couteaux_de_lancer_targets_strongest()
    smoke_default_policy_tambour_de_kui_discards_dangerous_visible_monsters()
    smoke_default_policy_divination_destinations_preserve_keep_bottom_rules()
    smoke_default_policy_fil_du_destin_orders_by_old_danger_heuristic()
    smoke_default_policy_fouet_du_fourbe_preserves_first_matching_choice()
    smoke_default_policy_cloche_du_deja_vu_split_choices()
    smoke_cloche_du_deja_vu_routes_distinct_fodder_and_pile_phases()
    smoke_custom_policy_controls_newly_routed_item_decisions()
    smoke_invalid_policy_rejected_for_newly_routed_item_decisions()
    smoke_ordonnanceur_policy_equivalence()
    smoke_legacy_wrappers()
    smoke_draft_policy_equivalence()
    smoke_hero_policy_can_decline()
    smoke_unavailable_hero_ability_does_not_call_policy()
    smoke_object_policy_can_decline_combat_use()
    smoke_object_policy_can_choose_target()
    smoke_policy_controls_object_order()
    smoke_invalid_policy_rejected()
    smoke_default_policy_normalizes_legacy_worthit()
    smoke_donjon_worker_batch_runs()
    smoke_traquenard_legality_independent_from_object_policy()
    smoke_fortune_wheel_policy_can_decline()
    smoke_event_beast_policy_choice_and_decline()
    smoke_guardian_angel_attrape_reves_confidence()
    print("policy smoke ok")
