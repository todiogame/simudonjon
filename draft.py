import random
from tqdm import tqdm
from objets import *
from perso import Joueur
from simu import   loguer_x_parties, ordonnanceur
from monstres import DonjonDeck

def preparer_game(objets_disponibles):
    # Créer une copie de la liste des objets disponibles pour cette simulation
    objets_disponibles_simu = list(objets_disponibles)
    # Réparer tous les objets
    for o in objets_disponibles_simu:
        o.intact = True

    # Initialisation des joueurs avec des points de vie aléatoires entre 2 et 4
    joueurs = []
    nb_joueurs = random.choice([3, 4])
    noms_joueurs = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]

    # Distribuer les objets initiaux
    mains_joueurs = []
    for _ in range(nb_joueurs):
        main = random.sample(objets_disponibles_simu, 7)
        for objet in main:
            objets_disponibles_simu.remove(objet)
        mains_joueurs.append(main)

    # Processus de draft
    objets_joueurs = [[] for _ in range(nb_joueurs)]
    round_counter = 1
    while any(len(objets) < 6 for objets in objets_joueurs):  # Tant qu'il reste des objets à drafter pour chaque joueur
        print(f"Round {round_counter}")
        
        # Collecter les choix de chaque joueur
        choix_joueurs = []
        for i in range(nb_joueurs):
            if len(objets_joueurs[i]) < 6 and mains_joueurs[i]:
                print(f"{noms_joueurs[i]} doit choisir entre ca: {[obj.nom for obj in mains_joueurs[i]]}")
                if len(objets_joueurs[i]): print(f"{noms_joueurs[i]} a deja dans son build: {[obj.nom for obj in objets_joueurs[i]]}\n")
                objet_choisi = choisirObjet(i, objets_joueurs, mains_joueurs)
                objets_joueurs[i].append(objet_choisi)
                mains_joueurs[i].remove(objet_choisi)
                choix_joueurs.append((i, objet_choisi))
                print(f"{noms_joueurs[i]} choisit: {objet_choisi.nom}\n")

        # Passer les mains après tous les choix
        mains_joueurs = [mains_joueurs[(i - 1) % nb_joueurs] for i in range(nb_joueurs)]
        
        round_counter += 1

    # Créer les joueurs avec leurs objets draftés
    for nom, objets in zip(noms_joueurs, objets_joueurs):
        joueurs.append(Joueur(nom, random.randint(2, 4), objets))
        print(f"Joueur {nom} objets finaux: {[obj.nom for obj in objets]}\n")
    print("Objets poubelle :", [obj.nom for main in mains_joueurs for obj in main if main])
    print("\n")

    calculWRfinal(objets_disponibles, noms_joueurs, objets_joueurs)
    jouerLaGame(objets_disponibles, noms_joueurs, objets_joueurs)

def calculWRfinal(objets_disponibles, noms_joueurs, objets_joueurs, iter=1000):
    win_counts = {}
    for _ in range(iter):
        joueurs = []
        for nom, objets in zip(noms_joueurs, objets_joueurs):
            joueurs.append(Joueur(nom, random.randint(2, 4), objets))
        objets_disponibles_simu = list(objets_disponibles)
        for o in objets_disponibles_simu: o.intact = True
        vainqueur = ordonnanceur(joueurs, DonjonDeck(), 6, objets_disponibles_simu, False)
        if vainqueur: win_counts[vainqueur.nom] = win_counts.get(vainqueur.nom, 0) + 1
    print(f"Probas de win la game:")
    for j, count in win_counts.items():
        print(f"{j}: {count / iter:.2%}")


def jouerLaGame(objets_disponibles, noms_joueurs, objets_joueurs):
    joueurs = []
    for nom, objets in zip(noms_joueurs, objets_joueurs):
        joueurs.append(Joueur(nom, random.randint(2, 4), objets))
    objets_disponibles_simu = list(objets_disponibles)
    for o in objets_disponibles_simu: o.intact = True
    ordonnanceur(joueurs, DonjonDeck(), 6, objets_disponibles_simu, True)


def choisirObjet(i, objets, mains):
    meilleur_objet = None
    meilleur_winrate = -1
    objets_actuels = objets[i]
    main = mains[i]
    objets_autres_joueurs = objets[:i] + objets[i+1:]  # Retirer les objets du joueur i
    
    for objet in main:
        combinaison = objets_actuels + [objet]
        winrate = calculWinrate(combinaison,objets_autres_joueurs)
        print(f"{objet.nom}: {winrate:.2f}", end="\n")  # Affichage du winrate de chaque objet
        if winrate > meilleur_winrate:
            meilleur_winrate = winrate
            meilleur_objet = objet
    return meilleur_objet

def calculWinrate(combinaison, objets_autres_joueurs, iterations=100):
    seuil_pv_essai_fuite = 6
    # Initialisation du compteur de victoires
    victoires = 0
    
    # Boucle sur le nombre d'itérations
    for _ in range(iterations):
        # Choisir aléatoirement le joueur qui jouera la combinaison à tester
        
        nb_joueurs = len(objets_autres_joueurs) +1
        noms_joueurs = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]
        joueur_surveille = random.choice(noms_joueurs)
        objets_disponibles_simu = list(objets_disponibles)
        # Reparer tous les objets et attribuer une priorité aléatoire
        for o in objets_disponibles_simu:
            o.intact = True
        # Création des joueurs avec des objets aléatoires
        joueurs = []
        i=0
        for nom in noms_joueurs:
            if nom == joueur_surveille:
                objets_joueur = combinaison + random.sample(objets_disponibles_simu, 6 - len(combinaison))  # Le joueur surveillé reçoit la combinaison à tester
            else:
                objets_joueur = objets_autres_joueurs[i] + random.sample(objets_disponibles_simu, 6 - len(objets_autres_joueurs[i]))  # Les autres joueurs reçoivent des objets aléatoires
                i+=1
            joueurs.append(Joueur(nom, random.randint(2, 4), objets_joueur))

        # Exécution de l'ordonnanceur sans afficher les logs
        vainqueur = ordonnanceur(joueurs,  DonjonDeck(), seuil_pv_essai_fuite, objets_disponibles_simu, False)
        
        # Vérification si le vainqueur est le joueur surveillé
        if vainqueur and vainqueur.nom == joueur_surveille:
            victoires += 1

    # Calcul du winrate
    winrate = victoires / iterations
    return winrate


# Exemple d'utilisation
objets_disponibles_simu = list(objets_disponibles)
preparer_game(objets_disponibles_simu)
