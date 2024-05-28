import random
import numpy as np
from objets import *
from perso import Joueur
from monstres import CarteMonstre, cartes, CarteEvent
import copy


# Fonction pour calculer les statistiques
def calculer_statistiques(resultats):
    moyenne = sum(resultats) / len(resultats)
    maximum = max(resultats)
    minimum = min(resultats)
    mediane = sorted(resultats)[len(resultats) // 2]
    return moyenne, mediane, maximum, minimum

def ordonnanceur(joueurs, donjon, pv_min_fuite, log=True):
    log_details = []
    
    random.shuffle(donjon)
    class Jeu:
        defausse = []
        tour = 0
        execute_next_monster = False
        traquenard_actif = False
        donjon
    Jeu.donjon = donjon

    index_joueur = 0  # Initialisation de l'index du joueur courant
    
    while Jeu.donjon:
        Jeu.tour += 1
        
        if log:
            for detail in log_details:
                print(detail)
        log_details = []

        # Vérifier s'il reste des joueurs vivants
        joueurs_dans_le_dj = [joueur for joueur in joueurs if joueur.dans_le_dj]
        if not joueurs_dans_le_dj:
            log_details.append("Tous les joueurs ont fini.")
            break

        # Le joueur courant
        while not joueurs[index_joueur].dans_le_dj:
            index_joueur += 1
            if index_joueur >= len(joueurs):
                index_joueur = 0
            # Ajouter une vérification pour éviter une boucle infinie
            if all(not joueur.dans_le_dj for joueur in joueurs):
                break

        joueur = joueurs[index_joueur]

        log_details.append(f"Tour de {joueur.nom}, {joueur.pv_total}PV")
        
        # Le joueur pioche une carte
        carte = donjon.pop(0)
        
        joueur.jet_fuite_lance = False

        if joueur.pv_total <= pv_min_fuite and sum(objet.actif and objet.intact for objet in joueur.objets) <= 1:
                        # Tentative de fuite
            joueur.jet_fuite = random.randint(1, 6) + joueur.calculer_modificateurs() 
            log_details.append(f"Tentative de fuite, {joueur.jet_fuite} (avec modif {joueur.calculer_modificateurs()}) ")
            joueur.jet_fuite_lance = True
            # if joueur.jet_fuite >= 7 and any(isinstance(objet, PatinsAGlace) and objet.intact for objet in joueur.objets):
            #     joueur.pv_total -= 1
            #     log_details.append(f"Jet de fuite de {joueur.jet_fuite}, Patins à Glace actifs, perd 1 PV. PV restant: {joueur.pv_total}")



        log_details.append(f"tour {Jeu.tour}. A pioché {carte.titre}.")
        if isinstance(carte, CarteEvent):
            log_details.append(f"A pioché un événement: {carte.titre}.")
            Jeu.execute_next_monster = False
            Jeu.traquenard_actif = False
            for objet in joueur.objets:
                objet.en_rencontre_event(joueur, carte, Jeu, log_details)
            
            if carte.effet == "HEAL":
                joueur.pv_total += 3
                log_details.append(f"{joueur.nom} gagne 3 PV grâce à {carte.titre}. PV restant: {joueur.pv_total}")
                # Ajouter 2 PV aux autres joueurs
                for autre_joueur in joueurs:
                    if autre_joueur != joueur:
                        autre_joueur.pv_total += 2
                        log_details.append(f"{autre_joueur.nom} gagne 2 PV grâce à {carte.titre}. PV restant: {autre_joueur.pv_total}")

            if carte.effet == "REPAIR":
                objets_brisés = [objet for objet in joueur.objets if not objet.intact]
                if objets_brisés:
                    objet_reparé = random.choice(objets_brisés)
                    objet_reparé.intact = True
                    joueur.pv_total += objet_reparé.pv_bonus
                    log_details.append(f"Réparé {objet_reparé.nom} grâce à {carte.titre}. PV total augmenté de {objet_reparé.pv_bonus}, PV restant: {joueur.pv_total}")
                else: log_details.append(f"{carte.titre} n'a' rien a reparer.")

            if carte.effet == "ALLY":
                Jeu.execute_next_monster = True
                log_details.append(f"L'effet {carte.titre} est actif. La prochaine carte monstre peut être exécutée.")

            if carte.effet == "TRAP":
                Jeu.traquenard_actif = True
                log_details.append(f"L'effet {carte.titre} est actif. La prochaine carte monstre Ne peut PAS être exécutée.")

            if carte.effet == "INJECTION":
                golem_count = sum(1 for monstre in joueur.pile_monstres_vaincus if "Golem" in monstre.types)
                if golem_count > 0:
                    joueur.pv_total += 3 * golem_count
                    log_details.append(f"Gagnez {3 * golem_count} PV grâce à {carte.titre} (3 PV pour chaque Golem). PV restant: {joueur.pv_total}")
                else:
                    log_details.append(f"{carte.titre} ne fait rien.")

        if joueur.pv_total > 0 and isinstance(carte, CarteMonstre):
            if carte.effet:
                if carte.effet == "MIROIR":
                    log_details.append(f"Le Miroir Maléfique est pioche.")
                    if joueur.pile_monstres_vaincus:
                        carte_copiee = joueur.pile_monstres_vaincus[-1]

                        carte.puissance = carte_copiee.puissance
                        carte.types = carte_copiee.types
                        # carte.effet = carte_copiee.effet
                        log_details.append(f"Le Miroir Maléfique copie {carte_copiee.titre} avec une puissance de {carte.puissance}.")
                    else:
                        carte.puissance = 0
                        log_details.append(f"Le Miroir Maléfique n'a pas de carte a copier, puissance zero.")

                if carte.effet == "SLEEPING":
                    jet_dragon = random.randint(1, 6)
                    if jet_dragon <= 3:
                        carte.puissance = 9
                    else:
                        carte.puissance = 0
                    log_details.append(f"Rencontré Dragon endormi, jet de {jet_dragon}, puissance déterminée à {carte.puissance}.")

                if carte.effet == "MIMIC":
                    objets_intacts = [objet for objet in joueur.objets if objet.intact]
                    carte.puissance = len(objets_intacts)
                    log_details.append(f"Rencontré Mimique, puissance déterminée à {carte.puissance} (égale au nombre d'objets possédés).")

                if carte.effet == "NOOB":
                    if joueur.medailles > 0:
                        carte.puissance = 2
                        log_details.append(f"Rencontré L'empaleur d'imprudent, puissance réduite à 2 grâce aux médailles.")

                if carte.effet == "MEDAIL":
                    carte.puissance = joueur.medailles
                    log_details.append(f"Rencontré Rongeur de médaille, puissance déterminée à {carte.puissance} (égale au nombre de médailles).")

                if carte.effet == "SCAVENGER":
                    carte.puissance = len(joueur.pile_monstres_vaincus)
                    log_details.append(f"Rencontré Rat charognard, puissance déterminée à {carte.puissance} (égale au nombre de monstres vaincus).")
            
            carte.dommages = carte.puissance

            if carte.effet and "ADD_2_DOM" in carte.effet:
                carte.dommages += 2  # Ajouter 2 dommages supplémentaires pour Chevaucheur de rat
                log_details.append(f"{carte.titre} inflige 2 dommages supplémentaires.")
            if carte.effet == "LORD" and joueur.medailles > 0:
                carte.dommages += 4
                log_details.append(f"Rencontré Seigneur Vampire, inflige 4 dommages supplémentaires grâce aux médailles, dommages {carte.dommages}.")
            
            #use items en_rencontre
            for objet in joueur.objets:
                objet.en_rencontre(joueur, carte, Jeu, log_details)

            if joueur.jet_fuite_lance: 
                if joueur.jet_fuite >= carte.puissance:
                    # Fuite réussie
                    log_details.append(f"Fuite réussie avec un jet de {joueur.jet_fuite} contre {carte.titre} puissance {carte.puissance}\n")
                    joueur.fuite()
                    donjon.insert(0, carte)
                    joueur.jet_fuite_lance = False
                    continue
                else:
                    # Fuite échouée, affronter le monstre normalement
                    log_details.append(f"Fuite échouée avec un jet de {joueur.jet_fuite} contre {carte.puissance}.")
                    joueur.jet_fuite_lance = False

            if Jeu.execute_next_monster and not Jeu.traquenard_actif:
                carte.executed = True
                joueur.pile_monstres_vaincus.append(carte)
                Jeu.execute_next_monster = False
                log_details.append(f"L'effet Exécute le prochain monstre est utilisé sur {carte.titre}.")
            else:
                #use items
                for objet in joueur.objets:
                    objet.en_combat(joueur, carte, Jeu, log_details)
                    if carte.executed or carte.dommages <= 0 or joueur.fuite_reussie:
                        break
                if(not joueur.dans_le_dj):
                    donjon.insert(0, carte)
                    continue
                
            if not carte.executed:
                Jeu.traquenard_actif = False
                joueur.pv_total -= carte.dommages
                #item survie ici
                # Ne pas ajouter le Gobelin Fantôme à la pile des monstres vaincus
                if carte.effet == "MAUDIT":  
                    Jeu.defausse.append(carte)
                    log_details.append(f"Le {carte.titre} disparait.")
                else:
                    if (joueur.vivant): joueur.pile_monstres_vaincus.append(carte)
                if carte.effet == "LIMON":
                    objets_intacts = [objet for objet in joueur.objets if objet.intact]
                    if objets_intacts:
                        objet_avalé = random.choice(objets_intacts)
                        log_details.append(f"Le limon Glouton avale {objet_avalé.nom}.")
                        objet_avalé.destroy()
                        if objet_avalé.pv_bonus:
                            joueur.pv_total -= objet_avalé.pv_bonus
                            log_details.append(f"L'objet avale {objet_avalé.nom} donnait {objet_avalé.pv_bonus}PV ca fait ca de moins. PV restant {joueur.pv_total}PV")
            
                log_details.append(f"Affronté {carte.titre}, perdu {carte.dommages} PV, restant {joueur.pv_total} PV.")

                if carte.effet and "ARRA" in carte.effet and len(joueur.pile_monstres_vaincus) > 1 and carte.dommages > 0:
                    monstre_remis = joueur.pile_monstres_vaincus.pop(-2)
                    donjon.insert(0,monstre_remis)
                    log_details.append(f"L'Arracheur a remis {monstre_remis.titre} sur le Donjon.")

                if carte.dommages >= 0 and carte.effet == "MEDAIL" and carte.dommages > 0:
                        joueur.medailles -= 1
                        log_details.append(f"Perdu une médaille en affrontant Rongeur de médaille, médailles restantes: {joueur.medailles}")
            
            if joueur.pv_total <= 0:
                #use items survie
                for objet in joueur.objets:
                    objet.en_survie(joueur, carte, Jeu, log_details)
                    if joueur.pv_total > 0:
                        break
            # vraiment mort        
            if joueur.pv_total <= 0:
                joueur.mort()
                log_details.append(f"OUPS!! Mort de {joueur.nom}, a court de PV.\n")
                donjon.insert(0, carte)
                index_joueur += 1
                if index_joueur >= len(joueurs):
                    index_joueur = 0
                continue
            
            #use items en_vaincu
            for objet in joueur.objets:
                objet.en_vaincu(joueur, carte, Jeu, log_details)


            if joueur.dans_le_dj and not Jeu.execute_next_monster:
                # Passer son tour, au joueur suivant
                joueur.tour += 1
                if len([joueur for joueur in joueurs if joueur.dans_le_dj]) > 1:
                    log_details.append(f"{joueur.nom} passe son tour.\n")
                    index_joueur += 1
                    if index_joueur >= len(joueurs):
                        index_joueur = 0

    # Calculer les scores finaux pour chaque joueur
    for j in joueurs:
        j.calculScoreFinal(log_details)
        log_details.append(f"Score final: {j.nom} : {j.score_final}, {'mort' if not j.vivant else 'fui' if j.fuite_reussie else 'ponceur' if j.dans_le_dj else 'vivant'}.\n")
    # Vérifier si des joueurs sont arrivés vivants au bout du donjon
    joueurs_dans_le_dj = [j for j in joueurs if j.dans_le_dj]

    # Loguer les joueurs toujours dans le donjon
    if joueurs_dans_le_dj:
        log_details.append("Les joueurs suivants sont toujours dans le donjon :")
        for j in joueurs_dans_le_dj:
            log_details.append(f"- {j.nom}")

    # Créer la liste finale des joueurs comptés
    if joueurs_dans_le_dj:
        joueurs_final = joueurs_dans_le_dj
        log_details.append("Des joueurs sont arrivés vivants au bout du donjon, les fuyards sont exclus.")
    else:
        joueurs_final = [j for j in joueurs if j.vivant]
        log_details.append("Aucun joueur n'a poncé le donjon, tous les joueurs vivants comptent.")

    #use items en_decompte
    for j in joueurs:
        for objet in j.objets:
            objet.en_decompte(j, joueurs_final, log_details)

    # Loguer les joueurs exclus et inclus
    for j in joueurs:
        if j in joueurs_final:
            log_details.append(f"{j.nom} est inclus dans le décompte final.")
        else:
            if not j.vivant:
                log_details.append(f"{j.nom} est exclu du décompte final car il est mort.")
            elif j.fuite_reussie:
                log_details.append(f"{j.nom} est exclu du décompte final car il a fui le donjon.")
            else: log_details.append(f"{j.nom}  A BUG ?? {j.vivant} {j.fuite_reussie} {j.dans_le_dj}")
    # Trier les joueurs par ordre de score décroissant
    joueurs_final.sort(key=lambda j: j.score_final, reverse=True)

    # Afficher les résultats avec une médaille pour le vainqueur
    for i, j in enumerate(joueurs_final):
        medaille = "MEDAILLE" if i == 0 else ""
        log_details.append(f"{j.nom} : {j.score_final} points, PV restant {j.pv_total}. {medaille}")

    log_details.append("\n")

    # Impression des logs (facultatif)
    if log:
        for detail in log_details:
            print(detail)

    #return score_final#, fuite_reussie, donjon_ponce
    # Retourner le joueur vainqueur s'il y en a un
    vainqueur = joueurs_final[0] if joueurs_final else None
    return vainqueur


def loguer_x_parties(x=1):
    objets_disponibles_simu = list(objets_disponibles)

    # Initialisation des joueurs avec des points de vie aléatoires entre 2 et 4
    joueurs = [
        Joueur("Sagarex", random.randint(2, 4), random.sample(objets_disponibles_simu, 6)),
        Joueur("Francis", random.randint(2, 4), random.sample(objets_disponibles_simu, 6)),
        Joueur("Mastho", random.randint(2, 4), random.sample(objets_disponibles_simu, 6)),
        Joueur("Mr.Adam", random.randint(2, 4), random.sample(objets_disponibles_simu, 6))
    ]

    seuil_pv_essai_fuite = 5

    for j in joueurs:
        print(f"Initialisation de  avec {j.pv_base} PV de base et les objets spécifiés")
        print(f"Objets : {[objet.nom for objet in j.objets]}")
    print(f"Seuil de PV pour tenter la fuite : {seuil_pv_essai_fuite}\n")
    for i in range(x):
          # Réparer tous les objets avant chaque partie
        
        joueurs_copie = [copy.deepcopy(joueur) for joueur in joueurs]
        cartes_copie = copy.deepcopy(cartes)
        print(f"\n--- Partie {i+1} ---")
        ordonnanceur(joueurs_copie, cartes_copie, seuil_pv_essai_fuite, True)
