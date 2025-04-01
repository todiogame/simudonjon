from objets import *
import random

class Joueur:
    def __init__(self, nom, perso_instance, objets=None, medailles=0):
        self.nom = nom
        self.perso_obj = perso_instance
        self.personnage_nom = self.perso_obj.nom
        self.pv_base = self.perso_obj.pv_bonus
        self.pv_total = self.pv_base
        self.medailles = medailles
        self.pv_min_fuite = random.randint(2, 7)
        self.vivant = True
        self.dans_le_dj = True
        self.fuite_reussie = False
        self.tour = 1
        self.objets = objets if objets is not None else []
        self.objets_initiaux = objets.copy() if objets is not None else []
        for objet in self.objets:
            self.pv_total += objet.pv_bonus
        self.pile_monstres_vaincus = []
        self.score_final = 0
        self.jet_fuite = 0
        self.rejoue = False #actuellement en train de repiocher
        self.monstres_ajoutes_ce_tour = 0
        self.tiebreaker = False


    def ajouter_objet(self, objet):
        self.objets.append(objet)
        self.pv_total += objet.pv_bonus
        self.trier_objets_par_priorite() # maintenir les objets tries dans le bon ordre d'utilisation

    def calculer_modificateurs(self):
        modificateur_perso = getattr(self.perso_obj, 'modificateur_de', 0)
        modificateur_de = sum(objet.modificateur_de for objet in self.objets)
        return modificateur_de + modificateur_perso
    
    def reset_objets_intacts(self):
        for objet in self.objets:
            objet.repare()

    def fuite(self):
        self.fuite_reussie = True
        self.dans_le_dj = False

    def mort(self):
        self.vivant = False
        self.dans_le_dj = False
    
    def calculScoreFinal(self, log_details):
        log_details.append(f"Calcul du score de {self.nom} : {len(self.pile_monstres_vaincus)} monstres vaincus.")
        self.score_final = len(self.pile_monstres_vaincus)
        if any(monstre.effet and "GOLD" in monstre.effet for monstre in self.pile_monstres_vaincus):
            log_details.append(f"+1 pour le Golem d'or")
            self.score_final += 1
        for objet in self.objets:
            objet.en_score(self, log_details)
        if hasattr(self, 'perso_obj'):
            self.perso_obj.en_score(self, log_details)

    def trier_objets_par_priorite(self):
        self.objets = sorted(self.objets, key=lambda obj: obj.priorite, reverse=True)

    def rollDice(self, Jeu, log_details, jet_voulu=4, reversed=False, rerolled=False): #de base on se considere content avec un 4.
        jet_voulu = min(6,max(1, jet_voulu))
        jet = random.randint(1, 6)
        log_details.append(f"{self.nom} roll un {jet}")
        if hasattr(self, 'perso_obj'):
            jet = self.perso_obj.en_roll(self, jet, jet_voulu, reversed, rerolled, Jeu, log_details)
        
        for objet in self.objets:
            nouveau_jet = objet.en_roll(self, jet, jet_voulu, reversed, rerolled, Jeu, log_details)
            if nouveau_jet and nouveau_jet != jet:
                # log_details.append(f"{self.nom} jet de {jet} modifié en {nouveau_jet} ")
                jet = nouveau_jet
        return jet
    
    def reset_monstres_ajoutes(self):
        self.monstres_ajoutes_ce_tour = 0

    # Dans les parties où tu modifies le joueur.pile_monstres_vaincus, incrémente monstre_ajoutes_ce_tour
    def ajouter_monstre_vaincu(self, carte):
        self.pile_monstres_vaincus.append(carte)
        self.monstres_ajoutes_ce_tour += 1
        

    # Modifier la méthode deciderDeFuir
    def deciderDeFuir(self, Jeu, log_details):
        # Condition 1: PV faibles et peu d'options actives restantes
        # Note: sum(True/False) fonctionne comme un compte. <= 1 signifie 0 ou 1 objet actif/intact.
        pv_faible_et_peu_options = (self.pv_total <= self.pv_min_fuite
                                 and sum(getattr(objet, 'actif', False) and getattr(objet, 'intact', False)
                                         for objet in self.objets) <= 1)

        if pv_faible_et_peu_options:
             log_details.append(f"--> {self.nom} Condition Fuite 1 (PV Faible/Opt): VRAI (PV {self.pv_total} <= Seuil {self.pv_min_fuite})")
        # else: # Log optionnel si faux
        #      log_details.append(f"--> {self.nom} Condition Fuite 1 (PV Faible/Opt): FAUX")


        # Condition 2: Est-on le dernier joueur encore vivant ?
        # Compte combien de joueurs (y compris soi-même) sont vivants
        joueurs_vivants_compte = sum(1 for j in Jeu.joueurs if j.vivant)
        # Si le compte est 1 ou moins ET qu'on est soi-même vivant, on est le dernier
        dernier_joueur_vivant = (joueurs_vivants_compte <= 1 and self.vivant)

        if dernier_joueur_vivant:
             log_details.append(f"--> {self.nom} Condition Fuite 2 (Dernier Vivant): VRAI")
        # else: # Log optionnel si faux
        #      log_details.append(f"--> {self.nom} Condition Fuite 2 (Dernier Vivant): FAUX")

        # Raison de base pour envisager la fuite
        raison_envisager_fuite = pv_faible_et_peu_options or dernier_joueur_vivant

        # --- NOUVELLE CONDITION : Forcé de continuer si un fuyard a plus de monstres ---
        force_a_continuer = False
        max_monstres_fuyard = -1 # Initialise à -1 pour savoir si un fuyard existe
        fuyard_detecte = False

        for autre_joueur in Jeu.joueurs:
            # Vérifier si c'est un autre joueur et s'il a réussi sa fuite
            if autre_joueur is not self and autre_joueur.fuite_reussie:
                fuyard_detecte = True
                # Mettre à jour le maximum de monstres parmi les fuyards
                nb_monstres_autre = len(autre_joueur.pile_monstres_vaincus)
                max_monstres_fuyard = max(max_monstres_fuyard, nb_monstres_autre)

        # Si au moins un autre joueur a fui, comparer son score au nôtre
        if fuyard_detecte:
            mes_monstres = len(self.pile_monstres_vaincus)
            if max_monstres_fuyard > mes_monstres:
                force_a_continuer = True
                log_details.append(f"--> {self.nom} Condition Fuite 3 (Blocage): VRAI - Forcé de continuer (Fuyard max a {max_monstres_fuyard} MV vs soi {mes_monstres} MV)")
            # else: # Log optionnel
            #     log_details.append(f"--> {self.nom} Condition Fuite 3 (Blocage): FAUX - Aucun fuyard avec plus de {mes_monstres} MV.")
        # else: # Log optionnel
        #      log_details.append(f"--> {self.nom} Condition Fuite 3 (Blocage): Non applicable (aucun autre fuyard).")
        # --- FIN NOUVELLE CONDITION ---

        # Décision finale : on fuit SI on a une raison de base ET on n'est PAS forcé de continuer
        decision_finale = raison_envisager_fuite and not force_a_continuer

        # Log final de la décision
        if decision_finale:
             log_details.append(f"==> {self.nom} DECIDE DE TENTER LA FUITE.")
        else:
             if raison_envisager_fuite and force_a_continuer:
                  log_details.append(f"==> {self.nom} NE TENTE PAS LA FUITE (raison de base présente mais bloqué par score fuyard).")
             elif not raison_envisager_fuite:
                  log_details.append(f"==> {self.nom} NE TENTE PAS LA FUITE (pas de raison de base).")

        return decision_finale