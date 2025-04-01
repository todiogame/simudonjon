# -*- coding: utf-8 -*-
import random
from tqdm import tqdm
from objets import *
from joueurs import Joueur
from simu import   loguer_x_parties, ordonnanceur
from monstres import DonjonDeck
import json
import pandas as pd
import os
from heros import persos_disponibles

# ==============================================
# Configuration Centralisée des Itérations
# ==============================================
NB_DRAFT_SIMULATIONS = 1000
NB_GAMES_PER_DRAFT_FOR_STATS = 10000
ITERATIONS_PER_CHOICE_EVALUATION = 100
ITERATIONS_INITIAL_RANDOM_WINRATE = 100
ITERATIONS_FINAL_WINRATE_CHECK = 1000
# ==============================================
# Configuration Sauvegarde Progressive
# ==============================================
SAVE_INTERVAL = 10
STATS_FILENAME = "item_stats_progressive.json"
# ==============================================

# Fonction helper pour initialiser/vérifier l'entrée d'un item dans les stats
def ensure_item_stats_entry(item_name, stats_dict):
    if item_name not in stats_dict:
        stats_dict[item_name] = {
            'draft': 0, 'pick': 0, 'win': 0,
            'played': 0, 'death': 0, 'fled': 0, 'cleared': 0 # Nouveaux compteurs
        }

def draftGame(log=True):
    # (Code inchangé)
    objets_disponibles_simu = list(objets_disponibles)
    for o in objets_disponibles_simu: o.repare()
    joueurs = []
    nb_joueurs = random.choice([3, 4])
    noms_joueurs = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]
    mains_joueurs = []
    for _ in range(nb_joueurs):
        nb_dispo = len(objets_disponibles_simu)
        nb_a_prendre = min(7, nb_dispo)
        if nb_a_prendre <= 0: return None
        main = random.sample(objets_disponibles_simu, nb_a_prendre)
        for objet in main: objets_disponibles_simu.remove(objet)
        mains_joueurs.append(main)
    objets_dans_le_draft = [objet for main in mains_joueurs for objet in main]
    objets_joueurs = [[] for _ in range(nb_joueurs)]
    round_counter = 1
    while any(len(objets) < 6 for objets in objets_joueurs) and any(mains_joueurs):
        if log: print(f"Round {round_counter}")
        choix_joueurs = []
        main_suivante = [[] for _ in range(nb_joueurs)]
        for i in range(nb_joueurs):
            if len(objets_joueurs[i]) < 6 and mains_joueurs[i]:
                if log: print(f"{noms_joueurs[i]} doit choisir entre ca: {[obj.nom for obj in mains_joueurs[i]]}")
                if log and len(objets_joueurs[i]): print(f"{noms_joueurs[i]} a deja: {[obj.nom for obj in objets_joueurs[i]]}\n")
                objet_choisi = choisirObjet(i, objets_joueurs, mains_joueurs, log)
                if objet_choisi:
                    objets_joueurs[i].append(objet_choisi)
                    try:
                        original_in_hand = next((o for o in mains_joueurs[i] if o.nom == objet_choisi.nom), None)
                        if original_in_hand: mains_joueurs[i].remove(original_in_hand)
                        else: print(f"ERREUR: Retrait {objet_choisi.nom} impossible (main {i})")
                    except ValueError: print(f"ERREUR Value: Retrait {objet_choisi.nom} impossible (main {i})")
                    choix_joueurs.append((i, objet_choisi))
                    if log: print(f"{noms_joueurs[i]} choisit: {objet_choisi.nom}\n")
                else:
                     if log: print(f"{noms_joueurs[i]} n'a pas pu choisir.")
            index_receveur = (i + 1) % nb_joueurs
            main_suivante[index_receveur] = mains_joueurs[i]
        mains_joueurs = main_suivante
        round_counter += 1
        if not any(mains_joueurs):
            if any(len(objets) < 6 for objets in objets_joueurs):
                 if log: print("AVERTISSEMENT: Draft terminé prématurément.")
            break
    objets_pris_joueurs =  [objet for j in objets_joueurs for objet in j]
    objets_poubelle = [objet for main in mains_joueurs for objet in main if main]
    if log: print("Objets poubelle :", [obj.nom for obj in objets_poubelle])
    objets_disponibles_retour = objets_disponibles_simu + objets_poubelle
    return (objets_dans_le_draft, objets_pris_joueurs, objets_disponibles_retour, noms_joueurs, objets_joueurs,)


def calculWRfinal(objets_disponibles, noms_joueurs, objets_joueurs, log, iter=ITERATIONS_FINAL_WINRATE_CHECK):
    # (Code inchangé)
    win_counts = {}
    for _ in range(iter):
        joueurs = []
        for nom, objets in zip(noms_joueurs, objets_joueurs):
            for o in objets: o.repare()
            joueurs.append(Joueur(nom, random.randint(2, 4), objets))
        objets_disponibles_simu = list(objets_disponibles); [o.repare() for o in objets_disponibles_simu]
        vainqueur, _ = ordonnanceur(joueurs, DonjonDeck(), 6, objets_disponibles_simu, False)
        if vainqueur: win_counts[vainqueur.nom] = win_counts.get(vainqueur.nom, 0) + 1
    if log: print(f"Probas de win la game:")
    for j, count in win_counts.items():
        if iter > 0: print(f"{j}: {count / iter:.2%}")
        else: print(f"{j}: N/A (0 itération)")


def jouerLaGame(objets_disponibles, noms_joueurs, objets_joueurs_listes, log):
    joueurs = []
    nb_joueurs = len(noms_joueurs)

    # --- Assignation des Personnages ---
    if len(persos_disponibles) < nb_joueurs:
        print(f"ERREUR dans jouerLaGame: Pas assez de personnages ({len(persos_disponibles)}) pour {nb_joueurs} joueurs.")
        # Que faire ici? Retourner None ? Lever une exception?
        # Pour l'instant, retournons None pour indiquer un échec
        return None, []
    # Assigner une instance unique et aléatoire à chaque joueur
    personnages_assigner = random.sample(persos_disponibles, nb_joueurs)
    # --- Fin Assignation Personnages ---

    # Créer les joueurs avec leur personnage et leurs objets
    for i, (nom, objets_liste) in enumerate(zip(noms_joueurs, objets_joueurs_listes)):
        # Récupérer l'instance Perso assignée
        perso_instance = personnages_assigner[i]
        # Préparer et réparer les objets pour ce joueur
        objets_pour_joueur = list(objets_liste)
        for o in objets_pour_joueur: o.repare()

        # --- Création du Joueur avec le personnage ---
        # Appelle Joueur(nom, perso_instance, objets)
        joueur_cree = Joueur(nom, perso_instance, objets_pour_joueur)
        joueurs.append(joueur_cree)
        # --- Fin Création Joueur ---

    # Préparer les objets non utilisés pour l'ordonnanceur
    objets_disponibles_simu = list(objets_disponibles); [o.repare() for o in objets_disponibles_simu]

    # Lancer la simulation de partie
    # Le seuil de fuite est fixé à 6 ici (cohérent avec calculWinrate)
    vainqueur, joueurs_finaux = ordonnanceur(joueurs, DonjonDeck(), 6, objets_disponibles_simu, log)

    # Retourner le résultat de la partie
    return vainqueur, joueurs_finaux


def choisirObjet(i, objets_joueurs, mains_joueurs, log):
    # (Code inchangé)
    joueur_index = i
    main_actuelle = mains_joueurs[joueur_index]
    objets_actuels_joueur = objets_joueurs[joueur_index]
    if not main_actuelle: return None
    meilleur_objet_instance = None
    meilleur_winrate = -1
    autres_joueurs_builds = [objets_joueurs[j] for j in range(len(objets_joueurs)) if j != joueur_index]
    main_reparee = [o for o in main_actuelle]; [o.repare() for o in main_reparee]
    objets_actuels_repares = [o for o in objets_actuels_joueur]; [o.repare() for o in objets_actuels_repares]
    autres_builds_repares = []
    for build in autres_joueurs_builds:
        build_repare = [o for o in build]; [o.repare() for o in build_repare]
        autres_builds_repares.append(build_repare)
    for objet_test in main_reparee:
        combinaison_test = objets_actuels_repares + [objet_test]
        winrate = calculWinrate(combinaison_test, autres_builds_repares)
        if log: print(f"  -> Test {objet_test.nom}: {winrate:.2f}", end="\n")
        if winrate > meilleur_winrate:
            meilleur_winrate = winrate
            meilleur_objet_instance = next((o for o in main_actuelle if o.nom == objet_test.nom), None)
    if meilleur_objet_instance is None and main_actuelle:
         meilleur_objet_instance = main_actuelle[0]
         if log: print(f"  -> Fallback: choix de {meilleur_objet_instance.nom}")
    return meilleur_objet_instance


def calculWinrate(combinaison, objets_autres_joueurs, iterations=ITERATIONS_PER_CHOICE_EVALUATION):
    seuil_pv_essai_fuite = 6 # Utiliser un seuil cohérent
    victoires = 0

    if iterations <= 0: return 0 # Éviter division par zéro

    for _ in range(iterations):
        # Déterminer le nombre de joueurs pour cette simulation
        nb_joueurs = len(objets_autres_joueurs) + 1
        noms_joueurs = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]
        # Choisir aléatoirement quel joueur aura la 'combinaison' testée
        joueur_surveille = random.choice(noms_joueurs)

        # --- Assignation des Personnages ---
        if len(persos_disponibles) < nb_joueurs:
            # Gérer l'erreur si pas assez de personnages définis
            print(f"ERREUR dans calculWinrate: Pas assez de personnages ({len(persos_disponibles)}) pour {nb_joueurs} joueurs.")
            # Retourner 0 ou une valeur par défaut ? Retournons 0 pour indiquer un échec potentiel.
            return 0 # Ou raise Exception("Pas assez de personnages")
        # Assigner une instance unique et aléatoire à chaque slot de joueur
        personnages_assigner_instances = random.sample(persos_disponibles, nb_joueurs)
        # Créer un mapping nom -> instance perso pour faciliter la récupération
        perso_map = {noms_joueurs[k]: personnages_assigner_instances[k] for k in range(nb_joueurs)}
        # --- Fin Assignation Personnages ---

        # Préparation des objets disponibles pour compléter les builds
        objets_pool_global = list(objets_disponibles); [o.repare() for o in objets_pool_global]
        objets_assignes_noms = set(o.nom for o in combinaison)
        for autre_build in objets_autres_joueurs: objets_assignes_noms.update(o.nom for o in autre_build)
        objets_disponibles_pour_complement = [o for o in objets_pool_global if o.nom not in objets_assignes_noms]

        joueurs = []
        idx_autres = 0
        # Création des joueurs
        for nom in noms_joueurs:
            # Récupérer l'instance Perso assignée
            perso_instance = perso_map[nom]

            # Déterminer les objets de base du joueur
            objets_base = []
            if nom == joueur_surveille:
                objets_base = list(combinaison)
            else:
                # Prendre le build connu des autres joueurs s'il existe
                if idx_autres < len(objets_autres_joueurs):
                    objets_base = list(objets_autres_joueurs[idx_autres])
                    idx_autres += 1
                # Si on manque d'info sur les autres (draft incomplet?), objets_base reste vide ici

            # Réparer les objets de base (au cas où ils seraient passés non réparés)
            for o_base in objets_base: o_base.repare()

            # Compléter le build à 6 objets
            nb_a_completer = max(0, 6 - len(objets_base))
            objets_complement = []
            if nb_a_completer > 0 and objets_disponibles_pour_complement:
                 nb_possible = min(nb_a_completer, len(objets_disponibles_pour_complement))
                 objets_complement = random.sample(objets_disponibles_pour_complement, nb_possible)
                 # Retirer les objets utilisés du pool pour éviter duplicats entre joueurs
                 objets_disponibles_pour_complement = [o for o in objets_disponibles_pour_complement if o not in objets_complement]

            objets_finaux_joueur = objets_base + objets_complement
            # S'assurer qu'on n'a pas plus de 6 objets (ne devrait pas arriver)
            if len(objets_finaux_joueur) > 6: objets_finaux_joueur = objets_finaux_joueur[:6]

            # --- Création du Joueur avec le personnage ---
            # Appelle Joueur(nom, perso_instance, objets)
            joueur_cree = Joueur(nom, perso_instance, objets_finaux_joueur)
            joueurs.append(joueur_cree)
            # --- Fin Création Joueur ---

        # Les objets restants sont passés à l'ordonnanceur
        objets_restants_pour_ordonnanceur = objets_disponibles_pour_complement

        # Exécution de la simulation de partie
        # Note: S'assurer que DonjonDeck() crée un nouveau deck frais
        vainqueur, _ = ordonnanceur(joueurs, DonjonDeck(), seuil_pv_essai_fuite, objets_restants_pour_ordonnanceur, False)

        # Compter la victoire
        if vainqueur and vainqueur.nom == joueur_surveille:
            victoires += 1

    # Calcul final du winrate
    winrate = victoires / iterations # iterations > 0 vérifié au début
    return winrate
def calculItemWinrateRandobuild(iter=ITERATIONS_INITIAL_RANDOM_WINRATE ):
    # (Code inchangé)
    resultats_builds = []
    objets_pool_global_copie = list(objets_disponibles)
    for _ in tqdm(range(iter), desc="Pré-calcul Winrate Objets (Builds Aléatoires)"):
        objets_disponibles_simu = list(objets_pool_global_copie); [o.repare() for o in objets_disponibles_simu]
        joueurs = []
        nb_joueurs = random.choice([3, 4])
        objets_restants_pool = list(objets_disponibles_simu)
        for nom in ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]:
            nb_a_prendre = min(6, len(objets_restants_pool))
            if nb_a_prendre < 6: continue
            objets_joueur = random.sample(objets_restants_pool, nb_a_prendre)
            for objet in objets_joueur: objets_restants_pool.remove(objet)
            joueurs.append(Joueur(nom, random.randint(2, 4), objets_joueur))
        if len(joueurs) != nb_joueurs: continue
        deck = DonjonDeck()
        vainqueur, _ = ordonnanceur(joueurs, deck, 6, objets_restants_pool, False)
        for joueur in joueurs:
            for objet in joueur.objets_initiaux: resultats_builds.append({'Objet': objet.nom,'Build': ', '.join(o.nom for o in joueur.objets_initiaux),'Victoire': 1 if joueur == vainqueur else 0,})
    if not resultats_builds: print("Aucune donnée collectée pendant calculItemWinrateRandobuild."); return
    df_resultats = pd.DataFrame(resultats_builds)
    pd.set_option('display.max_rows', 200)
    df_stats_objets = df_resultats.groupby('Objet')['Victoire'].agg(['sum', 'count']).reset_index()
    df_stats_objets.columns = ['Objet', 'Victoires', 'Total']
    df_stats_objets['Winrate'] = df_stats_objets.apply(lambda row: (row['Victoires'] / row['Total']) * 100 if row['Total'] > 0 else 0, axis=1)
    for objet_global in objets_disponibles:
        winrate_series = df_stats_objets.loc[df_stats_objets['Objet'] == objet_global.nom, 'Winrate']
        if not winrate_series.empty: objet_global.winrate = winrate_series.iloc[0]


def simudraftgames(iter=NB_DRAFT_SIMULATIONS, nb_games=NB_GAMES_PER_DRAFT_FOR_STATS, filename=STATS_FILENAME):
    item_stats = {}
    start_draft = 0
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
                item_stats = saved_data.get('item_stats', {})
                start_draft = saved_data.get('drafts_completed', 0)
                print(f"Fichier stats trouvé. Reprise à draft {start_draft + 1}.")
        except (json.JSONDecodeError, KeyError, FileNotFoundError, UnicodeDecodeError) as e:
            print(f"Erreur chargement {filename}: {e}. Démarrage.")
            item_stats = {}; start_draft = 0
    else:
        print("Aucun fichier stats trouvé. Démarrage.")

    if start_draft == 0:
         print("Exécution pré-calcul winrates initiaux...")
         calculItemWinrateRandobuild(iter=ITERATIONS_INITIAL_RANDOM_WINRATE)
         print("Pré-calcul terminé.")
    else:
         print("Pré-calcul ignoré car reprise.")

    print(f"Objectif total: {iter} drafts.")
    for draft_iteration in tqdm(range(start_draft, iter), initial=start_draft, total=iter, desc="Simulation des drafts"):
        resultat = draftGame(False)
        if resultat is None: print(f"Erreur draft {draft_iteration + 1}, skip."); continue
        objets_dans_le_draft, objets_pris_joueurs, objets_disponibles_local, noms_joueurs, objets_joueurs_listes = resultat
        set_objets_dans_le_draft = set(o.nom for o in objets_dans_le_draft)
        set_objets_pris_joueurs = set(o.nom for o in objets_pris_joueurs)

        for objet_nom in set_objets_dans_le_draft:
            ensure_item_stats_entry(objet_nom, item_stats)
            item_stats[objet_nom]['draft'] += 1
        for objet_nom in set_objets_pris_joueurs:
            ensure_item_stats_entry(objet_nom, item_stats)
            item_stats[objet_nom]['pick'] += 1

        # Simulation des parties
        for _ in range(nb_games):
            # --- MODIFICATION IMPORTANTE ICI ---
            vainqueur, joueurs_apres_partie = jouerLaGame(objets_disponibles_local, noms_joueurs, objets_joueurs_listes, False)

            for joueur_final in joueurs_apres_partie:
                # Est-ce le vainqueur ?
                is_winner = (vainqueur is not None and joueur_final.nom == vainqueur.nom)
                # Issues
                is_dead = not joueur_final.vivant
                did_flee = joueur_final.fuite_reussie
                did_clear = joueur_final.dans_le_dj # Encore dans le donjon à la fin = "poncé"

                # Mise à jour des stats pour chaque objet initial du joueur
                for objet in joueur_final.objets_initiaux:
                    ensure_item_stats_entry(objet.nom, item_stats)
                    item_stats[objet.nom]['played'] += 1
                    if is_dead: item_stats[objet.nom]['death'] += 1
                    elif did_flee: item_stats[objet.nom]['fled'] += 1
                    elif did_clear: item_stats[objet.nom]['cleared'] += 1
                    # Incrémenter win si le joueur est le vainqueur
                    if is_winner:
                        item_stats[objet.nom]['win'] += 1
            # --- FIN MODIFICATION IMPORTANTE ---

        # --- Sauvegarde progressive ---
        num_draft_actuel = draft_iteration + 1
        if num_draft_actuel % SAVE_INTERVAL == 0 or num_draft_actuel == iter:
             save_data = {
                 "drafts_completed": num_draft_actuel,
                 # Pas besoin de nb_games_per_draft, on utilise 'played'
                 "item_stats": item_stats
             }
             try:
                 with open(filename, "w", encoding='utf-8') as json_file:
                     json.dump(save_data, json_file, indent=4, ensure_ascii=False)
             except IOError as e: print(f"\nERREUR sauvegarde stats: {e}")

    # --- Calcul et Affichage final ---
    print("\nSimulation terminée. Calcul stats finales...")
    final_stats_list = []
    for objet_nom, stats in item_stats.items():
        played_count = stats.get('played', 0)
        win_count = stats.get('win', 0); death_count = stats.get('death', 0)
        fled_count = stats.get('fled', 0); cleared_count = stats.get('cleared', 0)
        pick_count = stats.get('pick', 0); draft_count = stats.get('draft', 1)
        pickrate = (pick_count / draft_count * 100) if draft_count > 0 else 0
        winrate = (win_count / played_count * 100) if played_count > 0 else 0
        death_rate = (death_count / played_count * 100) if played_count > 0 else 0
        fled_rate = (fled_count / played_count * 100) if played_count > 0 else 0
        cleared_rate = (cleared_count / played_count * 100) if played_count > 0 else 0
        final_stats_list.append({'Objet': objet_nom, 'Picks': pick_count, 'Played': played_count,'Pickrate%': pickrate, 'Winrate%': winrate, 'Death%': death_rate,'Fled%': fled_rate, 'Cleared%': cleared_rate})
    sorted_items_stats = sorted(final_stats_list, key=lambda x: x['Winrate%'], reverse=True)
    print("-" * 110)
    print(f"{'Objet':<35} {'Picks':<10} {'Played':<10} {'Pick%':<8} {'Win%':<8} {'Death%':<8} {'Fled%':<8} {'Clear%':<8}")
    print("-" * 110)
    for stats in sorted_items_stats: print(f"{stats['Objet']:<35} {stats['Picks']:<10} {stats['Played']:<10} {stats['Pickrate%']:<8.0f} {stats['Winrate%']:<8.2f} {stats['Death%']:<8.2f} {stats['Fled%']:<8.2f} {stats['Cleared%']:<8.2f}")
    print("-" * 110)
    print(f"\nStats finales basées sur {iter} drafts simulés.")
    print(f"Données brutes sauvegardées dans {filename}")

# Lancement
simudraftgames()