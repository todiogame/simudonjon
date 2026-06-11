# Script de profiling temporaire — a supprimer apres analyse
import cProfile, pstats, io, time, random, re
random.seed(7)
import numpy as np
np.random.seed(7)

from objets import objets_disponibles
from joueurs import Joueur
from monstres import DonjonDeck
from heros import persos_disponibles
from simu import ordonnanceur

def run_games(n, collect_rows=False):
    rows = []
    for _ in range(n):
        objets_simu = list(objets_disponibles)
        for o in objets_simu: o.repare()
        nb = random.choice([3, 4])
        persos = random.sample(persos_disponibles, nb)
        joueurs = []
        for i, nom in enumerate(["A","B","C","D"][:nb]):
            objs = random.sample(objets_simu, 6)
            for o in objs: objets_simu.remove(o)
            joueurs.append(Joueur(nom, persos[i], objs, int(random.random() < 0.3)))
        vainqueur, js = ordonnanceur(joueurs, DonjonDeck(), 5, objets_simu, False)
        if collect_rows:
            for j in js:
                for o in j.objets_initiaux:
                    rows.append({'Objet': o.nom, 'Personnage': j.personnage_nom,
                                 'Priorite': o.priorite,
                                 'Build': ', '.join(x.nom for x in j.objets_initiaux),
                                 'Victoire': 1 if j is vainqueur else 0})
    return rows

# --- vitesse brute
t0 = time.perf_counter(); run_games(300); t1 = time.perf_counter()
print(f"Vitesse brute moteur: {300/(t1-t0):.0f} parties/s\n")

# --- profil moteur
pr = cProfile.Profile()
pr.enable()
run_games(1500)
pr.disable()
s = io.StringIO()
pstats.Stats(pr, stream=s).sort_stats('tottime').print_stats(24)
out = s.getvalue()
out = re.sub(r'[A-Za-z]:.*?simudonjon.', '', out)
print(out)
