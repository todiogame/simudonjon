# Fichier: minijeu.py
import random
import os
import sys # Pour exit()

# --- Bibliothèque externe pour menus ---
try:
    import questionary
except ImportError:
    print("ERREUR: La bibliothèque 'questionary' est nécessaire.")
    print("Veuillez l'installer avec : pip install questionary")
    sys.exit(1) # Quitter si la bibliothèque manque

# --- Imports depuis ton projet ---
# Adapter les noms de fichiers/variables si nécessaire
try:
    from objets import objets_disponibles
    # Ajuster le nom du fichier si c'est personnages.py ou heros.py
    from heros import persos_disponibles
    from draft import calculWinrate # Utiliser calculWinrate de draft.py
    # Ajuster le nom du fichier si c'est perso.py ou joueurs.py
except ImportError as e:
    print(f"Erreur d'importation des modules du projet: {e}")
    print("Vérifiez les noms et l'accessibilité des fichiers :")
    print("objets.py, personnages.py, perso.py, simu.py, monstres.py, draft.py")
    sys.exit(1)

# --- Configuration ---
ITERATIONS_MINIJEU = 500 # Nb simulations pour évaluer chaque choix

# --- Fonction Helper pour l'affichage ---
def format_item_list_with_emoji(item_list):
    """Formate une liste d'objets en chaîne, ajoutant ⚡ aux actifs."""
    if not item_list:
        return "Aucun"
    formatted_items = []
    for item in item_list:
        prefix = "⚡ " if getattr(item, 'actif', False) else ""
        formatted_items.append(f"{prefix}{item.nom}")
    return ', '.join(formatted_items)

# --- Génération du Scénario ---
def generer_scenario():
    """Crée un scénario de draft aléatoire avec infos adversaires."""
    if not persos_disponibles or not objets_disponibles:
        print("ERREUR: listes persos_disponibles ou objets_disponibles vides.")
        return None
    perso_joueur = random.choice(persos_disponibles)

    objets_pool = list(objets_disponibles)
    random.shuffle(objets_pool)

    nb_objets_deja_pris = random.randint(0, 5)
    nb_objets_deja_pris = min(nb_objets_deja_pris, len(objets_pool))
    objets_actuels = objets_pool[:nb_objets_deja_pris]
    objets_restants = objets_pool[nb_objets_deja_pris:]

    if len(objets_restants) < 3: return None # Pas assez pour la main
    nb_objets_main = min(random.randint(3, 5), len(objets_restants))
    main_actuelle = objets_restants[:nb_objets_main]
    objets_restants = objets_restants[nb_objets_main:]

    objets_des_opposants = []
    nb_opposants = 3
    for _ in range(nb_opposants):
        if len(objets_restants) >= nb_objets_deja_pris:
            objets_opp = objets_restants[:nb_objets_deja_pris]
            objets_des_opposants.append(objets_opp)
            objets_restants = objets_restants[nb_objets_deja_pris:]
        else:
            objets_des_opposants.append(objets_restants)
            objets_restants = []

    for o_list in [objets_actuels, main_actuelle] + objets_des_opposants:
        for o in o_list:
             # Assurer que la méthode repare existe avant de l'appeler
             if hasattr(o, 'repare'): o.repare()

    return perso_joueur, objets_actuels, main_actuelle, objets_des_opposants

# --- Calcul du Meilleur Choix ---
def trouver_meilleur_choix(perso_joueur, objets_actuels, main_actuelle):
    """Utilise calculWinrate pour trouver le meilleur objet et stocke tous les WR."""
    meilleur_objet = None
    meilleur_winrate = -1.0
    winrates_calcules = {}

    nb_opposants = 3
    persos_autres = []
    pool_opposants = [p for p in persos_disponibles if p.nom != perso_joueur.nom]
    if len(pool_opposants) >= nb_opposants:
       persos_autres = random.sample(pool_opposants, nb_opposants)
    else:
        persos_autres = random.sample(persos_disponibles, nb_opposants)
    objets_autres_joueurs = [[] for _ in range(nb_opposants)] # Builds vides

    objets_actuels_repares = list(objets_actuels); [o.repare() for o in objets_actuels_repares if hasattr(o,'repare')]

    print(f"\nCalcul du meilleur choix ({ITERATIONS_MINIJEU} itérations par objet)...")
    for objet_test in main_actuelle:
        if hasattr(objet_test, 'repare'): objet_test.repare()
        combinaison_test_reparee = objets_actuels_repares + [objet_test]
        try:
            winrate = calculWinrate(combinaison_test_reparee, objets_autres_joueurs,
                                    perso_joueur, persos_autres, iterations=ITERATIONS_MINIJEU)
            winrates_calcules[objet_test.nom] = winrate
            # print(f"  -> WR simulé pour {objet_test.nom}: {winrate:.3f}") # Log optionnel
            if winrate > meilleur_winrate:
                meilleur_winrate = winrate
                meilleur_objet = objet_test
        except Exception as e:
            print(f"ERREUR pendant calculWinrate pour {objet_test.nom}: {e}")
            winrates_calcules[objet_test.nom] = -1 # Marquer comme erreur

    if meilleur_objet is None and main_actuelle:
        # Si erreur partout ou tous WR<=0, prendre le premier comme fallback
        meilleur_objet = main_actuelle[0]
        meilleur_winrate = winrates_calcules.get(meilleur_objet.nom, -1.0)

    return meilleur_objet, meilleur_winrate, winrates_calcules

# --- Boucle Principale du Jeu ---
if __name__ == "__main__":
    print("--- Mini-Jeu d'entraînement au Draft ---")
    print("Utilisez les flèches HAUT/BAS pour naviguer, ENTRÉE pour choisir.")
    print("(Nécessite la bibliothèque 'questionary': pip install questionary)")

    script_dir = os.path.dirname(__file__)
    if script_dir:
        try: os.chdir(script_dir)
        except Exception as e: print(f"WARN: Chgt répertoire: {e}")

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
        pv_total_joueur = perso_joueur.pv_bonus + sum(getattr(o, 'pv_bonus', 0) for o in objets_actuels)
        print("Objets des adversaires :")
        for i, opp_objets in enumerate(objets_des_opposants):
            print(f"  Opposant {i+1}: {format_item_list_with_emoji(opp_objets)}")
        print(f"\nVotre personnage : {perso_joueur.nom} ({perso_joueur.pv_bonus} PV base, {pv_total_joueur} PV actuels, Mod. Dé: {perso_joueur.modificateur_de})")
        print(f"Objets déjà choisis : {format_item_list_with_emoji(objets_actuels)}")

        # --- Choix Joueur (avec questionary) ---
        print("\nChoisissez le MEILLEUR objet parmi :") # Titre avant le menu
        q_choices = []
        for obj in main_actuelle:
            prefix = "⚡ " if getattr(obj, 'actif', False) else "  "
            q_choices.append(questionary.Choice(title=f"{prefix}{obj.nom}", value=obj))

        if not q_choices:
             print("Erreur: Aucune option à choisir.")
             continue

        choix_joueur_instance = questionary.select(
            "Votre choix :",
            choices=q_choices,
            use_shortcuts=False # Désactiver sélection par numéro
        ).ask()

        # Gérer si l'utilisateur annule (Ctrl+C)
        if choix_joueur_instance is None:
            print("\nSélection annulée. Arrêt du jeu.")
            break

        # --- Comparer et Donner Feedback ---
        print(f"\nVotre choix : {choix_joueur_instance.nom}")
        is_correct = (choix_joueur_instance.nom == meilleur_objet_calcule.nom)

        if is_correct:
            print(">>> \033[92mCORRECT !\033[0m <<<") # Vert
            print(f"    (WR simulé: {meilleur_wr_calcule * 100:.3f}%)")
        else:
            print(f">>> \033[91mINCORRECT.\033[0m <<<") # Rouge
            wr_choix_joueur = winrates_calcules.get(choix_joueur_instance.nom, -1)
            print(f"    Votre choix ({choix_joueur_instance.nom}) -> WR simulé: {wr_choix_joueur * 100:.3f}%")
            print(f"    Meilleur choix calculé : {meilleur_objet_calcule.nom} -> WR simulé: {meilleur_wr_calcule * 100:.3f}%")

        # --- Continuer ? ---
        try:
            continuer = questionary.confirm("Autre question ?", default=True).ask()
            if continuer is None or not continuer : # Gère Ctrl+C et réponse 'n'
                 break
        except KeyboardInterrupt: # Gère Ctrl+C proprepement
             break


    print("\nMerci d'avoir joué !")