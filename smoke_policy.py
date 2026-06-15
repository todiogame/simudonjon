import random

import numpy as np

from ai_policy import DefaultDungeonPolicy, default_draft_policy, default_dungeon_policy
from ai_decisions import DecisionContext, DecisionKind, require_option
from draft import _charger_priors, _draft_rapide
from heros import BeteDeLEvenement, Princesse, SANS_HOOK_PERSO, persos_disponibles
from joueurs import Joueur
from monstres import CarteEvent, CarteMonstre, DonjonDeck
from objets import ArmureEnCuir, AttrapeReves, CouteauSuisse, HacheDeGlace, Objet, SANS_HOOK_OBJET, objets_disponibles
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


if __name__ == "__main__":
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
