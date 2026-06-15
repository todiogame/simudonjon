import random

import numpy as np

from ai_policy import default_draft_policy, default_dungeon_policy
from draft import _charger_priors, _draft_rapide
from heros import persos_disponibles
from joueurs import Joueur
from monstres import DonjonDeck
from objets import objets_disponibles
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
    vainqueur_a, joueurs_a = ordonnanceur(joueurs_a, DonjonDeck(), 5, objets_a, False)

    joueurs_b, objets_b = _build_players(77)
    vainqueur_b, joueurs_b = ordonnanceur(
        joueurs_b, DonjonDeck(), 5, objets_b, False, policy=default_dungeon_policy()
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


if __name__ == "__main__":
    smoke_ordonnanceur_policy_equivalence()
    smoke_legacy_wrappers()
    smoke_draft_policy_equivalence()
    print("policy smoke ok")
