# -*- coding: utf-8 -*-
"""Cout en temps de l'IA v2 vs v1 (parties identiques en composition, un seul process)."""
import random
import time
import numpy as np

from objets import objets_disponibles
from joueurs import Joueur
from simu import ordonnanceur
from monstres import DonjonDeck
from heros import persos_disponibles

NB = 4000

def chrono(politique):
    random.seed(7)
    np.random.seed(7)
    debut = time.perf_counter()
    for _ in range(NB):
        objets_simu = list(objets_disponibles)
        for o in objets_simu:
            o.repare()
        nb_joueurs = random.choice([3, 4])
        persos = random.sample(persos_disponibles, nb_joueurs)
        joueurs = []
        for i in range(nb_joueurs):
            objs = random.sample(objets_simu, 6)
            for o in objs:
                objets_simu.remove(o)
            j = Joueur(f"J{i}", persos[i], objs)
            j.politique_fuite = politique
            joueurs.append(j)
        ordonnanceur(joueurs, DonjonDeck(), 6, objets_simu, False)
    return time.perf_counter() - debut

if __name__ == "__main__":
    t_seuils = chrono('seuils')
    t_ev = chrono('ev')
    print(f"seuils : {t_seuils:.2f}s ({t_seuils / NB * 1000:.2f} ms/partie)")
    print(f"ev     : {t_ev:.2f}s ({t_ev / NB * 1000:.2f} ms/partie)")
    print(f"surcout ev : {(t_ev / t_seuils - 1) * 100:+.1f}%")
