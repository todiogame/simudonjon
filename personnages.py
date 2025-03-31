import random
import json
# Lire le fichier JSON une fois au début
with open('priorites_objets.json', 'r') as json_file:
    priorites_objets = json.load(json_file)

class Perso:
    def __init__(self, nom, pv_bonus=0, modificateur_de=0, effet=None):
        self.nom = nom
        self.pv_bonus = pv_bonus
        self.modificateur_de = modificateur_de
        self.effet = effet
        self.priorite = priorites_objets.get(nom, 49.5)  # Utilise la priorité du JSON ou 0 par défaut
        self.compteur = 0

    def rules(self, joueur, carte, Jeu, log_details):
        # rule condition to use the item
        return True
    def worthit(self, joueur, carte, Jeu, log_details):
        # worth it to use the item?
        return True
    def condition(self, joueur, carte, Jeu, log_details): # check if we use the item or not
        return (self.rules(joueur, carte, Jeu, log_details)
            and self.worthit(joueur, carte, Jeu, log_details))

    def combat_effet(self, joueur, carte, Jeu, log_details):
        pass
    def rencontre_effet(self, joueur, carte, Jeu, log_details):
        pass
    def rencontre_event_effet(self, joueur_proprietaire, joueur_actif, carte, Jeu, log_details):
        pass
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        pass
    def survie_effet(self, joueur, carte, Jeu, log_details):
        pass
    def decompte_effet(self,joueur, joueurs_final, log_details):
        pass
    def debut_tour(self, joueur, Jeu, log_details): 
        pass
    def debut_partie(self, joueur, Jeu, log_details): 
        pass    
    def fin_tour(self, joueur, Jeu, log_details): 
        pass
    def score_effet(self, joueur, log_details):
        pass
    def subit_dommages_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        pass
    def activated_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        pass
    def mort_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        pass
    def fuite_definitive_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        pass

    def en_subit_dommages(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if(joueur_proprietaire.dans_le_dj):
            self.subit_dommages_effet(joueur_proprietaire, joueur, carte, Jeu, log_details)
        
    def en_activated(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if joueur_proprietaire.dans_le_dj:
            self.activated_effet(joueur_proprietaire, joueur, objet, Jeu, log_details)
        
    def en_mort(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        self.mort_effet(joueur_proprietaire, joueur, objet, Jeu, log_details)
        
    def en_fuite_definitive(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        self.fuite_definitive_effet(joueur_proprietaire, joueur, objet, Jeu, log_details)

    def en_rencontre(self, joueur, carte, Jeu, log_details):
        self.rencontre_effet(joueur, carte, Jeu, log_details)

    def en_fuite(self, joueur, Jeu, log_details):
        pass

    def en_rencontre_event(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        self.rencontre_event_effet(joueur_proprietaire, joueur, carte, Jeu, log_details)    

    

    def en_combat(self, joueur, carte, Jeu, log_details):
        if self.condition(joueur, carte, Jeu, log_details):
            self.combat_effet(joueur, carte, Jeu, log_details)

    
    def en_vaincu(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if(joueur_proprietaire.dans_le_dj):
            self.vaincu_effet(joueur_proprietaire, joueur, carte, Jeu, log_details) 
    
    def en_survie(self, joueur, carte, Jeu, log_details):
            self.survie_effet(joueur, carte, Jeu, log_details)

    def en_score(self, joueur, log_details):
            self.score_effet(joueur, log_details)

    def en_decompte(self, joueur, joueurs_final, log_details):
            self.decompte_effet(joueur, joueurs_final, log_details)
            
    def en_roll(self, joueur,jet, jet_voulu, reversed, rerolled, Jeu, log_details):
        return jet
            
    
    def execute(self, joueur, carte, log_details):
        carte.executed = True
        joueur.ajouter_monstre_vaincu(carte)
        log_details.append(f"{joueur.nom} utilise {self.nom} pour exécuter {carte.titre}")

    def executeEtDefausse(self, joueur, carte, Jeu, log_details):
        carte.executed = True
        joueur.monstres_ajoutes_ce_tour += 1
        Jeu.defausse.append(carte)
        log_details.append(f"{joueur.nom} utilise {self.nom} pour exécuter et défausser {carte.titre}")

    def absorbe(self, joueur, carte, log_details):
        carte.executed = True
        joueur.pv_total += carte.puissance  # Absorber les PV
        joueur.ajouter_monstre_vaincu(carte)
        log_details.append(f"{joueur.nom} utilise {self.nom} sur {carte.titre} pour absorber {carte.puissance} PV. Total {joueur.pv_total} PV.")

    def reduc_damage(self, value, joueur, carte, log_details):
        carte.dommages = max(carte.dommages - value, 0)
        if(value):
            log_details.append(f"{joueur.nom} utilise {self.nom} sur {carte.titre} pour réduire les dommages de {value}.")

    def add_damage(self, value, joueur, carte, log_details):
        carte.dommages = carte.dommages + value
        log_details.append(f"{joueur.nom} utilise {self.nom} sur {carte.titre} pour augmenter les dommages de {value}.")

    def gagnePV(self, value, joueur, log_details):
        joueur.pv_total += value
        log_details.append(f"{joueur.nom} utilise {self.nom} pour gagner {value} PV. Total {joueur.pv_total} PV.")

    def perdPV(self, value, joueur, log_details):
        joueur.pv_total -= value
        log_details.append(f"{joueur.nom} utilise {self.nom} et perd {value} PV. Total {joueur.pv_total} PV.")
        if(joueur.pv_total <= 0): joueur.mort()

    def survit(self, value, joueur, carte, log_details):
        joueur.pv_total = value
        joueur.ajouter_monstre_vaincu(carte)
        log_details.append(f"{joueur.nom} utilise {self.nom} pour survivre avec {value} PV et vaincre {carte.titre}")

    def piocheItem(self, joueur, Jeu, log_details):
        if len(Jeu.objets_dispo):
            nouvel_objet = random.choice(Jeu.objets_dispo)
            Jeu.objets_dispo.remove(nouvel_objet)
            joueur.ajouter_objet(nouvel_objet)
            log_details.append(f"{joueur.nom} utilise {self.nom} pour piocher un nouvel objet: {nouvel_objet.nom},  {f"PV bonus: {nouvel_objet.pv_bonus}. Nouveau PV {joueur.nom}: {joueur.pv_total} PV." if nouvel_objet.pv_bonus else ''}")
            
    def scoreChange(self, value, joueur, log_details):
        if value > 0:
            log_details.append(f"{self.nom} , gain de {value} points de victoire qui s'ajoutent aux {joueur.score_final} points, total {joueur.score_final + value}.")
        else:
            log_details.append(f"{self.nom} , perte de {value} points de victoire qui se soustraient aux {joueur.score_final} points, total {joueur.score_final + value}.")
        joueur.score_final += value


class Ninja(Perso):
    def __init__(self):
        super().__init__("Ninja", 3, 3)

class Princesse(Perso):
    def __init__(self):
        # Le PV de base (2) est géré par la classe Joueur
        super().__init__("Princesse", 2)
        self.premier_objet_pioche = False # Etat pour la capacité unique

    def debut_tour(self, joueur, Jeu, log_details):
        # Se déclenche seulement au tour 1 du joueur
        if joueur.tour == 1 and not self.premier_objet_pioche:
            log_details.append(f"{joueur.nom} ({self.nom}) utilise sa capacité au début du tour 1.")
            self.piocheItem(joueur, Jeu, log_details) # Utilise la méthode héritée
            self.premier_objet_pioche = True # Marquer comme utilisé


class MercenaireOrc(Perso):
    def __init__(self):
        # Le PV de base (5) est géré par la classe Joueur
        super().__init__("Mercenaire Orc", 5)
        
        
class ChevalierDragon(Perso):
    def __init__(self):
        super().__init__(nom="Chevalier Dragon", pv_bonus=2)

    def combat_effet(self, joueur, carte, Jeu, log_details):
        if "Dragon" in getattr(carte, 'types', []) and not Jeu.traquenard_actif and not carte.executed:
            # Utilise la méthode executeEtDefausse héritée de Perso
            self.executeEtDefausse(joueur, carte, Jeu, log_details)
            
persos_disponibles=[
    Ninja(),
    Princesse(),
    MercenaireOrc(),
    ChevalierDragon(), # Ajouté
]

__all__=[
    "Ninja",
    "Princesse",
    "MercenaireOrc",
    "ChevalierDragon", # Ajouté
]