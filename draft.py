# -*- coding: utf-8 -*-
import random
import os
import json
import pandas as pd
from tqdm import tqdm

# --- Imports locaux (vérifier les noms de fichiers) ---
from objets import objets_disponibles # Liste globale des instances d'objets
from joueurs import Joueur              # Classe Joueur
from simu import ordonnanceur         # Moteur de simulation de partie
from monstres import DonjonDeck       # Gestion du deck de donjon
from heros import persos_disponibles # Liste globale des instances Perso

# ==============================================
# Configuration
# ==============================================
NB_DRAFT_SIMULATIONS = 10000            # Nombre total de drafts à simuler
NB_GAMES_PER_DRAFT_FOR_STATS = 10000   # Nb parties jouées pour évaluer chaque draft
ITERATIONS_PER_CHOICE_EVALUATION = 100 # Nb simulations dans calculWinrate (précision IA)
ITERATIONS_INITIAL_RANDOM_WINRATE = 1000# Nb simulations pour pré-calcul WR objet
SAVE_INTERVAL = 1                     # Sauvegarder les stats tous les X drafts
STATS_FILENAME = "item_stats_progressive.json" # Fichier de sauvegarde
# ==============================================

# --- Fonctions Helper pour Stats ---
def ensure_item_stats_entry(item_name, stats_dict):
    """Initialise l'entrée pour un objet s'il n'existe pas."""
    if item_name not in stats_dict:
        stats_dict[item_name] = {
            'draft': 0, 'pick': 0, 'win': 0,
            'played': 0, 'death': 0, 'fled': 0, 'cleared': 0
        }

def ensure_perso_stats_entry(perso_name, stats_dict):
    """Initialise l'entrée pour un personnage s'il n'existe pas."""
    if perso_name not in stats_dict:
        stats_dict[perso_name] = {
            'win': 0, 'played': 0, 'death': 0, 'fled': 0, 'cleared': 0
        }

# --- Pré-calcul Winrate Objets (Optionnel, au premier lancement) ---
def calculItemWinrateRandobuild(iter=ITERATIONS_INITIAL_RANDOM_WINRATE):
    """Calcule un winrate initial pour chaque objet basé sur des builds aléatoires."""
    resultats_builds = []
    objets_pool_global_copie = list(objets_disponibles)
    print(f"Calcul WR initial objets sur {iter} simulations...")

    for _ in tqdm(range(iter), desc="Winrate Objets Initiaux"):
        objets_disponibles_simu = list(objets_pool_global_copie); [o.repare() for o in objets_disponibles_simu]
        joueurs = []
        nb_joueurs = random.choice([3, 4])
        noms_joueurs = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]

        if len(persos_disponibles) < nb_joueurs: continue
        personnages_assigner = random.sample(persos_disponibles, nb_joueurs)

        objets_restants_pool = list(objets_disponibles_simu)
        builds_valides = True
        for i, nom in enumerate(noms_joueurs):
            nb_a_prendre = min(6, len(objets_restants_pool))
            if nb_a_prendre < 6: builds_valides = False; break
            objets_joueur = random.sample(objets_restants_pool, nb_a_prendre)
            for objet in objets_joueur: objets_restants_pool.remove(objet)
            perso_instance = personnages_assigner[i]
            joueurs.append(Joueur(nom, perso_instance, objets_joueur))

        if not builds_valides or len(joueurs) != nb_joueurs: continue

        deck = DonjonDeck()
        vainqueur, _ = ordonnanceur(joueurs, deck, 6, objets_restants_pool, False)
        for joueur in joueurs:
            is_winner = 1 if joueur == vainqueur else 0
            for objet in joueur.objets_initiaux:
                resultats_builds.append({'Objet': objet.nom, 'Victoire': is_winner})

    if not resultats_builds: print("WARN: Aucune donnée pour calculItemWinrateRandobuild."); return

    df_resultats = pd.DataFrame(resultats_builds)
    df_stats_objets = df_resultats.groupby('Objet')['Victoire'].agg(['sum', 'count']).reset_index()
    df_stats_objets.columns = ['Objet', 'Victoires', 'Total']
    df_stats_objets['Winrate'] = df_stats_objets.apply(lambda r: (r['Victoires']/r['Total'])*100 if r['Total']>0 else 0, axis=1)

    for obj_g in objets_disponibles:
        wr_series = df_stats_objets.loc[df_stats_objets['Objet'] == obj_g.nom, 'Winrate']
        obj_g.winrate = wr_series.iloc[0] if not wr_series.empty else 0.0

    print("Winrates initiaux assignés.")


# --- Calcul Winrate pour une combinaison et un personnage donné ---
def calculWinrate(combinaison, objets_autres_joueurs, perso_joueur, persos_autres, iterations=ITERATIONS_PER_CHOICE_EVALUATION):
    """Simule des parties pour évaluer une combinaison d'items pour un personnage spécifique."""
    seuil_pv_essai_fuite = 6
    victoires = 0
    if iterations <= 0: return 0.0

    for _ in range(iterations):
        nb_joueurs = 1 + len(persos_autres)
        noms_joueurs = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]
        idx_joueur_teste = random.randrange(nb_joueurs)
        nom_joueur_teste = noms_joueurs[idx_joueur_teste]

        perso_map = {}
        build_map = {}
        perso_map[nom_joueur_teste] = perso_joueur
        build_map[nom_joueur_teste] = list(combinaison)

        idx_autre_assigne = 0
        for i in range(nb_joueurs):
            if i != idx_joueur_teste:
                if idx_autre_assigne < len(persos_autres):
                    perso_map[noms_joueurs[i]] = persos_autres[idx_autre_assigne]
                    build_map[noms_joueurs[i]] = list(objets_autres_joueurs[idx_autre_assigne])
                    idx_autre_assigne += 1
                else:
                     print(f"ERREUR calculWinrate: Manque perso/build autre pour {noms_joueurs[i]}")
                     # Fallback très simple : perso aléatoire, build vide
                     perso_map[noms_joueurs[i]] = random.choice(persos_disponibles)
                     build_map[noms_joueurs[i]] = []


        objets_pool_global = list(objets_disponibles); [o.repare() for o in objets_pool_global]
        objets_assignes_noms = set(o.nom for build in build_map.values() for o in build)
        objets_disponibles_pour_complement = [o for o in objets_pool_global if o.nom not in objets_assignes_noms]

        joueurs = []
        for nom in noms_joueurs:
            perso_instance = perso_map[nom]
            objets_base = build_map[nom]
            for o_base in objets_base: o_base.repare()

            nb_a_completer = max(0, 6 - len(objets_base))
            objets_complement = []
            if nb_a_completer > 0 and objets_disponibles_pour_complement:
                 nb_possible = min(nb_a_completer, len(objets_disponibles_pour_complement))
                 if nb_possible > 0 :
                    objets_complement = random.sample(objets_disponibles_pour_complement, nb_possible)
                    objets_disponibles_pour_complement = [o for o in objets_disponibles_pour_complement if o not in objets_complement]

            objets_finaux_joueur = (objets_base + objets_complement)[:6]
            joueur_cree = Joueur(nom, perso_instance, objets_finaux_joueur)
            joueurs.append(joueur_cree)

        objets_restants = objets_disponibles_pour_complement
        vainqueur, _ = ordonnanceur(joueurs, DonjonDeck(), seuil_pv_essai_fuite, objets_restants, False)

        if vainqueur and vainqueur.nom == nom_joueur_teste:
            victoires += 1

    return victoires / iterations


# --- Choix d'objet par l'IA pendant le draft ---
def choisirObjet(i, objets_joueurs, mains_joueurs, personnages_assigner, log):
    """Évalue les objets dans la main et retourne le meilleur selon calculWinrate."""
    joueur_index = i
    main_actuelle = mains_joueurs[joueur_index]
    if not main_actuelle: return None

    objets_actuels_joueur = objets_joueurs[joueur_index]
    perso_instance_joueur = personnages_assigner[joueur_index]
    persos_autres = [personnages_assigner[j] for j in range(len(objets_joueurs)) if j != joueur_index]
    autres_builds = [objets_joueurs[j] for j in range(len(objets_joueurs)) if j != joueur_index]

    meilleur_objet_instance = None
    meilleur_winrate = -1.0 # Utiliser float pour comparaison

    # Préparer objets pour simulation (une seule fois)
    main_reparee = list(main_actuelle); [o.repare() for o in main_reparee]
    objets_actuels_repares = list(objets_actuels_joueur); [o.repare() for o in objets_actuels_repares]
    autres_builds_repares = [[o for o in build] for build in autres_builds]
    for build in autres_builds_repares: [o.repare() for o in build]

    if log: print(f"  Évaluation pour {perso_instance_joueur.nom}:")
    for objet_test in main_reparee:
        combinaison_test = objets_actuels_repares + [objet_test]
        winrate = calculWinrate(combinaison_test, autres_builds_repares, perso_instance_joueur, persos_autres)
        if log: print(f"    -> Test {objet_test.nom}: {winrate:.2f}")
        if winrate > meilleur_winrate:
            meilleur_winrate = winrate
            meilleur_objet_instance = next((o for o in main_actuelle if o.nom == objet_test.nom), None)

    if meilleur_objet_instance is None and main_actuelle:
        # Fallback : prendre le 1er objet de la main si aucun WR positif trouvé
        meilleur_objet_instance = main_actuelle[0]
        if log: print(f"    -> Fallback (aucun WR>0): choix de {meilleur_objet_instance.nom}")

    return meilleur_objet_instance


# --- Simulation d'un draft complet ---
def draftGame(noms_joueurs, personnages_assigner, log=False):
    """Simule le processus de draft pour un set de joueurs/personnages."""
    objets_disponibles_simu = list(objets_disponibles)
    for o in objets_disponibles_simu: o.repare()
    nb_joueurs = len(noms_joueurs)

    mains_joueurs = []
    for _ in range(nb_joueurs):
        nb_dispo = len(objets_disponibles_simu)
        nb_a_prendre = min(7, nb_dispo)
        if nb_a_prendre <= 0: return None
        main = random.sample(objets_disponibles_simu, nb_a_prendre)
        for objet in main: objets_disponibles_simu.remove(objet)
        mains_joueurs.append(main)
    if any(not main for main in mains_joueurs): return None

    objets_dans_le_draft = [objet for main in mains_joueurs for objet in main]
    objets_joueurs = [[] for _ in range(nb_joueurs)] # Builds finaux
    round_counter = 1

    while any(len(objets) < 6 for objets in objets_joueurs) and any(mains_joueurs):
        if log: print(f"Round {round_counter}")
        main_suivante = [[] for _ in range(nb_joueurs)]
        for i in range(nb_joueurs):
            if len(objets_joueurs[i]) < 6 and mains_joueurs[i]:
                if log: print(f"{noms_joueurs[i]}({personnages_assigner[i].nom}) choisit parmi: {[obj.nom for obj in mains_joueurs[i]]}")
                objet_choisi = choisirObjet(i, objets_joueurs, mains_joueurs, personnages_assigner, log)
                if objet_choisi:
                    objets_joueurs[i].append(objet_choisi)
                    try:
                        original_in_hand = next((o for o in mains_joueurs[i] if o.nom == objet_choisi.nom), None)
                        if original_in_hand: mains_joueurs[i].remove(original_in_hand)
                        else: print(f"WARN draftGame: Retrait {objet_choisi.nom} main {i} échoué")
                    except ValueError: print(f"WARN draftGame: ValueError retrait {objet_choisi.nom} main {i}")
                    if log: print(f"  -> Choix: {objet_choisi.nom}\n")
                else:
                     if log: print(f"  -> Aucun objet choisi.")
            index_receveur = (i + 1) % nb_joueurs
            main_suivante[index_receveur] = mains_joueurs[i] # Passe la main restante
        mains_joueurs = main_suivante
        round_counter += 1
        if not any(mains_joueurs): break

    objets_pris_joueurs = [objet for build in objets_joueurs for objet in build]
    objets_poubelle = [objet for main in mains_joueurs for objet in main if main]
    if log: print("Objets poubelle:", [obj.nom for obj in objets_poubelle])
    objets_disponibles_retour = objets_disponibles_simu + objets_poubelle

    return (objets_dans_le_draft, objets_pris_joueurs, objets_disponibles_retour, noms_joueurs, objets_joueurs)


# --- Simulation d'une partie avec persos/builds donnés ---
def jouerLaGame(objets_disponibles, noms_joueurs, objets_joueurs_listes, personnages_assigner, log):
    """Lance une partie avec une configuration joueur/perso/objets spécifique."""
    joueurs = []
    nb_joueurs = len(noms_joueurs)
    if len(personnages_assigner) != nb_joueurs:
         print("ERREUR jouerLaGame: Incohérence nombre persos.")
         return None, []

    for i, (nom, objets_liste) in enumerate(zip(noms_joueurs, objets_joueurs_listes)):
        perso_instance = personnages_assigner[i]
        objets_pour_joueur = list(objets_liste); [o.repare() for o in objets_pour_joueur]
        joueur_cree = Joueur(nom, perso_instance, objets_pour_joueur)
        joueurs.append(joueur_cree)

    objets_disponibles_simu = list(objets_disponibles); [o.repare() for o in objets_disponibles_simu]
    vainqueur, joueurs_finaux = ordonnanceur(joueurs, DonjonDeck(), 6, objets_disponibles_simu, log)
    return vainqueur, joueurs_finaux


# --- Fonction Principale ---
def simudraftgames(iter=NB_DRAFT_SIMULATIONS, nb_games=NB_GAMES_PER_DRAFT_FOR_STATS, filename=STATS_FILENAME):
    """Lance la simulation complète des drafts et des parties associées."""
    item_stats = {}
    perso_stats = {}
    start_draft = 0

    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f: saved_data = json.load(f)
            item_stats = saved_data.get('item_stats', {})
            perso_stats = saved_data.get('perso_stats', {})
            start_draft = saved_data.get('drafts_completed', 0)
            print(f"Reprise à draft {start_draft + 1}/{iter}.")
        except Exception as e:
            print(f"Erreur chargement {filename}: {e}. Redémarrage.")
            item_stats = {}; perso_stats = {}; start_draft = 0
    else:
        print("Démarrage nouvelle simulation.")

    if start_draft >= iter:
        print("Simulation déjà complétée.")
    else:
        if start_draft == 0:
            calculItemWinrateRandobuild(iter=ITERATIONS_INITIAL_RANDOM_WINRATE)

        print(f"Objectif: {iter} drafts. Démarrage de {start_draft + 1}...")
        for draft_iteration in tqdm(range(start_draft, iter), initial=start_draft, total=iter, desc="Simulation drafts"):
            nb_joueurs = random.choice([3, 4])
            noms = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]
            if len(persos_disponibles) < nb_joueurs: continue
            persos = random.sample(persos_disponibles, nb_joueurs)

            resultat_draft = draftGame(noms, persos, False)
            if resultat_draft is None: continue
            objets_draft, objets_pris, objets_dispo_local, _, builds = resultat_draft

            for obj in objets_draft: ensure_item_stats_entry(obj.nom, item_stats); item_stats[obj.nom]['draft'] += 1
            for obj in objets_pris: ensure_item_stats_entry(obj.nom, item_stats); item_stats[obj.nom]['pick'] += 1

            objets_dispo_simu = list(objets_dispo_local)
            for _ in range(nb_games):
                vainqueur, joueurs_apres = jouerLaGame(objets_dispo_simu, noms, builds, persos, False)
                if joueurs_apres is None: continue

                nom_vainqueur = getattr(vainqueur, 'nom', None)
                for j_final in joueurs_apres:
                    is_win = (j_final.nom == nom_vainqueur)
                    is_dead = not j_final.vivant
                    fled = j_final.fuite_reussie
                    cleared = j_final.dans_le_dj
                    perso_nom = getattr(j_final, 'personnage_nom', 'Inconnu')

                    # Stats Perso
                    ensure_perso_stats_entry(perso_nom, perso_stats)
                    stats_p = perso_stats[perso_nom]
                    stats_p['played'] += 1
                    if is_dead: stats_p['death'] += 1
                    elif fled: stats_p['fled'] += 1
                    elif cleared: stats_p['cleared'] += 1
                    if is_win: stats_p['win'] += 1

                    # Stats Objets
                    for obj in j_final.objets_initiaux:
                        ensure_item_stats_entry(obj.nom, item_stats)
                        stats_i = item_stats[obj.nom]
                        stats_i['played'] += 1
                        if is_dead: stats_i['death'] += 1
                        elif fled: stats_i['fled'] += 1
                        elif cleared: stats_i['cleared'] += 1
                        if is_win: stats_i['win'] += 1

            # Sauvegarde
            num_draft_actuel = draft_iteration + 1
            if num_draft_actuel % SAVE_INTERVAL == 0 or num_draft_actuel == iter:
                 save_data = {"drafts_completed": num_draft_actuel, "item_stats": item_stats, "perso_stats": perso_stats}
                 try:
                     with open(filename, "w", encoding='utf-8') as f: json.dump(save_data, f, indent=4, ensure_ascii=False)
                 except IOError as e: print(f"\nERREUR sauvegarde: {e}")

    # --- Calcul et Affichage final ---
    print("\nCalcul stats finales...")
    final_stats_items = []
    total_picks_overall = sum(stats.get('pick', 0) for stats in item_stats.values())

    for nom, stats in item_stats.items():
        played = stats.get('played', 0)
        drafts = stats.get('draft', 1); picks = stats.get('pick', 0)
        wins = stats.get('win', 0); deaths = stats.get('death', 0)
        fled = stats.get('fled', 0); cleared = stats.get('cleared', 0)
        pickrate = (picks / drafts * 100) if drafts > 0 else 0
        popularity = (picks / total_picks_overall * 100) if total_picks_overall > 0 else 0
        winrate = (wins / played * 100) if played > 0 else 0
        death_rate = (deaths / played * 100) if played > 0 else 0
        fled_rate = (fled / played * 100) if played > 0 else 0
        cleared_rate = (cleared / played * 100) if played > 0 else 0
        final_stats_items.append({
            'Objet': nom, 'Picks': picks, 'Played': played, 'Pick%': pickrate, 'Pop%': popularity,
            'Win%': winrate, 'Death%': death_rate, 'Fled%': fled_rate, 'Clear%': cleared_rate
        })

    sorted_items = sorted(final_stats_items, key=lambda x: x['Win%'], reverse=True)
    print("\n--- Statistiques Objets ---")
    print("-" * 120)
    print(f"{'Objet':<35} {'Picks':<10} {'Played':<10} {'Pick%':<8} {'Pop%':<8} {'Win%':<8} {'Death%':<8} {'Fled%':<8} {'Clear%':<8}")
    print("-" * 120)
    for s in sorted_items: print(f"{s['Objet']:<35} {s['Picks']:<10} {s['Played']:<10} {s['Pick%']:<8.0f} {s['Pop%']:<8.1f} {s['Win%']:<8.2f} {s['Death%']:<8.2f} {s['Fled%']:<8.2f} {s['Clear%']:<8.2f}")
    print("-" * 120)

    final_stats_persos = []
    for nom, stats in perso_stats.items():
        played = stats.get('played', 0)
        wins = stats.get('win', 0); deaths = stats.get('death', 0)
        fled = stats.get('fled', 0); cleared = stats.get('cleared', 0)
        winrate = (wins / played * 100) if played > 0 else 0
        death_rate = (deaths / played * 100) if played > 0 else 0
        fled_rate = (fled / played * 100) if played > 0 else 0
        cleared_rate = (cleared / played * 100) if played > 0 else 0
        final_stats_persos.append({
            'Personnage': nom, 'Played': played, 'Win%': winrate,
            'Death%': death_rate, 'Fled%': fled_rate, 'Clear%': cleared_rate
        })

    sorted_persos = sorted(final_stats_persos, key=lambda x: x['Win%'], reverse=True)
    print("\n--- Statistiques Personnages ---")
    print("-" * 70)
    print(f"{'Personnage':<20} {'Played':<10} {'Win%':<8} {'Death%':<8} {'Fled%':<8} {'Clear%':<8}")
    print("-" * 70)
    for s in sorted_persos: print(f"{s['Personnage']:<20} {s['Played']:<10} {s['Win%']:<8.2f} {s['Death%']:<8.2f} {s['Fled%']:<8.2f} {s['Clear%']:<8.2f}")
    print("-" * 70)

    print(f"\nStats finales basées sur {iter if start_draft >= iter else start_draft} drafts complétés.")
    print(f"Données sauvegardées dans {filename}")

# --- Lancement ---
if __name__ == "__main__":
     script_dir = os.path.dirname(__file__)
     # Change le répertoire courant pour celui du script si possible (pour json)
     if script_dir:
         try:
             os.chdir(script_dir)
             print(f"Répertoire de travail: {os.getcwd()}")
         except Exception as e:
              print(f"WARN: Impossible de changer de répertoire: {e}")

     simudraftgames()