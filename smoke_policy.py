import random

import numpy as np

from ai_policy import DefaultDungeonPolicy, default_draft_policy, default_dungeon_policy, random_dungeon_policy
from ai_decisions import CombatObjectChoice, DecisionContext, DecisionKind, require_option
from draft import _charger_priors, _draft_rapide
from heros import BeteDeLEvenement, Princesse, SANS_HOOK_PERSO, persos_disponibles
from joueurs import Joueur
from monstres import CarteEvent, CarteMonstre, DonjonDeck
from objets import ArmureEnCuir, AttrapeReves, ClocheDuDejaVu, CouteauSuisse, HacheDeGlace, Objet, SANS_HOOK_OBJET, objets_disponibles
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
        def decide_should_flee(self, context):
            return False

        def decide_choose_combat_object(self, context):
            return CombatObjectChoice.RESOLVE_NOW

    hache = HacheDeGlace()
    joueur = Joueur("O", Princesse(1), [hache])
    joueur.pv_total = 5
    carte = CarteMonstre("Dragon test", 9, ["Dragon"])
    carte.dommages = 10
    deck = _single_card_deck(carte)
    jeu = GameState([joueur], deck, [], DeclineObjectsPolicy())

    ordonnanceur([joueur], deck, [], False, policy=DeclineObjectsPolicy())

    assert not carte.executed
    assert hache.intact
    assert joueur.pile_monstres_vaincus == []


def smoke_combat_object_policy_can_chain_multiple_objects():
    trace = []

    class TraceObject(Objet):
        def __init__(self, nom, delta):
            super().__init__(nom, actif=True)
            self.delta = delta

        def combat_effet(self, joueur, carte, Jeu, log_details):
            trace.append(self.nom)
            self.compteur += 1
            carte.dommages = max(0, carte.dommages - self.delta)

    class ScriptedCombatPolicy(DefaultDungeonPolicy):
        def decide_should_flee(self, context):
            return False

        def decide_choose_combat_object(self, context):
            if context.meta('combat_step', 0) == 0:
                return next(objet for objet in context.options if objet.nom == "Second")
            if context.meta('combat_step', 0) == 1:
                return next(objet for objet in context.options if objet.nom == "Premier")
            return CombatObjectChoice.RESOLVE_NOW

    premier = TraceObject("Premier", 2)
    second = TraceObject("Second", 3)
    joueur = Joueur("C", Princesse(1), [premier, second])
    joueur.pv_total = 10
    carte = CarteMonstre("Dragon test", 9, ["Dragon"])
    carte.dommages = 6
    deck = _single_card_deck(carte)

    ordonnanceur([joueur], deck, [], False, policy=ScriptedCombatPolicy())

    assert joueur.pile_monstres_vaincus
    assert carte.executed is False
    assert carte.dommages == 4
    assert joueur.pv_total == 6
    assert premier.compteur == 1
    assert second.compteur == 1
    assert trace == ["Second", "Premier"]


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
    class InvalidCombatChoicePolicy(DefaultDungeonPolicy):
        def decide_should_flee(self, context):
            return False

        def decide_choose_combat_object(self, context):
            return None

    hache = HacheDeGlace()
    joueur = Joueur("I", Princesse(1), [hache])
    carte = CarteMonstre("Dragon test", 9, ["Dragon"])
    carte.dommages = 10
    deck = _single_card_deck(carte)

    try:
        ordonnanceur([joueur], deck, [], False, policy=InvalidCombatChoicePolicy())
    except ValueError:
        pass
    else:
        raise AssertionError("invalid combat choice policy return was not rejected")

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

    for seed in (12345, 12346, 12347, 12348):
        donjon._simuler_batch((128, seed))


def smoke_random_policy_runs_full_games():
    for seed in range(16):
        joueurs, objets_simu = _build_players(1000 + seed)
        ordonnanceur(joueurs, DonjonDeck(), objets_simu, False, policy=random_dungeon_policy())


def smoke_policy_map_routes_by_actor():
    class ReverseInventoryPolicy(DefaultDungeonPolicy):
        def decide_order_objects(self, context):
            return tuple(reversed(context.options))

    class KeepInventoryPolicy(DefaultDungeonPolicy):
        def decide_order_objects(self, context):
            return tuple(context.options)

    joueurs = [
        Joueur("A", Princesse(1), [HacheDeGlace(), ArmureEnCuir()]),
        Joueur("B", Princesse(1), [HacheDeGlace(), ArmureEnCuir()]),
    ]
    jeu = GameState(
        joueurs,
        DonjonDeck(),
        [],
        policy={0: ReverseInventoryPolicy(), 1: KeepInventoryPolicy()},
    )

    assert joueurs[0].policy is jeu.policy
    assert joueurs[1].policy is jeu.policy
    joueurs[0].ordonner_objets_pour_ia()
    joueurs[1].ordonner_objets_pour_ia()
    assert [objet.nom for objet in joueurs[0].objets] == ["Armure en cuir", "Hache de Glace"]
    assert [objet.nom for objet in joueurs[1].objets] == ["Hache de Glace", "Armure en cuir"]


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
