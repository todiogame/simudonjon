# -*- coding: utf-8 -*-
"""bench_party.py : compare les politiques de fuite au niveau SOIREE (le vrai
metrique). Dans chaque soiree, la moitie des sieges joue 'ev' et l'autre
'seuils' (la politique d'un joueur est fixe pour toute la soiree).

Usage : python bench_party.py [nb_soirees] [VALEUR_MEDAILLE_PTS...]
        python bench_party.py 20000 3 6 9   -> teste 3 valeurs de Medaille
"""
import random
import os
import sys
import multiprocessing
import numpy as np
from tqdm import tqdm

POLITIQUES = ('ev', 'seuils')
NB_SOIREES_DEFAUT = 20000


def _batch(args):
    nb, seed, overrides = args
    import joueurs
    import party
    from draft import _charger_priors
    for cle, v in (overrides or {}).items():
        setattr(joueurs, cle, v)
    _charger_priors()

    # politique par nom de joueur, retiree au debut de chaque soiree
    politiques_par_nom = {}
    orig_init = joueurs.Joueur.__init__

    def init_patch(self, nom, perso_instance, objets=None, medailles=0):
        orig_init(self, nom, perso_instance, objets, medailles)
        self.politique_fuite = politiques_par_nom.get(nom, 'ev')

    joueurs.Joueur.__init__ = init_patch

    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)
    stats = {p: {'played': 0, 'night_win': 0} for p in POLITIQUES}
    try:
        for _ in range(nb):
            noms = party.NOMS_JOUEURS
            nb_ev = len(noms) // 2  # 2 EV sur 3-4 sieges potentiels, tire au sort
            sieges_ev = set(random.sample(range(len(noms)), nb_ev))
            politiques_par_nom.clear()
            politiques_par_nom.update(
                {nom: ('ev' if i in sieges_ev else 'seuils') for i, nom in enumerate(noms)})
            vainqueur_idx, _, infos = party.jouer_soiree(False)
            for i in range(infos['nb_joueurs']):
                p = politiques_par_nom[noms[i]]
                stats[p]['played'] += 1
                stats[p]['night_win'] += (i == vainqueur_idx)
    finally:
        joueurs.Joueur.__init__ = orig_init
    return stats


def main(nb_soirees, overrides=None, silencieux=False):
    nb_process = max(1, (os.cpu_count() or 2) - 1)
    stats = {p: {'played': 0, 'night_win': 0} for p in POLITIQUES}
    nb_batches = nb_process * 4
    base, reste = divmod(nb_soirees, nb_batches)
    travaux = [(base + (1 if i < reste else 0), random.randrange(2**31), overrides)
               for i in range(nb_batches)]
    travaux = [t for t in travaux if t[0] > 0]
    with multiprocessing.Pool(nb_process) as pool:
        iterateur = pool.imap_unordered(_batch, travaux)
        for r in (iterateur if silencieux else tqdm(iterateur, total=len(travaux))):
            for p in POLITIQUES:
                for cle, v in r[p].items():
                    stats[p][cle] += v
    return stats


if __name__ == "__main__":
    script_dir = os.path.dirname(__file__)
    if script_dir:
        os.chdir(script_dir)
    from draft import calculer_priors
    calculer_priors()  # s'assure que le cache existe avant le Pool
    nb = int(sys.argv[1]) if len(sys.argv) > 1 else NB_SOIREES_DEFAUT
    valeurs_med = [float(v) for v in sys.argv[2:]] or [None]
    for vm in valeurs_med:
        ov = {'VALEUR_MEDAILLE_PTS': vm} if vm is not None else None
        s = main(nb, overrides=ov)
        n_ev, n_se = max(1, s['ev']['played']), max(1, s['seuils']['played'])
        w_ev = s['ev']['night_win'] / n_ev
        w_se = s['seuils']['night_win'] / n_se
        se_diff = (w_ev * (1 - w_ev) / n_ev + w_se * (1 - w_se) / n_se) ** 0.5
        etiquette = f"medaille={vm}" if vm is not None else "base"
        print(f"{etiquette:<14} NightWin ev {w_ev*100:.2f}% / seuils {w_se*100:.2f}%  "
              f"ecart {(w_ev - w_se)*100:+.2f} (±{1.96*se_diff*100:.2f})", flush=True)
