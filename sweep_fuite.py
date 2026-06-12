# -*- coding: utf-8 -*-
"""Balayage rapide des constantes de la politique de fuite EV (une a la fois,
autour de la config courante). Chaque config est evaluee en tables mixtes
contre l'ancienne politique a seuils."""
import random
import bench_fuite

NB = 30000

CONFIGS = [
    ("base", {}),
    ("survie 0.5", {'VALEUR_SURVIE_PTS': 0.5}),
    ("survie 2.0", {'VALEUR_SURVIE_PTS': 2.0}),
    ("efficacite 0.4", {'EFFICACITE_OPTION': 0.4}),
    ("efficacite 0.8", {'EFFICACITE_OPTION': 0.8}),
    ("taux gain 0.5", {'TAUX_GAIN_PAR_PIOCHE': 0.5}),
    ("taux gain 0.9", {'TAUX_GAIN_PAR_PIOCHE': 0.9}),
    ("medaille 3", {'VALEUR_MEDAILLE_PTS': 3.0}),
    ("medaille 9", {'VALEUR_MEDAILLE_PTS': 9.0}),
    ("ponceur 0", {'BONUS_PONCEUR_PTS': 0.0}),
    ("ponceur 3", {'BONUS_PONCEUR_PTS': 3.0}),
]

if __name__ == "__main__":
    random.seed(20260612)
    print(f"{'Config':<18} {'WinEV%':>8} {'WinSeuils%':>11} {'Ecart':>7} {'DeathEV%':>9}")
    for nom, ov in CONFIGS:
        stats = bench_fuite.main(NB, overrides=ov, silencieux=True)
        ev, se = stats['ev'], stats['seuils']
        w_ev = ev['win'] / max(1, ev['played']) * 100
        w_se = se['win'] / max(1, se['played']) * 100
        d_ev = ev['death'] / max(1, ev['played']) * 100
        print(f"{nom:<18} {w_ev:>8.2f} {w_se:>11.2f} {w_ev - w_se:>+7.2f} {d_ev:>9.2f}",
              flush=True)
