import random
import pandas as pd
import itertools
import time
from tqdm import tqdm
import numpy as np
from simu import   loguer_x_parties, ordonnanceur
from objets import *
from perso import Joueur
from monstres import cartes
import copy
import itertools

# Nombre de simulations souhaitées
total_simulations = 20000
seuil_pv_essai_fuite=6



def display_simu():
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

        # Initialisation des joueurs avec des points de vie aléatoires entre 2 et 4
        joueurs = [
            Joueur("Sagarex", random.randint(2, 4), random.sample(objets_disponibles_simu, 6)),
            Joueur("Francis", random.randint(2, 4), random.sample(objets_disponibles_simu, 6)),
            Joueur("Mastho", random.randint(2, 4), random.sample(objets_disponibles_simu, 6)),
            Joueur("Mr.Adam", random.randint(2, 4), random.sample(objets_disponibles_simu, 6))
        ]

        # Enregistrer les objets initiaux des joueurs pour les statistiques
        for joueur in joueurs:
            joueur.objets_initiaux = joueur.objets.copy()

        # Création de la copie des joueurs et des cartes
        joueurs_copie = [copy.deepcopy(joueur) for joueur in joueurs]
        cartes_copie = copy.deepcopy(cartes)

        # Exécution de l'ordonnanceur sans afficher les logs
        vainqueur = ordonnanceur(joueurs_copie, cartes_copie, seuil_pv_essai_fuite, False)

        # Mise à jour du highscore max et du meilleur vainqueur
        if vainqueur and vainqueur.score_final > highscore_max:
            highscore_max = vainqueur.score_final
            meilleur_vainqueur = copy.deepcopy(vainqueur)
        
        # Mise à jour des statistiques
        for joueur in joueurs_copie:
            for objet in joueur.objets_initiaux:
                resultats_builds.append({
                    'Objet': objet.nom,
                    'Build': ', '.join(o.nom for o in joueur.objets_initiaux),
                    'Victoire': 1 if joueur == vainqueur else 0
                })

    # Mesurer le temps de simulation
    end_time = time.time()
    total_time = end_time - start_time

    # Convertir les résultats en DataFrame
    df_resultats = pd.DataFrame(resultats_builds)

    # Calculer le nombre total de victoires et de défaites pour chaque objet
    df_stats_objets = df_resultats.groupby('Objet')['Victoire'].agg(['sum', 'count']).reset_index()
    df_stats_objets.columns = ['Objet', 'Victoires', 'Total']

    # Calculer le winrate pour chaque objet
    df_stats_objets['Winrate'] = (df_stats_objets['Victoires'] / df_stats_objets['Total']) * 100
    # Trier les statistiques par winrate
    df_stats_objets = df_stats_objets.sort_values(by='Winrate', ascending=False)

    # Calculer les meilleurs et les pires duos d'objets
    duos_scores = {}

    for index, row in df_resultats.iterrows():
        build_objets = row['Build'].split(', ')
        for duo in itertools.combinations(sorted(build_objets), 2):
            if duo not in duos_scores:
                duos_scores[duo] = {'victoires': 0, 'total': 0}
            duos_scores[duo]['victoires'] += row['Victoire']
            duos_scores[duo]['total'] += 1

    duos_stats = []
    for duo, scores in duos_scores.items():
        winrate_duo = (scores['victoires'] / scores['total']) * 100
        duos_stats.append({
            'Duo': ' & '.join(duo),
            'Winrate': winrate_duo,
            'Total': scores['total']
        })

    df_duos_scores = pd.DataFrame(duos_stats)
    df_duos_scores.sort_values(by='Winrate', ascending=False, inplace=True)
    top_10_duos = df_duos_scores.head(10)
    flop_10_duos = df_duos_scores.tail(10)

    # Afficher les résultats
    print("\nStatistiques par objet:")
    print(df_stats_objets)
    print("\nMeilleurs duos d'objets:")
    print(top_10_duos)
    print("\nPires duos d'objets:")
    print(flop_10_duos)
    print(f"\nTemps total des simulations : {total_time:.2f} secondes")
    if meilleur_vainqueur:
            print(f"\nHighscore Max: {highscore_max}")
            print(f"Meilleur Vainqueur: {meilleur_vainqueur.nom} avec les objets: {', '.join(objet.nom for objet in meilleur_vainqueur.objets)}")


display_simu()

# loguer_x_parties()
