# Fichier: minijeu.py
import random
import os

# --- Imports depuis ton projet ---
# Adapter les noms de fichiers/variables si nécessaire
try:
    from objets import objets_disponibles
    from heros import persos_disponibles
    # On a besoin de calculWinrate qui est dans draft.py
    # calculWinrate dépend lui-même d'autres modules (Joueur, ordonnanceur, DonjonDeck)
    # Il faut s'assurer que draft.py peut les importer correctement.
    from draft import calculWinrate, ITERATIONS_PER_CHOICE_EVALUATION
    # Importer Joueur est nécessaire si on veut typer ou utiliser des méthodes
    from joueurs import Joueur
except ImportError as e:
    print(f"Erreur d'importation: {e}")
    print("Assurez-vous que les fichiers objets.py, personnages.py, perso.py, simu.py, monstres.py et draft.py sont accessibles.")
    exit()

# --- Configuration pour le Mini-Jeu ---
# Utiliser moins d'itérations pour que la réponse soit plus rapide
ITERATIONS_MINIJEU = 500 # Ajuster selon la vitesse souhaitée vs précision

def generer_scenario():
    """Crée un scénario de draft aléatoire."""
    # 1. Choisir un personnage pour le joueur
    if not persos_disponibles: return None # Sécurité
    perso_joueur = random.choice(persos_disponibles)

    # 2. Choisir les objets déjà possédés (0 à 5)
    objets_pool = list(objets_disponibles)
    random.shuffle(objets_pool) # Mélanger pour sélection aléatoire
    nb_objets_deja_pris = random.randint(0, 5)
    objets_actuels = objets_pool[:nb_objets_deja_pris]

    # 3. Choisir la main (3 à 5 objets restants)
    objets_restants = objets_pool[nb_objets_deja_pris:]
    if len(objets_restants) < 3: return None # Pas assez d'objets pour une main valide
    nb_objets_main = min(random.randint(3, 5), len(objets_restants))
    main_actuelle = objets_restants[:nb_objets_main]

    # Réparer les objets (important pour calculWinrate)
    for o in objets_actuels: o.repare()
    for o in main_actuelle: o.repare()

    return perso_joueur, objets_actuels, main_actuelle

def trouver_meilleur_choix(perso_joueur, objets_actuels, main_actuelle):
    """Utilise calculWinrate pour trouver le meilleur objet dans la main."""
    meilleur_objet = None
    meilleur_winrate = -1.0

    # Créer des adversaires "dummy" pour calculWinrate
    # (On suppose un contexte 4 joueurs pour le calcul)
    nb_opposants = 3
    persos_autres = []
    if len(persos_disponibles) > 1: # Éviter de choisir le même perso que le joueur
        pool_opposants = [p for p in persos_disponibles if p.nom != perso_joueur.nom]
        if len(pool_opposants) >= nb_opposants:
           persos_autres = random.sample(pool_opposants, nb_opposants)
        else: # Si pas assez d'autres persos, compléter aléatoirement
            persos_autres = random.sample(persos_disponibles, nb_opposants)
    else: # Si un seul perso défini
        persos_autres = [random.choice(persos_disponibles) for _ in range(nb_opposants)]

    # Les builds des autres sont vides pour simplifier ce mini-jeu
    objets_autres_joueurs = [[] for _ in range(nb_opposants)]

    objets_actuels_repares = list(objets_actuels); [o.repare() for o in objets_actuels_repares]

    # print(f"Calcul du meilleur choix (simulation avec {ITERATIONS_MINIJEU} itérations)...")
    for objet_test in main_actuelle:
        objet_test.repare() # S'assurer qu'il est réparé
        combinaison_test_reparee = objets_actuels_repares + [objet_test]
        # Appel à calculWinrate avec moins d'itérations pour la vitesse
        winrate = calculWinrate(combinaison_test_reparee, objets_autres_joueurs,
                                perso_joueur, persos_autres, iterations=ITERATIONS_MINIJEU)

        # print(f"  -> WR simulé pour {objet_test.nom}: {winrate:.3f}") # Log pendant calcul
        if winrate > meilleur_winrate:
            meilleur_winrate = winrate
            meilleur_objet = objet_test

    # Fallback si tous les winrates sont négatifs ou nuls (peu probable)
    if meilleur_objet is None and main_actuelle:
        meilleur_objet = main_actuelle[0]

    return meilleur_objet, meilleur_winrate

# --- Boucle Principale du Jeu ---
if __name__ == "__main__":
    print("--- Mini-Jeu d'entraînement au Draft ---")

    # S'assurer que le répertoire courant est correct pour les imports relatifs si besoin
    script_dir = os.path.dirname(__file__)
    if script_dir:
        try:
            os.chdir(script_dir)
        except Exception as e:
            print(f"WARN: Impossible de changer de répertoire: {e}")

    while True:
        print("\n=========================================")
        print("Nouvelle situation de draft :")

        # 1. Générer le scénario
        scenario = generer_scenario()
        if scenario is None:
            print("Erreur lors de la génération du scénario (pas assez d'objets/persos?).")
            break
        perso_joueur, objets_actuels, main_actuelle = scenario

        # 2. Trouver la meilleure réponse en arrière-plan
        meilleur_objet_calcule, meilleur_wr_calcule = trouver_meilleur_choix(perso_joueur, objets_actuels, main_actuelle)

        if meilleur_objet_calcule is None:
             print("Erreur lors du calcul du meilleur choix.")
             continue # Essayer une autre question

        # 3. Afficher le scénario au joueur
        print(f"\nVotre personnage : {perso_joueur.nom} (PV base: {perso_joueur.pv_bonus}, Mod. Dé: {perso_joueur.modificateur_de})") # Afficher stats de base
        if objets_actuels:
            print(f"Objets déjà choisis : {', '.join([o.nom for o in objets_actuels])}")
        else:
            print("Objets déjà choisis : Aucun")
        print("\nChoisissez le MEILLEUR objet parmi :")
        for i, obj in enumerate(main_actuelle):
            print(f"  {i+1}: {obj.nom}")

        # 4. Obtenir le choix du joueur
        choix_joueur_instance = None
        while choix_joueur_instance is None:
            try:
                choix_str = input(f"Votre choix (1-{len(main_actuelle)}) ? ")
                choix_idx = int(choix_str) - 1 # Convertir en index base 0
                if 0 <= choix_idx < len(main_actuelle):
                    choix_joueur_instance = main_actuelle[choix_idx]
                else:
                    print("Choix invalide.")
            except ValueError:
                print("Entrez un numéro valide.")

        # 5. Comparer et donner le feedback
        print(f"\nVotre choix : {choix_joueur_instance.nom}")
        if choix_joueur_instance.nom == meilleur_objet_calcule.nom:
            print(">>> CORRECT ! <<<")
        else:
            print(f">>> INCORRECT. <<<")
            print(f"    Le meilleur choix calculé était : {meilleur_objet_calcule.nom} (WR simulé: {meilleur_wr_calcule * 100:.3f}%)")

        # 6. Continuer ?
        continuer = input("\nAutre question (o/n) ? ").lower()
        if continuer != 'o':
            break

    print("\nMerci d'avoir joué !")