import random
import pandas as pd
import itertools
import time
from tqdm import tqdm
import numpy as np
from simu import   loguer_x_parties, ordonnanceur
from objets import *
from perso import Joueur
from monstres import DonjonDeck
import copy
import itertools
import json
import shutil
# Nombre de simulations souhaitées
total_simulations = 10000
seuil_pv_essai_fuite=6

def display_simu(r=0):
        
    # # Lire le fichier JSON une fois au début
    # with open('priorites_objets.json', 'r') as json_file:
    #     priorites_objets = json.load(json_file)
        
    # Initialisation des résultats
    resultats_builds = []
    highscore_max = 0
    meilleur_vainqueur = None

    # Mesurer le temps de simulation
    start_time = time.time()

    # Simuler les builds aléatoires et stocker les résultats
    for _ in tqdm(range(total_simulations), desc="Simulation des builds"):
        # Créer une copie de la liste des objets disponibles pour cette simulation
        objets_disponibles_simu = list(objets_disponibles)
        # Reparer tous les objets et attribuer une priorité aléatoire
        for o in objets_disponibles_simu:
            o.intact = True
            # o.priorite = priorites_objets.get(o.nom, 0) * (1 + random.uniform(-0.1, 0.1))

        # Initialisation des joueurs avec des points de vie aléatoires entre 2 et 4
        joueurs = []
        for nom in ["Sagarex", "Francis", "Mastho", "Mr.Adam"]:
            objets_joueur = random.sample(objets_disponibles_simu, 6)
            for objet in objets_joueur:
                objets_disponibles_simu.remove(objet)
            joueurs.append(Joueur(nom, random.randint(2, 4), objets_joueur))

        # Création de la copie des joueurs et des cartes
        deck = DonjonDeck()

        # Exécution de l'ordonnanceur sans afficher les logs
        vainqueur = ordonnanceur(joueurs, deck, seuil_pv_essai_fuite, objets_disponibles_simu, False)

        # Mise à jour du highscore max et du meilleur vainqueur
        if vainqueur and vainqueur.score_final > highscore_max:
            highscore_max = vainqueur.score_final
            meilleur_vainqueur = copy.deepcopy(vainqueur)
        
        # Mise à jour des statistiques
        for joueur in joueurs:
            for objet in joueur.objets_initiaux:
                resultats_builds.append({
                    'Objet': objet.nom,
                    'Priorite': objet.priorite,
                    'Build': ', '.join(o.nom for o in joueur.objets_initiaux),
                    'Victoire': 1 if joueur == vainqueur else 0
                })

    # Mesurer le temps de simulation
    end_time = time.time()
    total_time = end_time - start_time

    # Convertir les résultats en DataFrame
    df_resultats = pd.DataFrame(resultats_builds)
    pd.set_option('display.max_rows', 100)

    # Calculer le nombre total de victoires et de défaites pour chaque objet
    df_stats_objets = df_resultats.groupby('Objet')['Victoire'].agg(['sum', 'count']).reset_index()
    df_stats_objets.columns = ['Objet', 'Victoires', 'Total']

    # Calculer le winrate pour chaque objet
    df_stats_objets['Winrate'] = (df_stats_objets['Victoires'] / df_stats_objets['Total']) * 100
    df_stats_objets = df_stats_objets.sort_values(by='Winrate', ascending=False)

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
    # Afficher les résultats
    print("\nStatistiques par objet:")
    print(df_stats_objets)
    print(f"\nTemps total des simulations : {total_time:.2f} secondes")
    if meilleur_vainqueur:
        print(f"\nHighscore Max: {highscore_max}")
        print(f"Meilleur Vainqueur: {meilleur_vainqueur.nom} avec les objets de départ:\n {', '.join(objet.nom for objet in meilleur_vainqueur.objets_initiaux)}\nBuild complet: {', '.join(objet.nom for objet in meilleur_vainqueur.objets)}")

# for r in range(20):
#     display_simu(r)
# display_simu()

loguer_x_parties(1)


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

    # df_duos_scores = pd.DataFrame(duos_stats)
    # df_duos_scores.sort_values(by='Winrate', ascending=False, inplace=True)
    # top_10_duos = df_duos_scores.head(10)
    # flop_10_duos = df_duos_scores.tail(10)