import random
import pandas as pd
import time
import os
import json
import shutil
import multiprocessing
from tqdm import tqdm
import numpy as np
from simu import ordonnanceur
from objets import objets_disponibles
from joueurs import Joueur
from monstres import DonjonDeck
from heros import persos_disponibles

# Nombre de simulations par round d'optimisation
total_simulations = 30000
seuil_pv_essai_fuite = 5
NB_ROUNDS = 100


def _simuler_batch(args):
    """Worker (multiprocessing) : simule nb_sims parties avec des priorites perturbees.

    Retourne des resultats compacts (nom, priorite, victoire) par objet joue,
    plus les compteurs de donjons ponces et le highscore."""
    nb_sims, seed, priorites_objets = args
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)

    resultats = []  # (nom_objet, priorite_jouee, victoire)
    ponces = {3: 0, 4: 0}
    highscore = 0

    for _ in range(nb_sims):
        objets_disponibles_simu = list(objets_disponibles)
        # Reparer tous les objets et attribuer une priorité perturbée (exploration ±30%)
        for o in objets_disponibles_simu:
            o.repare()
            o.priorite = priorites_objets.get(o.nom, 49.5) * (1 + random.uniform(-0.3, 0.3))

        # Initialisation des joueurs avec des personnages aléatoires
        joueurs = []
        nb_joueurs = random.choice([3, 4])
        personnages_assigner = random.sample(persos_disponibles, nb_joueurs)
        for i, nom in enumerate(["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]):
            objets_joueur = random.sample(objets_disponibles_simu, 6)
            for objet in objets_joueur:
                objets_disponibles_simu.remove(objet)
            joueurs.append(Joueur(nom, personnages_assigner[i], objets_joueur))

        vainqueur, _ = ordonnanceur(joueurs, DonjonDeck(), seuil_pv_essai_fuite, objets_disponibles_simu, False)

        if vainqueur and vainqueur.score_final > highscore:
            highscore = vainqueur.score_final

        for joueur in joueurs:
            victoire = 1 if joueur is vainqueur else 0
            for objet in joueur.objets_initiaux:
                resultats.append((objet.nom, objet.priorite, victoire))

        if any(joueur.dans_le_dj for joueur in joueurs):
            ponces[nb_joueurs] += 1

    return resultats, ponces, highscore


def display_simu(r=0, nb_process=None, afficher_tableau=True):
    """Un round d'optimisation : simule, puis reecrit priorites_objets.json
    avec la priorite mediane observee dans les parties gagnees."""
    if nb_process is None:
        nb_process = max(1, (os.cpu_count() or 2) - 1)

    # Lire le fichier JSON une fois au début (il evolue a chaque round)
    with open('priorites_objets.json', 'r') as json_file:
        priorites_objets = json.load(json_file)

    start_time = time.time()

    nb_batches = nb_process * 4 if nb_process > 1 else 1
    base, reste = divmod(total_simulations, nb_batches)
    travaux = [(base + (1 if i < reste else 0), random.randrange(2**31), priorites_objets)
               for i in range(nb_batches)]
    travaux = [t for t in travaux if t[0] > 0]

    resultats_builds = []
    dj_ponces3j = 0
    dj_ponces4j = 0
    highscore_max = 0

    if nb_process > 1:
        with multiprocessing.Pool(nb_process) as pool:
            batches = list(tqdm(pool.imap_unordered(_simuler_batch, travaux),
                                total=len(travaux), desc=f"Round {r + 1}/{NB_ROUNDS} ({nb_process} process)"))
    else:
        batches = [_simuler_batch(t) for t in tqdm(travaux, desc=f"Round {r + 1}/{NB_ROUNDS}")]

    for res, ponces, hs in batches:
        resultats_builds.extend(res)
        dj_ponces3j += ponces[3]
        dj_ponces4j += ponces[4]
        highscore_max = max(highscore_max, hs)

    total_time = time.time() - start_time

    # Convertir les résultats en DataFrame
    df_resultats = pd.DataFrame(resultats_builds, columns=['Objet', 'Priorite', 'Victoire'])
    pd.set_option('display.max_rows', None)

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

    # Afficher les résultats (tableau complet seulement periodiquement, sinon une ligne)
    if afficher_tableau:
        print("\nStatistiques par objet:")
        print(df_stats_objets)
    print(f"Round {r + 1}: {total_time:.1f}s, highscore {highscore_max}, "
          f"ponces 3j {dj_ponces3j / total_simulations * 100:.2f}%, "
          f"4j {dj_ponces4j / total_simulations * 100:.2f}%")


if __name__ == "__main__":
    shutil.copyfile('priorites_objets.json', 'priorites_objets_backup.json')
    for r in range(NB_ROUNDS):
        display_simu(r, afficher_tableau=(r % 10 == 9 or r == NB_ROUNDS - 1))
