import random
import os
import sys

# --- Bibliothèque externe pour menus ---
try:
    import questionary
except ImportError:
    print("ERREUR: La bibliothèque 'questionary' est nécessaire.")
    print("Veuillez l'installer avec : pip install questionary")
    sys.exit(1)

# --- Imports depuis ton projet (Corrigés) ---
try:
    from objets import objets_disponibles
    from heros import persos_disponibles       # Corrigé
    from draft import calculWinrate           # Assumer défini dans draft.py
    from joueurs import Joueur                 # Corrigé
except ImportError as e:
    print(f"Erreur d'importation des modules du projet: {e}")
    print("Vérifiez les noms et l'accessibilité des fichiers :")
    print("objets.py, heros.py, joueurs.py, simu.py, monstres.py, draft.py") # Noms mis à jour
    sys.exit(1)

# --- Configuration ---
ITERATIONS_MINIJEU = 500
OPPONENT_NAMES = ["Sagarex", "Francis", "Mastho", "Mr.Adam", "Diouze", "Nicoco"]

# --- Fonction Helper pour affichage simple (emoji + nom) ---
def format_item_list_with_emoji(item_list):
    """Formate une liste d'objets en chaîne [emoji] Nom, [emoji] Nom."""
    if not item_list:
        return "Aucun"
    formatted_items = []
    for item in item_list:
        prefix = "⚡ " if getattr(item, 'actif', False) else ""
        formatted_items.append(f"{prefix}{item.nom}")
    return ', '.join(formatted_items)

# --- Génération du Scénario (Logique 7 items) ---
def generer_scenario():
    """Crée un scénario de draft aléatoire avec 7 objets au total et min 2 choix."""
    if not persos_disponibles or not objets_disponibles: return None
    perso_joueur = random.choice(persos_disponibles)

    objets_pool = list(objets_disponibles)
    random.shuffle(objets_pool)
    total_items_round = 7 # Toujours 7 items dans le "round" (déjà pris + main)

    if len(objets_pool) < total_items_round:
        print(f"WARN: Pas assez d'objets ({len(objets_pool)}) pour simuler un round de 7.")
        return None

    # Choisir taille main (entre 2 et 6 inclus => 1 à 5 objets déjà pris)
    nb_objets_main = random.randint(2, 6)
    nb_objets_deja_pris = total_items_round - nb_objets_main

    objets_actuels = objets_pool[:nb_objets_deja_pris]
    main_actuelle = objets_pool[nb_objets_deja_pris:total_items_round]
    objets_restants = objets_pool[total_items_round:]

    # Générer objets pour 3 adversaires (au même stade)
    objets_des_opposants = []
    nb_opposants = 3
    # Vérifier si assez d'objets restants pour les adversaires
    items_needed_for_opponents = nb_opposants * nb_objets_deja_pris
    if len(objets_restants) < items_needed_for_opponents:
        print(f"WARN: Pas assez d'objets restants ({len(objets_restants)}) pour simuler les {nb_opposants} adversaires avec {nb_objets_deja_pris} objets chacun.")
        # Optionnel: on pourrait adapter ou retourner None
        # Pour l'instant, on continue avec ce qu'on a, certains auront moins/pas d'objets
        pass # La boucle ci-dessous gérera ça

    for _ in range(nb_opposants):
        if len(objets_restants) >= nb_objets_deja_pris:
            objets_opp = objets_restants[:nb_objets_deja_pris]
            objets_des_opposants.append(objets_opp)
            objets_restants = objets_restants[nb_objets_deja_pris:]
        else:
            # Donner le reste si pas assez
            objets_des_opposants.append(objets_restants)
            objets_restants = []

    # Réparer tous les objets utilisés dans le scénario
    for o_list in [objets_actuels, main_actuelle] + objets_des_opposants:
        for o in o_list:
             if hasattr(o, 'repare'): o.repare()

    return perso_joueur, objets_actuels, main_actuelle, objets_des_opposants

# --- Calcul du Meilleur Choix (inchangé) ---
def trouver_meilleur_choix(perso_joueur, objets_actuels, main_actuelle):
    meilleur_objet = None
    meilleur_winrate = -1.0
    winrates_calcules = {}
    nb_opposants = 3
    persos_autres = []
    pool_opposants = [p for p in persos_disponibles if p.nom != perso_joueur.nom]
    if len(pool_opposants) >= nb_opposants: persos_autres = random.sample(pool_opposants, nb_opposants)
    else: persos_autres = random.sample(persos_disponibles, nb_opposants)
    objets_autres_joueurs = [[] for _ in range(nb_opposants)]
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
            print(f"ERREUR pendant calculWinrate pour {objet_test.nom}: {e}")
            winrates_calcules[objet_test.nom] = -1
    if meilleur_objet is None and main_actuelle:
        meilleur_objet = main_actuelle[0]
        meilleur_winrate = winrates_calcules.get(meilleur_objet.nom, -1.0)
    return meilleur_objet, meilleur_winrate, winrates_calcules

# --- Boucle Principale du Jeu ---
if __name__ == "__main__":
    print("--- Mini-Jeu d'entraînement au Draft ---")
    print("Utilisez les flèches HAUT/BAS pour naviguer, ENTRÉE pour choisir.")
    if 'questionary' not in sys.modules: print("(Nécessite: pip install questionary)")
    script_dir = os.path.dirname(__file__)
    if script_dir:
        try: os.chdir(script_dir)
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
        # 1. Opposants (avant le joueur)
        noms_opposants = random.sample(available_opponent_names, len(objets_des_opposants))
        print("\nObjets des adversaires :")
        for i, opp_objets in enumerate(objets_des_opposants):
            print(f"  {noms_opposants[i]}: {format_item_list_with_emoji(opp_objets)}")

        # 2. Joueur (en gras)
        pv_total_joueur = perso_joueur.pv_bonus + sum(getattr(o, 'pv_bonus', 0) for o in objets_actuels)
        # Utilisation de ** pour le gras (markdown)
        print(f"\n\033[1mVotre personnage : {perso_joueur.nom} ({perso_joueur.pv_bonus} PV base, {pv_total_joueur} PV actuels \033[0m")
        print(f"\n\033[1mObjets déjà choisis : {format_item_list_with_emoji(objets_actuels)}\033[0m")


        # 3. Choix possibles pour le joueur
        q_choices = []
        max_len_name = max(len(obj.nom) for obj in main_actuelle) if main_actuelle else 20
        for obj in main_actuelle:
            prefix = "⚡ " if getattr(obj, 'actif', False) else "  "
            pv = getattr(obj, 'pv_bonus', 0)
            mod = getattr(obj, 'modificateur_de', 0)
            stat_parts = []
            if pv != 0: stat_parts.append(f"PV:{pv:+d}")
            # Utilisation de "Fuite"
            if mod != 0: stat_parts.append(f"Fuite:{mod:+d}")
            stats_str = ""
            if stat_parts: stats_str = f" ({', '.join(stat_parts)})"
            display_name = f"{prefix}{obj.nom}"
            # Titre formaté pour questionary
            q_choices.append(questionary.Choice(title=f"{display_name:<{max_len_name+3}}{stats_str}", value=obj))

        if not q_choices: print("Erreur: Aucune option à choisir."); continue

        choix_joueur_instance = questionary.select(
            "\nChoisissez le MEILLEUR objet parmi :", # Message avant la liste
            choices=q_choices,
            use_shortcuts=False
        ).ask()

        if choix_joueur_instance is None: print("\nSélection annulée."); break

        # --- Comparer et Donner Feedback ---
        print(f"\nVotre choix : {choix_joueur_instance.nom}")
        is_correct = (choix_joueur_instance.nom == meilleur_objet_calcule.nom)
        if is_correct:
            print(">>> \033[92mCORRECT !\033[0m <<<")
            print(f"    (WR simulé: {meilleur_wr_calcule * 100:.3f}%)")
        else:
            print(f">>> \033[91mINCORRECT.\033[0m <<<")
            wr_choix_joueur = winrates_calcules.get(choix_joueur_instance.nom, -1)
            print(f"    Votre choix ({choix_joueur_instance.nom}) -> WR simulé: {wr_choix_joueur * 100:.3f}%")
            print(f"    Meilleur choix calculé : {meilleur_objet_calcule.nom} -> WR simulé: {meilleur_wr_calcule * 100:.3f}%")

        # --- Continuer ? ---
        try:
            continuer = questionary.confirm("Autre question ?", default=True).ask()
            if continuer is None or not continuer : break
        except KeyboardInterrupt: break

    print("\nMerci d'avoir joué !")