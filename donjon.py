import random
import pandas as pd
import itertools
import time
from tqdm import tqdm
import numpy as np
from simu import   loguer_x_parties
from objets import *
from perso import Joueur
from monstres import cartes
import copy

# Nombre de simulations souhaitées
total_simulations = 10000
seuil_pv_essai_fuite=7


def display_simu():
    # Initialisation des résultats
    resultats_builds = []
    total_games_simulees = 0

    # Mesurer le temps de simulation
    start_time = time.time()

    # Simuler les builds aléatoires et stocker les résultats avec une barre de progression
    for _ in tqdm(range(total_simulations), desc="Simulation des builds"):
        build = random.sample(objets, 6)
        stats, pourcentage_fuite_reussie, pourcentage_donjon_ponce, variance = simuler_build(build, 3, seuil_pv_essai_fuite)
        build_noms = [objet.nom for objet in build]
        resultats_builds.append({
            'Build': ', '.join(build_noms),
            'Score moyen': stats[0],
            'Score médian': stats[1],
            'Score maximum': stats[2],
            'Score minimum': stats[3],
            'Pourcentage de fuite réussie': pourcentage_fuite_reussie,
            'Pourcentage de donjon ponce': pourcentage_donjon_ponce,
            'Variance': variance
        })
        total_games_simulees += 1

    # Mesurer le temps de simulation
    end_time = time.time()
    total_time = end_time - start_time

    # Afficher le tableau récapitulatif
    df_resultats = pd.DataFrame(resultats_builds)

    # Calculer le score moyen global par jeu
    moyenne_globale = df_resultats['Score moyen'].mean()

    # Calculer les scores pour chaque objet
    objets_scores = {objet.nom: {'total_score': 0, 'count': 0, 'variances': []} for objet in objets}
    for index, row in df_resultats.iterrows():
        for objet in row['Build'].split(', '):
            objets_scores[objet]['total_score'] += row['Score moyen']
            objets_scores[objet]['count'] += 1
            objets_scores[objet]['variances'].append(row['Variance'])

    # Calculer le score moyen par jeu, la variance et l'efficacité pour chaque objet
    objets_stats = []
    for objet, scores in objets_scores.items():
        score_moyen_par_jeu = scores['total_score'] / scores['count']
        variance_moyenne = np.mean(scores['variances'])
        efficacite = (score_moyen_par_jeu / moyenne_globale) * 100
        objets_stats.append({
            'Objet': objet,
            'Score moyen par jeu': score_moyen_par_jeu,
            'Variance': variance_moyenne,
            'Efficacité (%)': efficacite
        })

    # Calculer les meilleurs et les pires duos d'objets
    duos_scores = {}

    for index, row in df_resultats.iterrows():
        build_objets = row['Build'].split(', ')
        for duo in itertools.combinations(build_objets, 2):
            if duo not in duos_scores:
                duos_scores[duo] = {'total_score': 0, 'count': 0}
            duos_scores[duo]['total_score'] += row['Score moyen']
            duos_scores[duo]['count'] += 1

    duos_stats = []
    for duo, scores in duos_scores.items():
        score_moyen_duo = scores['total_score'] / scores['count']
        duos_stats.append({
            'Duo': ' & '.join(duo),
            'Score moyen par jeu': score_moyen_duo
        })

    df_duos_scores = pd.DataFrame(duos_stats)
    df_duos_scores.sort_values(by='Score moyen par jeu', ascending=False, inplace=True)
    top_10_duos = df_duos_scores.head(10)
    flop_10_duos = df_duos_scores.tail(10)

    # Afficher les scores pour chaque objet
    df_objets_scores = pd.DataFrame(objets_stats)
    df_objets_scores.sort_values(by='Score moyen par jeu', ascending=False, inplace=True)

    print("Récapitulatif des builds:")
    print(df_resultats)
    print("\nScores pour chaque objet:")
    print(df_objets_scores)
    print("\nTop 10 des duos d'objets:")
    print(top_10_duos)
    print("\nFlop 10 des duos d'objets:")
    print(flop_10_duos)
    print(f"\nTemps total des simulations : {total_time:.2f} secondes")
    print(f"Total de jeux simulés : {total_games_simulees}")

# display_simu()


loguer_x_parties()
