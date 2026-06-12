# -*- coding: utf-8 -*-
import itertools
import random
import os
import json
import multiprocessing
from tqdm import tqdm
import sys
import numpy as np

# --- Imports locaux ---
from objets import objets_disponibles # Liste globale des instances d'objets
from joueurs import Joueur              # Classe Joueur
from simu import ordonnanceur         # Moteur de simulation de partie
from monstres import DonjonDeck       # Gestion du deck de donjon
from heros import persos_disponibles # Liste globale des instances Perso

# ==============================================
# Configuration
# ==============================================
NB_DRAFT_SIMULATIONS = 10000            # Nombre total de drafts à simuler
NB_GAMES_PER_DRAFT_FOR_STATS = 1000   # Nb parties jouées pour évaluer chaque draft
ITERATIONS_PER_CHOICE_EVALUATION = 30 # Nb simulations Monte-Carlo par candidat (graines communes => moins d'iterations suffisent)
MC_PICKS_A_PARTIR_DE = 4              # picks 1-4 : priors seuls ; picks suivants : Monte-Carlo
MC_NB_CANDIDATS = 3                   # le Monte-Carlo n'evalue que les meilleurs candidats au prior
PRIORS_NB_PARTIES = 60000             # parties par iteration pour calculer les priors de pick
PRIORS_ITERATIONS = 3                 # 1 = builds aleatoires ; au-dela : self-play (l'IA drafte
                                      # avec les priors de l'iteration precedente, puis on remesure)
PRIORS_EPSILON = 0.15                 # part de picks aleatoires en self-play (exploration :
                                      # sans elle, un objet sous-cote ne serait plus jamais mesure)
PRIORS_FICHIER = "draft_priors.json"  # cache des priors (python draft.py priors pour recalculer)
STATS_FILENAME = "item_stats_progressive.json"  # nom fixe : la reprise fonctionne et wr.py le trouve
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

def _fusionner_stats(dest, src):
    """Additionne les compteurs d'un batch (dict de dicts d'entiers) dans le total."""
    for nom, valeurs in src.items():
        d = dest.setdefault(nom, {})
        for cle, v in valeurs.items():
            d[cle] = d.get(cle, 0) + v

# ==============================================
# Priors de pick : winrate global par objet + synergie perso/objet,
# calcules une fois sur des builds aleatoires puis mis en cache sur disque.
# L'IA de pick utilise ces priors pour les premiers choix (au lieu de 50
# parties Monte-Carlo par candidat, dont la decision etait surtout du bruit).
# ==============================================
_PRIORS = None

def _charger_priors():
    global _PRIORS
    if _PRIORS is None and os.path.exists(PRIORS_FICHIER):
        with open(PRIORS_FICHIER, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _PRIORS = {
            'objets': {nom: tuple(vt) for nom, vt in data['objets'].items()},
            'perso_objet': {tuple(cle.split('||')): tuple(vt) for cle, vt in data['perso_objet'].items()},
        }
    return _PRIORS

def _draft_rapide(persos, priors_par_joueur, epsilon=0.0):
    """Draft complet aux priors seuls (mains de 7 qui tournent, 6 picks chacun),
    sans Monte-Carlo. priors_par_joueur : un dict de priors par siege (le meme pour
    tous en self-play). epsilon : part de picks uniformes (exploration).
    Retourne (builds, objets_restants)."""
    pool = list(objets_disponibles)
    for o in pool:
        o.repare()
    nb = len(persos)
    mains = []
    for _ in range(nb):
        main = random.sample(pool, min(7, len(pool)))
        for o in main:
            pool.remove(o)
        mains.append(main)
    builds = [[] for _ in range(nb)]
    while any(len(b) < 6 for b in builds) and any(mains):
        suivantes = [[] for _ in range(nb)]
        for i in range(nb):
            if len(builds[i]) < 6 and mains[i]:
                if epsilon and random.random() < epsilon:
                    choix = random.choice(mains[i])
                else:
                    priors = priors_par_joueur[i]
                    choix = max(mains[i], key=lambda o: score_pick(o, persos[i], priors))
                builds[i].append(choix)
                mains[i].remove(choix)
            suivantes[(i + 1) % nb] = mains[i]
        mains = suivantes
    poubelle = [o for main in mains for o in main]
    return builds, pool + poubelle


def _priors_batch(args):
    """Worker : parties pour estimer les winrates objet et perso/objet.
    priors=None : builds aleatoires (iteration 1). Sinon : builds draftes aux priors
    de l'iteration precedente, avec epsilon d'exploration (self-play)."""
    nb_parties, seed, priors, epsilon = args
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)
    stats_objets = {}
    stats_perso_objet = {}
    for _ in range(nb_parties):
        nb_joueurs = random.choice([3, 4])
        noms = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]
        persos = random.sample(persos_disponibles, nb_joueurs)
        if priors is None:
            objets_simu = list(objets_disponibles)
            for o in objets_simu:
                o.repare()
            builds = []
            for _i in range(nb_joueurs):
                objs = random.sample(objets_simu, 6)
                for o in objs:
                    objets_simu.remove(o)
                builds.append(objs)
            restants = objets_simu
        else:
            builds, restants = _draft_rapide(persos, [priors] * nb_joueurs, epsilon)
        joueurs = [Joueur(noms[i], persos[i], builds[i]) for i in range(nb_joueurs)]
        vainqueur, _ = ordonnanceur(joueurs, DonjonDeck(), 6, restants, False)
        for joueur in joueurs:
            v = 1 if joueur is vainqueur else 0
            pnom = joueur.personnage_nom
            for o in joueur.objets_initiaux:
                s = stats_objets.setdefault(o.nom, [0, 0]); s[0] += v; s[1] += 1
                s = stats_perso_objet.setdefault((pnom, o.nom), [0, 0]); s[0] += v; s[1] += 1
    return stats_objets, stats_perso_objet

def calculer_priors(nb_parties=PRIORS_NB_PARTIES, nb_process=None, force=False,
                    iterations=PRIORS_ITERATIONS):
    """Calcule (ou recharge depuis le cache) les priors de pick, par self-play itere :
    iteration 1 sur builds aleatoires, puis chaque iteration drafte avec les priors de
    la precedente et remesure. Corrige le biais 'valeur d'un objet quand tout le monde
    joue au hasard' ; seuls les priors de la derniere iteration sont conserves."""
    global _PRIORS
    if not force and _charger_priors() is not None:
        return _PRIORS
    if nb_process is None:
        nb_process = max(1, (os.cpu_count() or 2) - 1)
    priors_courants = None
    for it in range(iterations):
        mode = "builds aléatoires" if priors_courants is None else f"self-play (eps={PRIORS_EPSILON})"
        print(f"Priors {it + 1}/{iterations} ({mode}) : {nb_parties} parties, {nb_process} process...")
        stats_objets = {}
        stats_perso_objet = {}
        nb_batches = nb_process * 4 if nb_process > 1 else 1
        base, reste = divmod(nb_parties, nb_batches)
        travaux = [(base + (1 if i < reste else 0), random.randrange(2**31),
                    priors_courants, PRIORS_EPSILON) for i in range(nb_batches)]
        travaux = [t for t in travaux if t[0] > 0]
        if nb_process > 1:
            with multiprocessing.Pool(nb_process) as pool:
                resultats = list(tqdm(pool.imap_unordered(_priors_batch, travaux),
                                      total=len(travaux), desc=f"Priors {it + 1}/{iterations}"))
        else:
            resultats = [_priors_batch(t) for t in tqdm(travaux, desc=f"Priors {it + 1}/{iterations}")]
        for so, spo in resultats:
            for nom, (v, t) in so.items():
                d = stats_objets.setdefault(nom, [0, 0]); d[0] += v; d[1] += t
            for cle, (v, t) in spo.items():
                d = stats_perso_objet.setdefault(cle, [0, 0]); d[0] += v; d[1] += t
        priors_courants = {'objets': {k: tuple(v) for k, v in stats_objets.items()},
                           'perso_objet': {k: tuple(v) for k, v in stats_perso_objet.items()}}
    with open(PRIORS_FICHIER, 'w', encoding='utf-8') as f:
        json.dump({
            'nb_parties': nb_parties,
            'iterations': iterations,
            'objets': {k: list(v) for k, v in priors_courants['objets'].items()},
            'perso_objet': {f"{p}||{o}": list(vt)
                            for (p, o), vt in priors_courants['perso_objet'].items()},
        }, f, ensure_ascii=False)
    _PRIORS = priors_courants
    print(f"Priors sauvegardés dans {PRIORS_FICHIER}.")
    return _PRIORS

def score_pick(objet, perso, priors):
    """Score d'un objet pour un perso : winrate global + synergie perso/objet (avec shrinkage)."""
    v, t = priors['objets'].get(objet.nom, (0, 0))
    wr_objet = v / t if t else 0.28
    v2, t2 = priors['perso_objet'].get((perso.nom, objet.nom), (0, 0))
    synergie = 0.0
    if t2:
        # la synergie observee est bruitee sur peu de parties : on la retrecit vers 0
        synergie = (v2 / t2 - wr_objet) * (t2 / (t2 + 200.0))
    return wr_objet + synergie


# --- Calcul Winrate pour une combinaison et un personnage donné ---
def calculWinrate(combinaison, objets_autres_joueurs, perso_joueur, persos_autres,
                  iterations=ITERATIONS_PER_CHOICE_EVALUATION, seed_base=None):
    """Simule des parties pour évaluer une combinaison d'items pour un personnage spécifique.

    seed_base (optionnel) : graines communes (CRN) — chaque iteration j est jouee avec la meme
    graine pour tous les candidats compares, ce qui reduit fortement le bruit de la comparaison."""
    seuil_pv_essai_fuite = 6
    victoires = 0
    if iterations <= 0: return 0.0

    for it in range(iterations):
        if seed_base is not None:
            random.seed(seed_base + it * 9973)
            np.random.seed((seed_base + it * 9973) & 0xFFFFFFFF)
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
            joueur_cree.perso_obj.capacite_utilisee = False
            joueurs.append(joueur_cree)

        objets_restants = objets_disponibles_pour_complement
        vainqueur, _ = ordonnanceur(joueurs, DonjonDeck(), seuil_pv_essai_fuite, objets_restants, False)

        if vainqueur and vainqueur.nom == nom_joueur_teste:
            victoires += 1

    return victoires / iterations


# --- Choix d'objet par l'IA pendant le draft ---
def choisirObjet(i, objets_joueurs, mains_joueurs, personnages_assigner, log):
    """Choisit un objet dans la main :
    - picks 1 a MC_PICKS_A_PARTIR_DE : priors (winrate objet + synergie perso), quasi gratuit ;
    - derniers picks : Monte-Carlo a graines communes sur les MC_NB_CANDIDATS meilleurs candidats."""
    main_actuelle = mains_joueurs[i]
    if not main_actuelle:
        return None
    perso_instance_joueur = personnages_assigner[i]
    priors = _charger_priors()

    if priors is not None:
        scores = {objet.nom: score_pick(objet, perso_instance_joueur, priors) for objet in main_actuelle}
        candidats = sorted(main_actuelle, key=lambda o: scores[o.nom], reverse=True)
        if log:
            print(f"  Priors pour {perso_instance_joueur.nom}: " +
                  ", ".join(f"{o.nom}={scores[o.nom]*100:.1f}" for o in candidats))
        if len(objets_joueurs[i]) < MC_PICKS_A_PARTIR_DE:
            if log: print(f"  -> Choix au prior: {candidats[0].nom}")
            return candidats[0]
        candidats = candidats[:MC_NB_CANDIDATS]
    else:
        candidats = list(main_actuelle)  # pas de priors : Monte-Carlo sur toute la main (mode degrade)

    # Monte-Carlo avec graines communes : tous les candidats sont evalues sur les memes parties
    objets_actuels_joueur = objets_joueurs[i]
    persos_autres = [personnages_assigner[j] for j in range(len(objets_joueurs)) if j != i]
    autres_builds = [objets_joueurs[j] for j in range(len(objets_joueurs)) if j != i]

    objets_actuels_repares = list(objets_actuels_joueur); [o.repare() for o in objets_actuels_repares]
    autres_builds_repares = [[o for o in build] for build in autres_builds]
    for build in autres_builds_repares: [o.repare() for o in build]

    # on sauvegarde l'etat RNG : les evaluations seedees ne doivent pas derailler le flux du draft
    etat_rnd = random.getstate()
    etat_np = np.random.get_state()
    seed_base = random.randrange(2**31)

    meilleur_objet = None
    meilleur_winrate = -1.0
    if log: print(f"  Évaluation Monte-Carlo pour {perso_instance_joueur.nom}:")
    for objet_test in candidats:
        objet_test.repare()
        combinaison_test = objets_actuels_repares + [objet_test]
        winrate = calculWinrate(combinaison_test, autres_builds_repares, perso_instance_joueur,
                                persos_autres, seed_base=seed_base)
        if log: print(f"    -> Test {objet_test.nom}: {winrate:.2f}")
        if winrate > meilleur_winrate:
            meilleur_winrate = winrate
            meilleur_objet = objet_test

    random.setstate(etat_rnd)
    np.random.set_state(etat_np)

    if meilleur_objet is None and main_actuelle:
        meilleur_objet = main_actuelle[0]
        if log: print(f"    -> Fallback: choix de {meilleur_objet.nom}")
    return meilleur_objet


# --- Simulation d'un draft complet ---
def draftGame(noms_joueurs, personnages_assigner, log=False):
    """Simule le processus de draft pour un set de joueurs/personnages."""
    objets_disponibles_simu = list(objets_disponibles)
    for o in objets_disponibles_simu: o.repare()
    persos_disponibles_simu = list(persos_disponibles)
    for p in persos_disponibles_simu: p.capacite_utilisee = False
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
    for j in joueurs: j.perso_obj.capacite_utilisee = False
    vainqueur, joueurs_finaux = ordonnanceur(joueurs, DonjonDeck(), 6, objets_disponibles_simu, log)
    return vainqueur, joueurs_finaux


# --- Worker multiprocessing : un batch de drafts complets ---
def _draft_batch(args):
    """Enchaine nb_drafts drafts complets (phase de picks + parties d'evaluation)
    et retourne des compteurs agreges, fusionnes ensuite par le parent."""
    nb_drafts, nb_games, seed = args
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)
    _charger_priors()  # depuis le cache disque (calcule par le parent avant le Pool)
    item_stats = {}
    perso_stats = {}
    duo_stats = {}          # "objet_a||objet_b" -> {'win', 'played'}
    perso_objet_stats = {}  # "perso||objet" -> {'win', 'played'}
    compteurs = {'parties': 0, 'joueurs': 0, 'morts': 0, 'fuites': 0, 'ponces': 0, 'scores': {}}
    drafts_faits = 0

    for _ in range(nb_drafts):
        nb_joueurs = random.choice([3, 4])
        noms = ["Sagarex", "Francis", "Mastho", "Mr.Adam"][:nb_joueurs]
        if len(persos_disponibles) < nb_joueurs:
            continue
        persos = random.sample(persos_disponibles, nb_joueurs)

        resultat_draft = draftGame(noms, persos, False)
        if resultat_draft is None:
            continue
        objets_draft, objets_pris, objets_dispo_local, _, builds = resultat_draft
        drafts_faits += 1

        for obj in objets_draft:
            ensure_item_stats_entry(obj.nom, item_stats); item_stats[obj.nom]['draft'] += 1
        for obj in objets_pris:
            ensure_item_stats_entry(obj.nom, item_stats); item_stats[obj.nom]['pick'] += 1

        for _ in range(nb_games):
            vainqueur, joueurs_apres = jouerLaGame(objets_dispo_local, noms, builds, persos, False)
            if joueurs_apres is None:
                continue
            compteurs['parties'] += 1
            nom_vainqueur = getattr(vainqueur, 'nom', None)
            for j_final in joueurs_apres:
                is_win = (j_final.nom == nom_vainqueur)
                is_dead = not j_final.vivant
                fled = j_final.fuite_reussie
                cleared = j_final.dans_le_dj
                perso_nom = getattr(j_final, 'personnage_nom', 'Inconnu')

                # Compteurs globaux (score "pose" = 0 si exclu du decompte)
                score_pose = j_final.score_final if getattr(j_final, 'compte_au_score', False) else 0
                compteurs['joueurs'] += 1
                compteurs['morts'] += is_dead
                compteurs['fuites'] += fled
                compteurs['ponces'] += cleared
                h = compteurs['scores']; h[score_pose] = h.get(score_pose, 0) + 1

                # Stats Perso
                ensure_perso_stats_entry(perso_nom, perso_stats)
                stats_p = perso_stats[perso_nom]
                stats_p['played'] += 1
                if is_dead: stats_p['death'] += 1
                elif fled: stats_p['fled'] += 1
                elif cleared: stats_p['cleared'] += 1
                if is_win: stats_p['win'] += 1

                # Stats Objets
                noms_objets = sorted(o.nom for o in j_final.objets_initiaux)
                for nom_obj in noms_objets:
                    ensure_item_stats_entry(nom_obj, item_stats)
                    stats_i = item_stats[nom_obj]
                    stats_i['played'] += 1
                    if is_dead: stats_i['death'] += 1
                    elif fled: stats_i['fled'] += 1
                    elif cleared: stats_i['cleared'] += 1
                    if is_win: stats_i['win'] += 1
                    # Synergie perso/objet
                    s = perso_objet_stats.setdefault(f"{perso_nom}||{nom_obj}", {'win': 0, 'played': 0})
                    s['played'] += 1
                    s['win'] += is_win

                # Duos d'objets du build
                for a, b in itertools.combinations(noms_objets, 2):
                    s = duo_stats.setdefault(f"{a}||{b}", {'win': 0, 'played': 0})
                    s['played'] += 1
                    s['win'] += is_win

    return item_stats, perso_stats, duo_stats, perso_objet_stats, compteurs, drafts_faits


# --- Fonction Principale ---
def simudraftgames(iter=NB_DRAFT_SIMULATIONS, nb_games=NB_GAMES_PER_DRAFT_FOR_STATS,
                   filename=STATS_FILENAME, nb_process=None):
    """Lance la simulation complète des drafts et des parties associées (multiprocess)."""
    if nb_process is None:
        nb_process = max(1, (os.cpu_count() or 2) - 1)

    item_stats = {}
    perso_stats = {}
    duo_stats = {}
    perso_objet_stats = {}
    compteurs = {'parties': 0, 'joueurs': 0, 'morts': 0, 'fuites': 0, 'ponces': 0, 'scores': {}}
    start_draft = 0

    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f: saved_data = json.load(f)
            item_stats = saved_data.get('item_stats', {})
            perso_stats = saved_data.get('perso_stats', {})
            duo_stats = saved_data.get('duo_stats', {})
            perso_objet_stats = saved_data.get('perso_objet_stats', {})
            compteurs.update(saved_data.get('compteurs', {}))
            # cles d'histogramme : json les stocke en str
            compteurs['scores'] = {int(k): v for k, v in compteurs.get('scores', {}).items()}
            start_draft = saved_data.get('drafts_completed', 0)
            print(f"Reprise à draft {start_draft + 1}/{iter}.")
        except Exception as e:
            print(f"Erreur chargement {filename}: {e}. Redémarrage.")
            item_stats = {}; perso_stats = {}; duo_stats = {}; perso_objet_stats = {}
            compteurs = {'parties': 0, 'joueurs': 0, 'morts': 0, 'fuites': 0, 'ponces': 0, 'scores': {}}
            start_draft = 0
    else:
        print("Démarrage nouvelle simulation.")

    drafts_completes = start_draft

    if start_draft >= iter:
        print("Simulation déjà complétée.")
    else:
        calculer_priors(nb_process=nb_process)

        restant = iter - start_draft
        # petits batches de drafts pour une progression/sauvegarde regulieres
        drafts_par_batch = max(1, min(5, restant // (nb_process * 4) if nb_process > 1 else restant))
        travaux = []
        attribues = 0
        while attribues < restant:
            n = min(drafts_par_batch, restant - attribues)
            travaux.append((n, nb_games, random.randrange(2**31)))
            attribues += n

        def integrer(resultat):
            nonlocal drafts_completes
            so, sp, sd, spo, cpt, faits = resultat
            _fusionner_stats(item_stats, so)
            _fusionner_stats(perso_stats, sp)
            _fusionner_stats(duo_stats, sd)
            _fusionner_stats(perso_objet_stats, spo)
            for cle in ('parties', 'joueurs', 'morts', 'fuites', 'ponces'):
                compteurs[cle] = compteurs.get(cle, 0) + cpt[cle]
            h = compteurs['scores']
            for valeur, nb in cpt['scores'].items():
                h[valeur] = h.get(valeur, 0) + nb
            drafts_completes += faits
            save_data = {"drafts_completed": drafts_completes, "item_stats": item_stats,
                         "perso_stats": perso_stats, "duo_stats": duo_stats,
                         "perso_objet_stats": perso_objet_stats, "compteurs": compteurs}
            try:
                with open(filename, "w", encoding='utf-8') as f:
                    json.dump(save_data, f, ensure_ascii=False)  # compact : duos volumineux
            except IOError as e:
                print(f"\nERREUR sauvegarde: {e}")

        print(f"Objectif: {iter} drafts ({nb_games} parties d'évaluation chacun), {nb_process} process. Démarrage de {start_draft + 1}...")
        if nb_process > 1:
            with multiprocessing.Pool(nb_process) as pool:
                for resultat in tqdm(pool.imap_unordered(_draft_batch, travaux),
                                     total=len(travaux), desc="Simulation drafts"):
                    integrer(resultat)
        else:
            for travail in tqdm(travaux, desc="Simulation drafts"):
                integrer(_draft_batch(travail))

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

    # --- Résumé global ---
    nb_joueurs_total = max(1, compteurs.get('joueurs', 0))
    scores_glob = compteurs.get('scores', {})
    print(f"\n{'=' * 26} RÉSUMÉ GLOBAL {'=' * 26}")
    print(f"Parties jouées : {compteurs.get('parties', 0)} ({nb_joueurs_total} joueurs-parties)")
    print(f"Joueurs morts : {compteurs.get('morts', 0) / nb_joueurs_total * 100:.2f}%  |  "
          f"ayant fui : {compteurs.get('fuites', 0) / nb_joueurs_total * 100:.2f}%  |  "
          f"ponceurs : {compteurs.get('ponces', 0) / nb_joueurs_total * 100:.2f}%")
    if scores_glob:
        score_moyen = sum(val * nb for val, nb in scores_glob.items()) / nb_joueurs_total
        cumul, mediane = 0, 0
        for valeur in sorted(scores_glob):
            cumul += scores_glob[valeur]
            if cumul >= (nb_joueurs_total + 1) / 2:
                mediane = valeur
                break
        print(f"Score posé : médian {mediane}, moyen {score_moyen:.2f} (0 = joueur exclu du décompte)")
        print("Distribution des scores posés :")
        for valeur in sorted(scores_glob):
            nb = scores_glob[valeur]
            barre = '#' * max(1, round(nb / nb_joueurs_total * 100)) if nb else ''
            print(f"  {valeur:>3} : {nb / nb_joueurs_total * 100:>6.2f}%  {barre}")

    # --- Duos (top/flop, chaque objet/perso n'apparait qu'une fois par tableau) ---
    def _top_flop_duos(stats, titre, separateur=' & ', minimum=None):
        lignes = [(cle.split('||'), s['win'] / s['played'] * 100, s['played'])
                  for cle, s in stats.items() if s.get('played', 0)]
        if not lignes:
            return
        if minimum is None:
            # seuil : un dixieme de l'echantillon median, plancher 200
            tailles = sorted(p for _, _, p in lignes)
            minimum = max(200, tailles[len(tailles) // 2] // 10)
        lignes = [l for l in lignes if l[2] >= minimum]
        lignes.sort(key=lambda l: l[1], reverse=True)

        def _selection(iterable):
            retenus, vus = [], set()
            for noms, wr_duo, played in iterable:
                if not any(nm in vus for nm in noms):
                    retenus.append((noms, wr_duo, played))
                    vus.update(noms)
                if len(retenus) == 10:
                    break
            return retenus

        print(f"\n{titre} (échantillon >= {minimum}) :")
        print(f"  {'-- top 10 --':<70} {'Win%':>7} {'Played':>9}")
        for noms, wr_duo, played in _selection(lignes):
            print(f"  {separateur.join(noms):<70} {wr_duo:>7.2f} {played:>9}")
        print(f"  {'-- flop 10 --':<70} {'Win%':>7} {'Played':>9}")
        for noms, wr_duo, played in _selection(reversed(lignes)):
            print(f"  {separateur.join(noms):<70} {wr_duo:>7.2f} {played:>9}")

    _top_flop_duos(duo_stats, "Duos d'objets")
    _top_flop_duos(perso_objet_stats, "Duos Personnage & Objet", separateur=' + ')

    print(f"\nStats finales basées sur {drafts_completes} drafts complétés.")
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

    # Vérifier les arguments de la ligne de commande
    if len(sys.argv) > 1 and sys.argv[1] == 'priors':
        # --- MODE : recalcul force des priors de pick (self-play itere) ---
        calculer_priors(force=True)

    elif len(sys.argv) > 1 and sys.argv[1] == '1':
        # --- MODE : Lancement d'UN SEUL draft avec logs ---
        print("\nMode : Lancement d'un draft unique avec logs (Argument '1' détecté)...")

        # 1. Choisir le nombre de joueurs pour ce test (3 ou 4)
        nb_joueurs_test = 3
        noms_test = ["JoueurTest1", "JoueurTest2", "JoueurTest3", "JoueurTest4"][:nb_joueurs_test]

        # 2. Vérifier qu'il y a assez de personnages disponibles
        if len(persos_disponibles) < nb_joueurs_test:
            print(f"ERREUR: Pas assez de personnages disponibles ({len(persos_disponibles)}) pour {nb_joueurs_test} joueurs.")
        else:
            # 3. S'assurer que les priors de pick existent
            calculer_priors()

            # 4. Assigner des personnages aléatoirement
            persos_test = random.sample(persos_disponibles, nb_joueurs_test)
            print(f"Joueurs et Personnages pour ce draft:")
            for nom, perso in zip(noms_test, persos_test):
                print(f"- {nom}: {perso.nom}")
            print("-" * 30)

            # 5. Appeler draftGame avec log=True
            resultat_draft_test = draftGame(noms_test, persos_test, log=True)

            # 6. Afficher le résultat du draft
            if resultat_draft_test:
                objets_dans_le_draft, objets_pris_joueurs, objets_disponibles_retour, _, objets_joueurs_finaux = resultat_draft_test
                print("\n--- Résultat du Draft ---")
                for i, nom in enumerate(noms_test):
                    print(f"{nom} ({persos_test[i].nom}) a drafté : {[obj.nom for obj in objets_joueurs_finaux[i]]}")
                # Estimation des objets non choisis
                objets_draft_noms = {o.nom for o in objets_dans_le_draft}
                objets_pris_noms = {o.nom for o in objets_pris_joueurs}
                objets_poubelle_noms = objets_draft_noms - objets_pris_noms
                print(f"\nObjets non choisis (poubelle draft): {list(objets_poubelle_noms)}")
            else:
                print("\nLe draft n'a pas pu être complété (peut-être pas assez d'objets ?).")

    elif len(sys.argv) > 1:
         # Si un argument est donné mais ce n'est pas '1'
         print(f"Argument non reconnu : '{sys.argv[1]}'")
         print("Usage :")
         print(f"  python {sys.argv[0]}        : Lance la simulation complète.")
         print(f"  python {sys.argv[0]} 1      : Lance un seul draft avec logs.")
         print(f"  python {sys.argv[0]} priors : Recalcule les priors de pick (self-play itéré).")

    else:
        # --- MODE : Simulation Complète (Comportement par défaut) ---
        print("\nMode : Lancement de la simulation complète...")
        simudraftgames()
