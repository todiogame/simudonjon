# -*- coding: utf-8 -*-
"""bench_fuite.py : compare la politique de fuite par esperance ('ev') a l'ancienne
politique a seuils ('seuils'), a tables mixtes : dans chaque partie, la moitie des
sieges joue 'ev' et l'autre 'seuils' (sieges tires au hasard). Persos et builds
aleatoires, Medailles aleatoires pour exercer la prudence du mode soiree.

Usage : python bench_fuite.py [nb_parties]   (defaut 200000)
"""
import random
import os
import sys
import multiprocessing
import numpy as np
from tqdm import tqdm

from objets import objets_disponibles
from joueurs import Joueur
from simu import ordonnanceur
from monstres import DonjonDeck
from heros import persos_disponibles

NB_PARTIES_DEFAUT = 200000
POLITIQUES = ('ev', 'seuils')


def _stats_vides():
    return {p: {'played': 0, 'win': 0, 'death': 0, 'fled': 0, 'cleared': 0,
                'score_pose': 0, 'medailles_perdues': 0} for p in POLITIQUES}


def _batch(args):
    nb, seed = args[0], args[1]
    if len(args) > 2 and args[2]:
        # constantes de joueurs.py a surcharger (sweep) ; applique dans le worker
        # car chaque process reimporte les modules
        import joueurs
        for cle, v in args[2].items():
            setattr(joueurs, cle, v)
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)
    stats = _stats_vides()
    for _ in range(nb):
        objets_simu = list(objets_disponibles)
        for o in objets_simu:
            o.repare()
        nb_joueurs = random.choice([3, 4])
        noms = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]
        persos = random.sample(persos_disponibles, nb_joueurs)
        # moitie des sieges en 'ev' (a 3 joueurs : 1 ou 2, au hasard)
        nb_ev = nb_joueurs // 2 + (nb_joueurs % 2 and random.random() < 0.5)
        sieges_ev = set(random.sample(range(nb_joueurs), nb_ev))
        joueurs = []
        medailles_avant = []
        for i, nom in enumerate(noms):
            objs = random.sample(objets_simu, 6)
            for o in objs:
                objets_simu.remove(o)
            j = Joueur(nom, persos[i], objs,
                       medailles=random.choice([0, 0, 0, 0, 0, 0, 1, 1, 2]))
            j.politique_fuite = 'ev' if i in sieges_ev else 'seuils'
            joueurs.append(j)
            medailles_avant.append(j.medailles)
        vainqueur, _ = ordonnanceur(joueurs, DonjonDeck(), 6, objets_simu, False)
        for i, j in enumerate(joueurs):
            s = stats[j.politique_fuite]
            s['played'] += 1
            s['win'] += j is vainqueur
            s['death'] += not j.vivant
            s['fled'] += j.fuite_reussie
            s['cleared'] += j.dans_le_dj
            if getattr(j, 'compte_au_score', False):
                s['score_pose'] += j.score_final
            s['medailles_perdues'] += max(0, medailles_avant[i] - j.medailles)
    return stats


def _fusionner(dest, src):
    for p in POLITIQUES:
        for cle, v in src[p].items():
            dest[p][cle] += v


def main(nb_parties, overrides=None, silencieux=False):
    nb_process = max(1, (os.cpu_count() or 2) - 1)
    stats = _stats_vides()
    nb_batches = nb_process * 8
    base, reste = divmod(nb_parties, nb_batches)
    travaux = [(base + (1 if i < reste else 0), random.randrange(2**31), overrides)
               for i in range(nb_batches)]
    travaux = [t for t in travaux if t[0] > 0]
    if not silencieux:
        print(f"Benchmark fuite EV vs seuils : {nb_parties} parties mixtes, {nb_process} process...")
    if nb_process > 1:
        with multiprocessing.Pool(nb_process) as pool:
            iterateur = pool.imap_unordered(_batch, travaux)
            for r in (iterateur if silencieux else tqdm(iterateur, total=len(travaux))):
                _fusionner(stats, r)
    else:
        for t in (travaux if silencieux else tqdm(travaux)):
            _fusionner(stats, _batch(t))
    if silencieux:
        return stats

    print(f"\n{'Politique':<10} {'Joues':>9} {'Win%':>12} {'Death%':>8} {'Fled%':>7} "
          f"{'Clear%':>7} {'ScorePose':>10} {'MedPerdues%':>12}")
    for p in POLITIQUES:
        s = stats[p]
        n = max(1, s['played'])
        wr = s['win'] / n
        se = (wr * (1 - wr) / n) ** 0.5
        print(f"{p:<10} {s['played']:>9} {wr*100:>7.2f}±{1.96*se*100:.2f} "
              f"{s['death']/n*100:>8.2f} {s['fled']/n*100:>7.2f} {s['cleared']/n*100:>7.2f} "
              f"{s['score_pose']/n:>10.3f} {s['medailles_perdues']/n*100:>12.2f}")
    n_ev, n_se = stats['ev']['played'], stats['seuils']['played']
    if n_ev and n_se:
        w_ev, w_se = stats['ev']['win'] / n_ev, stats['seuils']['win'] / n_se
        se_diff = (w_ev * (1 - w_ev) / n_ev + w_se * (1 - w_se) / n_se) ** 0.5
        print(f"\nEcart de winrate ev - seuils : {(w_ev - w_se)*100:+.2f} points "
              f"(±{1.96*se_diff*100:.2f} a 95%)")


if __name__ == "__main__":
    script_dir = os.path.dirname(__file__)
    if script_dir:
        os.chdir(script_dir)
    nb = int(sys.argv[1]) if len(sys.argv) > 1 else NB_PARTIES_DEFAUT
    main(nb)
