import random

import numpy as np

from ai_policy import DefaultDungeonPolicy, default_draft_policy, default_dungeon_policy
from draft import _charger_priors, _draft_rapide
from heros import Princesse, persos_disponibles
from joueurs import Joueur
from monstres import CarteMonstre, DonjonDeck
from objets import ArmureEnCuir, CouteauSuisse, HacheDeGlace, Objet, objets_disponibles
from party import draft_soiree
from simu import GameState, ordonnanceur


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


if __name__ == "__main__":
    smoke_ordonnanceur_policy_equivalence()
    smoke_legacy_wrappers()
    smoke_draft_policy_equivalence()
    smoke_hero_policy_can_decline()
    smoke_object_policy_can_decline_combat_use()
    smoke_object_policy_can_choose_target()
    smoke_policy_controls_object_order()
    smoke_invalid_policy_rejected()
    smoke_default_policy_normalizes_legacy_worthit()
    smoke_donjon_worker_batch_runs()
    print("policy smoke ok")
