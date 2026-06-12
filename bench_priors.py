# -*- coding: utf-8 -*-
"""bench_priors.py : compare deux jeux de priors de pick a tables mixtes.
Dans chaque partie, la moitie des sieges drafte avec les priors A (nouveaux,
draft_priors.json) et l'autre avec les priors B (anciens, draft_priors.v1-random.json).
Le draft est aux priors seuls (comme party.py), puis une manche est jouee.

Usage : python bench_priors.py [nb_parties]         (defaut 100000)
        python bench_priors.py [nb_parties] total    IA v2 complete vs IA v1 complete
                                                     (les sieges A jouent aussi la fuite
                                                     'ev', les sieges B la fuite 'seuils')
"""
import json
import os
import random
import sys
import multiprocessing
import numpy as np
from tqdm import tqdm

FICHIER_A = "draft_priors.json"
FICHIER_B = "draft_priors.v1-random.json"
NB_PARTIES_DEFAUT = 100000


def _charger(fichier):
    with open(fichier, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {
        'objets': {nom: tuple(vt) for nom, vt in data['objets'].items()},
        'perso_objet': {tuple(cle.split('||')): tuple(vt) for cle, vt in data['perso_objet'].items()},
    }


def _batch(args):
    nb, seed, combine_politique = args
    from objets import objets_disponibles  # noqa: F401 (import worker)
    from joueurs import Joueur
    from simu import ordonnanceur
    from monstres import DonjonDeck
    from heros import persos_disponibles
    from draft import _draft_rapide

    priors_a = _charger(FICHIER_A)
    priors_b = _charger(FICHIER_B)
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)
    stats = {'nouveaux': [0, 0], 'anciens': [0, 0]}  # [wins, played]
    for _ in range(nb):
        nb_joueurs = random.choice([3, 4])
        noms = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]
        persos = random.sample(persos_disponibles, nb_joueurs)
        nb_a = nb_joueurs // 2 + (nb_joueurs % 2 and random.random() < 0.5)
        sieges_a = set(random.sample(range(nb_joueurs), nb_a))
        priors_par_joueur = [priors_a if i in sieges_a else priors_b for i in range(nb_joueurs)]
        builds, restants = _draft_rapide(persos, priors_par_joueur)
        joueurs = [Joueur(noms[i], persos[i], builds[i]) for i in range(nb_joueurs)]
        if combine_politique:
            for i, j in enumerate(joueurs):
                j.politique_fuite = 'ev' if i in sieges_a else 'seuils'
        vainqueur, _ = ordonnanceur(joueurs, DonjonDeck(), 6, restants, False)
        for i, j in enumerate(joueurs):
            cle = 'nouveaux' if i in sieges_a else 'anciens'
            stats[cle][1] += 1
            stats[cle][0] += j is vainqueur
    return stats


def main(nb_parties, combine_politique=False):
    nb_process = max(1, (os.cpu_count() or 2) - 1)
    stats = {'nouveaux': [0, 0], 'anciens': [0, 0]}
    nb_batches = nb_process * 8
    base, reste = divmod(nb_parties, nb_batches)
    travaux = [(base + (1 if i < reste else 0), random.randrange(2**31), combine_politique)
               for i in range(nb_batches)]
    travaux = [t for t in travaux if t[0] > 0]
    objet = "IA v2 complete vs IA v1 complete" if combine_politique else "priors nouveaux vs anciens"
    print(f"Benchmark {objet} : {nb_parties} parties mixtes, {nb_process} process...")
    with multiprocessing.Pool(nb_process) as pool:
        for r in tqdm(pool.imap_unordered(_batch, travaux), total=len(travaux)):
            for cle in stats:
                stats[cle][0] += r[cle][0]
                stats[cle][1] += r[cle][1]
    resume = {}
    for cle, (w, n) in stats.items():
        resume[cle] = (w / max(1, n), n)
        print(f"{cle:<10} winrate {w / max(1, n) * 100:.2f}%  ({n} joueurs-parties)")
    (wa, na), (wb, nb_) = resume['nouveaux'], resume['anciens']
    se = (wa * (1 - wa) / na + wb * (1 - wb) / nb_) ** 0.5
    print(f"Ecart nouveaux - anciens : {(wa - wb) * 100:+.2f} points (±{1.96 * se * 100:.2f} a 95%)")


if __name__ == "__main__":
    script_dir = os.path.dirname(__file__)
    if script_dir:
        os.chdir(script_dir)
    main(int(sys.argv[1]) if len(sys.argv) > 1 else NB_PARTIES_DEFAUT,
         combine_politique=(len(sys.argv) > 2 and sys.argv[2] == 'total'))
