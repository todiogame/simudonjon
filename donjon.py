import random
import pandas as pd
import itertools
import time
from tqdm import tqdm
import numpy as np
from simu import   loguer_x_parties, ordonnanceur
from objets import *
from joueurs import Joueur
from monstres import DonjonDeck
import copy
import itertools
import json
import shutil
import sys
import os
import multiprocessing
from heros import persos_disponibles

# Nombre de simulations souhaitées
total_simulations = 3000000
seuil_pv_essai_fuite=5

def _simuler_batch(args):
    """Worker (multiprocessing) : simule nb_sims parties et retourne des compteurs agrégés.

    Chaque process a ses propres instances d'objets/persos (re-import du module),
    donc aucun etat partage. Les compteurs sont fusionnes par le parent."""
    nb_sims, seed = args
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)

    with open('priorites_objets.json', 'r') as json_file:
        priorites_objets = json.load(json_file)

    stats_objets = {}      # nom -> [victoires, total]
    stats_persos = {}      # nom -> [victoires, total]
    duos_scores = {}       # (objet_a, objet_b) -> [victoires, total]
    duos_perso_item = {}   # (perso, objet) -> [victoires, total]
    scores_objets = {}     # nom -> {score_pose: nb}  (score 0 si le joueur ne compte pas)
    scores_persos = {}     # nom -> {score_pose: nb}
    compteurs = {'joueurs': 0, 'morts': 0, 'fuites': 0, 'scores': {}}  # scores: histogramme global
    ponces = {3: 0, 4: 0}
    highscore = 0

    for _ in range(nb_sims):
        # Créer une copie de la liste des objets disponibles pour cette simulation
        objets_disponibles_simu = list(objets_disponibles)
        # Reparer tous les objets et attribuer une priorité aléatoire
        for o in objets_disponibles_simu:
            o.repare()
            o.priorite = min(100, max(0, priorites_objets.get(o.nom, 49.5) + random.uniform(-20, 20)))

        # Initialisation des joueurs avec des perso aléatoires
        # (l'etat une-fois-par-partie des persos est reset par debut_partie dans l'ordonnanceur)
        joueurs = []
        nb_joueurs = random.choice([3, 4])
        player_names = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]
        personnages_assigner = random.sample(persos_disponibles, nb_joueurs)

        for i, nom_base in enumerate(player_names):
            objets_joueur = random.sample(objets_disponibles_simu, 6)
            for objet in objets_joueur:
                objets_disponibles_simu.remove(objet)
            joueurs.append(Joueur(nom_base, personnages_assigner[i], objets_joueur))

        # Exécution de l'ordonnanceur sans afficher les logs
        vainqueur, _ = ordonnanceur(joueurs, DonjonDeck(), seuil_pv_essai_fuite, objets_disponibles_simu, False)

        if vainqueur and vainqueur.score_final > highscore:
            highscore = vainqueur.score_final

        for joueur in joueurs:
            victoire = 1 if joueur is vainqueur else 0
            # score "pose": le score final si le joueur compte au decompte, sinon 0 (mort/fuyard exclu)
            score_pose = joueur.score_final if getattr(joueur, 'compte_au_score', False) else 0
            compteurs['joueurs'] += 1
            if not joueur.vivant:
                compteurs['morts'] += 1
            elif joueur.fuite_reussie:
                compteurs['fuites'] += 1
            h = compteurs['scores']; h[score_pose] = h.get(score_pose, 0) + 1
            perso_nom = joueur.personnage_nom
            s = stats_persos.setdefault(perso_nom, [0, 0]); s[0] += victoire; s[1] += 1
            h = scores_persos.setdefault(perso_nom, {}); h[score_pose] = h.get(score_pose, 0) + 1
            noms_objets = sorted(o.nom for o in joueur.objets_initiaux)
            for nom in noms_objets:
                s = stats_objets.setdefault(nom, [0, 0]); s[0] += victoire; s[1] += 1
                s = duos_perso_item.setdefault((perso_nom, nom), [0, 0]); s[0] += victoire; s[1] += 1
                h = scores_objets.setdefault(nom, {}); h[score_pose] = h.get(score_pose, 0) + 1
            for duo in itertools.combinations(noms_objets, 2):
                s = duos_scores.setdefault(duo, [0, 0]); s[0] += victoire; s[1] += 1

        if any(joueur.dans_le_dj for joueur in joueurs):
            ponces[nb_joueurs] += 1

    return stats_objets, stats_persos, duos_scores, duos_perso_item, ponces, highscore, scores_objets, scores_persos, compteurs


def _fusionner(dest, src):
    """Additionne les compteurs [victoires, total] d'un batch dans le total."""
    for cle, (v, t) in src.items():
        d = dest.setdefault(cle, [0, 0])
        d[0] += v
        d[1] += t


def _fusionner_hist(dest, src):
    """Additionne des histogrammes {valeur: nb} indexes par cle."""
    for cle, hist in src.items():
        d = dest.setdefault(cle, {})
        for valeur, nb in hist.items():
            d[valeur] = d.get(valeur, 0) + nb


def _mediane_hist(hist):
    """Mediane d'un histogramme {valeur: nb}."""
    total = sum(hist.values())
    if not total:
        return 0
    cible = (total + 1) / 2
    cumul = 0
    for valeur in sorted(hist):
        cumul += hist[valeur]
        if cumul >= cible:
            return valeur
    return 0


def display_simu(r=0, nb_process=None):
    if nb_process is None:
        nb_process = max(1, (os.cpu_count() or 2) - 1)

    stats_objets = {}
    stats_persos = {}
    duos_scores = {}
    duos_perso_item = {}
    scores_objets = {}
    scores_persos = {}
    compteurs_globaux = {'joueurs': 0, 'morts': 0, 'fuites': 0, 'scores': {}}
    dj_ponces3j = 0
    dj_ponces4j = 0
    highscore_max = 0

    start_time = time.time()

    # decoupage en batches (plusieurs par process pour une progression reguliere)
    nb_batches = nb_process * 8 if nb_process > 1 else 1
    base, reste = divmod(total_simulations, nb_batches)
    travaux = [(base + (1 if i < reste else 0), random.randrange(2**31))
               for i in range(nb_batches)]
    travaux = [t for t in travaux if t[0] > 0]

    def consommer(resultats_batches):
        nonlocal dj_ponces3j, dj_ponces4j, highscore_max
        for so, sp, ds, dpi, ponces, hs, sco, scp, cpt in resultats_batches:
            _fusionner(stats_objets, so)
            _fusionner(stats_persos, sp)
            _fusionner(duos_scores, ds)
            _fusionner(duos_perso_item, dpi)
            _fusionner_hist(scores_objets, sco)
            _fusionner_hist(scores_persos, scp)
            compteurs_globaux['joueurs'] += cpt['joueurs']
            compteurs_globaux['morts'] += cpt['morts']
            compteurs_globaux['fuites'] += cpt['fuites']
            for valeur, nb in cpt['scores'].items():
                compteurs_globaux['scores'][valeur] = compteurs_globaux['scores'].get(valeur, 0) + nb
            dj_ponces3j += ponces[3]
            dj_ponces4j += ponces[4]
            highscore_max = max(highscore_max, hs)

    if nb_process > 1:
        with multiprocessing.Pool(nb_process) as pool:
            consommer(tqdm(pool.imap_unordered(_simuler_batch, travaux),
                           total=len(travaux), desc=f"Simulation des builds ({nb_process} process)"))
    else:
        consommer(_simuler_batch(t) for t in tqdm(travaux, desc="Simulation des builds"))

    # Mesurer le temps de simulation
    end_time = time.time()
    total_time = end_time - start_time

    # Statistiques par objet (depuis les compteurs fusionnes)
    df_stats_objets = pd.DataFrame(
        [{'Objet': nom, 'Victoires': v, 'Total': t, 'Winrate': (v / t) * 100,
          'Score médian': _mediane_hist(scores_objets.get(nom, {}))}
         for nom, (v, t) in stats_objets.items()]
    ).sort_values(by='Winrate', ascending=False)
    pd.set_option('display.max_rows', None)  # afficher tous les objets (270+ depuis la synchro tableur)

    # Afficher les résultats
    print("\nStatistiques par objet:")
    print(df_stats_objets)
    print(f"\nTemps total des simulations : {total_time:.2f} secondes")
    print(f"Pourcentage de donjons ponces a 3j : {dj_ponces3j / total_simulations* 100:.2f}%")
    print(f"Pourcentage de donjons ponces a 4j : {dj_ponces4j / total_simulations* 100:.2f}%")
    nb_joueurs_total = max(1, compteurs_globaux['joueurs'])
    print(f"Score médian posé (toutes parties) : {_mediane_hist(compteurs_globaux['scores'])}")
    print(f"Pourcentage de joueurs morts : {compteurs_globaux['morts'] / nb_joueurs_total * 100:.2f}%")
    print(f"Pourcentage de joueurs ayant fui : {compteurs_globaux['fuites'] / nb_joueurs_total * 100:.2f}%")

    # --- Statistiques par Personnage ---
    if stats_persos:
        df_stats_persos = pd.DataFrame(
            [{'Personnage': nom, 'Victoires': v, 'Total_Parties': t, 'Winrate (%)': round(v * 100 / t, 2),
              'Score médian': _mediane_hist(scores_persos.get(nom, {}))}
             for nom, (v, t) in stats_persos.items()]
        ).sort_values(by='Winrate (%)', ascending=False)

        print("\nStatistiques par Personnage:")
        print(df_stats_persos.to_string(index=False)) # Affichage sans index
    else:
        print("\nPas de données collectées pour les statistiques par personnage.")
    # Calculer les meilleurs et les pires duos d'objets (compteurs remplis pendant la simulation)
    duos_stats = []
    for duo, (victoires, total) in duos_scores.items():
        duos_stats.append({
            'Duo': ' & '.join(duo),
            'Winrate': (victoires / total) * 100,
            'Total': total
        })

    df_duos_scores = pd.DataFrame(duos_stats)
    df_duos_scores.sort_values(by='Winrate', ascending=False, inplace=True)
    
    unique_duos = []
    seen_items = set()
    for _, row in df_duos_scores.iterrows():
        items = row['Duo'].split(' & ')
        if not any(item in seen_items for item in items):
            unique_duos.append(row)
            seen_items.update(items)
        if len(unique_duos) == 10:
            break
    top_10_duos = pd.DataFrame(unique_duos)
    
    unique_duos = []
    seen_items = set()
    for _, row in df_duos_scores.iloc[::-1].iterrows():
        items = row['Duo'].split(' & ')
        if not any(item in seen_items for item in items):
            unique_duos.append(row)
            seen_items.update(items)
        if len(unique_duos) == 10:
            break
    flop_10_duos = pd.DataFrame(unique_duos)

    print("\nMeilleurs duos d'objets:")
    print(top_10_duos)
    print("\nPires duos d'objets:")
    print(flop_10_duos)

    # Calculer les meilleurs et les pires duos Personnage & Objet (compteurs fusionnes)
    df_duos_perso_item = pd.DataFrame(
        [{'Personnage': p, 'Objet': o, 'Victoires': v, 'Total': t}
         for (p, o), (v, t) in duos_perso_item.items()]
    )
    # filtrer les combinaisons trop rares pour etre significatives
    df_duos_perso_item = df_duos_perso_item[df_duos_perso_item['Total'] >= 20]
    df_duos_perso_item['Winrate'] = (df_duos_perso_item['Victoires'] / df_duos_perso_item['Total']) * 100
    df_duos_perso_item.sort_values(by='Winrate', ascending=False, inplace=True)

    def duos_perso_item_uniques(df_iter):
        # selection gloutonne : chaque personnage et chaque objet n'apparait qu'une fois
        lignes, persos_vus, objets_vus = [], set(), set()
        for _, row in df_iter.iterrows():
            if row['Personnage'] not in persos_vus and row['Objet'] not in objets_vus:
                lignes.append(row)
                persos_vus.add(row['Personnage'])
                objets_vus.add(row['Objet'])
            if len(lignes) == 10:
                break
        return pd.DataFrame(lignes, columns=['Personnage', 'Objet', 'Winrate', 'Total'])

    top_10_duos_perso = duos_perso_item_uniques(df_duos_perso_item)
    flop_10_duos_perso = duos_perso_item_uniques(df_duos_perso_item.iloc[::-1])

    print("\nMeilleurs duos Personnage & Objet:")
    print(top_10_duos_perso.to_string(index=False))
    print("\nPires duos Personnage & Objet:")
    print(flop_10_duos_perso.to_string(index=False))
    
    #  # Calculer la priorité médiane et moyenne parmi les jeux joués
    # priorite_stats = df_resultats.groupby('Objet')['Priorite'].agg(['median', 'mean']).reset_index()
    # priorite_stats.columns = ['Objet', 'Priorite_mediane', 'Priorite_moyenne']

    # # Calculer la priorité médiane et moyenne parmi les jeux gagnés
    # priorite_stats_gagnees = df_resultats[df_resultats['Victoire'] == 1].groupby('Objet')['Priorite'].agg(['median', 'mean']).reset_index()
    # priorite_stats_gagnees.columns = ['Objet', 'Priorite_mediane_gagnee', 'Priorite_moyenne_gagnee']

    # # Fusionner les priorités médianes et moyennes avec les statistiques des objets
    # df_stats_objets = df_stats_objets.merge(priorite_stats, on='Objet')
    # df_stats_objets = df_stats_objets.merge(priorite_stats_gagnees, on='Objet')

    # # Calculer la différence de moyenne
    # df_stats_objets['Diff_moyenne'] = df_stats_objets['Priorite_moyenne_gagnee'] - df_stats_objets['Priorite_moyenne']

    # # Trier les statistiques par différence de moyenne
    # df_stats_objets = df_stats_objets.sort_values(by='Diff_moyenne', ascending=False)

    # # Sélectionner les colonnes pertinentes pour le JSON
    # df_priorites = df_stats_objets[['Objet', 'Priorite_mediane_gagnee']]
    # df_priorites_sorted = df_priorites.sort_values(by='Priorite_mediane_gagnee')
    # # Convertir en dictionnaire et exporter en JSON
    # priorites_dict = dict(zip(df_priorites_sorted['Objet'], df_priorites_sorted['Priorite_mediane_gagnee']))
    # with open('priorites_objets.json', 'w') as json_file:
    #     json.dump(priorites_dict, json_file, indent=4)
    # shutil.copyfile('priorites_objets.json', f'backupfile_{r}.json')
    
    
    
    

# for r in range(10):
#     display_simu(r)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        display_simu()
    elif len(sys.argv) == 2 and sys.argv[1].isdigit():
        x = int(sys.argv[1])
        loguer_x_parties(x)
    else:
        print("Utilisation :")
        print("  python3 donjon.py \t\t Pour afficher la simulation")
        print("  python3 donjon.py x \t Pour log x parties (x est un nombre)")

    # Calculer les meilleurs et les pires duos d'objets
    # duos_scores = {}

    # for index, row in df_resultats.iterrows():
    #     build_objets = row['Build'].split(', ')
    #     for duo in itertools.combinations(sorted(build_objets), 2):
    #         if duo not in duos_scores:
    #             duos_scores[duo] = {'victoires': 0, 'total': 0}
    #         duos_scores[duo]['victoires'] += row['Victoire']
    #         duos_scores[duo]['total'] += 1

    # duos_stats = []
    # for duo, scores in duos_scores.items():
    #     winrate_duo = (scores['victoires'] / scores['total']) * 100
    #     duos_stats.append({
    #         'Duo': ' & '.join(duo),
    #         'Winrate': winrate_duo,
    #         'Total': scores['total']
    #     })


    
    
    
    
    
    
     # # Calculer la priorité médiane et moyenne parmi les jeux joués
    # priorite_stats = df_resultats.groupby('Objet')['Priorite'].agg(['median', 'mean']).reset_index()
    # priorite_stats.columns = ['Objet', 'Priorite_mediane', 'Priorite_moyenne']

    # # Calculer la priorité médiane et moyenne parmi les jeux gagnés
    # priorite_stats_gagnees = df_resultats[df_resultats['Victoire'] == 1].groupby('Objet')['Priorite'].agg(['median', 'mean']).reset_index()
    # priorite_stats_gagnees.columns = ['Objet', 'Priorite_mediane_gagnee', 'Priorite_moyenne_gagnee']

    # # Fusionner les priorités médianes et moyennes avec les statistiques des objets
    # df_stats_objets = df_stats_objets.merge(priorite_stats, on='Objet')
    # df_stats_objets = df_stats_objets.merge(priorite_stats_gagnees, on='Objet')

    # # Calculer la différence de moyenne
    # df_stats_objets['Diff_moyenne'] = df_stats_objets['Priorite_moyenne_gagnee'] - df_stats_objets['Priorite_moyenne']

    # # Trier les statistiques par différence de moyenne
    # df_stats_objets = df_stats_objets.sort_values(by='Diff_moyenne', ascending=False)

    # # Sélectionner les colonnes pertinentes pour le JSON
    # df_priorites = df_stats_objets[['Objet', 'Priorite_mediane_gagnee']]
    # df_priorites_sorted = df_priorites.sort_values(by='Priorite_mediane_gagnee')
    # # Convertir en dictionnaire et exporter en JSON
    # priorites_dict = dict(zip(df_priorites_sorted['Objet'], df_priorites_sorted['Priorite_mediane_gagnee']))
    # with open('priorites_objets.json', 'w') as json_file:
    #     json.dump(priorites_dict, json_file, indent=4)
    # shutil.copyfile('priorites_objets.json', f'backupfile_{r}.json')
    
    
    
    
                    # 'Survie': 1 if joueur.vivant else 0,
                    # 'Fuite': 1 if joueur.fuite_reussie else 0,
                    # 'Poncage': 1 if joueur.dans_le_dj else 0,
                    # 'Score': joueur.score_final,
    # # Convertir les résultats en DataFrame
    # df_resultats = pd.DataFrame(resultats_builds)
    # pd.set_option('display.max_rows', 100)

    # # Calculer les statistiques par objet pour chaque catégorie
    # categories = ['Victoire', 'Survie', 'Fuite', 'Poncage','Score']
    # df_stats = {}

    # for categorie in categories:
    #     if categorie == 'Score':
    #         df_stats[categorie] = df_resultats.groupby('Objet')[categorie].mean().reset_index()
    #         df_stats[categorie] = df_stats[categorie].sort_values(by=categorie, ascending=False)
    #     else:
    #         df_stats[categorie] = df_resultats.groupby('Objet')[categorie].agg(['sum', 'count']).reset_index()
    #         df_stats[categorie].columns = ['Objet', 'Succès', 'Total']
    #         df_stats[categorie][f'{categorie}rate'] = (df_stats[categorie]['Succès'] / df_stats[categorie]['Total']) * 100
    #         df_stats[categorie] = df_stats[categorie].sort_values(by=f'{categorie}rate', ascending=False)

    # for categorie in categories:
    #     if categorie == 'Score':
    #         top5 = df_stats[categorie].head(5)[['Objet', categorie]].reset_index(drop=True)
    #         flop5 = df_stats[categorie].tail(5)[['Objet', categorie]].reset_index(drop=True)
    #         top5.columns = [f'Top 5 {categorie}', f'Top {categorie}']
    #         flop5.columns = [f'Flop 5 {categorie}', f'Flop {categorie}']
    #     else:
    #         top5 = df_stats[categorie].head(5)[['Objet', f'{categorie}rate']].reset_index(drop=True)
    #         flop5 = df_stats[categorie].tail(5)[['Objet', f'{categorie}rate']].reset_index(drop=True)
    #         top5.columns = [f'Top 5 {categorie}', f'Top {categorie}rate (%)']
    #         flop5.columns = [f'Flop 5 {categorie}', f'Flop {categorie}rate (%)']

    #     # Concaténer les DataFrames top5 et flop5 horizontalement
    #     combined = pd.concat([top5, flop5], axis=1)

    #     print(f"\nTop 5 et Flop 5 des objets pour {categorie} (en pourcentage):")
    #     print(combined.to_string(index=False))
   