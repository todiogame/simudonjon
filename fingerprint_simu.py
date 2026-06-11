# Empreinte d'equivalence: a seed fixe, le resultat de 3000 parties doit etre
# identique avant/apres optimisation (les optimisations ne consomment pas de RNG).
import random, hashlib
random.seed(123)
import numpy as np
np.random.seed(123)

from objets import objets_disponibles
from joueurs import Joueur
from monstres import DonjonDeck
from heros import persos_disponibles
from simu import ordonnanceur

h = hashlib.sha256()
for sim in range(3000):
    objets_simu = list(objets_disponibles)
    for o in objets_simu:
        o.repare()
    nb = random.choice([3, 4])
    persos = random.sample(persos_disponibles, nb)
    joueurs = []
    for i, nom in enumerate(["A", "B", "C", "D"][:nb]):
        objs = random.sample(objets_simu, 6)
        for o in objs:
            objets_simu.remove(o)
        joueurs.append(Joueur(nom, persos[i], objs, int(random.random() < 0.3)))
    vainqueur, js = ordonnanceur(joueurs, DonjonDeck(), 5, objets_simu, False)
    etat = repr([(j.nom, j.personnage_nom, j.pv_total, j.score_final, j.vivant,
                  j.fuite_reussie, j.dans_le_dj,
                  [m.titre for m in j.pile_monstres_vaincus]) for j in js])
    etat += getattr(vainqueur, 'nom', 'None')
    h.update(etat.encode())

print("FINGERPRINT:", h.hexdigest())
