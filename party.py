# -*- coding: utf-8 -*-
"""party.py : simulation de soirées complètes (la façon dont on joue vraiment).

Une soirée = 2 à 5 manches (tirage uniforme), puis des manches de départage tant
qu'aucun joueur n'a strictement plus de Médailles que les autres.
- Avant CHAQUE manche : draft complet, picks aux priors de draft.py (pas de
  Monte-Carlo), ajustés à l'état des Médailles.
- Vainqueur d'une manche : +1 Médaille (Coupe des champions intacte : +2).
- Survivant (fuite incluse) : son héros passe (ou reste) niveau 2.
- Mort : perd une Médaille (géré par le moteur, Totem d'immunité protège),
  son héros retourne dans le pool de la soirée et il en repioche un autre
  au niveau 1 (héros uniques entre joueurs à tout instant).
Le joueur avec le plus de Médailles remporte la soirée. Métrique principale :
winrate de soirée par objet et par héros.

Usage :
  python party.py      Simulation de masse (multiprocess, reprise via party_stats.json)
  python party.py x    Joue x soirées avec les logs complets
"""
import itertools
import random
import os
import json
import sys
import multiprocessing
from tqdm import tqdm
import numpy as np

from objets import objets_disponibles
from joueurs import Joueur
from simu import ordonnanceur
from monstres import DonjonDeck
from heros import _classes_persos
from draft import calculer_priors, _charger_priors, score_pick

# ==============================================
# Configuration
# ==============================================
NB_SOIREES = 2000000               # nombre total de soirées à simuler
SEUIL_PV_ESSAI_FUITE = 6
MANCHES_MIN, MANCHES_MAX = 2, 5    # nombre de manches prévues (uniforme)
MAX_MANCHES_PAR_SOIREE = 30        # garde-fou si le départage s'éternise
TAILLE_MAIN_DRAFT = 7
NB_OBJETS_PAR_JOUEUR = 6
STATS_FILENAME = "party_stats.json"  # nom fixe : la reprise fonctionne

# Ajustements de pick liés à l'état de la soirée. Les priors de draft.py sont
# calculés sur des manches isolées à 0 Médaille : on corrige les objets dont la
# valeur dépend des Médailles en jeu (constantes en points de winrate, à régler).
MALUS_PICK_SANS_MEDAILLE = 0.03   # objets "si vous n'avez pas de Médaille" quand on en a une
BONUS_PICK_PROTEGE = 0.02         # Totem d'immunité quand on a une Médaille à protéger
BONUS_PICK_PARFUM = 0.015         # Parfum de Scandale, par Médaille adverse en jeu
BONUS_PICK_COUPE = 0.02           # Coupe des champions (la 2e Médaille n'existe pas en manche isolée)
# ==============================================

NOMS_JOUEURS = ["Sagarex", "Francis", "Mastho", "Mr.Adam"]


# --- Stats helpers ---
def _entree_stats(nom, stats_dict):
    if nom not in stats_dict:
        stats_dict[nom] = {'seen': 0, 'pick': 0, 'night_win': 0,
                           'played': 0, 'win': 0, 'death': 0, 'fled': 0, 'cleared': 0}
    return stats_dict[nom]


def _fusionner_stats(dest, src):
    for nom, valeurs in src.items():
        d = dest.setdefault(nom, {})
        for cle, v in valeurs.items():
            if cle == 'etats':
                e = d.setdefault('etats', {})
                for etat, (nw, n, sd) in v.items():
                    cur = e.setdefault(etat, [0, 0, 0])
                    cur[0] += nw; cur[1] += n; cur[2] += sd
            else:
                d[cle] = d.get(cle, 0) + v


def _fusionner_baseline(dest, src):
    for etat, (nw, n, sd) in src.items():
        cur = dest.setdefault(etat, [0, 0, 0])
        cur[0] += nw; cur[1] += n; cur[2] += sd


# --- État d'un joueur avant une manche (pour corriger le biais de sélection) ---
# Le winrate de soirée brut confond "l'objet aide à gagner" et "l'objet est pické
# quand on est déjà en train de gagner/perdre" (ex: les objets novice, pickés à
# 0 Médaille). On stratifie donc chaque observation par l'état au moment du pick,
# et on compare l'issue à l'attendu des joueurs dans le même état.
def _cle_etat(nb_joueurs, medailles, i, niveau, manches_prevues, manche):
    mes = min(medailles[i], 3)
    adv = min(max(medailles[j] for j in range(nb_joueurs) if j != i), 3)
    restantes = max(0, min(3, manches_prevues - manche))  # 0 = derniere prevue ou departage
    return f"{nb_joueurs}|{mes}|{adv}|{restantes}|{niveau}"


# --- Pick aux priors, ajusté à l'état des Médailles ---
def score_pick_soiree(objet, perso, priors, mes_medailles, medailles_adverses):
    if priors is None:
        return objet.priorite / 100.0  # mode dégradé : pas de priors calculés
    s = score_pick(objet, perso, priors)
    if mes_medailles:
        if getattr(objet, 'bonus_sans_medaille', False):
            s -= MALUS_PICK_SANS_MEDAILLE
        if getattr(objet, 'protege_medailles', False):
            s += BONUS_PICK_PROTEGE
    if getattr(objet, 'vole_medailles_perdues', False):
        s += BONUS_PICK_PARFUM * medailles_adverses
    if getattr(objet, 'medailles_victoire', 0):
        s += BONUS_PICK_COUPE
    return s


# --- Draft complet aux priors (avant chaque manche) ---
def draft_soiree(persos, medailles, log=False):
    """Draft : mains de 7 qui tournent, chacun garde 6 objets.
    Retourne (builds, objets_restants_pour_la_manche)."""
    pool = list(objets_disponibles)
    for o in pool:
        o.repare()
    nb = len(persos)
    priors = _charger_priors()

    mains = []
    for _ in range(nb):
        main = random.sample(pool, min(TAILLE_MAIN_DRAFT, len(pool)))
        for o in main:
            pool.remove(o)
        mains.append(main)

    builds = [[] for _ in range(nb)]
    total_medailles = sum(medailles)
    while any(len(b) < NB_OBJETS_PAR_JOUEUR for b in builds) and any(mains):
        suivantes = [[] for _ in range(nb)]
        for i in range(nb):
            if len(builds[i]) < NB_OBJETS_PAR_JOUEUR and mains[i]:
                adverses = total_medailles - medailles[i]
                choix = max(mains[i], key=lambda o: score_pick_soiree(
                    o, persos[i], priors, medailles[i], adverses))
                builds[i].append(choix)
                mains[i].remove(choix)
                if log:
                    print(f"  {persos[i].nom} ({medailles[i]} med.) picke {choix.nom}")
            suivantes[(i + 1) % nb] = mains[i]
        mains = suivantes

    poubelle = [o for main in mains for o in main]
    return builds, pool + poubelle


# --- Une soirée complète ---
def jouer_soiree(log=False):
    """Joue une soirée et retourne (index_vainqueur, historique, infos).
    historique = liste de manches ; une manche = liste par joueur de
    (nom_perso, [noms objets draftés], win, mort, fui, poncé, etat_avant, delta_medailles)."""
    nb_joueurs = random.choice([3, 4])
    noms = NOMS_JOUEURS[:nb_joueurs]

    classes_pool = list(_classes_persos)
    random.shuffle(classes_pool)
    classes_joueurs = [classes_pool.pop() for _ in range(nb_joueurs)]
    niveaux = [1] * nb_joueurs
    medailles = [0] * nb_joueurs
    manches_prevues = random.randint(MANCHES_MIN, MANCHES_MAX)

    historique = []
    vainqueur_idx = None
    manche = 0
    while True:
        manche += 1
        if manche > MAX_MANCHES_PAR_SOIREE:
            # départage interminable : tirage au sort parmi les leaders
            maxi = max(medailles)
            vainqueur_idx = random.choice([i for i in range(nb_joueurs) if medailles[i] == maxi])
            if log:
                print(f"Garde-fou {MAX_MANCHES_PAR_SOIREE} manches atteint, "
                      f"{noms[vainqueur_idx]} gagne au tirage au sort.")
            break

        persos = [cls(niveaux[i]) for i, cls in enumerate(classes_joueurs)]
        if log:
            etat = ", ".join(f"{noms[i]}={persos[i].nom}({medailles[i]} med.)" for i in range(nb_joueurs))
            print(f"\n===== Manche {manche}/{manches_prevues} : {etat} =====")

        # etat de chaque joueur AVANT la manche (sert a corriger le biais de selection)
        etats_avant = [_cle_etat(nb_joueurs, medailles, i, niveaux[i], manches_prevues, manche)
                       for i in range(nb_joueurs)]
        medailles_avant = list(medailles)

        builds, objets_restants = draft_soiree(persos, medailles, log)
        joueurs = [Joueur(noms[i], persos[i], builds[i], medailles=medailles[i])
                   for i in range(nb_joueurs)]
        vainqueur, _ = ordonnanceur(joueurs, DonjonDeck(), SEUIL_PV_ESSAI_FUITE, objets_restants, log)

        enregistrement = []
        for i, j in enumerate(joueurs):
            win = j is vainqueur
            medailles[i] = j.medailles  # pertes en cours de manche (mort, Rongeur) et gains (Parfum)
            if win:
                gain = 1
                for o in j.objets:
                    if o.intact and getattr(o, 'medailles_victoire', 0) > gain:
                        gain = o.medailles_victoire
                medailles[i] += gain
                if log:
                    print(f"{j.nom} remporte la manche et gagne {gain} Médaille(s) -> {medailles[i]}.")
            if j.vivant:
                niveaux[i] = 2
            else:
                # le héros mort retourne dans le pool, on en repioche un autre au niveau 1
                nouvelle = random.choice(classes_pool)
                classes_pool.remove(nouvelle)
                classes_pool.append(classes_joueurs[i])
                classes_joueurs[i] = nouvelle
                niveaux[i] = 1
                if log:
                    print(f"{j.nom} est mort : son héros retourne dans le pool, "
                          f"il jouera {nouvelle(1).nom} à la prochaine manche.")
            enregistrement.append((persos[i].nom, [o.nom for o in builds[i]],
                                   win, not j.vivant, j.fuite_reussie, j.dans_le_dj,
                                   etats_avant[i], medailles[i] - medailles_avant[i]))
        historique.append(enregistrement)

        if manche >= manches_prevues:
            maxi = max(medailles)
            leaders = [i for i in range(nb_joueurs) if medailles[i] == maxi]
            if len(leaders) == 1:
                vainqueur_idx = leaders[0]
                break
            if log:
                egaux = ", ".join(noms[i] for i in leaders)
                print(f"Égalité à {maxi} Médaille(s) entre {egaux} : manche de départage !")

    if log:
        bilan = ", ".join(f"{noms[i]}: {medailles[i]} med." for i in range(nb_joueurs))
        print(f"\n***** {noms[vainqueur_idx]} remporte la soirée en {manche} manche(s) ! ({bilan}) *****\n")

    infos = {'manches': manche, 'manches_prevues': manches_prevues,
             'departage': manche > manches_prevues, 'nb_joueurs': nb_joueurs,
             'medailles_finales': sum(medailles)}
    return vainqueur_idx, historique, infos


# --- Worker multiprocessing : un batch de soirées ---
def _soirees_batch(args):
    nb_soirees, seed = args
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)
    _charger_priors()  # depuis le cache disque (calculé par le parent avant le Pool)

    item_stats = {}
    perso_stats = {}
    duo_stats = {}          # "objet_a||objet_b" -> {'night_win', 'win', 'played'}
    perso_objet_stats = {}  # "perso||objet" -> {'night_win', 'win', 'played'}
    baseline = {}  # etat -> [night_wins, joueurs-manches, somme delta medailles]
    compteurs = {'soirees': 0, 'manches': 0, 'departages': 0, 'medailles_finales': 0,
                 'hist_manches': {}}

    def _maj_etat(stats_entry, etat, night_win, delta):
        e = stats_entry.setdefault('etats', {})
        cur = e.setdefault(etat, [0, 0, 0])
        cur[0] += night_win; cur[1] += 1; cur[2] += delta

    for _ in range(nb_soirees):
        vainqueur_idx, historique, infos = jouer_soiree(False)
        compteurs['soirees'] += 1
        compteurs['manches'] += infos['manches']
        compteurs['departages'] += 1 if infos['departage'] else 0
        compteurs['medailles_finales'] += infos['medailles_finales']
        h = compteurs['hist_manches']
        h[infos['manches']] = h.get(infos['manches'], 0) + 1

        for manche in historique:
            for i, (perso_nom, objets_noms, win, mort, fui, ponce, etat, delta) in enumerate(manche):
                night_win = (i == vainqueur_idx)
                cur = baseline.setdefault(etat, [0, 0, 0])
                cur[0] += night_win; cur[1] += 1; cur[2] += delta
                sp = _entree_stats(perso_nom, perso_stats)
                sp['played'] += 1
                sp['night_win'] += night_win
                sp['win'] += win
                sp['death'] += mort
                sp['fled'] += fui
                sp['cleared'] += ponce
                _maj_etat(sp, etat, night_win, delta)
                for nom in objets_noms:
                    si = _entree_stats(nom, item_stats)
                    si['pick'] += 1
                    si['played'] += 1
                    si['night_win'] += night_win
                    si['win'] += win
                    si['death'] += mort
                    si['fled'] += fui
                    si['cleared'] += ponce
                    _maj_etat(si, etat, night_win, delta)
                    s = perso_objet_stats.setdefault(f"{perso_nom}||{nom}",
                                                     {'night_win': 0, 'win': 0, 'played': 0})
                    s['played'] += 1
                    s['night_win'] += night_win
                    s['win'] += win
                for a, b in itertools.combinations(sorted(objets_noms), 2):
                    s = duo_stats.setdefault(f"{a}||{b}",
                                             {'night_win': 0, 'win': 0, 'played': 0})
                    s['played'] += 1
                    s['night_win'] += night_win
                    s['win'] += win

    return item_stats, perso_stats, duo_stats, perso_objet_stats, baseline, compteurs


# --- Affichage ---
def _tables_baseline(baseline, k_shrink=50):
    """Attendu par état (winrate de soirée, delta de Médailles), rétréci vers le global
    pour les états rares. Retourne (base_win, base_delta)."""
    tot_w = sum(v[0] for v in baseline.values())
    tot_n = sum(v[1] for v in baseline.values())
    tot_d = sum(v[2] for v in baseline.values())
    if not tot_n:
        return {}, {}, 0.0, 0.0
    p_glob = tot_w / tot_n
    d_glob = tot_d / tot_n
    base_win = {e: (v[0] + k_shrink * p_glob) / (v[1] + k_shrink) for e, v in baseline.items()}
    base_delta = {e: (v[2] + k_shrink * d_glob) / (v[1] + k_shrink) for e, v in baseline.items()}
    return base_win, base_delta, p_glob, d_glob


def _scores_ajustes(stats_entry, base_win, base_delta, p_glob, d_glob):
    """(WinAdj, MedAdj) : issue de soirée et delta de Médailles, en écart à l'attendu
    de l'état au moment du pick (corrige le biais de sélection). En points pour Win."""
    etats = stats_entry.get('etats', {})
    n_tot = sum(v[1] for v in etats.values())
    if not n_tot:
        return 0.0, 0.0
    exces_win = sum(v[0] - v[1] * base_win.get(e, p_glob) for e, v in etats.items())
    exces_delta = sum(v[2] - v[1] * base_delta.get(e, d_glob) for e, v in etats.items())
    return exces_win / n_tot * 100, exces_delta / n_tot


def _afficher_stats(item_stats, perso_stats, baseline, compteurs,
                    duo_stats=None, perso_objet_stats=None):
    soirees = max(1, compteurs.get('soirees', 0))
    manches = max(1, compteurs.get('manches', 0))
    print(f"\n{'=' * 30} RÉSUMÉ {'=' * 30}")
    print(f"Soirées simulées          : {compteurs.get('soirees', 0)}")
    print(f"Manches par soirée (moy.) : {compteurs.get('manches', 0) / soirees:.2f}")
    print(f"Soirées avec départage    : {compteurs.get('departages', 0) / soirees * 100:.1f}%")
    print(f"Médailles en fin de soirée (moy.) : {compteurs.get('medailles_finales', 0) / soirees:.2f}")
    hist = compteurs.get('hist_manches', {})
    if hist:
        dist = ", ".join(f"{k}: {hist[k] / soirees * 100:.1f}%" for k in sorted(hist, key=int))
        print(f"Distribution du nombre de manches : {dist}")

    base_win, base_delta, p_glob, d_glob = _tables_baseline(baseline)

    def _lignes(stats, cle_nom):
        lignes = []
        for nom, s in stats.items():
            played = s.get('played', 0)
            if not played:
                continue
            win_adj, med_adj = _scores_ajustes(s, base_win, base_delta, p_glob, d_glob)
            delta_total = sum(v[2] for v in s.get('etats', {}).values())
            lignes.append({
                cle_nom: nom, 'Played': played,
                'WinAdj': win_adj,
                'MedAdj': med_adj,
                'MedDelta': delta_total / played,
                'NightWin%': s.get('night_win', 0) / played * 100,
                'GameWin%': s.get('win', 0) / played * 100,
                'Death%': s.get('death', 0) / played * 100,
                'Fled%': s.get('fled', 0) / played * 100,
                'Clear%': s.get('cleared', 0) / played * 100,
            })
        lignes.sort(key=lambda x: x['WinAdj'], reverse=True)
        return lignes

    def _imprimer(lignes, cle_nom, largeur_nom):
        sep = "-" * (largeur_nom + 96)
        print(sep)
        print(f"{cle_nom:<{largeur_nom}} {'Played':<8} {'WinAdj':<8} {'MedAdj':<8} {'MedDelta':<9} "
              f"{'NightWin%':<10} {'GameWin%':<9} {'Death%':<7} {'Fled%':<7} {'Clear%':<7}")
        print(sep)
        for l in lignes:
            print(f"{l[cle_nom]:<{largeur_nom}} {l['Played']:<8} {l['WinAdj']:<+8.2f} {l['MedAdj']:<+8.3f} "
                  f"{l['MedDelta']:<+9.3f} {l['NightWin%']:<10.2f} {l['GameWin%']:<9.2f} {l['Death%']:<7.2f} "
                  f"{l['Fled%']:<7.2f} {l['Clear%']:<7.2f}")
        print(sep)

    print("\n--- Statistiques Objets (classement par WinAdj, corrigé du biais de sélection) ---")
    _imprimer(_lignes(item_stats, 'Objet'), 'Objet', 35)

    print("\n--- Statistiques Personnages (classement par WinAdj) ---")
    _imprimer(_lignes(perso_stats, 'Personnage'), 'Personnage', 22)

    # --- Duos (top/flop par NightWin% brut, chaque nom n'apparait qu'une fois) ---
    def _top_flop_duos(stats, titre, separateur=' & '):
        lignes = [(cle.split('||'), s['night_win'] / s['played'] * 100,
                   s['win'] / s['played'] * 100, s['played'])
                  for cle, s in (stats or {}).items() if s.get('played', 0)]
        if not lignes:
            return
        tailles = sorted(p for _, _, _, p in lignes)
        minimum = max(200, tailles[len(tailles) // 2] // 10)
        lignes = [l for l in lignes if l[3] >= minimum]
        lignes.sort(key=lambda l: l[1], reverse=True)

        def _selection(iterable):
            retenus, vus = [], set()
            for noms, nw, gw, played in iterable:
                if not any(nm in vus for nm in noms):
                    retenus.append((noms, nw, gw, played))
                    vus.update(noms)
                if len(retenus) == 10:
                    break
            return retenus

        print(f"\n{titre} (échantillon >= {minimum}, NightWin% brut — biais de sélection non corrigé) :")
        print(f"  {'-- top 10 --':<70} {'NightWin%':>10} {'GameWin%':>9} {'Played':>8}")
        for noms, nw, gw, played in _selection(lignes):
            print(f"  {separateur.join(noms):<70} {nw:>10.2f} {gw:>9.2f} {played:>8}")
        print(f"  {'-- flop 10 --':<70} {'NightWin%':>10} {'GameWin%':>9} {'Played':>8}")
        for noms, nw, gw, played in _selection(reversed(lignes)):
            print(f"  {separateur.join(noms):<70} {nw:>10.2f} {gw:>9.2f} {played:>8}")

    _top_flop_duos(duo_stats, "Duos d'objets")
    _top_flop_duos(perso_objet_stats, "Duos Héros & Objet", separateur=' + ')

    print("\nNB : WinAdj = points de victoire de soirée au-dessus de l'attendu de l'état au moment")
    print("du pick (Médailles des deux camps, manches restantes, niveau du héros, nb joueurs) :")
    print("c'est la contribution propre du pick, débarrassée du biais de sélection. MedAdj = pareil")
    print("pour le delta de Médailles de la manche ; MedDelta = delta brut (gagnées - perdues).")
    print(f"NightWin% brut : hasard ~{100/3.5:.1f}% (3-4 joueurs), biaisé par l'état au pick.")


# --- Simulation de masse (multiprocess, avec reprise) ---
def simuler_soirees(iter=NB_SOIREES, filename=STATS_FILENAME, nb_process=None):
    if nb_process is None:
        nb_process = max(1, (os.cpu_count() or 2) - 1)

    item_stats = {}
    perso_stats = {}
    duo_stats = {}
    perso_objet_stats = {}
    baseline = {}
    compteurs = {}
    start = 0

    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            if saved.get('format') != 3:
                print(f"{filename} est dans un ancien format (sans duos) : redémarrage.")
            else:
                item_stats = saved.get('item_stats', {})
                perso_stats = saved.get('perso_stats', {})
                duo_stats = saved.get('duo_stats', {})
                perso_objet_stats = saved.get('perso_objet_stats', {})
                baseline = saved.get('baseline', {})
                compteurs = saved.get('compteurs', {})
                # cles d'histogramme: json les stocke en str
                compteurs['hist_manches'] = {int(k): v for k, v in compteurs.get('hist_manches', {}).items()}
                start = saved.get('soirees_completed', 0)
                print(f"Reprise à la soirée {start + 1}/{iter}.")
        except Exception as e:
            print(f"Erreur chargement {filename}: {e}. Redémarrage.")
            item_stats, perso_stats, duo_stats, perso_objet_stats = {}, {}, {}, {}
            baseline, compteurs, start = {}, {}, 0
    else:
        print("Démarrage nouvelle simulation.")

    soirees_completes = start
    if start >= iter:
        print("Simulation déjà complétée.")
    else:
        calculer_priors(nb_process=nb_process)

        restant = iter - start
        soirees_par_batch = max(1, min(50, restant // (nb_process * 8) if nb_process > 1 else restant))
        travaux = []
        attribues = 0
        while attribues < restant:
            n = min(soirees_par_batch, restant - attribues)
            travaux.append((n, random.randrange(2**31)))
            attribues += n

        def sauvegarder():
            save = {'format': 3, 'soirees_completed': soirees_completes, 'compteurs': compteurs,
                    'baseline': baseline, 'item_stats': item_stats, 'perso_stats': perso_stats,
                    'duo_stats': duo_stats, 'perso_objet_stats': perso_objet_stats}
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(save, f, ensure_ascii=False)  # compact: le fichier est volumineux (stats par etat)
            except IOError as e:
                print(f"\nERREUR sauvegarde: {e}")

        batchs_depuis_save = 0

        def integrer(resultat):
            nonlocal soirees_completes, batchs_depuis_save
            so, sp, sd, spo, bl, cpt = resultat
            _fusionner_stats(item_stats, so)
            _fusionner_stats(perso_stats, sp)
            _fusionner_stats(duo_stats, sd)
            _fusionner_stats(perso_objet_stats, spo)
            _fusionner_baseline(baseline, bl)
            for cle in ('soirees', 'manches', 'departages', 'medailles_finales'):
                compteurs[cle] = compteurs.get(cle, 0) + cpt[cle]
            h = compteurs.setdefault('hist_manches', {})
            for k, v in cpt['hist_manches'].items():
                h[k] = h.get(k, 0) + v
            soirees_completes += cpt['soirees']
            batchs_depuis_save += 1
            if batchs_depuis_save >= 20:  # le fichier est gros, on n'ecrit pas a chaque batch
                batchs_depuis_save = 0
                sauvegarder()

        print(f"Objectif: {iter} soirées, {nb_process} process. Démarrage à {start + 1}...")
        if nb_process > 1:
            with multiprocessing.Pool(nb_process) as pool:
                for resultat in tqdm(pool.imap_unordered(_soirees_batch, travaux),
                                     total=len(travaux), desc="Simulation soirées"):
                    integrer(resultat)
        else:
            for travail in tqdm(travaux, desc="Simulation soirées"):
                integrer(_soirees_batch(travail))
        sauvegarder()

    _afficher_stats(item_stats, perso_stats, baseline, compteurs, duo_stats, perso_objet_stats)
    print(f"\nStats basées sur {soirees_completes} soirées. Données sauvegardées dans {filename}")


# --- Lancement ---
if __name__ == "__main__":
    script_dir = os.path.dirname(__file__)
    if script_dir:
        try:
            os.chdir(script_dir)
        except Exception as e:
            print(f"WARN: Impossible de changer de répertoire: {e}")

    if len(sys.argv) == 2 and sys.argv[1].isdigit():
        x = int(sys.argv[1])
        print(f"Mode log : {x} soirée(s) détaillée(s).")
        calculer_priors()
        for n in range(x):
            print(f"\n{'#' * 25} SOIRÉE {n + 1}/{x} {'#' * 25}")
            jouer_soiree(log=True)
    elif len(sys.argv) == 1:
        simuler_soirees()
    else:
        print("Utilisation :")
        print("  python party.py   \t Simulation de masse (winrates de soirée)")
        print("  python party.py x \t Joue x soirées avec les logs complets")
