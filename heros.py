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
        self.capacite_utilisee = False
        
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
    def combat_effet_late(self, joueur, carte, Jeu, log_details):
        pass
    def rencontre_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
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

    def en_rencontre(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        self.rencontre_effet(joueur_proprietaire, joueur, carte, Jeu, log_details)

    def en_fuite(self, joueur, Jeu, log_details):
        pass

    def en_rencontre_event(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        self.rencontre_event_effet(joueur_proprietaire, joueur, carte, Jeu, log_details)    

    

    def en_combat(self, joueur, carte, Jeu, log_details):
        if self.condition(joueur, carte, Jeu, log_details):
            self.combat_effet(joueur, carte, Jeu, log_details)
            
    def en_combat_late(self, joueur, carte, Jeu, log_details):
        if self.condition(joueur, carte, Jeu, log_details):
            self.combat_effet_late(joueur, carte, Jeu, log_details)

    
    
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
        if(joueur.pv_total <= 0): joueur.mort(log_details)

    def survit(self, value, joueur, carte, log_details):
        joueur.pv_total = value
        joueur.ajouter_monstre_vaincu(carte)
        log_details.append(f"{joueur.nom} utilise {self.nom} pour survivre avec {value} PV et vaincre {carte.titre}")

    def piocheItem(self, joueur, Jeu, log_details):
        if len(Jeu.objets_dispo):
            nouvel_objet = random.choice(Jeu.objets_dispo)
            Jeu.objets_dispo.remove(nouvel_objet)
            joueur.ajouter_objet(nouvel_objet)
            log_details.append(f"{joueur.nom} utilise {self.nom} pour piocher un nouvel objet: {nouvel_objet.nom}. Total {len(joueur.objets)} ")
            
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
        super().__init__("Princesse", 1)

    def debut_tour(self, joueur, Jeu, log_details):
        # Se déclenche seulement au tour 1 du joueur
        if not self.capacite_utilisee :
            log_details.append(f"{joueur.nom} ({self.nom}) utilise sa capacité pour piocher un objet")
            self.piocheItem(joueur, Jeu, log_details)
            self.capacite_utilisee = True


class MercenaireOrc(Perso):
    def __init__(self):
        # Le PV de base (5) est géré par la classe Joueur
        super().__init__("Mercenaire Orc", 5)
        
        
class ChevalierDragon(Perso):
    def __init__(self):
        super().__init__(nom="Chevalier Dragon", pv_bonus=3)

    def combat_effet(self, joueur, carte, Jeu, log_details):
        if "Dragon" in getattr(carte, 'types', []) and not Jeu.traquenard_actif and not carte.executed:
            self.executeEtDefausse(joueur, carte, Jeu, log_details)

class PersoUseless2PV(Perso):
    def __init__(self):
        # Le PV de base (5) est géré par la classe Joueur
        super().__init__("Perso Useless 2PV", 2)

class PersoUseless3PV(Perso):
    def __init__(self):
        # Le PV de base (5) est géré par la classe Joueur
        super().__init__("Perso Useless 3PV", 3)

class Tricheur(Perso):
    def __init__(self):
        super().__init__("Tricheur", 3)
    def score_effet(self, joueur, log_details):
        self.scoreChange(1,joueur,log_details)
        
class DocteurDePeste(Perso):
    def __init__(self):
        super().__init__(nom="DocteurDePeste", pv_bonus=2)

    def combat_effet(self, joueur, carte, Jeu, log_details):
        if "Rat" in getattr(carte, 'types', []) and not Jeu.traquenard_actif and not carte.executed:
            # Utilise la méthode executeEtDefausse héritée de Perso
            # self.executeEtDefausse(joueur, carte, Jeu, log_details)
            self.execute(joueur, carte, log_details)
            
class RoiSorcier(Perso):
    def __init__(self):
        super().__init__("Roi Sorcier", 2)
        
    def subit_dommages_effet(self,joueur_proprietaire, joueur, carte, Jeu, log_details):
        if carte.dommages >= 4 and joueur.nom != joueur_proprietaire.nom:
            self.gagnePV(1, joueur_proprietaire, log_details)
            
class InventeurGenial(Perso):
    def __init__(self):
        # pv_bonus=3 pour les PV de base
        super().__init__(nom="Inventeur génial", pv_bonus=3, modificateur_de=0)
        self.capacite_utilisee = False # Pour s'assurer que c'est une fois par partie

    def combat_effet(self, joueur, carte, Jeu, log_details):
        # Vérifier si capacité dispo et conditions remplies
        if not self.capacite_utilisee:
            # Trouver les objets brisés (non intacts)
            objets_brises = [o for o in joueur.objets if not getattr(o, 'intact', True)]

            # Condition: au moins 2 objets brisés
            if len(objets_brises) >= 2:
                # Décision IA : on utilise dès que possible
                log_details.append(f"{joueur.nom} ({self.nom}) utilise sa capacité (une fois par partie).")

                # Choisir 2 objets brisés au hasard à défausser
                objets_a_defausser = random.sample(objets_brises, 2)
                noms_defausse = [o.nom for o in objets_a_defausser]
                log_details.append(f"--> Défausse {noms_defausse}.")

                # Les retirer de l'inventaire du joueur et ajuster PV total si besoin
                for obj in objets_a_defausser:
                    joueur.objets.remove(obj)
                    joueur.pv_total -= getattr(obj, 'pv_bonus', 0)

                self.piocheItem(joueur, Jeu, log_details)
                self.capacite_utilisee = True



class Flutiste(Perso):
    def __init__(self):
        # pv_bonus=3 for base HP
        super().__init__(nom="Flutiste", pv_bonus=2, modificateur_de=0)

    def rencontre_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if "Gobelin" in carte.types and joueur_proprietaire.dans_le_dj:
            dommages_suppl = 1
            carte.dommages+=dommages_suppl
            log_details.append(f"{carte.titre} est booste de {dommages_suppl} dommages par {joueur_proprietaire.nom} ({self.nom})")
            
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Gobelin" in carte.types) and not Jeu.traquenard_actif
        
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details) 
        self.gagnePV(1, joueur, log_details)
    
class SavantFou(Perso):
    def __init__(self):
        super().__init__("Savant Fou", 2)
        
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        log_details.append(f"{joueur.nom} tente le pouvoir du Savant Fou {joueur_proprietaire.nom}")
    
        if joueur.nom == joueur_proprietaire.nom:
            jet_savant = joueur.rollDice(Jeu, log_details, 5)
            if jet_savant >= 5:
                self.gagnePV(1, joueur_proprietaire, log_details)

class Avatar(Perso):
    def __init__(self):
        super().__init__(nom="Avatar", pv_bonus=2)
        self.capacite_utilisee = False # Pour s'assurer que c'est une fois par partie

    def combat_effet_late(self, joueur, carte, Jeu, log_details):
        # Vérifier si capacité dispo et conditions remplies
        if not self.capacite_utilisee and not Jeu.traquenard_actif and not carte.executed and carte.dommages > (joueur.pv_total / 2) :
            self.executeEtDefausse(joueur, carte, Jeu, log_details)
            self.capacite_utilisee = True

persos_disponibles=[
    Ninja(),
    Princesse(),
    MercenaireOrc(),
    ChevalierDragon(),
    Tricheur(),
    DocteurDePeste(),
    RoiSorcier(),
    InventeurGenial(),
    Flutiste(),
    SavantFou(),
    Avatar(),
    # PersoUseless2PV(),
    # PersoUseless3PV(),
]

__all__=[
    "Ninja",
    "Princesse",
    "MercenaireOrc",
    "ChevalierDragon",
    "Tricheur",
    "DocteurDePeste",
    "RoiSorcier",
    "InventeurGenial",
    "Flutiste",
    # "PersoUseless2PV",
    # "PersoUseless3PV",
]