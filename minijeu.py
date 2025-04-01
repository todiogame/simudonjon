# Fichier: minijeu.py
# -*- coding: utf-8 -*-
import random
import os
import sys
import json

# --- Imports depuis ton projet (Noms Corrigés) ---
try:
    from objets import objets_disponibles
    from heros import persos_disponibles
    from draft import calculWinrate
    from joueurs import Joueur
except ImportError as e:
    print(f"Erreur d'importation des modules du projet: {e}")
    print("Vérifiez les noms et l'accessibilité des fichiers :")
    print("objets.py, heros.py, joueurs.py, simu.py, monstres.py, draft.py")
    sys.exit(1)

# --- Chargement et Préparation des Descriptions ---
item_visuals_data = {}
try:
    script_dir_vis = os.path.dirname(os.path.abspath(__file__)) # Utiliser chemin absolu
    visuals_path = os.path.join(script_dir_vis, 'item_visuals.json')
    with open(visuals_path, 'r', encoding='utf-8') as f:
        raw_visuals = json.load(f)
    item_visuals_data = {name.lower(): data for name, data in raw_visuals.items()}
    print("Descriptions des objets chargées.")
except FileNotFoundError:
    print("WARN: Fichier item_visuals.json non trouvé.")
except json.JSONDecodeError:
    print("WARN: Erreur de lecture de item_visuals.json.")
except Exception as e:
    print(f"WARN: Erreur chargement item_visuals.json: {e}")

# --- Configuration & Constantes ANSI ---
ITERATIONS_MINIJEU = 500
OPPONENT_NAMES = ["Sagarex", "Francis", "Mastho", "Mr.Adam", "Diouze", "Nicoco"]
COLOR_MAP = {1: "\033[91m", 2: "\033[92m", 3: "\033[94m", 4: "\033[95m", 5: "\033[93m"}
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"

# --- Fonctions Helper ---
def clean_description(desc_html, use_ansi_bold=True, newline_replace=" | "):
    """Nettoie la description : remplace <b> par ANSI, remplace \\n."""
    if not desc_html: return ""
    desc = desc_html.replace("<b>", ANSI_BOLD if use_ansi_bold else "").replace("</b>", ANSI_RESET if use_ansi_bold else "")
    desc = desc.replace("\\n", newline_replace)
    return desc

def get_item_display_info(item_obj, use_ansi_bold_desc=True, newline_replace_desc=" | "):
    """Récupère prefixe, nom formaté (couleur), description formatée (gras)."""
    prefix = "⚡ " if getattr(item_obj, 'actif', False) else "  "
    visual_data = item_visuals_data.get(item_obj.nom.lower(), {})
    color_code = visual_data.get('color_code')
    ansi_color = COLOR_MAP.get(color_code, "")
    color_reset = ANSI_RESET if ansi_color else ""
    item_name_fmt = f"{ansi_color}{item_obj.nom}{color_reset}"
    description_html = visual_data.get('description')
    description_fmt = clean_description(description_html, use_ansi_bold_desc, newline_replace_desc)
    return prefix, item_name_fmt, description_fmt

def format_opponent_item_list(item_list):
    """Formate liste objets opposants ([emoji][nom coloré])."""
    if not item_list: return "Aucun"
    formatted = []
    for item in item_list:
        prefix, name_fmt, _ = get_item_display_info(item) # Desc non utilisée
        # Enlève l'espace si pas d'emoji pour compacter un peu
        formatted.append(f"{prefix.strip() if not prefix.strip() else prefix}{name_fmt}")
    return ', '.join(formatted)

# --- Génération du Scénario (Logique 7 items) ---
def generer_scenario():
    """Crée un scénario de draft aléatoire (7 items total, 2-6 choix)."""
    if not persos_disponibles or not objets_disponibles: return None
    perso_joueur = random.choice(persos_disponibles)
    objets_pool = list(objets_disponibles); random.shuffle(objets_pool)
    total_items_round = 7
    if len(objets_pool) < total_items_round: return None
    nb_objets_main = random.randint(2, 6)
    nb_objets_deja_pris = total_items_round - nb_objets_main
    objets_actuels = objets_pool[:nb_objets_deja_pris]
    main_actuelle = objets_pool[nb_objets_deja_pris:total_items_round]
    objets_restants = objets_pool[total_items_round:]
    objets_des_opposants = []; nb_opposants = 3
    items_needed = nb_opposants * nb_objets_deja_pris
    # if len(objets_restants) < items_needed: print("WARN: Pas assez objets restants pour opposants")
    for _ in range(nb_opposants):
        take_count = min(nb_objets_deja_pris, len(objets_restants))
        objets_opp = objets_restants[:take_count]
        objets_des_opposants.append(objets_opp)
        objets_restants = objets_restants[take_count:]
    for o_list in [objets_actuels, main_actuelle] + objets_des_opposants:
        for o in o_list:
             if hasattr(o, 'repare'): o.repare()
    return perso_joueur, objets_actuels, main_actuelle, objets_des_opposants

# --- Calcul du Meilleur Choix ---
def trouver_meilleur_choix(perso_joueur, objets_actuels, main_actuelle):
    """Utilise calculWinrate pour trouver le meilleur objet et stocke tous les WR."""
    meilleur_objet = None; meilleur_winrate = -1.0; winrates_calcules = {}
    nb_opposants = 3; persos_autres = []; objets_autres_joueurs = [[] for _ in range(nb_opposants)]
    pool_opposants = [p for p in persos_disponibles if p.nom != perso_joueur.nom]
    if len(pool_opposants) >= nb_opposants: persos_autres = random.sample(pool_opposants, nb_opposants)
    else: persos_autres = random.sample(persos_disponibles, nb_opposants)
    objets_actuels_repares = list(objets_actuels); [o.repare() for o in objets_actuels_repares if hasattr(o,'repare')]
    print(f"\nCalcul du meilleur choix ({ITERATIONS_MINIJEU} itérations par objet)...")
    for objet_test in main_actuelle:
        if hasattr(objet_test, 'repare'): objet_test.repare()
        combinaison_test_reparee = objets_actuels_repares + [objet_test]
        try:
            winrate = calculWinrate(combinaison_test_reparee, objets_autres_joueurs,
                                    perso_joueur, persos_autres, iterations=ITERATIONS_MINIJEU)
            winrates_calcules[objet_test.nom] = winrate
            if winrate > meilleur_winrate:
                meilleur_winrate = winrate; meilleur_objet = objet_test
        except Exception as e:
            print(f"\nERREUR pendant calculWinrate pour {objet_test.nom}: {e}")
            winrates_calcules[objet_test.nom] = -1
    if meilleur_objet is None and main_actuelle: # Fallback
        meilleur_objet = main_actuelle[0]
        meilleur_winrate = winrates_calcules.get(meilleur_objet.nom, -1.0)
    return meilleur_objet, meilleur_winrate, winrates_calcules

# --- Boucle Principale du Jeu ---
if __name__ == "__main__":
    print("--- Mini-Jeu d'entraînement au Draft ---")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir:
        try: os.chdir(script_dir); print(f"Répertoire de travail: {os.getcwd()}")
        except Exception as e: print(f"WARN: Chgt répertoire: {e}")
    available_opponent_names = list(OPPONENT_NAMES)

    while True:
        print("\n=========================================")
        print("Nouvelle situation de draft :")
        scenario = generer_scenario()
        if scenario is None: print("Erreur génération scénario."); break
        perso_joueur, objets_actuels, main_actuelle, objets_des_opposants = scenario

        print("Analyse des options en cours...")
        resultat_calcul = trouver_meilleur_choix(perso_joueur, objets_actuels, main_actuelle)
        if resultat_calcul[0] is None: print("Erreur calcul meilleur choix."); continue
        meilleur_objet_calcule, meilleur_wr_calcule, winrates_calcules = resultat_calcul

        # --- Affichage Scénario ---
        # 1. Opposants
        noms_opposants = random.sample(available_opponent_names, len(objets_des_opposants))
        print("\nObjets des adversaires :")
        for i, opp_objets in enumerate(objets_des_opposants):
            print(f"  {noms_opposants[i]:<10}: {format_opponent_item_list(opp_objets)}")

        # 2. Joueur (gras ANSI, description multiligne AVEC gras ANSI)
        pv_total_joueur = perso_joueur.pv_bonus + sum(getattr(o, 'pv_bonus', 0) for o in objets_actuels)
        print(f"\n{ANSI_BOLD}Votre personnage : {perso_joueur.nom} ({perso_joueur.pv_bonus} PV base, {pv_total_joueur} PV actuels, Fuite: {perso_joueur.modificateur_de:+d}){ANSI_RESET}")
        print(f"{ANSI_BOLD}Objets déjà choisis :{ANSI_RESET}")
        if objets_actuels:
            for obj in objets_actuels:
                prefix, name_fmt, description_fmt = get_item_display_info(obj, use_ansi_bold_desc=True, newline_replace_desc=f"\n      {ANSI_RESET}└─ ") # Desc avec reset avant indent
                print(f"  {ANSI_BOLD}{prefix}{name_fmt}{ANSI_RESET}")
                if description_fmt: print(f"    {ANSI_RESET}└─ {description_fmt}")
        else: print("  Aucun")

        # 3. Choix possibles pour le joueur (liste numérotée)
        print("\nChoisissez le MEILLEUR objet parmi :")
        if not main_actuelle: print("Erreur: Aucune option à choisir."); continue
        for i, obj in enumerate(main_actuelle):
            prefix, name_fmt, description_fmt = get_item_display_info(obj, use_ansi_bold_desc=True, newline_replace_desc=f"\n      {ANSI_RESET}└─ ") # Desc avec reset avant indent
            # Affichage Numéro, Nom (gras+couleur), puis Desc (gras+couleur+indent)
            print(f"\n{i+1}: {ANSI_BOLD}{prefix}{name_fmt}{ANSI_RESET}")
            if description_fmt: print(f"    {ANSI_RESET}└─ {description_fmt}")

        # 4. Obtenir Choix Joueur (via input numéro)
        choix_joueur_instance = None
        while choix_joueur_instance is None:
            try:
                choix_str = input(f"\nVotre choix (1-{len(main_actuelle)}) ? ")
                choix_idx = int(choix_str) - 1
                if 0 <= choix_idx < len(main_actuelle):
                    choix_joueur_instance = main_actuelle[choix_idx]
                else: print("Choix invalide.")
            except ValueError: print("Entrez un numéro valide.")
            except EOFError: print("\nEntrée interrompue."); sys.exit(0) # Gérer Ctrl+D
            except KeyboardInterrupt: print("\nArrêt demandé."); sys.exit(0) # Gérer Ctrl+C

        # --- Comparer et Donner Feedback ---
        _, choix_joueur_name_fmt, _ = get_item_display_info(choix_joueur_instance)
        _, meilleur_objet_name_fmt, _ = get_item_display_info(meilleur_objet_calcule)
        print(f"\nVotre choix : {choix_joueur_name_fmt}")
        is_correct = (choix_joueur_instance.nom == meilleur_objet_calcule.nom)
        if is_correct:
            print(f">>> \033[92mCORRECT !\033[0m <<<")
            print(f"    (WR simulé: {meilleur_wr_calcule * 100:.3f}%)")
        else:
            print(f">>> \033[91mINCORRECT.\033[0m <<<")
            wr_choix_joueur = winrates_calcules.get(choix_joueur_instance.nom, -1)
            wr_joueur_str = f"{wr_choix_joueur * 100:.3f}%" if wr_choix_joueur != -1 else "N/A"
            wr_calcule_str = f"{meilleur_wr_calcule * 100:.3f}%" if meilleur_wr_calcule != -1 else "N/A"
            print(f"    Votre choix ({choix_joueur_name_fmt}) -> WR simulé: {wr_joueur_str}")
            print(f"    Meilleur choix calculé : ({meilleur_objet_name_fmt}) -> WR simulé: {wr_calcule_str}")

        # --- Continuer ? ---
        try:
            continuer_str = input("\nAutre question (o/n) ? ").lower()
            if continuer_str != 'o': break
        except EOFError: break
        except KeyboardInterrupt: print("\nArrêt demandé."); break

    print("\nMerci d'avoir joué !")