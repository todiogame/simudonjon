import random
import numpy as np
from objets import *
from joueurs import Joueur
from monstres import CarteMonstre, DonjonDeck, CarteEvent
from heros import *
from heros import persos_disponibles
def ordonnanceur(joueurs, donjon, pv_min_fuite, objets_dispo, log=True):
    # arreter la simulation si on a un objet casse dans une main
    for j in joueurs:
        for o in j.objets:
            if not o.intact: 1/0

    log_details = []
    nb_joueurs = len(joueurs)
    
    donjon.melange()
    class Jeu:
        defausse = []
        tour = 0
        execute_next_monster = False
        traquenard_actif = False
        donjon
    Jeu.joueurs = joueurs
    Jeu.donjon = donjon
    Jeu.objets_dispo = objets_dispo
    Jeu.nb_joueurs = nb_joueurs
    log_details = []
    index_joueur = 0  # Initialisation de l'index du joueur courant
    
    for j in joueurs:
        j.trier_objets_par_priorite()
        for objet in j.objets:
            objet.debut_partie(j, Jeu, log_details)
    
    if log:
        for detail in log_details:
            print(detail)
        print("\n")
    log_details = []
    # Boucle de jeu principale
    while not Jeu.donjon.vide:
        Jeu.tour += 1
        
        if log:
            for detail in log_details:
                print(detail)
        log_details = []

        # Vérifier s'il reste des joueurs vivants
        if not any(True for joueur in joueurs if joueur.dans_le_dj):
            log_details.append("Tous les joueurs ont fini.")
            break

        # Le joueur courant
        while not joueurs[index_joueur].dans_le_dj:
            index_joueur += 1
            if index_joueur >= nb_joueurs:
                index_joueur = 0
            # Ajouter une vérification pour éviter une boucle infinie
            if all(not joueur.dans_le_dj for joueur in joueurs):
                break

        joueur = joueurs[index_joueur]

        log_details.append(f"Tour de {joueur.nom} ({joueur.perso_obj.nom}), {joueur.pv_total}PV, {len(joueur.pile_monstres_vaincus)}MV {',qui rejoue' if joueur.rejoue else ''}")
        
        # trigger de debut de tour
        if not joueur.rejoue:
            if hasattr(joueur, 'perso_obj'):
                joueur.perso_obj.debut_tour(joueur, Jeu, log_details)
            for objet in joueur.objets:
                objet.debut_tour(joueur, Jeu, log_details)
        for j in joueurs:
            j.rejoue = False
            j.reset_monstres_ajoutes()  # Réinitialise le compteur de monstres ajoutés pour chaque joueur
        
        # Le joueur pioche une carte
        carte = donjon.prochaine_carte()
        if carte is None:
            log_details.append("Le Donjon est vide. Fin de la partie.")
            break
        if isinstance(carte, CarteMonstre):
            carte.executed = False

        joueur.jet_fuite_lance = False

        if joueur.deciderDeFuir(Jeu, log_details):
            # Tentative de fuite
            joueur.jet_fuite = joueur.rollDice(Jeu, log_details) + joueur.calculer_modificateurs()
            log_details.append(f"Tentative de fuite, {joueur.jet_fuite} (avec modif {joueur.calculer_modificateurs()}) ")
            joueur.jet_fuite_lance = True
            #use items en_fuite
            for objet in joueur.objets:
                objet.en_fuite(joueur, Jeu, log_details)
            



        log_details.append(f"tour {joueur.tour}. {joueur.nom} ({joueur.perso_obj.nom}) a pioché {carte.titre}.")
        effet_carte = carte.effet
        carte_ignoree = False
        if isinstance(carte, CarteEvent):
            Jeu.execute_next_monster = False
            Jeu.traquenard_actif = False
            for joueur_proprietaire in Jeu.joueurs:
                for objet in joueur_proprietaire.objets:
                    objet.en_rencontre_event(joueur_proprietaire, joueur, carte, Jeu, log_details)
            
            if effet_carte == "INCEPTION":
                event_defausse = [c for c in Jeu.defausse if getattr(c, 'event', False)]
                if(event_defausse):
                    effet_carte = event_defausse[0].effet
                    log_details.append(f"{carte.titre} copie la dernière carte événement dans la défausse: {event_defausse[0].titre}.")
                else:
                    log_details.append(f"Pas de carte événement dans la défausse.") 
            if effet_carte == "HEAL":
                joueur.pv_total += 3
                log_details.append(f"{joueur.nom} gagne 3 PV grâce à {carte.titre}. PV restant: {joueur.pv_total}")
                # Ajouter 2 PV aux autres joueurs
                for autre_joueur in joueurs:
                    if autre_joueur != joueur and autre_joueur.dans_le_dj:
                        autre_joueur.pv_total += 2
                        log_details.append(f"{autre_joueur.nom} gagne 2 PV grâce à {carte.titre}. PV restant: {autre_joueur.pv_total}")

            if effet_carte == "REPAIR":
                objets_brisés = [objet for objet in joueur.objets if not objet.intact]
                if objets_brisés:
                    objet_reparé = random.choice(objets_brisés)
                    objet_reparé.repare()
                    joueur.pv_total += objet_reparé.pv_bonus
                    log_details.append(f"Réparé {objet_reparé.nom} grâce à {carte.titre}. PV total augmenté de {objet_reparé.pv_bonus}, PV restant: {joueur.pv_total}")
                else: log_details.append(f"{carte.titre} n'a' rien a reparer.")

            if effet_carte == "ALLY":
                Jeu.execute_next_monster = True
                log_details.append(f"L'effet {carte.titre} est actif. La prochaine carte monstre peut être exécutée.")

            if effet_carte == "TRAP":
                Jeu.traquenard_actif = True
                Jeu.execute_next_monster = False
                log_details.append(f"L'effet {carte.titre} est actif. La prochaine carte monstre Ne peut PAS être exécutée.")

            if effet_carte == "INJECTION":
                golem_count = sum(1 for monstre in joueur.pile_monstres_vaincus if "Golem" in monstre.types)
                if golem_count > 0:
                    joueur.pv_total += 2 * golem_count
                    log_details.append(f"Gagnez {2 * golem_count} PV grâce à {carte.titre} (2 PV pour chaque Golem). PV restant: {joueur.pv_total}")
                else:
                    log_details.append(f"{carte.titre} ne fait rien.")
                    
            if effet_carte == "FORTUNE_WHEEL":
                jet_wheel = joueur.rollDice(Jeu, log_details, 2)
                joueur.pv_total += jet_wheel
                log_details.append(f"{joueur.nom} a gagné {jet_wheel} PV grâce à {carte.titre}. PV: {joueur.pv_total}")
                if jet_wheel == 1:
                    objets_intacts = [objet for objet in joueur.objets if objet.intact]
                    if objets_intacts:
                        objet_casse_wheel = random.choice(objets_intacts)
                        log_details.append(f"{carte.titre} brise {objet_casse_wheel.nom}.")
                        objet_casse_wheel.destroy(joueur, Jeu, log_details)
                        if objet_casse_wheel.pv_bonus:
                            joueur.pv_total -= objet_casse_wheel.pv_bonus
                            log_details.append(f"L'objet casse {objet_casse_wheel.nom} donnait {objet_casse_wheel.pv_bonus}PV ca fait ca de moins. PV restant {joueur.pv_total}PV")
            
            if effet_carte == "SOULSTORM":
                for autre_joueur in joueurs:
                    if autre_joueur.dans_le_dj:
                        if autre_joueur.pile_monstres_vaincus:
                            monstre_remis = autre_joueur.pile_monstres_vaincus.pop()
                            donjon.ajouter_monstre(monstre_remis)
                            log_details.append(f"{autre_joueur.nom} a remis {monstre_remis.titre} dans le Donjon.")
                        else:
                            log_details.append(f"{autre_joueur.nom} n'a rien a remettre dans le Donjon.")
                donjon.remelange()
                log_details.append(f"Le donjon est remelangé.")
                
            if effet_carte == "DRAG":
                dragons_trouves = False
                for autre_joueur in joueurs:
                    if autre_joueur.dans_le_dj:
                        dragons_a_defausser = [monstre for monstre in autre_joueur.pile_monstres_vaincus if "Dragon" in monstre.types]
                        if dragons_a_defausser:
                            dragons_trouves = True
                        for dragon in dragons_a_defausser:
                            autre_joueur.pile_monstres_vaincus.remove(dragon)
                            Jeu.defausse.append(dragon)
                            log_details.append(f"{autre_joueur.nom} défausse {dragon.titre} et pioche un objet.")
                            if len(Jeu.objets_dispo):
                                nouvel_objet = random.choice(Jeu.objets_dispo)
                                Jeu.objets_dispo.remove(nouvel_objet)
                                autre_joueur.ajouter_objet(nouvel_objet)
                                log_details.append(f"{autre_joueur.nom} pioche un nouvel objet: {nouvel_objet.nom}, PV bonus: {nouvel_objet.pv_bonus}, Jet de fuite: {nouvel_objet.modificateur_de}. Nouveau PV {joueur.nom}: {joueur.pv_total} PV.")
                            break
                if not dragons_trouves:
                    log_details.append("Aucun joueur n'a de Dragons à défausser.")

            if effet_carte == "SHOP":
                objets_intacts = [objet for objet in joueur.objets if objet.intact]
                if len(objets_intacts) < 4:
                    log_details.append(f"{joueur.nom} a moins de 4 objets intacts et utilise l'effet {carte.titre} pour piocher un objet.")
                    if len(Jeu.objets_dispo):
                        nouvel_objet = random.choice(Jeu.objets_dispo)
                        Jeu.objets_dispo.remove(nouvel_objet)
                        joueur.ajouter_objet(nouvel_objet)
                        log_details.append(f"{joueur.nom} pioche un nouvel objet: {nouvel_objet.nom}, PV bonus: {nouvel_objet.pv_bonus}, Jet de fuite: {nouvel_objet.modificateur_de}. Nouveau PV {joueur.nom}: {joueur.pv_total} PV.")
                    else:
                        log_details.append(f"Pas d'objet disponible pour {joueur.nom} à piocher.")
                else:
                    log_details.append(f"{joueur.nom} a {len(objets_intacts)} objets intacts, il n'en pioche pas.")

            # Le joueur rejoue
            Jeu.defausse.append(carte)
            joueur.rejoue = True
            
        if isinstance(carte, CarteMonstre):
            if effet_carte:
                if effet_carte == "MIROIR":
                    log_details.append(f"Le {carte.titre} est pioche.")
                    if joueur.pile_monstres_vaincus:
                        carte_copiee = joueur.pile_monstres_vaincus[-1]

                        carte.puissance = carte_copiee.puissance
                        carte.types = carte_copiee.types
                        effet_carte = carte_copiee.effet
                        log_details.append(f"Le {carte.titre} copie {carte_copiee.titre} avec une puissance de {carte.puissance}.")
                    else:
                        carte.puissance = 0
                        carte.types = []
                        log_details.append(f"Le {carte.titre} n'a pas de carte a copier, puissance zero.")

                if effet_carte == "SHAPESHIFTER":
                    # on parcours les type_tags des objets intacts du joueur
                    # le premier type qu'on trouve on le donne au monstre
                    for objet in joueur.objets:
                        if objet.intact and objet.types_tags:
                            carte.types = objet.types_tags[0]
                            log_details.append(f"Le {carte.titre} devient un {carte.types} (car {joueur.nom} a {objet.nom}.).")
                            break
                            
                if effet_carte == "SLEEPING":
                    jet_dragon = joueur.rollDice(Jeu, log_details)
                    if jet_dragon <= 3:
                        carte.puissance = 9
                    else:
                        carte.puissance = 0
                    log_details.append(f"Rencontré {carte.titre}, jet de {jet_dragon}, puissance déterminée à {carte.puissance}.")

                if effet_carte == "MIMIC":
                    objets_intacts = [objet for objet in joueur.objets if objet.intact]
                    carte.puissance = len(objets_intacts)
                    log_details.append(f"Rencontré {carte.titre}, puissance déterminée à {carte.puissance} (égale au nombre d'objets possédés).")

                if effet_carte == "MONKEY_TEAM":
                    nb_joueurs_dans_le_dj = 0
                    for j in Jeu.joueurs:
                        if j.dans_le_dj:
                            nb_joueurs_dans_le_dj += 1
                    carte.puissance = nb_joueurs_dans_le_dj * 2
                    log_details.append(f"Rencontré {carte.titre}, puissance déterminée à {carte.puissance} (2x le nombre de joueurs dans le donjon).")
                    
                if effet_carte == "REAPER":
                    carte.puissance = joueur.pv_total // 2
                    log_details.append(f"Rencontré {carte.titre}, puissance déterminée à {carte.puissance} (la moitie des PV (arrondi inferieur)).")

                if effet_carte == "NOOB":
                    if joueur.medailles > 0:
                        carte.puissance = 2
                        log_details.append(f"Rencontré {carte.titre}, puissance réduite à 2 grâce aux médailles.")

                if effet_carte == "MEDAIL":
                    nb_medailles = 0
                    for j in Jeu.joueurs:
                        nb_medailles += 1
                    carte.puissance = nb_medailles
                    log_details.append(f"Rencontré {carte.titre}, puissance déterminée à {carte.puissance} (égale au nombre de médailles).")

                if effet_carte == "SCAVENGER":
                    carte.puissance = len(joueur.pile_monstres_vaincus)
                    log_details.append(f"Rencontré {carte.titre}, puissance déterminée à {carte.puissance} (égale au nombre de monstres vaincus).")
            
            carte.dommages = carte.puissance

            if effet_carte and "ADD_2_DOM" in effet_carte:
                carte.dommages += 2  # Ajouter 2 dommages supplémentaires pour Chevaucheur de rat
                log_details.append(f"{carte.titre} inflige 2 dommages supplémentaires.")
            if effet_carte == "LORD" and joueur.medailles > 0:
                carte.dommages += 4 * joueur.medailles
                log_details.append(f"Rencontré {carte.titre}, inflige +4 dommages par médaille, total {carte.dommages}.")

            
            #use items en_rencontre
            for joueur_proprietaire in Jeu.joueurs:
                joueur_proprietaire.perso_obj.en_rencontre(joueur_proprietaire, joueur, carte, Jeu, log_details)

                for objet in joueur_proprietaire.objets:
                    objet.en_rencontre(joueur_proprietaire, joueur, carte, Jeu, log_details)
                

            if joueur.jet_fuite_lance: 
                if joueur.jet_fuite >= carte.puissance:
                    # Fuite réussie
                    log_details.append(f"Fuite réussie avec un jet de {joueur.jet_fuite} contre {carte.titre} puissance {carte.puissance}\n")
                    joueur.fuite()
                    donjon.rajoute_en_haut_de_la_pile(carte)
                    joueur.jet_fuite_lance = False
                    for joueur_proprietaire in Jeu.joueurs:
                        for objet in joueur_proprietaire.objets:
                            objet.en_fuite_definitive(joueur_proprietaire, joueur, carte, Jeu, log_details)
                    continue
                else:
                    # Fuite échouée, affronter le monstre normalement
                    log_details.append(f"Fuite échouée avec un jet de {joueur.jet_fuite} contre {carte.puissance}.")
                    joueur.jet_fuite_lance = False

            if Jeu.execute_next_monster and not Jeu.traquenard_actif:
                carte.executed = True
                joueur.ajouter_monstre_vaincu(carte)
                Jeu.execute_next_monster = False
                log_details.append(f"L'effet Exécute le prochain monstre est utilisé sur {carte.titre}.")
            else:
                if effet_carte == "KRAKEN":
                    # Vérifier si le joueur a un objet intact avec puissance 10
                    has_power_10 = False
                    for objet in joueur.objets:
                        if objet.intact and 10 in objet.puissance_tags:
                            log_details.append(f"{joueur.nom} decide d'affronter {carte.titre} confiant avec ({objet.nom})")
                            has_power_10 = True
                            break
                    if not has_power_10:
                        log_details.append(f"{joueur.nom} decide de remettre le {carte.titre} car il n'a pas d'objet pour le gerer.")
                        Jeu.defausse.append(carte) #todo remettre en dessous de la pile
                        carte_ignoree = True

                if effet_carte == "GUARDIAN_ANGEL":
                    # Vérifier si le joueur a un objet intact avec puissance 8
                    has_power_8 = False
                    for objet in joueur.objets:
                        if objet.intact and 8 in objet.puissance_tags:
                            log_details.append(f"{joueur.nom} decide d'affronter {carte.titre} confiant avec ({objet.nom})")
                            has_power_8 = True
                            break
                    if not has_power_8:
                        log_details.append(f"{joueur.nom} decide de defausser {carte.titre} car il n'a pas d'objet pour le gerer.")
                        Jeu.defausse.append(carte)
                        carte_ignoree = True
                
                #use items
                if not carte_ignoree:
                    joueur.perso_obj.en_combat(joueur, carte, Jeu, log_details)
                    for objet in joueur.objets:
                        objet.en_combat(joueur, carte, Jeu, log_details)
                        if carte.executed or (carte.dommages <= 0 and not effet_carte == "LIMON") or joueur.fuite_reussie:
                            break
                    if(not joueur.dans_le_dj):
                        donjon.rajoute_en_haut_de_la_pile(carte)
                        continue
                    joueur.perso_obj.en_combat_late(joueur, carte, Jeu, log_details)
                
            if not carte_ignoree and not carte.executed:
                Jeu.traquenard_actif = False
                joueur.pv_total -= carte.dommages
                

                #item survie ici
                # Ne pas ajouter le Gobelin Fantôme à la pile des monstres vaincus
                if effet_carte == "MAUDIT":  
                    Jeu.defausse.append(carte)
                    log_details.append(f"Le {carte.titre} disparait.")
                else:
                    if (joueur.vivant): joueur.ajouter_monstre_vaincu(carte)
                if effet_carte == "LIMON":
                    objets_intacts = [objet for objet in joueur.objets if objet.intact]
                    if objets_intacts:
                        objet_avale = random.choice(objets_intacts)
                        log_details.append(f"Le {carte.titre} avale {objet_avale.nom}.")
                        objet_avale.destroy(joueur, Jeu, log_details)
                        if objet_avale.pv_bonus:
                            joueur.pv_total -= objet_avale.pv_bonus
                            log_details.append(f"L'objet avalé {objet_avale.nom} donnait {objet_avale.pv_bonus}PV ca fait ca de moins. PV restant {joueur.pv_total}PV")
            
                log_details.append(f"Affronté {carte.titre}, perdu {carte.dommages} PV, restant {joueur.pv_total} PV.")
                
                for joueur_proprietaire in Jeu.joueurs:
                    joueur_proprietaire.perso_obj.en_subit_dommages(joueur_proprietaire, joueur, carte, Jeu, log_details)
                    for objet in joueur_proprietaire.objets:
                        objet.en_subit_dommages(joueur_proprietaire, joueur, carte, Jeu, log_details)
                        
                if effet_carte and "ARRA" in effet_carte and carte.effet and "ARRA" in carte.effet and len(joueur.pile_monstres_vaincus) > 1 and carte.dommages > 0:
                    # fix hard du miroir il ne copie pas l'arracheur sinon ca boucle infinie...
                    monstre_remis = joueur.pile_monstres_vaincus.pop(-2)
                    donjon.rajoute_en_haut_de_la_pile(monstre_remis)
                    log_details.append(f"L'Arracheur a remis {monstre_remis.titre} sur le Donjon.")

                if effet_carte == "MEDAIL" and carte.dommages > 0 and joueur.medailles >= 0:
                    joueur.medailles -= 1
                    log_details.append(f"Perdu une medaille en affrontant {carte.titre}, médailles restantes: {joueur.medailles}")

            if effet_carte == "SHAPESHIFTER":
                # il perd son type ici
                carte.types = []

            if joueur.pv_total <= 0:
                #use items survie
                for objet in joueur.objets:
                    objet.en_survie(joueur, carte, Jeu, log_details)
                    if joueur.pv_total > 0:
                        break
            # drop Egide
            if not carte_ignoree and effet_carte == "GUARDIAN_ANGEL":
                log_details.append(f"{joueur.nom} recoit l'Egide !")
                joueur.ajouter_objet(Egide())

            # vraiment mort        
            if joueur.pv_total <= 0:
                joueur.mort(log_details)
                log_details.append(f"OUPS!! Mort de {joueur.nom}, a court de PV.\n")
                
                for joueur_proprietaire in Jeu.joueurs:
                    for objet in joueur_proprietaire.objets:
                        objet.en_mort(joueur_proprietaire, joueur, carte, Jeu, log_details)
                
                donjon.rajoute_en_haut_de_la_pile(carte)
                index_joueur += 1
                if index_joueur >= nb_joueurs:
                    index_joueur = 0
                continue
            
            #use items en_vaincu
            joueur.perso_obj.en_vaincu(joueur, joueur, carte, Jeu, log_details) #opti, que le savant fou
            for joueur_proprietaire in Jeu.joueurs:
                for objet in joueur_proprietaire.objets:
                    objet.en_vaincu(joueur_proprietaire, joueur, carte, Jeu, log_details)

            if joueur.dans_le_dj and not Jeu.execute_next_monster:
                #sequence objets fin du tour
                for objet in joueur.objets:
                    objet.fin_tour(joueur, Jeu, log_details)
                # Passer son tour, au joueur suivant
                joueur.tour += 1
                if len([joueur for joueur in joueurs if joueur.dans_le_dj]) > 1:
                    log_details.append(f"{joueur.nom} passe son tour.\n")
                    index_joueur += 1
                    if index_joueur >= nb_joueurs:
                        index_joueur = 0
            else:
                # Le joueur rejoue
                joueur.rejoue = True

    log_details.append(f"\nFIN DE LA PARTIE !\nCalcul des scores:")
    # Calculer les scores finaux pour chaque joueur
    for j in joueurs:
        j.calculScoreFinal(log_details)
        log_details.append(f"Score final: {j.nom} : {j.score_final}, {'mort' if not j.vivant else 'fui' if j.fuite_reussie else 'ponceur' if j.dans_le_dj else 'vivant'}.\n")
    # Vérifier si des joueurs sont arrivés vivants au bout du donjon
    joueurs_dans_le_dj = [j for j in joueurs if j.dans_le_dj]

    # Loguer les joueurs toujours dans le donjon
    if joueurs_dans_le_dj:
        log_details.append("Les joueurs suivants ont poncé le donjon :")
        for j in joueurs_dans_le_dj:
            log_details.append(f"- {j.nom}")

    # Créer la liste finale des joueurs comptés
    if joueurs_dans_le_dj:
        joueurs_final = joueurs_dans_le_dj
        log_details.append("Des joueurs sont arrivés vivants au bout du donjon, les fuyards sont exclus.")
    else:
        joueurs_final = [j for j in joueurs if j.vivant]
        log_details.append("Aucun joueur n'a poncé le donjon, tous les joueurs vivants comptent.")

    # use items en_decompte
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
            else:
                log_details.append(f"{j.nom}  A BUG ?? {j.vivant} {j.fuite_reussie} {j.dans_le_dj}")

    # Trier les joueurs par ordre de score décroissant
    joueurs_final.sort(key=lambda j: j.score_final, reverse=True)

    # Déterminer le vainqueur après avoir appliqué tous les effets de décompte
    joueurs_egalite = [j for j in joueurs_final if j.score_final == joueurs_final[0].score_final]

    if len(joueurs_egalite) > 1:
        joueurs_avec_tiebreaker = [j for j in joueurs if j.tiebreaker and j.vivant]
        if joueurs_avec_tiebreaker:
            vainqueur = joueurs_avec_tiebreaker[0]
            log_details.append(f"{vainqueur.nom} remporte la manche grâce à son avantage en cas d'égalité.")
        else:
            vainqueur = random.choice(joueurs_egalite)
            log_details.append(f"{vainqueur.nom} remporte la manche suite à un tirage au sort parmi les joueurs avec le même score.")
    elif len(joueurs_egalite) == 1:
        vainqueur = joueurs_egalite[0]
    else:
        vainqueur = None

    # Afficher les résultats avec une médaille pour le vainqueur
    for i, j in enumerate(joueurs_final):
        medaille = "MEDAILLE" if j == vainqueur else ""
        log_details.append(f"{j.nom} : {j.score_final} points, PV restant {j.pv_total}. {medaille}")

    log_details.append("\n")

    # Impression des logs (facultatif)
    if log:
        for detail in log_details:
            print(detail)

    # Retourner le joueur vainqueur s'il y en a un
    return vainqueur, joueurs



def loguer_x_parties(x=1):
    # Constantes pour cette fonction de test/log
    seuil_pv_essai_fuite = 6 # Cohérent avec prio.py/donjon.py
    nb_items_par_joueur = 5 # Nombre d'items pour les joueurs non-test
    nb_joueurs_total = 4    # On garde 4 joueurs pour ce mode log
    nom_joueur_test = "Sagarex"
    perso_test = Flutiste() # Personnage spécifique pour Sagarex
    noms_joueurs_base = ["Sagarex", "Francis", "Mastho", "Mr.Adam", "Diouze", "Nicoco"]

    # Liste des objets spécifiques pour le joueur de test
    # IMPORTANT: Assure-toi que ces classes existent bien dans objets.py
    noms_objets_test = [
        "Couronne d'épines",
        # "Codex Diabolus",
        # "Potion feerique",
        # "Sac de Constantinople",
        # "Trou Noir Portatif"
    ]

    for i in range(x):
        print(f"\n--- Partie Test Log {i+1} ---")

        # Préparer les objets disponibles pour cette partie
        objets_pool_global = list(objets_disponibles) # Copie de la liste globale
        objets_disponibles_partie = []
        objets_test_instances = []

        # Extraire les objets de test et créer la liste des objets restants
        for objet_global in objets_pool_global:
            objet_global.repare() # Réparer tous les objets de la copie
            if objet_global.nom in noms_objets_test:
                objets_test_instances.append(objet_global)
            else:
                objets_disponibles_partie.append(objet_global)

        # Vérifier si on a trouvé tous les objets de test
        if len(objets_test_instances) != len(noms_objets_test):
            print(f"ERREUR: Impossible de trouver tous les objets de test requis.")
            print(f"  Requis: {noms_objets_test}")
            print(f"  Trouvés: {[o.nom for o in objets_test_instances]}")
            continue # Passer à la prochaine partie de log

        # Préparer les personnages
        joueurs = []
        noms_joueurs = noms_joueurs_base[:nb_joueurs_total]

        # Assigner les personnages
        persos_assigner = []
        # Exclure le perso de test de la liste pour l'assignation aléatoire
        autres_persos_pool = [p for p in persos_disponibles if p.nom != perso_test.nom]
        if len(autres_persos_pool) < nb_joueurs_total - 1:
             print(f"ERREUR: Pas assez de personnages disponibles ({len(autres_persos_pool)}) pour les autres joueurs.")
             continue

        persos_autres_assignes = random.sample(autres_persos_pool, nb_joueurs_total - 1)

        # Créer la liste ordonnée des persos pour chaque joueur
        perso_map = {}
        perso_map[nom_joueur_test] = perso_test
        idx_autres = 0
        for nom in noms_joueurs:
            if nom != nom_joueur_test:
                perso_map[nom] = persos_autres_assignes[idx_autres]
                idx_autres += 1

        # Créer les joueurs
        for nom_joueur in noms_joueurs:
            perso_instance = perso_map[nom_joueur]
            objets_joueur = []

            if nom_joueur == nom_joueur_test:
                objets_joueur = objets_test_instances[:] # Utiliser les objets de test
                #assigner des objets pour completer la main
                if len(objets_joueur) < nb_items_par_joueur:
                    nb_a_ajouter = nb_items_par_joueur - len(objets_joueur)
                    extra_objs = random.sample(objets_disponibles_partie, nb_a_ajouter)
                    objets_joueur += extra_objs
                    for obj in extra_objs:
                        objets_disponibles_partie.remove(obj)
            else:
                # Assigner des objets aléatoires aux autres
                if len(objets_disponibles_partie) < nb_items_par_joueur:
                    print(f"ERREUR: Pas assez d'objets disponibles ({len(objets_disponibles_partie)}) pour {nom_joueur}.")
                    # Gérer l'erreur - ici on saute la partie
                    break # Sortir de la boucle de création joueur
                objets_joueur = random.sample(objets_disponibles_partie, nb_items_par_joueur)
                # Retirer les objets assignés du pool pour éviter duplicats
                for obj in objets_joueur:
                    objets_disponibles_partie.remove(obj)

            # Si on n'a pas pu assigner d'objets à un joueur non-test, on arrête
            if nom_joueur != nom_joueur_test and not objets_joueur:
                 joueurs = [] # Vider la liste pour indiquer l'échec
                 break

            # Créer l'instance Joueur
            joueur_cree = Joueur(nom_joueur, perso_instance, objets_joueur, int(random.random() < 0.3))
            joueurs.append(joueur_cree)

        # Vérifier si la création a échoué
        if len(joueurs) != nb_joueurs_total:
             print("Échec de la création des joueurs pour cette partie.")
             continue # Passer à la partie suivante

        # Logs initiaux
        for j in joueurs:
            # Le log détaillé est déjà dans Joueur.__init__
            print(f"  -> {j.nom} ({j.personnage_nom}) commence avec {j.pv_total} PV."+ (f" Il a {j.medailles} medaille(s)." if j.medailles else ""))
            print(f"     Objets: {[o.nom for o in j.objets]}")

        print(f"Seuil de PV pour tenter la fuite : {seuil_pv_essai_fuite}\n")

        # Lancer la simulation
        deck = DonjonDeck()
        # Les objets restants dans objets_disponibles_partie sont passés à l'ordonnanceur
        ordonnanceur(joueurs, deck, seuil_pv_essai_fuite, objets_disponibles_partie, True) # log=True
