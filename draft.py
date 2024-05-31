import random
from tqdm import tqdm
from objets import *
from perso import Joueur
from simu import   loguer_x_parties, ordonnanceur
from monstres import DonjonDeck

def draftGame(log=True):
    # Créer une copie de la liste des objets disponibles pour cette simulation
    objets_disponibles_simu = list(objets_disponibles)
    # Réparer tous les objets
    for o in objets_disponibles_simu:
        o.repare()

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
    objets_dans_le_draft = [objet for main in mains_joueurs for objet in main]
    
    # Processus de draft
    objets_joueurs = [[] for _ in range(nb_joueurs)]
    round_counter = 1
    while any(len(objets) < 6 for objets in objets_joueurs):  # Tant qu'il reste des objets à drafter pour chaque joueur
        if log: print(f"Round {round_counter}")
        # Collecter les choix de chaque joueur
        choix_joueurs = []
        for i in range(nb_joueurs):
            if len(objets_joueurs[i]) < 6 and mains_joueurs[i]:
                if log: print(f"{noms_joueurs[i]} doit choisir entre ca: {[obj.nom for obj in mains_joueurs[i]]}")
                if log and len(objets_joueurs[i]): print(f"{noms_joueurs[i]} a deja dans son build: {[obj.nom for obj in objets_joueurs[i]]}\n")
                objet_choisi = choisirObjet(i, objets_joueurs, mains_joueurs, log)
                objets_joueurs[i].append(objet_choisi)
                mains_joueurs[i].remove(objet_choisi)
                choix_joueurs.append((i, objet_choisi))
                if log: print(f"{noms_joueurs[i]} choisit: {objet_choisi.nom}\n")
        # Passer les mains après tous les choix
        mains_joueurs = [mains_joueurs[(i - 1) % nb_joueurs] for i in range(nb_joueurs)]
        round_counter += 1

    objets_pris_joueurs =  [objet for j in objets_joueurs for objet in j]
    # Créer les joueurs avec leurs objets draftés
    for nom, objets in zip(noms_joueurs, objets_joueurs):
        joueurs.append(Joueur(nom, random.randint(2, 4), objets))
        if log: print(f"Joueur {nom} objets finaux: {[obj.nom for obj in objets]}\n")
    if log: print("Objets poubelle :", [obj.nom for main in mains_joueurs for obj in main if main])
    if log: print("\n")

    # calculWRfinal(objets_disponibles, noms_joueurs, objets_joueurs, log)
    return (jouerLaGame(objets_disponibles, noms_joueurs, objets_joueurs, log), objets_dans_le_draft, objets_pris_joueurs)

def calculWRfinal(objets_disponibles, noms_joueurs, objets_joueurs, log, iter=1000):
    win_counts = {}
    for _ in range(iter):
        joueurs = []
        for nom, objets in zip(noms_joueurs, objets_joueurs):
            joueurs.append(Joueur(nom, random.randint(2, 4), objets))
        objets_disponibles_simu = list(objets_disponibles)
        for o in objets_disponibles_simu: o.repare()
        vainqueur = ordonnanceur(joueurs, DonjonDeck(), 6, objets_disponibles_simu, False)
        if vainqueur: win_counts[vainqueur.nom] = win_counts.get(vainqueur.nom, 0) + 1
    if log: print(f"Probas de win la game:")
    for j, count in win_counts.items():
        if log: print(f"{j}: {count / iter:.2%}")


def jouerLaGame(objets_disponibles, noms_joueurs, objets_joueurs, log):
    joueurs = []
    for nom, objets in zip(noms_joueurs, objets_joueurs):
        joueurs.append(Joueur(nom, random.randint(2, 4), objets))
    objets_disponibles_simu = list(objets_disponibles)
    for o in objets_disponibles_simu: o.repare()
    return ordonnanceur(joueurs, DonjonDeck(), 6, objets_disponibles_simu, log)


def choisirObjet(i, objets, mains, log):
    meilleur_objet = None
    meilleur_winrate = -1
    objets_actuels = objets[i]
    main = mains[i]
    objets_autres_joueurs = objets[:i] + objets[i+1:]  # Retirer les objets du joueur i
    
    for objet in main:
        combinaison = objets_actuels + [objet]
        winrate = calculWinrate(combinaison,objets_autres_joueurs)
        if log: print(f"{objet.nom}: {winrate:.2f}", end="\n")  # Affichage du winrate de chaque objet
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
            o.repare()
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

iter = 100
item_stats = {}

# Initialiser un dictionnaire pour stocker les informations sur les items
for _ in tqdm(range(iter), desc="Simulation des drafts"):
    resultat = draftGame(False)
    vainqueur = resultat[0]
    objets_dans_le_draft = resultat[1]
    objets_pris_joueurs = resultat[2]
    
    # Stocker les objets présents dans le draft pour le calcul du pickrate
    set_objets_dans_le_draft = set(objet.nom for objet in objets_dans_le_draft)
    set_objets_pris_joueurs = set(objet.nom for objet in objets_pris_joueurs)
    
    for objet in set_objets_dans_le_draft:
        item_stats[objet] = item_stats.get(objet, {'draft':0, 'pick': 0, 'win': 0})
        item_stats[objet]['draft'] += 1
    for objet in set_objets_pris_joueurs:
        item_stats[objet]['pick'] += 1
        
    if vainqueur:
        for objet in vainqueur.objets_initiaux:
            item_stats[objet.nom]['win'] += 1
            
# Calculer le winrate pour chaque objet
for objet, stats in item_stats.items():
    pickrate = stats['pick'] / stats['draft'] * 100 if stats['draft'] > 0 else 0
    winrate = stats['win'] / stats['pick'] * 100 if stats['pick'] > 0 else 0
    stats['pickrate'] = int(pickrate)
    stats['winrate'] = int(winrate)

# Trier les objets par winrate
sorted_items = sorted(item_stats.items(), key=lambda x: x[1]['winrate'], reverse=True)
# Afficher les objets triés par winrate avec des colonnes
print("{:<20} {:<10} {:<10}".format("Objet", "Pickrate%", "Winrate%"))
print("-" * 40)  # Ligne de séparation

for objet, stats in sorted_items:
    print("{:<20} {:<10} {:<10}".format(objet, stats['pickrate'], stats['winrate']))
