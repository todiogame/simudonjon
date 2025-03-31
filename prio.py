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

def display_simu(r=0):
        
    # Lire le fichier JSON une fois au début
    with open('priorites_objets.json', 'r') as json_file:
        priorites_objets = json.load(json_file)
        
    # Initialisation des résultats
    resultats_builds = []
    highscore_max = 0
    dj_ponces3j=0
    dj_ponces4j=0
    # Mesurer le temps de simulation
    start_time = time.time()

    # Simuler les builds aléatoires et stocker les résultats
    for _ in tqdm(range(total_simulations), desc="Simulation des builds"):
        # Créer une copie de la liste des objets disponibles pour cette simulation
        objets_disponibles_simu = list(objets_disponibles)
        # Reparer tous les objets et attribuer une priorité aléatoire
        for o in objets_disponibles_simu:
            o.repare()
            o.priorite = priorites_objets.get(o.nom, 49.5) * (1 + random.uniform(-0.3, 0.3))
            # o.priorite = min(100, max(0, priorites_objets.get(o.nom, 49.5) + random.uniform(-20, 20)))

        # Initialisation des joueurs avec des points de vie aléatoires entre 2 et 4
        joueurs = []
        nb_joueurs = random.choice([3, 4])
        for nom in ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]:
            objets_joueur = random.sample(objets_disponibles_simu, 6)
            for objet in objets_joueur:
                objets_disponibles_simu.remove(objet)
            joueurs.append(Joueur(nom, random.randint(2, 4), objets_joueur))

        # Création de la copie des joueurs et des cartes
        deck = DonjonDeck()

        # Exécution de l'ordonnanceur sans afficher les logs
        vainqueur, _ = ordonnanceur(joueurs, deck, seuil_pv_essai_fuite, objets_disponibles_simu, False)

        # Mise à jour du highscore max et du meilleur vainqueur
        if vainqueur and vainqueur.score_final > highscore_max:
            highscore_max = vainqueur.score_final
        
        # Mise à jour des statistiques
        for joueur in joueurs:
            for objet in joueur.objets_initiaux:
                resultats_builds.append({
                    'Objet': objet.nom,
                    'Priorite': objet.priorite,
                    'Build': ', '.join(o.nom for o in joueur.objets_initiaux),
                    'Victoire': 1 if joueur == vainqueur else 0,
                }),
        if any(joueur.dans_le_dj for joueur in joueurs): 
            if nb_joueurs == 3: dj_ponces3j+=1
            if nb_joueurs == 4: dj_ponces4j+=1

    # Mesurer le temps de simulation
    end_time = time.time()
    total_time = end_time - start_time

    # Convertir les résultats en DataFrame
    df_resultats = pd.DataFrame(resultats_builds)
    pd.set_option('display.max_rows', 200)

    # Calculer le nombre total de victoires et de défaites pour chaque objet
    df_stats_objets = df_resultats.groupby('Objet')['Victoire'].agg(['sum', 'count']).reset_index()
    df_stats_objets.columns = ['Objet', 'Victoires', 'Total']

    # Calculer le winrate pour chaque objet
    df_stats_objets['Winrate'] = (df_stats_objets['Victoires'] / df_stats_objets['Total']) * 100
    df_stats_objets = df_stats_objets.sort_values(by='Winrate', ascending=False)
     
     # Calculer la priorité médiane et moyenne parmi les jeux joués
    priorite_stats = df_resultats.groupby('Objet')['Priorite'].agg(['median', 'mean']).reset_index()
    priorite_stats.columns = ['Objet', 'Priorite_mediane', 'Priorite_moyenne']

    # Calculer la priorité médiane et moyenne parmi les jeux gagnés
    priorite_stats_gagnees = df_resultats[df_resultats['Victoire'] == 1].groupby('Objet')['Priorite'].agg(['median', 'mean']).reset_index()
    priorite_stats_gagnees.columns = ['Objet', 'Priorite_mediane_gagnee', 'Priorite_moyenne_gagnee']

    # Fusionner les priorités médianes et moyennes avec les statistiques des objets
    df_stats_objets = df_stats_objets.merge(priorite_stats, on='Objet')
    df_stats_objets = df_stats_objets.merge(priorite_stats_gagnees, on='Objet')

    # Calculer la différence de moyenne
    df_stats_objets['Diff_moyenne'] = df_stats_objets['Priorite_moyenne_gagnee'] - df_stats_objets['Priorite_moyenne']

    # Trier les statistiques par différence de moyenne
    df_stats_objets = df_stats_objets.sort_values(by='Diff_moyenne', ascending=False)

    # Sélectionner les colonnes pertinentes pour le JSON
    df_priorites = df_stats_objets[['Objet', 'Priorite_mediane_gagnee']]
    df_priorites_sorted = df_priorites.sort_values(by='Priorite_mediane_gagnee')
    # Convertir en dictionnaire et exporter en JSON
    priorites_dict = dict(zip(df_priorites_sorted['Objet'], df_priorites_sorted['Priorite_mediane_gagnee']))
    with open('priorites_objets.json', 'w') as json_file:
        json.dump(priorites_dict, json_file, indent=4)
    shutil.copyfile('priorites_objets.json', f'backupfile_{r}.json')
    
    
    
    # Afficher les résultats
    print("\nStatistiques par objet:")
    print(df_stats_objets)
    print(f"\nTemps total des simulations : {total_time:.2f} secondes")
    print(f"Pourcentage de donjons ponces a 3j : {dj_ponces3j / total_simulations* 100:.2f}%")
    print(f"Pourcentage de donjons ponces a 4j : {dj_ponces4j / total_simulations* 100:.2f}%")


# Nombre de simulations souhaitées
total_simulations = 30000
seuil_pv_essai_fuite=5

shutil.copyfile('priorites_objets.json', f'priorites_objets_backup.json')
for r in range(100):
    display_simu(r)
