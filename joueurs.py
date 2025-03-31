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
        self.pv_min_fuite = 5
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
        
    def deciderDeFuir(self, Jeu, log_details):
        decision_pv_faible = (self.pv_total <= self.pv_min_fuite
                               and sum(objet.actif and objet.intact for objet in self.objets) <= 1)

        # Vérifier si tous les autres joueurs sont morts
        # le marteau d'eternite counter mais bon on est plus a ca pret
        autres_joueurs_morts = True
        joueurs_vivants = 0
        for joueur in Jeu.joueurs:
            if joueur.vivant:
                joueurs_vivants += 1

        autres_joueurs_morts = (joueurs_vivants <= 1) # Only the current player is alive

        decision = decision_pv_faible or autres_joueurs_morts
        return decision