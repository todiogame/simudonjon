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

# Nombre de simulations souhaitées
total_simulations = 10000
seuil_pv_essai_fuite=7


def display_simu():
    # Initialisation des résultats
    resultats_builds = []
    total_games_simulees = 0

    # Mesurer le temps de simulation
    start_time = time.time()

    # Simuler les builds aléatoires et stocker les résultats
    for _ in tqdm(range(total_simulations), desc="Simulation des builds"):
        # Créer une copie de la liste des objets disponibles pour cette simulation
        objets_disponibles_simu = list(objets_disponibles)

        # Initialisation des joueurs avec des points de vie aléatoires entre 2 et 4
        joueurs = [
            Joueur("Sagarex", random.randint(2, 4), random.sample(objets_disponibles_simu, 3)),
            Joueur("Francis", random.randint(2, 4), random.sample(objets_disponibles_simu, 3)),
            Joueur("Mastho", random.randint(2, 4), random.sample(objets_disponibles_simu, 3))
        ]

        # Création de la copie des joueurs et des cartes
        joueurs_copie = [copy.deepcopy(joueur) for joueur in joueurs]
        cartes_copie = copy.deepcopy(cartes)

        # Exécution de l'ordonnanceur sans afficher les logs
        vainqueur = ordonnanceur(joueurs_copie, cartes_copie, seuil_pv_essai_fuite, False)

        # Mise à jour des statistiques
        for joueur in joueurs_copie:
            for objet in joueur.objets:
                total_games_simulees += 1
                if joueur == vainqueur:
                    resultats_builds.append({
                        'Objet': objet.nom,
                        'Victoire': 1
                    })
                else:
                    resultats_builds.append({
                        'Objet': objet.nom,
                        'Victoire': 0
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

    # Afficher les résultats
    print("Récapitulatif des builds:")
    print(df_resultats)
    print("\nStatistiques par objet:")
    print(df_stats_objets)
    print(f"\nTemps total des simulations : {total_time:.2f} secondes")
    print(f"Total de jeux simulés : {total_games_simulees}")

display_simu()


# loguer_x_parties()
