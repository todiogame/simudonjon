from objets import *

class Joueur:
    def __init__(self, nom, pv_base, objets=None, medailles=0):
        self.nom = nom
        self.pv_base = pv_base
        self.pv_total = pv_base
        self.medailles = medailles
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

    def ajouter_objet(self, objet):
        self.objets.append(objet)
        self.pv_total += objet.pv_bonus

    def calculer_modificateurs(self):
        modificateur_de = sum(objet.modificateur_de for objet in self.objets)
        return modificateur_de
    
    def reset_objets_intacts(self):
        for objet in self.objets:
            objet.reset_intact()

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

    def trier_objets_par_priorite(self):
        self.objets = sorted(self.objets, key=lambda obj: obj.priorite, reverse=True)
