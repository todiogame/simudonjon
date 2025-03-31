import random
import json
# Lire le fichier JSON une fois au début
with open('priorites_objets.json', 'r') as json_file:
    priorites_objets = json.load(json_file)

class Objet:
    def __init__(self, nom, actif=False, pv_bonus=0, modificateur_de=0, effet=None, intact=True):
        self.nom = nom
        self.pv_bonus = pv_bonus
        self.modificateur_de = modificateur_de
        self.effet = effet
        self.intact = intact
        self.actif = actif
        self.priorite = priorites_objets.get(nom, 49.5)  # Utilise la priorité du JSON ou 0 par défaut
        self.compteur = 0

    def rules(self, joueur, carte, Jeu, log_details):
        # rule condition to use the item
        return True
    def worthit(self, joueur, carte, Jeu, log_details):
        # worth it to use the item?
        return True
    def condition(self, joueur, carte, Jeu, log_details): # check if we use the item or not
        return (self.intact 
            and self.rules(joueur, carte, Jeu, log_details)
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
        # attention, check si les items sont intacts
        if(joueur_proprietaire.dans_le_dj):
            self.subit_dommages_effet(joueur_proprietaire, joueur, carte, Jeu, log_details)
        
    def en_activated(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        # attention, check si les items sont intacts
        if joueur_proprietaire.dans_le_dj:
            self.activated_effet(joueur_proprietaire, joueur, objet, Jeu, log_details)
        
    def en_mort(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        # attention, check si les items sont intacts
        self.mort_effet(joueur_proprietaire, joueur, objet, Jeu, log_details)
        
    def en_fuite_definitive(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        # attention, check si les items sont intacts
        self.fuite_definitive_effet(joueur_proprietaire, joueur, objet, Jeu, log_details)

    def en_rencontre(self, joueur, carte, Jeu, log_details):
        # attention, check si les items sont intacts
        self.rencontre_effet(joueur, carte, Jeu, log_details)

    def en_fuite(self, joueur, Jeu, log_details):
        # attention, check si les items sont intacts
        pass

    def en_rencontre_event(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        # attention, check si les items sont intacts
        self.rencontre_event_effet(joueur_proprietaire, joueur, carte, Jeu, log_details)    

    

    def en_combat(self, joueur, carte, Jeu, log_details):
        if self.condition(joueur, carte, Jeu, log_details):
            self.combat_effet(joueur, carte, Jeu, log_details)

    
    def en_vaincu(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        # attention, check si les items sont intacts
        if(joueur_proprietaire.dans_le_dj):
            self.vaincu_effet(joueur_proprietaire, joueur, carte, Jeu, log_details) 
    
    def en_survie(self, joueur, carte, Jeu, log_details):
        if self.intact:
            self.survie_effet(joueur, carte, Jeu, log_details)

    def en_score(self, joueur, log_details):
        if self.intact:
            self.score_effet(joueur, log_details)

    def en_decompte(self, joueur, joueurs_final, log_details):
        if self.intact:
            self.decompte_effet(joueur, joueurs_final, log_details)
            
    def en_roll(self, joueur,jet, jet_voulu, reversed, rerolled, Jeu, log_details):
        # attention, check si les items sont intacts
        pass
            
    def repare(self):
        self.intact = True
        self.compteur = 0
    def destroy(self, joueur, Jeu, log_details):
        if self.intact:
            self.intact = False
            for joueur_proprietaire in Jeu.joueurs:
                for objet in joueur_proprietaire.objets:
                    objet.en_activated(joueur_proprietaire, joueur, self, Jeu, log_details)
    
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
            log_details.append(f"{joueur.nom} utilise {self.nom} pour piocher un nouvel objet: {nouvel_objet.nom}, PV bonus: {nouvel_objet.pv_bonus}, Jet de fuite: {nouvel_objet.modificateur_de}. Nouveau PV {joueur.nom}: {joueur.pv_total} PV.")
            
    def scoreChange(self, value, joueur, log_details):
        if value > 0:
            log_details.append(f"{self.nom} intact, gain de {value} points de victoire qui s'ajoutent aux {joueur.score_final} points, total {joueur.score_final + value}.")
        else:
            log_details.append(f"{self.nom} intact, perte de {value} points de victoire qui se soustraient aux {joueur.score_final} points, total {joueur.score_final + value}.")
        joueur.score_final += value

# Définir les objets spécifiques
class FleauDesLiches(Objet):
    def __init__(self):
        super().__init__("Fleau des liches")
    def rules(self, joueur, carte, Jeu, log_details):
        return "Liche" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.absorbe(joueur, carte, log_details)

class Katana(Objet):
    def __init__(self):
        super().__init__("Katana")
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance >= 7 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)

class HacheExecution(Objet):
    def __init__(self):
        super().__init__("Hache de Glace", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
        for obj in joueur.objets:
            if obj.nom == self.nom:
                joueur.objets.remove(obj)
                break
class MarteauDeGuerre(Objet):
    def __init__(self):
        super().__init__("Marteau de Guerre",False, 0, -1)
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Golem" in carte.types or "Squelette" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        
class EpauletteDuBourrin(Objet):
    def __init__(self):
        super().__init__("Epaulette du Bourrin", False, 4, -2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(1, joueur, carte, log_details)

class MainDeMidas(Objet):
    def __init__(self):
        super().__init__("Main de Midas", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance <= 5 and carte.puissance >= 4 and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.puissance == 5 or carte.puissance ==4 or carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.absorbe(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
class MainDeMidasB(Objet):
    def __init__(self):
        super().__init__("Main de Midas B", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance <= 4 and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.puissance ==4 or carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.absorbe(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
class Item6PV(Objet):
    def __init__(self):
        super().__init__("Item 6PV", False, 6)
class ArmureEnCuir(Objet):
    def __init__(self):
        super().__init__("Item 5PV", False, 5)
class CotteDeMailles(Objet):
    def __init__(self):
        super().__init__("Item 4PV", False, 4)
class Item2PV(Objet):
    def __init__(self):
        super().__init__("Item 2PV", False, 4)
class ParcheminDeBahn(Objet):
    def __init__(self):
        super().__init__("Parchemin de Bahn", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        self.gagnePV(1, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

class SingeDore(Objet):
    def __init__(self):
        super().__init__("Singe doré", False, 0, -2)
    def score_effet(self, joueur, log_details):
        jet = random.randint(1, 6)
        self.scoreChange(jet, joueur, log_details)
class GateauSpatial(Objet):
    def __init__(self):
        super().__init__("Gâteau spatial", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet_gateau = joueur.rollDice(Jeu, log_details)
        if jet_gateau == 1:
            joueur.fuite()
            log_details.append(f"{joueur.nom} utilise Gâteau spatial, jet de {jet_gateau}, fuite immédiate du Donjon.\n")
        else:
            self.gagnePV(jet_gateau, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

class CouteauSuisse(Objet):
    def __init__(self):
        super().__init__("Couteau Suisse", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return len([obj for obj in joueur.objets if not obj.intact])
    def combat_effet(self, joueur, carte, Jeu, log_details):
        objets_brisés = [obj for obj in joueur.objets if (not obj.intact and not obj.nom == "Couteau Suisse")]
        if objets_brisés:
            objet_repare = random.choice(objets_brisés)
            objet_repare.repare()
            log_details.append(f"{joueur.nom} utilise Couteau Suisse pour réparer {objet_repare.nom}.")
            if objet_repare.pv_bonus: self.gagnePV(objet_repare.pv_bonus, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

class CaisseEnchantee(Objet):
    def __init__(self):
        super().__init__("Caisse enchantée", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance < 6 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet_caisse = joueur.rollDice(Jeu, log_details, carte.puissance+1)
        log_details.append(f"{joueur.nom} utilise Caisse enchantée sur {carte.titre}, jet de {jet_caisse}")
        if jet_caisse > carte.puissance:
            self.execute(joueur, carte, log_details)
        else:
            log_details.append(f"Pas assez !")
        if jet_caisse == 1:
            log_details.append(f"Caisse enchantée brisée.")
            self.destroy(joueur, Jeu, log_details)

class BouclierGolemique(Objet):
    def __init__(self):
        super().__init__("Bouclier Golemique", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Golem" in carte.types) and not Jeu.traquenard_actif and not any("Golem" in monstre.types for monstre in joueur.pile_monstres_vaincus)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class Barde(Objet):
    def __init__(self):
        super().__init__("Barde", True, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and joueur.pv_total > 3
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 3 and carte.dommages >= (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.perdPV(self.pv_bonus, joueur, log_details)
        self.execute(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class BouclierDragon(Objet):
    def __init__(self):
        super().__init__("Bouclier Dragon", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet1 = joueur.rollDice(Jeu, log_details)
        jet2 = joueur.rollDice(Jeu, log_details)
        self.reduc_damage(jet1+jet2, joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
    def rencontre_effet(self, joueur, carte, Jeu, log_details):
        if ("Dragon" in carte.types):
            self.repare()

class PotionDeMana(Objet):
    def __init__(self):
        super().__init__("Potion de Mana", True)
    def survie_effet(self, joueur, carte, Jeu, log_details):
        if len(joueur.pile_monstres_vaincus):
            self.survit(1, joueur, carte, log_details)
            self.destroy(joueur, Jeu, log_details)

class KebabRevigorant(Objet):
    def __init__(self):
        super().__init__("Kebab revigorant", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return joueur.tour >= 3
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(7, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

class ArcEnflamme(Objet):
    def __init__(self):
        super().__init__("Arc enflammé", False, 7)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if self.intact and (carte.puissance %2 ==1):
            self.add_damage(1, joueur, carte, log_details)

class ParcheminDeTeleportation(Objet):
    def __init__(self):
        super().__init__("Parchemin de Téléportation", False, 2 , -100)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur and (joueur_proprietaire.pv_total <= 4 and sum(objet.actif and objet.intact for objet in joueur.objets) <= 1):
            log_details.append(f"{joueur.nom} utilise {self.nom} pour fuir le donjon !\n")
            joueur.fuite()
            # self.destroy(joueur, Jeu, log_details)

class GrosBoulet(Objet):
    def __init__(self):
        super().__init__("Gros boulet", False, 7, -1)

class PotionFeerique(Objet):
    def __init__(self):
        super().__init__("Potion féérique", True)
    def rencontre_effet(self, joueur, carte, Jeu, log_details):
        if not self.intact and ("Fée" == carte.titre):
            self.repare()
    def survie_effet(self, joueur, carte, Jeu, log_details):
        self.survit(1, joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class PotionDeGlace(Objet):
    def __init__(self):
        super().__init__("Potion de Glace", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        log_details.append(f"{joueur.nom} utilise {self.nom} pour réduire à 0 {carte.titre} !")
        carte.puissance = 0
        carte.dommages = 0
        self.destroy(joueur, Jeu, log_details)

class PotionDraconique(Objet):
    def __init__(self):
        super().__init__("Potion draconique", True)
    def survie_effet(self, joueur, carte, Jeu, log_details):
        if ("Dragon" in carte.types):
            self.survit(9, joueur, carte, log_details)
        else:
            self.survit(1, joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
        
class PiocheDeDiamant(Objet):
    def __init__(self):
        super().__init__("Pioche de diamant", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and carte.puissance <= 5
    def worthit(self, joueur, carte, Jeu, log_details):
        return "Golem" in carte.types or carte.dommages >= (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if not ("Golem" in carte.types):
            self.destroy(joueur, Jeu, log_details)
        self.execute(joueur, carte, log_details)

class ChapeauDuNovice(Objet):
    def __init__(self):
        super().__init__("Chapeau du novice", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Orc" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        if joueur.medailles == 0:
            Jeu.execute_next_monster = True
            log_details.append(f"Pas de médaille, la prochaine carte monstre peut être exécutée.")

class MasqueDeLaPeste(Objet):
    def __init__(self):
        super().__init__("Masque de la Peste", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return "Rat" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class TorcheRouge(Objet):
    def __init__(self):
        super().__init__("Torche Rouge", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Gobelin" in carte.types or "Squelette" in carte.types or "Orc" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class RobeDeMage(Objet):
    def __init__(self):
        super().__init__("Robe de mage", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and "Démon" in carte.types
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.gagnePV(5, joueur, log_details)

class ValisesDeCash(Objet):
    def __init__(self):
        super().__init__("Valises de Cash", False)
    def score_effet(self, joueur, log_details):
        self.scoreChange(3,joueur,log_details)

class TronconneuseEnflammee(Objet):
    def __init__(self):
        super().__init__("Tronçonneuse enflammée", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= 3 and joueur.pv_total > 3
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.perdPV(3, joueur, log_details)
    
class TuniqueClasse(Objet):
    def __init__(self):
        super().__init__("Tunique classe", False, 4, -1)
    def score_effet(self, joueur, log_details):
        self.scoreChange(1,joueur,log_details)

class AnneauDuFeu(Objet):
    def __init__(self):
        super().__init__("Anneau du Feu", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and "Vampire" in carte.types
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.gagnePV(2, joueur, log_details)

class AnneauMagique(Objet):
    def __init__(self):
        super().__init__("Anneau Magique", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and (carte.puissance == 1 or carte.puissance == 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.absorbe(joueur, carte, log_details)

class TroisPV(Objet):
    def __init__(self):
        super().__init__("Item 3PV", False, 3)
class TroisPV_(Objet):
    def __init__(self):
        super().__init__("Item 3PV 2", False, 3)
class ArmureDHonneur(Objet):
    def __init__(self):
        super().__init__("Armure d'honneur", False, 3)
    def decompte_effet(self, joueur, joueurs_final, log_details):
        if not joueur.vivant and joueur not in joueurs_final:
            log_details.append(f"L'armure d'honneur de {joueur.nom} pose 4")
            joueur.score_final = 4
            joueurs_final.append(joueur)

class PierreDAme(Objet):
    def __init__(self):
        super().__init__("Pierre d'âme", False, 3)
    def score_effet(self, joueur, log_details):
        if any("Dragon" in monstre.types for monstre in joueur.pile_monstres_vaincus):    
            self.scoreChange(3,joueur,log_details)

class CoeurDeGolem(Objet):
    def __init__(self):
        super().__init__("Cœur de Golem", False, 3)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if any("Golem" in monstre.types for monstre in joueur.pile_monstres_vaincus):    
            nb_golems = sum("Golem" in monstre.types for monstre in joueur.pile_monstres_vaincus)
            self.reduc_damage(nb_golems, joueur, carte, log_details)

class CouronneDEpines(Objet):
    def __init__(self):
        super().__init__("Couronne d'épines", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.dommages >1
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(2, joueur, carte, log_details)
        if carte.dommages <= 0:
            self.add_damage(1, joueur, carte, log_details)
#note la courronne peut etre reduite encore par un item reduc dommage utilise en suivant

class MasqueAGaz(Objet):
    def __init__(self):
        super().__init__("Masque à gaz", True, 4)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and joueur.pv_total > 4 
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 4 and carte.dommages >= (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.perdPV(self.pv_bonus, joueur, log_details)
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)

class BouclierCameleon(Objet):
    def __init__(self):
        super().__init__("Bouclier caméléon", False, 0, -1)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and carte.puissance >= 6 
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= 2 and joueur.pv_total > 2 
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.perdPV(2, joueur, log_details)

class YoYoProtecteur(Objet):
    def __init__(self):
        super().__init__("Yo-yo protecteur", True)
    
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance % 2 == 0 and not Jeu.traquenard_actif
    
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.puissance > 2 or carte.dommages >= joueur.pv_total / 2
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
        jet_yoyo = joueur.rollDice(Jeu, log_details)
        if jet_yoyo >= 4 and self in joueur.objets:
            self.repare()
        else:
            log_details.append(f"{joueur.nom} essaie de reparer {self.nom}... raté ({jet_yoyo})!")

class BouclierCasse(Objet):
    def __init__(self):
        super().__init__("Bouclier cassé", False)
    
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance >= 6
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet_bouclier = joueur.rollDice(Jeu, log_details)
        self.reduc_damage(jet_bouclier, joueur, carte, log_details)

class GlaiveDArgent(Objet):
    def __init__(self):
        super().__init__("Glaive d'argent", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return "Vampire" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if any("Vampire" in monstre.types for monstre in joueur.pile_monstres_vaincus):
            self.gagnePV(4, joueur, log_details)
        self.execute(joueur, carte, log_details)

class ChapeletDeVitalite(Objet):
    def __init__(self):
        super().__init__("Chapelet de Vitalité", False, 3)
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact:
            jet_chapelet = joueur.rollDice(Jeu, log_details, 6)
            if jet_chapelet == 6:
                self.gagnePV(1, joueur, log_details)

class TalismanIncertain(Objet):
    def __init__(self):
        super().__init__("Talisman Incertain", False, 2)
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet_talisman = joueur.rollDice(Jeu, log_details, 6)
        if jet_talisman == 6:
            self.execute(joueur, carte, log_details)
        else:
            log_details.append(f"{joueur.nom} utilise {self.nom}... raté !")
            
class PlanPresqueParfait(Objet):
    def __init__(self):
        super().__init__("Plan presque parfait", False, 3)
    
    def rencontre_event_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if joueur_proprietaire == joueur:
            Jeu.execute_next_monster = True
            log_details.append(f"Effet {self.nom} actif: la prochaine carte monstre peut être exécutée. Sauf si...")

class GraalEnMousse(Objet):
    def __init__(self):
        super().__init__("Graal en Mousse", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return ((carte.puissance == 0 or carte.puissance == 2 or carte.puissance == 4 or carte.puissance == 6 ) and not Jeu.traquenard_actif)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        if len(joueur.pile_monstres_vaincus) >= 5 and self.intact:
            self.destroy(joueur, Jeu, log_details)

class ItemUseless(Objet):
    def __init__(self):
        super().__init__("ItemUseless", False)

class ArmureDamnee(Objet):
    def __init__(self):
        super().__init__("Armure Damnée", False, 7)
    def score_effet(self, joueur, log_details):
        self.scoreChange(-1, joueur, log_details)

class AnneauDesSurmulots(Objet):
    def __init__(self):
        super().__init__("Anneau des surmulots", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return "Rat" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.gagnePV(3, joueur, log_details)
        
class PatinsAGlace(Objet):
    def __init__(self):
        super().__init__("Patins à Glace", False, 3, 3)
    def en_fuite(self, joueur, Jeu, log_details):
        if joueur.jet_fuite >= 7:
            self.perdPV(1, joueur, log_details)


class CoquillageMagique(Objet):
    def __init__(self):
        super().__init__("Coquillage Magique", True)
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact:
           self.piocheItem(joueur,Jeu,log_details)
           self.destroy(joueur, Jeu, log_details)

class MasqueDragon(Objet):
    def __init__(self):
        super().__init__("Masque Dragon", False)
    
    def rules(self, joueur, carte, Jeu, log_details):
        return "Dragon" in carte.types and not Jeu.traquenard_actif
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.piocheItem(joueur,Jeu,log_details)
        self.destroy(joueur, Jeu, log_details)

class PiedDeBiche(Objet):
    def __init__(self):
        super().__init__("Pied de Biche", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return "Mimique" in carte.titre and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.piocheItem(joueur,Jeu,log_details)
           
class MarmiteGelatineuse(Objet):
    def __init__(self):
        super().__init__("Marmite Gélatineuse", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.effet and "LIMON" in carte.effet and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.piocheItem(joueur,Jeu,log_details)

class GrimoireInconnu(Objet):
    def __init__(self):
        super().__init__("Grimoire Inconnu", True)
    
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact:
            jet_grimoire = joueur.rollDice(Jeu, log_details, 6)
            if jet_grimoire == 6:
                self.piocheItem(joueur,Jeu,log_details)

class GantsDeCombat(Objet):
    def __init__(self):
        super().__init__("Gants de combat", True)
    
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance <= 2 and not Jeu.traquenard_actif
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.piocheItem(joueur,Jeu,log_details)
        self.destroy(joueur, Jeu, log_details)

class GantsDeGaia(Objet):
    def __init__(self):
        super().__init__("Gants de Gaïa", True)
    
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact:
            objets_brisés = [obj for obj in joueur.objets if not obj.intact]
            objets_actifs_intacts = [obj for obj in joueur.objets if obj.actif and obj.intact]
            # on s'assure qu'on a deja joue tous nos actifs avant de piocher la suite
            if (len(objets_brisés) >= 2) or (len(objets_brisés) == 1 and len(objets_actifs_intacts) == 1 and objets_actifs_intacts[0] == self):
                nombre_a_defausser = min(2, len(objets_brisés))
                for _ in range(nombre_a_defausser):
                    objet_brisé = objets_brisés.pop()
                    joueur.objets.remove(objet_brisé)
                    log_details.append(f"{joueur.nom} utilise {self.nom} pour défausser objet brisé: {objet_brisé.nom}")
                for _ in range(nombre_a_defausser):
                    self.piocheItem(joueur, Jeu, log_details)
                self.destroy(joueur, Jeu, log_details)

class ChampDeForceEnMousse(Objet):
    def __init__(self):
        super().__init__("Champ de force en mousse", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet_cf = joueur.rollDice(Jeu, log_details, 5)
        if jet_cf >= 5:
            self.execute(joueur, carte, log_details)
        else:
            log_details.append(f"{joueur.nom} utilise {self.nom}... raté !")
        if len(joueur.pile_monstres_vaincus) >= 5 and self.intact:
            self.destroy(joueur, Jeu, log_details)

class BoiteDePandore(Objet):
    def __init__(self):
        super().__init__("Boîte de Pandore", True)
    
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact:
            self.gagnePV(3, joueur, log_details)
            for j in Jeu.joueurs:
                self.piocheItem(j, Jeu, log_details)
            self.destroy(joueur, Jeu, log_details)

class TorcheBleue(Objet):
    def __init__(self):
        super().__init__("Torche Bleue", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance <= 2 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class TorcheEnMousse(Objet):
    def __init__(self):
        super().__init__("Torche En Mousse", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance <= 3 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        if len(joueur.pile_monstres_vaincus) >= 5 and self.intact:
            self.destroy(joueur, Jeu, log_details)
            
class AnneauPlussain(Objet):
    def __init__(self):
        super().__init__("Anneau Plussain", False, 1, 1)
    def score_effet(self, joueur, log_details):
        self.scoreChange(1,joueur,log_details)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance == 1 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        
class GetasDuNovice(Objet):
    def __init__(self):
        super().__init__("Getas du novice", False, 2, 2)
    def en_fuite(self, joueur, Jeu, log_details):
        # 1 reroll
        if (not joueur.medailles and joueur.jet_fuite < 4) and self.intact:
            log_details.append(f"Utilise {self.nom}, pour reroll: {joueur.jet_fuite} (avec modif {joueur.calculer_modificateurs()}) ")
            joueur.jet_fuite = joueur.rollDice(Jeu, log_details) + joueur.calculer_modificateurs()
    
class MarteauDEternite(Objet):
    def __init__(self):
        super().__init__("Marteau d'Eternité", False, 0, -100) #-100 fuite car inutile de fuir avec cet objet
    def score_effet(self, joueur, log_details):
        self.scoreChange(-1,joueur,log_details)
    def decompte_effet(self, joueur, joueurs_final, log_details):
        if not joueur.vivant and joueur not in joueurs_final and self.intact:
            log_details.append(f"Le {self.nom} de {joueur.nom} le fait compter parmi les gagnants")
            joueurs_final.append(joueur)

class CaliceDuRoiSorcier(Objet):
    def __init__(self):
        super().__init__("Calice du Roi Sorcier", False)
        
    def subit_dommages_effet(self,joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.intact and carte.dommages >= 3 and joueur.nom != joueur_proprietaire.nom:
            self.gagnePV(1, joueur_proprietaire, log_details)
                
class PerceuseABreche(Objet):
    def __init__(self):
        super().__init__("Perceuse a Breche", False)
        
    def subit_dommages_effet(self,joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.intact and "Golem" in carte.types and joueur.nom != joueur_proprietaire.nom:
            self.gagnePV(carte.dommages, joueur_proprietaire, log_details)
            
class BourseGarnie(Objet):
    def __init__(self):
        super().__init__("Bourse Garnie", False, 3)
    def score_effet(self, joueur, log_details):
        self.scoreChange(1,joueur,log_details)
                
class EnclumeInstable(Objet):
    def __init__(self):
        super().__init__("Enclume instable", True)
    
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact:
            objets_brisés_autres_joueurs = [obj for j in Jeu.joueurs if j != joueur for obj in j.objets if not obj.intact]
            if objets_brisés_autres_joueurs:
                objet_vole = random.choice(objets_brisés_autres_joueurs)
                objet_vole.repare()
                ancien_proprietaire = next(j for j in Jeu.joueurs if objet_vole in j.objets)
                ancien_proprietaire.objets.remove(objet_vole)
                joueur.ajouter_objet(objet_vole)
                log_details.append(f"{joueur.nom} utilise {self.nom} pour voler et réparer {objet_vole.nom} de {ancien_proprietaire.nom}")
                self.destroy(joueur, Jeu, log_details)

class CoffreAnime(Objet):
    def __init__(self):
        super().__init__("Coffre animé", False)

    def activated_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if self.intact:
            if objet in joueur.objets and not objet.intact:
                jet_de = joueur_proprietaire.rollDice(Jeu, log_details, 6)
                if jet_de == 6:
                    if joueur_proprietaire.nom != joueur.nom:
                        joueur.objets.remove(objet)
                        objet.repare()
                        joueur_proprietaire.ajouter_objet(objet)
                        log_details.append(f"{joueur_proprietaire.nom} utilise {self.nom} pour voler et réparer {objet.nom} de {joueur.nom}")
                    else:
                        objet.repare()
                        log_details.append(f"{joueur_proprietaire.nom} utilise {self.nom} pour réparer son {objet.nom}")
            else:log_details.append(f" {joueur_proprietaire.nom} utilise {self.nom} pour essayer de voler et réparer {objet.nom} de {joueur.nom} MAIS cela ECHOUE!")
                            
class AnneauDeVie(Objet):
    def __init__(self):
        super().__init__("Anneau de Vie", False)
    def fin_tour(self, joueur, Jeu, log_details):
        if(joueur.pv_total >= 6) and self.intact:
            self.gagnePV(1,joueur,log_details)
                

class BottesDeVitesse(Objet):
    def __init__(self):
        super().__init__("Bottes de Vitesse", False, 2, 7)
#todo vous rentrez en premier


class Randotion(Objet):
    def __init__(self):
        super().__init__("Randotion", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(joueur.rollDice(Jeu, log_details), joueur, log_details)
        self.gagnePV(joueur.rollDice(Jeu, log_details), joueur, log_details)
        self.perdPV(joueur.rollDice(Jeu, log_details, 3,True), joueur, log_details)
        self.destroy(joueur, Jeu, log_details)
        
class LameDeLHarmonie(Objet):
    def __init__(self):
        super().__init__("Lame de l'Harmonie", False)
    def rules(self, joueur, carte, Jeu, log_details):
        count_same_type = sum(1 for monstre in joueur.pile_monstres_vaincus if any(type_ in monstre.types for type_ in carte.types))
        return not Jeu.traquenard_actif and count_same_type == 1
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class ChampignonVeneneux(Objet):
    def __init__(self):
        super().__init__("Champignon Vénéneux", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total > 1 and carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.perdPV(1, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

class BouletDeCanon(Objet):
    def __init__(self):
        super().__init__("Boulet de Canon", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and carte.puissance >= 6
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class PotionOuPoison(Objet):
    def __init__(self):
        super().__init__("PotionOuPoison", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(6, joueur, log_details)
        jet_de_de = joueur.rollDice(Jeu, log_details, 2)
        if jet_de_de == 1:
            self.perdPV(7, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

class CoquilleSalvatrice(Objet):
    def __init__(self):
        super().__init__("Coquille Salvatrice", True)
    def survie_effet(self, joueur, carte, Jeu, log_details):
        self.survit(3, joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class FeuilleEternelle(Objet):
    def __init__(self):
        super().__init__("Feuille Eternelle", False, 0, 0)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and ( "Démon" in carte.types or  "Dragon" in carte.types)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= 1 and joueur.pv_total > 1 
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.perdPV(1, joueur, log_details)

class PatteDuRatLiche(Objet):
    def __init__(self):
        super().__init__("Patte du RatLiche", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Rat" in carte.types or "Liche" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class LameDraconique(Objet):
    def __init__(self):
        super().__init__("Lame Draconique", False)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if "Dragon" in carte.types and not Jeu.traquenard_actif:
            self.execute(joueur, carte, log_details)
        else:
            nb_dragons = sum("Dragon" in monstre.types for monstre in joueur.pile_monstres_vaincus)
            self.reduc_damage(nb_dragons, joueur, carte, log_details)

class FouetDuFourbe(Objet):
    def __init__(self):
        super().__init__("Fouet du fourbe", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        type_monstre = carte.types
        for autre_joueur in Jeu.joueurs:
            if autre_joueur != joueur:
                for monstre in autre_joueur.pile_monstres_vaincus:
                    if any(t in type_monstre for t in monstre.types):
                        autre_joueur.pile_monstres_vaincus.remove(monstre)
                        Jeu.defausse.append(monstre)
                        log_details.append(f"{autre_joueur.nom} défausse {monstre.titre} à cause du {self.nom} de {joueur.nom}")
                        break
        self.destroy(joueur, Jeu, log_details)

class CraneDuRoiLiche(Objet):
    def __init__(self):
        super().__init__("Crâne du Roi Liche", False)

    def rules(self, joueur, carte, Jeu, log_details):
        return "Liche" in carte.types and not Jeu.traquenard_actif

    def combat_effet(self, joueur, carte, Jeu, log_details):
        if "Liche" in carte.types:
            self.execute(joueur, carte, log_details)

    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if "Liche" in carte.types and carte.titre != "Changeforme" and self.intact:
            if joueur_proprietaire != joueur:
                if carte in joueur.pile_monstres_vaincus:
                    joueur.pile_monstres_vaincus.remove(carte)
                    joueur_proprietaire.ajouter_monstre_vaincu(carte)
                    log_details.append(f"{joueur_proprietaire.nom} récupère {carte.titre} de {joueur.nom} grâce à {self.nom}")
                elif carte in Jeu.defausse:
                    Jeu.defausse.remove(carte)
                    joueur_proprietaire.ajouter_monstre_vaincu(carte)
                    log_details.append(f"{joueur_proprietaire.nom} récupère {carte.titre} de la defausse grâce à {self.nom}")
                else:
                    log_details.append(f"{joueur_proprietaire.nom} essaie de récupèrer {carte.titre} mais la carte a disparu !!")
    
class LivreSacre(Objet):
    def __init__(self):
        super().__init__("Livre Sacré", False, 2)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and "Squelette" in carte.types
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        
class PendentifDuNovice(Objet):
    def __init__(self):
        super().__init__("Pendentif du Novice", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and "Gobelin" in carte.types and not joueur.medailles
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.gagnePV(1, joueur, log_details)
      
class PistoletPirate(Objet):
    def __init__(self):
        super().__init__("Pistolet Pirate", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return (carte.puissance == 2 or carte.puissance == 3) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class ArmureArdente(Objet):
    def __init__(self):
        super().__init__("Armure Ardente", False, 4)
    def rules(self, joueur, carte, Jeu, log_details):
        return "Dragon" in carte.types
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(5, joueur, carte, log_details)

class SeringueDuDocteurFou(Objet):
    def __init__(self):
        super().__init__("Seringue du docteur fou", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(10, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)
    
    def rencontre_effet(self, joueur, carte, Jeu, log_details):
        if not self.intact:
            self.perdPV(1, joueur, log_details)
            
    def rencontre_event_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if not self.intact:
            self.perdPV(1, joueur, log_details)
            
class CorneDAbordage(Objet):
    def __init__(self):
        super().__init__("Corne d'abordage", True)

    def debut_tour(self, joueur, Jeu, log_details):
        autres_joueurs_dans_le_dj = [autre_joueur for autre_joueur in Jeu.joueurs if autre_joueur != joueur and autre_joueur.dans_le_dj]

        if self.intact and all(autre_joueur.pile_monstres_vaincus for autre_joueur in autres_joueurs_dans_le_dj) and joueur.pv_total>2:
            log_details.append(f"{joueur.nom} utilise {self.nom}")
            for autre_joueur in autres_joueurs_dans_le_dj:
                if autre_joueur.pile_monstres_vaincus:
                    monstre_volee = random.choice(autre_joueur.pile_monstres_vaincus)
                    autre_joueur.pile_monstres_vaincus.remove(monstre_volee)
                    joueur.ajouter_monstre_vaincu(monstre_volee)
                    log_details.append(f"{joueur.nom} utilise {self.nom} pour voler {monstre_volee.titre} de {autre_joueur.nom}")
            self.perdPV(2, joueur, log_details)
            self.destroy(joueur, Jeu, log_details)

class SceptreActif(Objet):
    def __init__(self):
        super().__init__("Sceptre actif", False, 2)

    def activated_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur:
            self.gagnePV(2, joueur, log_details)

class CapeVaudou(Objet):
    def __init__(self):
        super().__init__("Cape vaudou", True)

    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total or carte.puissance >= 1.5 * joueur.pv_total

    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        joueur.pv_total = carte.puissance
        log_details.append(f"{joueur.nom} utilise {self.nom} pour fixer ses PV à {carte.puissance} après avoir exécuté et défaussé {carte.titre}.")
        self.destroy(joueur, Jeu, log_details)

class FerACheval(Objet):
    def __init__(self):
        super().__init__("Fer a Cheval", False)
    def en_roll(self, joueur,jet, jet_voulu, reversed, rerolled, Jeu, log_details):
        # attention, check si les items sont intacts
        if self.intact and not rerolled and ((jet < jet_voulu and not reversed) or (reversed and jet > jet_voulu)):
                log_details.append(f"{joueur.nom} utilise {self.nom} pour reroll son dé de {jet}.")
                return joueur.rollDice(Jeu, log_details, jet_voulu, reversed, True)

class DeDuTricheur(Objet):
    def __init__(self):
        super().__init__("Dé du Tricheur", False, 3)
    def en_roll(self, joueur, jet, jet_voulu, reversed, rerolled, Jeu, log_details):
        # +1 à tous vos jets de dés, sauf si vous faites 5
        if self.intact and not reversed and jet < 5 and not jet_voulu == 6:
            log_details.append(f"{joueur.nom} utilise {self.nom} pour passer son dé de {jet} à {jet+1}.")
            return jet + 1

class EspritDuDonjon(Objet):
    def __init__(self):
        super().__init__("Esprit du Donjon", True)

    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact:
            autres_joueurs_dans_le_dj = [autre_joueur for autre_joueur in Jeu.joueurs if autre_joueur != joueur and autre_joueur.dans_le_dj]
            if all(autre_joueur.pile_monstres_vaincus for autre_joueur in autres_joueurs_dans_le_dj):
                log_details.append(f"{joueur.nom} utilise {self.nom}")
                for autre_joueur in autres_joueurs_dans_le_dj:
                    if autre_joueur.pile_monstres_vaincus:
                        monstre_remis = random.choice(autre_joueur.pile_monstres_vaincus)
                        autre_joueur.pile_monstres_vaincus.remove(monstre_remis)
                        Jeu.donjon.ajouter_monstre(monstre_remis)
                        log_details.append(f"{autre_joueur.nom} a remis {monstre_remis.titre} dans le Donjon.")
                for autre_joueur in autres_joueurs_dans_le_dj:
                    if autre_joueur.pile_monstres_vaincus:
                        monstre_remis = random.choice(autre_joueur.pile_monstres_vaincus)
                        autre_joueur.pile_monstres_vaincus.remove(monstre_remis)
                        Jeu.donjon.ajouter_monstre(monstre_remis)
                        log_details.append(f"{autre_joueur.nom} a remis {monstre_remis.titre} dans le Donjon.")
                    else:
                        log_details.append(f"{autre_joueur.nom} n'a rien a remettre dans le Donjon.")   
                Jeu.donjon.remelange()                 
                self.destroy(joueur, Jeu, log_details)

class SabreMecanique(Objet):
    def __init__(self):
        super().__init__("Sabre mécanique", False, 0, -1)
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Gobelin" in carte.types or "Golem" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class CouronneEnMousse(Objet):
    def __init__(self):
        super().__init__("Couronne en Mousse", False)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(2, joueur, carte, log_details)    
        if len(joueur.pile_monstres_vaincus) >= 5 and self.intact:
            self.destroy(joueur, Jeu, log_details)

class KatanaEnMousse(Objet):
    def __init__(self):
        super().__init__("Katana en Mousse", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance >= 7 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        if len(joueur.pile_monstres_vaincus) >= 5 and self.intact:
            self.destroy(joueur, Jeu, log_details)

class MarteauFlamboyant(Objet):
    def __init__(self):
        super().__init__("Marteau flamboyant", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return "Golem" in carte.types or "Dragon" in carte.types
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(4, joueur, carte, log_details)

class TreizeASeize(Objet):
    def __init__(self):
        super().__init__("Treize à Seize", False)
    def rules(self, joueur, carte, Jeu, log_details):
        if any("Dragon" in monstre.types for monstre in joueur.pile_monstres_vaincus):
            return (carte.puissance == 1 or carte.puissance == 6) and not Jeu.traquenard_actif
        return (carte.puissance == 1 or carte.puissance == 3) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class Scaphandre(Objet):
    def __init__(self):
        super().__init__("Scaphandre", False, 0, -3)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(2, joueur, carte, log_details)

class BouclierDeLInventeur(Objet):
    def __init__(self):
        super().__init__("Bouclier de l'inventeur", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total/2 -2
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        if joueur.rollDice(Jeu, log_details, 4) >= 4:
            self.piocheItem(joueur, Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)        

class EpeeMystique(Objet):
    def __init__(self):
        super().__init__("Epee mystique", False, 0, 4)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance == joueur.calculer_modificateurs() and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class DelicieusePizza(Objet):
    def __init__(self):
        super().__init__("Délicieuse pizza", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total 
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        joueur.pv_total = 6
        log_details.append(f"{joueur.nom} utilise {self.nom} et fixe ses PV à 6. Total {joueur.pv_total} PV.")
        self.destroy(joueur, Jeu, log_details)

class BoiteAButin(Objet):
    def __init__(self):
        super().__init__("Boîte à butin", False)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.intact and joueur_proprietaire.dans_le_dj and joueur_proprietaire == joueur:
            jet_boite = joueur.rollDice(Jeu, log_details, 6)
            if jet_boite == 6:
                self.piocheItem(joueur, Jeu, log_details)
                self.piocheItem(joueur, Jeu, log_details)
                self.destroy(joueur, Jeu, log_details)

class PlatreeDeBerniques(Objet):
    def __init__(self):
        super().__init__("Platree de Berniques", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total 
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        jet = joueur.rollDice(Jeu, log_details)
        joueur.pv_total = jet
        log_details.append(f"{joueur.nom} utilise {self.nom} et fixe ses PV à {jet}. Total {joueur.pv_total} PV.")
        self.destroy(joueur, Jeu, log_details)

class AnneauOceanique(Objet):
    def __init__(self):
        super().__init__("Anneau Oceanique")
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance >= 8 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class BoomerangMystique(Objet):
    def __init__(self):
        super().__init__("Boomerang Mystique", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        Jeu.execute_next_monster = True
        log_details.append(f"La prochaine carte monstre peut être exécutée.")
        self.destroy(joueur, Jeu, log_details)

class CoiffeDeSorcier(Objet):
    def __init__(self):
        super().__init__("Coiffe de sorcier")
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Gobelin" in carte.types or "Vampire" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class ArmureDuRoiLiche(Objet):
    def __init__(self):
        super().__init__("Armure du Roi Liche", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return "Liche" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class ElixirDeChance(Objet):
    def __init__(self):
        super().__init__("Elixir de chance", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(3, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)
    def en_roll(self, joueur, jet, jet_voulu, reversed, rerolled, Jeu, log_details):
        if self.intact and (jet < jet_voulu and not reversed) or (jet > jet_voulu and reversed):
            self.gagnePV(3, joueur, log_details)
            self.destroy(joueur, Jeu, log_details)
            return 1 if reversed else 6


class ChapeauStyle(Objet):
    def __init__(self):
        super().__init__("Chapeau stylé", False, 2)
    def decompte_effet(self, joueur, joueurs_final, log_details):
        joueur.tiebreaker = True
        
class Chameau(Objet):
    def __init__(self):
        super().__init__("Chameau", True)
    def chameau(self, joueur, Jeu, log_details):
        if self.intact and joueur.dans_le_dj:
            autres_joueurs_dans_le_dj = [j.pv_total for j in Jeu.joueurs if j.dans_le_dj and j != joueur]
            if autres_joueurs_dans_le_dj:
                min_pv_joueur = min(autres_joueurs_dans_le_dj)
                if joueur.pv_total < min_pv_joueur:
                    self.gagnePV(6, joueur, log_details)
                    self.destroy(joueur, Jeu, log_details)
    def debut_tour(self, joueur, Jeu, log_details):
        self.chameau(joueur, Jeu, log_details)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.chameau(joueur, Jeu, log_details)

class PotionDeFeuLiquide(Objet):
    def __init__(self):
        super().__init__("Potion de feu liquide", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)
    def rencontre_effet(self, joueur, carte, Jeu, log_details):
        if not self.intact and "Dragon" in carte.types:
            self.repare()
            
class CasquePlus(Objet):
    def __init__(self):
        super().__init__("Casque Plus", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and self.compteur <= 2
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.compteur += 1
        # self.execute(joueur, carte, log_details)
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        log_details.append(f"Le Casque Plus fait bing, utilisations: {self.compteur}")
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.compteur >= 2 and self.intact and joueur_proprietaire.dans_le_dj and joueur_proprietaire == joueur:
            log_details.append(f"Le Casque Plus est detruit.")
            self.destroy(joueur_proprietaire, Jeu, log_details)
            
class AnkhDeReincarnation(Objet):
    def __init__(self):
        super().__init__("Ankh de réincarnation", True)
    def survie_effet(self, joueur, carte, Jeu, log_details):
        if self.intact and joueur.pv_total <= 0:
            self.survit(1, joueur, carte, log_details)
            self.destroy(joueur, Jeu, log_details)
    def en_mort(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if not self.intact and not joueur.vivant and joueur_proprietaire.dans_le_dj:
            log_details.append(f"{self.nom} de {joueur_proprietaire.nom} se repare suite a la mort de {joueur.nom}.")
            self.repare()

class CoffreDuRoiSorcier(Objet):
    def __init__(self):
        super().__init__("Coffre du Roi Sorcier", False, 3)
    def en_mort(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if joueur_proprietaire.dans_le_dj and not joueur.vivant and self.intact:
            log_details.append(f"{joueur_proprietaire.nom} utilise {self.nom} pour tenter de récupérer des objets de {joueur.nom}.")
            for objet in joueur.objets:
                if objet.intact:
                    jet = joueur_proprietaire.rollDice(Jeu, log_details)
                    if jet == 6:
                        log_details.append(f"{joueur_proprietaire.nom} récupère {objet.nom} de {joueur.nom} grâce à {self.nom}.")
                        joueur.objets.remove(objet)
                        joueur_proprietaire.ajouter_objet(objet)

class CoeurDeDragon(Objet):
    def __init__(self):
        super().__init__("Cœur de Dragon", False)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if "Dragon" in carte.types and self.intact:
            self.gagnePV(4, joueur_proprietaire, log_details)

class PotionDAdrenaline(Objet):
    def __init__(self):
        super().__init__("Potion d'adrénaline", True)
    def potionDAdrenaline(self, joueur, Jeu, log_details):
        if self.intact:
            if joueur.pv_total == 1:
                self.gagnePV(10, joueur, log_details)
            else:
                self.gagnePV(2, joueur, log_details)
            self.destroy(joueur, Jeu, log_details)
    
    def debut_tour(self, joueur, Jeu, log_details):
        if joueur.pv_total == 1:
            self.potionDAdrenaline(joueur, Jeu, log_details)
        
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if (joueur.pv_total <= carte.dommages and joueur.pv_total+2 > carte.dommages)  or joueur.pv_total == 1:
            self.potionDAdrenaline(joueur, Jeu, log_details)

class PeigneEnOr(Objet):
    def __init__(self):
        super().__init__("Peigne en or", False, 3)
    def score_effet(self, joueur, log_details):
        gobelins = sum(1 for monstre in joueur.pile_monstres_vaincus if "Gobelin" in monstre.types)
        if gobelins > 0:
            self.scoreChange(gobelins, joueur, log_details)
            log_details.append(f"{joueur.nom} gagne {gobelins} points de victoire supplémentaires grâce à {self.nom} pour les Gobelins vaincus.")

class LampeMagique(Objet):
    def __init__(self):
        super().__init__("Lampe magique", False, 3)
    def score_effet(self, joueur, log_details):
        demons = sum(1 for monstre in joueur.pile_monstres_vaincus if "Démon" in monstre.types)
        if demons > 0:
            self.scoreChange(2 * demons, joueur, log_details)
            log_details.append(f"{joueur.nom} gagne {2 * demons} points de victoire supplémentaires grâce à {self.nom} pour les Démons vaincus.")

class CanneAChep(Objet):
    def __init__(self):
        super().__init__("Canne à Chep", True)
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact and joueur.dans_le_dj:
            joueurs_morts = [autre_joueur for autre_joueur in Jeu.joueurs if not autre_joueur.vivant]
            if ((all(not autre_joueur.dans_le_dj for autre_joueur in Jeu.joueurs if autre_joueur != joueur) or len(joueurs_morts) >= 2)):
                self.utiliser(joueur, Jeu, log_details)
                self.destroy(joueur, Jeu, log_details)
    def worthit(self, joueur, carte, Jeu, log_details):
        joueurs_morts = [autre_joueur for autre_joueur in Jeu.joueurs if not autre_joueur.vivant]
        return joueur.pv_total <= carte.dommages or (all(not autre_joueur.dans_le_dj for autre_joueur in Jeu.joueurs if autre_joueur != joueur) or len(joueurs_morts) >= 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.utiliser(joueur, Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)
    def utiliser(self, joueur, Jeu, log_details):
            self.gagnePV(4, joueur, log_details)
            for autre_joueur in Jeu.joueurs:
                if not autre_joueur.vivant:
                    objets_intacts = [objet for objet in autre_joueur.objets if objet.intact]
                    if objets_intacts:
                        objet_vole = random.choice(objets_intacts)
                        autre_joueur.objets.remove(objet_vole)
                        joueur.ajouter_objet(objet_vole)
                        log_details.append(f"{joueur.nom} utilise {self.nom} pour voler {objet_vole.nom} de {autre_joueur.nom}.")


class AnneauVolcanique(Objet):
    def __init__(self):
        super().__init__("Anneau volcanique", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return "Golem" in carte.types and any("Dragon" in monstre.types for monstre in joueur.pile_monstres_vaincus) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class Dragoune(Objet):
    def __init__(self):
        super().__init__("Dragoune", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return "Dragon" in carte.types and len(joueur.pile_monstres_vaincus) >= 5 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class KitVaudou(Objet):
    def __init__(self):
        super().__init__("Kit vaudou", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total < 7 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class MarteauDeCombat(Objet):
    def __init__(self):
        super().__init__("Marteau de combat", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return "Golem" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class EpeeMagiqueAleatoire(Objet):
    def __init__(self):
        super().__init__("Épée magique aléatoire", False)
        self.puissance_a_executer = -1
    def debut_partie(self, joueur, Jeu, log_details):
        jet = joueur.rollDice(Jeu, log_details)
        if jet in [1, 2]:
            self.puissance_a_executer = 5
        elif jet in [3, 4]:
            self.puissance_a_executer = 6
        else:
            self.puissance_a_executer = 7
        log_details.append(f"{joueur.nom} utilise {self.nom}, jet de {jet}, exécute les monstres de puissance {self.puissance_a_executer}.")
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance == self.puissance_a_executer and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class FausseCouronne(Objet):
    def __init__(self):
        super().__init__("Fausse couronne", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return   carte.puissance % 2 == 0

    def combat_effet(self, joueur, carte, Jeu, log_details):
            self.reduc_damage(1, joueur, carte, log_details)
            
class ArbaleteTropGrosse(Objet):
    def __init__(self):
        super().__init__("Arbalète trop grosse", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance > joueur.pv_total and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class MasqueDeLInquisiteur(Objet):
    def __init__(self):
        super().__init__("Masque de l'Inquisiteur", False, 2)
    def fin_tour(self, joueur, Jeu, log_details):
        if self.intact and (joueur.pv_total == 2 or joueur.pv_total == 4 or joueur.pv_total == 8):           
            self.gagnePV(2, joueur, log_details)

class PareBuffleDuPonceur(Objet):
    def __init__(self):
        super().__init__("Pare-Buffle du Ponceur", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance >= 6
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(4, joueur, carte, log_details)

class FromagePuant(Objet):
    def __init__(self):
        super().__init__("Fromage Puant", True)
        
    def utiliser(self, dernier_monstre, joueur, Jeu, log_details):
        self.gagnePV(dernier_monstre.puissance, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact and joueur.pile_monstres_vaincus:
            dernier_monstre = joueur.pile_monstres_vaincus[-1]
            if dernier_monstre.puissance >= 6:
                self.utiliser(dernier_monstre, joueur, Jeu, log_details)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if self.intact and joueur.pv_total <= carte.dommages and joueur.pile_monstres_vaincus:
            dernier_monstre = joueur.pile_monstres_vaincus[-1]
            self.utiliser(dernier_monstre, joueur, Jeu, log_details)

class MailletDArgile(Objet):
    def __init__(self):
        super().__init__("Maillet D'Argile", False, 2)
    def rules(self, joueur, carte, Jeu, log_details):
        return "Golem" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)

class AllianceSanguine(Objet):
    def __init__(self):
        super().__init__("Alliance Sanguine", False, 1)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if joueur.pv_total <= 2:
            self.reduc_damage(3, joueur, carte, log_details)


class FauxDeLaMort(Objet):
    def __init__(self):
        super().__init__("Faux De La Mort",False, 2)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance == joueur.pv_total and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)


class QueueDuCharognard(Objet):
    def __init__(self):
        super().__init__("Queue Du Charognard",False, 2)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance == len(joueur.pile_monstres_vaincus) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        
class CasqueBerserk(Objet):
    def __init__(self):
        super().__init__("CasqueBerserk", False, 7)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if self.intact and (carte.puissance <= 3):
            self.add_damage(1, joueur, carte, log_details)
        
# 2025

class TentaculeDuKraken(Objet):
    def __init__(self):
        super().__init__("Tentacule du Kraken", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance % 2 == 0 
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(carte.puissance, joueur, log_details)
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        # Jeu.donjon.ajouter_monstre(carte)
        Jeu.donjon.remelange()
        log_details.append(f"{joueur.nom} remet {carte.titre} dans le Donjon grâce à {self.nom}.")
        self.destroy(joueur, Jeu, log_details)

# class HamacReposant(Objet):
#     def __init__(self):
#         super().__init__("Hamac reposant", False, 2)
#     def debut_tour(self, joueur, Jeu, log_details):
#         if joueur.rollDice(Jeu, log_details) >= 4:
#             joueur.passe_tour = True
#             log_details.append(f"{joueur.nom} passe son tour grâce à {self.nom}.")

# class SacDeCouchette(Objet):
#     def __init__(self):
#         super().__init__("Sac de couchette", True)
#     def fin_tour(self, joueur, Jeu, log_details):
#         joueur.skip_turns(2, Jeu)
#         self.piocheItem(joueur, Jeu, log_details)
#         self.destroy(joueur, Jeu, log_details)

class CorbeilleDOr(Objet):
    def __init__(self):
        super().__init__("Corbeille d'or", False, 1, 0)
    def score_effet(self, joueur, log_details):
        objets_brises = sum(1 for objet in joueur.objets if not objet.intact)
        self.scoreChange(objets_brises, joueur, log_details)

class OsseletsDeResurrection(Objet):
    def __init__(self):
        super().__init__("Osselets de Résurrection", False, 0)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    # def survie_effet(self, joueur, carte, Jeu, log_details):
    #     if joueur.pv_total >= 3:
    #         self.survit(1, joueur, carte, log_details)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if joueur.pv_total >= 3:
            carte.executed = True
            self.survit(1, joueur, carte, log_details)
            
class LunettesDuBricoleur(Objet):
    def __init__(self):
        super().__init__("Lunettes du Bricoleur", False, 2)
    def activated_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur and joueur.rollDice(Jeu, log_details) == 6:
            objet.repare()
            log_details.append(f"{self.nom} répare {objet.nom} automatiquement.")

class AttrapeReves(Objet):
    def __init__(self):
        super().__init__("Attrape-Rêves", False, 2)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if not carte.types:
            self.execute(joueur, carte, log_details)

class DeMaudit(Objet):
    def __init__(self):
        super().__init__("Dé Maudit", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance <= 6 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet = joueur.rollDice(Jeu, log_details, carte.puissance+1)
        log_details.append(f"{joueur.nom} utilise De maudit sur {carte.titre}, jet de {jet}")
        if jet == carte.puissance:
            self.execute(joueur, carte, log_details)
        else:
            log_details.append(f"rate !")

class PelleDuFossoyeur(Objet):
    def __init__(self):
        super().__init__("Pelle du Fossoyeur", True)

    # Helper method containing the core logic
    def _activer_pelle(self, joueur, Jeu, log_details):
        # Identify monsters in discard
        monstres_defausse = [c for c in Jeu.defausse if hasattr(c, 'types') and not getattr(c, 'event', False)]

        # Activation Log
        log_details.append(f"{joueur.nom} utilise {self.nom}")

        # Prioritized Selection (exactly 4)
        golem_or_dispo = []
        dragons_dispo = []
        autres_dispo = []
        for monstre in monstres_defausse:
            # ... (sorting logic as before) ...
            if getattr(monstre, 'effet', None) == "GOLD":
                golem_or_dispo.append(monstre)
            elif "Dragon" in getattr(monstre, 'types', []):
                dragons_dispo.append(monstre)
            else:
                autres_dispo.append(monstre)

        monstres_choisis = []
        MAX_CHOIX = 4 # Should always be 4 now

        if golem_or_dispo:
            monstres_choisis.append(golem_or_dispo[0])
        random.shuffle(dragons_dispo)
        while len(monstres_choisis) < MAX_CHOIX and dragons_dispo:
            monstres_choisis.append(dragons_dispo.pop())
        random.shuffle(autres_dispo)
        while len(monstres_choisis) < MAX_CHOIX and autres_dispo:
            monstres_choisis.append(autres_dispo.pop())

        # Log chosen monsters
        noms_choisis = [m.titre for m in monstres_choisis]
        log_details.append(f"--> Récupère {len(monstres_choisis)} monstres (priorité GolemOr>Dragon>Autre): {noms_choisis}")

        # Remove from discard
        ids_choisis = {id(m) for m in monstres_choisis}
        Jeu.defausse = [c for c in Jeu.defausse if id(c) not in ids_choisis]

        # Add to player's victory pile
        for monstre in monstres_choisis:
            joueur.ajouter_monstre_vaincu(monstre)

        # Destroy the item
        self.destroy(joueur, Jeu, log_details)
        return True # Indicate successful activation

    # Trigger 1: Fin de tour
    def fin_tour(self, joueur, Jeu, log_details):
        monstres_defausse = [c for c in Jeu.defausse if hasattr(c, 'types') and not getattr(c, 'event', False)]

        if self.intact and len(monstres_defausse) >= 4:
            self._activer_pelle(joueur, Jeu, log_details)

    # Trigger 2: Fuite définitive
    def fuite_definitive_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
            # Check if intact and if the owner is the one fleeing
            if self.intact and joueur_proprietaire == joueur:
                self._activer_pelle(joueur, Jeu, log_details)
                
                
class PateDAnge(Objet):
    def __init__(self):
        super().__init__("Pâté d'Ange", True)
    
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total <= carte.dommages or all(not autre_joueur.dans_le_dj for autre_joueur in Jeu.joueurs if autre_joueur != joueur)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if self.intact:
            self.gagnePV(7, joueur, log_details)
            for autre_joueur in Jeu.joueurs:
                if autre_joueur != joueur and autre_joueur.dans_le_dj:
                    autre_joueur.pv_total += 4
                    log_details.append(f"{autre_joueur.nom} gagne 4 PV grâce à {self.nom}. PV restant: {autre_joueur.pv_total}.")
            self.destroy(joueur, Jeu, log_details)

class AnneauDesSquelettes(Objet):
    def __init__(self):
        super().__init__("Anneau des Squelettes", False)
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if ("Squelette" in carte.types and not Jeu.traquenard_actif):
            self.execute(joueur, carte, log_details)
            self.gagnePV(1, joueur, log_details)

        if "Démon" in carte.types:
            self.reduc_damage(4, joueur, carte, log_details)

class GriffesDeLArracheur(Objet):
    def __init__(self):
        super().__init__("Griffes de l'Arracheur", False)
    
    def rules(self, joueur, carte, Jeu, log_details):
        return "Orc" in carte.types and not Jeu.traquenard_actif
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        joueur.pv_total += carte.puissance
        log_details.append(f"{joueur.nom} utilise {self.nom} pour exécuter {carte.titre} et gagne {carte.puissance} PV. Total {joueur.pv_total} PV.")


class Harpe(Objet):
    def __init__(self):
        super().__init__("Harpe", False, 0, 0)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and joueur.pv_total <= 4
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total > 2 - (carte.puissance % 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.perdPV(2 - (carte.puissance % 2), joueur, log_details)

class BouclierMagique(Objet):
    def __init__(self):
        super().__init__("Bouclier Magique", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        len(joueur.pile_monstres_vaincus) >= 7
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(4, joueur, carte, log_details)        


class ViandeCrue(Objet):
    def __init__(self):
        super().__init__("Viande Crue", True)
   
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if any("Dragon" in monstre.types for monstre in joueur.pile_monstres_vaincus):    
            self.gagnePV(8, joueur, log_details)
        else:
            self.gagnePV(3, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)    
        
    
class MailletDuRoiLiche(Objet):
    def __init__(self):
        super().__init__("Maillet Du Roi Liche", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and ("Golem" in carte.types or "Lich" in carte.types or "Démon" in carte.types)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.gagnePV(3, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)    


class CouteauEntreLesDents(Objet):
    def __init__(self):
        super().__init__("Couteau Entre Les Dents", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Vampire" in carte.types or "Orc" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class PainMaudit(Objet):
    def __init__(self):
        super().__init__("Pain maudit", True)
    
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if self.intact:
            self.gagnePV(4, joueur, log_details)
            demons_dragons = []
            # Chercher dans la défausse
            for card in Jeu.defausse[:]:
                if hasattr(card, 'types') and ("Démon" in card.types or "Dragon" in card.types):
                    demons_dragons.append(card)
                    Jeu.defausse.remove(card)
            
            # Chercher dans les piles de monstres vaincus
            for j in Jeu.joueurs:
                for card in j.pile_monstres_vaincus[:]:
                    if hasattr(card, 'types') and ("Démon" in card.types or "Dragon" in card.types):
                        demons_dragons.append(card)
                        j.pile_monstres_vaincus.remove(card)
            
            # Remettre les monstres dans le donjon
            for monstre in demons_dragons:
                Jeu.donjon.ajouter_monstre(monstre)
                log_details.append(f"{monstre.titre} retourne dans le Donjon.")
            
            if demons_dragons:
                Jeu.donjon.remelange()
                log_details.append("Le Donjon a été mélangé.")
            
            self.destroy(joueur, Jeu, log_details)
        
class PierreDuNaga(Objet):
    def __init__(self):
        super().__init__("Pierre du Naga", False, 2)  # False pour actif = non, et 2 pour le bonus de PV initial
    

    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if carte.puissance >= 7:
            log_details.append(f"{self.nom} de {joueur_proprietaire.nom} se declenche car {joueur.nom} a vaincu un monstre de puissance 7 ou plus.")
            self.gagnePV(1, joueur_proprietaire, log_details)

class CapeDePlumes(Objet):
    def __init__(self):
        super().__init__("Cape de Plumes", True)  # True pour actif = oui

    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)

    def combat_effet(self, joueur, carte, Jeu, log_details):
        # Réduire les dommages du monstre de 8
        reduction = 8
        carte.dommages = max(0, carte.dommages - reduction)
        log_details.append(f"{joueur.nom} utilise {self.nom} pour réduire les dommages de {carte.titre} de {reduction}. Nouveaux dommages: {carte.dommages}.")
        self.destroy(joueur, Jeu, log_details)  

class SetDeCoeurs(Objet):
    def __init__(self):
        super().__init__("Set de Cœurs", True)  
    
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total and joueur.pv_total < 7 and carte.dommages < 7
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        joueur.pv_total = 7
        log_details.append(f"{joueur.nom} utilise {self.nom} pour fixer ses PV à 7.")
        self.destroy(joueur, Jeu, log_details) 

class GrelotDuBouffon(Objet):
    def __init__(self):
        super().__init__("Grelot du Bouffon", False, 1)  
    
    def rencontre_event_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        self.gagnePV(1, joueur_proprietaire, log_details)
        log_details.append(f"{joueur_proprietaire.nom} gagne 1 PV grâce à {self.nom} car un événement a été pioché.")

class FruitDuDestin(Objet):
    def __init__(self):
        super().__init__("Fruit du Destin", True)
    
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total

    def combat_effet(self, joueur, carte, Jeu, log_details):
        # Séparer les cartes monstres et évènements de la défausse
        monsters = [c for c in Jeu.defausse if hasattr(c, 'types') and not getattr(c, 'event', False)]
        events = [c for c in Jeu.defausse if getattr(c, 'event', False)]
        
        if not (monsters or events):
            log_details.append(f"{self.nom} n'a aucun effet : aucune carte monstre ou évènement en défausse.")
        else:
            # Choisir le type de carte à défausser
            if len(monsters) >= len(events):
                chosen_cards = monsters
                chosen_type = "monstre"
            else:
                chosen_cards = events
                chosen_type = "évènement"
            
            nb = len(chosen_cards)

            
            self.gagnePV(nb, joueur, log_details)
            log_details.append(f"{joueur.nom} utilise {self.nom} sur les {chosen_type} pour gagner {nb} PV. ({len(monsters)} monstres et {len(events)} events )")

        self.destroy(joueur, Jeu, log_details)

class CocktailMolotov(Objet):
    def __init__(self):
        super().__init__("Cocktail Molotov", True)
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        # Défaussez sans les jouer 3 cartes du dessus du Donjon.
        log_details.append(f"{joueur.nom} utilise {self.nom}.")
        for _ in range(3):
            if not Jeu.donjon.vide:
                # Utiliser la méthode 'prochaine_carte()' pour respecter l'ordre mélangé.
                card = Jeu.donjon.prochaine_carte()
                remaining = Jeu.donjon.nb_cartes - Jeu.donjon.index
                if hasattr(card, 'types') and not getattr(card, 'event', False):
                    joueur.ajouter_monstre_vaincu(card)
                    log_details.append(f"{card.titre} ajouté à la pile des monstres vaincus. Cartes restantes dans le donjon: {remaining}")
                else:
                    Jeu.defausse.append(card)
                    log_details.append(f"{card.titre} défaussé sans être joué.")
            else:
                log_details.append("Le Donjon est vide.")
                break
        self.destroy(joueur, Jeu, log_details)

class ParcheminDePonçage(Objet):
    def __init__(self):
        super().__init__("Parchemin de ponçage", True, 1)
    
    def rules(self, joueur, carte, Jeu, log_details):
        return (carte.puissance % 2 == 1)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if self.intact:
            puissance = carte.puissance
            self.execute(joueur, carte, log_details)
            for _ in range(puissance):
                if not Jeu.donjon.vide:
                    card = Jeu.donjon.prochaine_carte()
                    Jeu.defausse.append(card)
                    remaining = Jeu.donjon.nb_cartes - Jeu.donjon.index
                    log_details.append(f"{card.titre} défaussé. Cartes restantes dans le Donjon: {remaining}")
                else:
                    log_details.append("Le Donjon est vide.")
                    break
            self.destroy(joueur, Jeu, log_details)

class AraigneeDomestique(Objet):
    def __init__(self):
        super().__init__("Araignée domestique", False)
    
    def steal_monsters(self,  owner,target, Jeu, log_details):
        
        stolen = 0
        for _ in range(2):
            if target.pile_monstres_vaincus:
                monstre = target.pile_monstres_vaincus.pop(0)
                owner.ajouter_monstre_vaincu(monstre)
                stolen += 1
                log_details.append(f"{owner.nom} vole {monstre.titre} dans la pile de {target.nom}.")
            else:
                break
        if stolen == 0:
            log_details.append(f"{owner.nom} n'a pas pu voler de monstres dans la pile de {target.nom}.")
        self.destroy(owner, Jeu, log_details)
# attention l'araignee n'est pas a jour. elle vole tous les joueurs au lieu de juste le premier
    def en_mort(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if joueur != joueur_proprietaire and joueur_proprietaire.dans_le_dj:
            self.steal_monsters(joueur_proprietaire, joueur, Jeu, log_details)
    
    def en_fuite_definitive(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if joueur != joueur_proprietaire and joueur_proprietaire.dans_le_dj:
            self.steal_monsters(joueur_proprietaire, joueur, Jeu, log_details)


class Exterminator(Objet):
    def __init__(self):
        super().__init__("Exterminator", False, 0, -2)
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Dragon" in carte.types or "Rat" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class CodexDiabolus(Objet):
    def __init__(self):
        super().__init__("Codex Diabolus", False, 0, -2)
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Vampire" in carte.types or "Démon" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class LanceDuDestin(Objet):
    def __init__(self):
        super().__init__("LanceDuDestin", False, 0, 0)
    def rules(self, joueur, carte, Jeu, log_details):
        return (carte.puissance == 6 or carte.puissance == 8 or carte.puissance == 10) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        
class AspisHeracles(Objet):
    def __init__(self):
        super().__init__("Aspis d'Héraclès", True) # True car c'est un objet Actif

    def rules(self, joueur, carte, Jeu, log_details):
        # On ne peut pas l'utiliser si Traquenard est actif
        return not Jeu.traquenard_actif

    def worthit(self, joueur, carte, Jeu, log_details):
        # Logique simple pour décider quand l'utiliser (peut être affinée)
        # Par exemple, si le monstre fait beaucoup de dégâts ou est puissant
        return carte.dommages > (joueur.pv_total / 2) or carte.puissance >= 6

    def combat_effet(self, joueur, carte, Jeu, log_details):
        puissance_monstre = carte.puissance # Sauvegarder la puissance avant défausse
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        if puissance_monstre >= 7:
            self.gagnePV(3, joueur, log_details)
        self.destroy(joueur, Jeu, log_details) # Se détruit après utilisation
        
class BouillonDAmes(Objet):
    def __init__(self):
        super().__init__("Bouillon d'âmes", True)

    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif

    def worthit(self, joueur, carte, Jeu, log_details):
        # Heuristique simple pour l'IA
        return carte.dommages > (joueur.pv_total / 2) or carte.puissance >= 6

    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)

        # Identifier les monstres en défausse (comme FruitDuDestin)
        monstres_a_remettre = [c for c in Jeu.defausse if hasattr(c, 'types') and not getattr(c, 'event', False)]

        if monstres_a_remettre:
            # Les retirer de la défausse
            Jeu.defausse = [c for c in Jeu.defausse if not (hasattr(c, 'types') and not getattr(c, 'event', False))]

            # Log amélioré avec la liste des noms
            noms_monstres = [m.titre for m in monstres_a_remettre]
            log_details.append(f"{joueur.nom} utilise {self.nom}. Remet {len(monstres_a_remettre)} monstres dans le Donjon et mélange.")
            log_details.append(f"--> Monstres remis: {noms_monstres}") # Log ajouté

            # Les remettre dans le pool du Donjon (comme EspritDuDonjon)
            for monstre in monstres_a_remettre:
                Jeu.donjon.ajouter_monstre(monstre) # Ajoute l'index à la fin de self.ordre

            # Mélanger le deck restant (comme EspritDuDonjon / Soulstorm)
            Jeu.donjon.remelange() # Mélange les cartes restantes à partir de l'index actuel

        else:
            log_details.append(f"{joueur.nom} utilise {self.nom}, mais la défausse ne contient aucun monstre.")

        self.destroy(joueur, Jeu, log_details)        


class ConcentreDeFun(Objet):
    def __init__(self):
        super().__init__("Concentré de fun", True)

    def survie_effet(self, joueur, carte, Jeu, log_details):
        # ordonnanceur calls this when joueur.pv_total <= 0
        # Set PV to base hero PV
        self.survit(joueur.pv_base, joueur, carte, log_details)

        # Check for Traquenard in discard
        traquenard_card = None
        for c in Jeu.defausse:
            # Check if it's an event card with the correct title
            if getattr(c, 'event', False) and getattr(c, 'titre', None) == "Traquenard":
                traquenard_card = c
                break # Found it

        if traquenard_card:
            try:
                Jeu.defausse.remove(traquenard_card)
                Jeu.donjon.rajoute_en_haut_de_la_pile(traquenard_card)
                log_details.append(f"La carte Traquenard est retirée de la défausse et remise sur le Donjon.")
            except ValueError:
                # Should not happen if found, but good practice
                log_details.append(f"Erreur: Impossible de retirer Traquenard de la défausse.")


        self.destroy(joueur, Jeu, log_details) # Destroy after use

# Liste des objets
objets_disponibles = [ 
    MainDeMidas(), 
    MainDeMidasB(),
    HacheExecution(), 
    MarteauDeGuerre(),
    FleauDesLiches(),
    EpauletteDuBourrin(),
    Item6PV(),
    ArmureEnCuir(),  # 5pv
    CotteDeMailles(), # 4pv
    ParcheminDeBahn(), 
    SingeDore(), 
    GateauSpatial(),
    CouteauSuisse(),
    CaisseEnchantee(),
    BouclierGolemique(),
    Barde(),
    BouclierDragon(),
    PotionDeMana(),
    KebabRevigorant(), 
    ArcEnflamme(),   
    ParcheminDeTeleportation(),
    GrosBoulet(),
    PotionFeerique(),
    PotionDeGlace(),
    PotionDraconique(),
    PiocheDeDiamant(),
    Katana(),
    ChapeauDuNovice(),
    MasqueDeLaPeste(),
    TorcheRouge(),
    RobeDeMage(),
    ValisesDeCash(),
    AnneauDuFeu(),
    TronconneuseEnflammee(),
    TuniqueClasse(),
    AnneauMagique(),
    TroisPV(),
    TroisPV_(),
    ArmureDHonneur(),
    PierreDAme(),
    CoeurDeGolem(),
    CouronneDEpines(),
    MasqueAGaz(),
    BouclierCameleon(),
    YoYoProtecteur(),
    TalismanIncertain(),
    ChapeletDeVitalite(),
    GlaiveDArgent(),
    BouclierCasse(),
    PlanPresqueParfait(),
    GraalEnMousse(),
    ItemUseless(),
    AnneauDesSurmulots(),
    ArmureDamnee(),
    PatinsAGlace(),
    CoquillageMagique(),
    MasqueDragon(),
    PiedDeBiche(),
    MarmiteGelatineuse(),
    GrimoireInconnu(),
    GantsDeCombat(),
    GantsDeGaia(),
    ChampDeForceEnMousse(),
    BoiteDePandore(),
    TorcheBleue(),
    AnneauPlussain(),
    GetasDuNovice(),
    MarteauDEternite(),
    CaliceDuRoiSorcier(),
    PerceuseABreche(),
    EnclumeInstable(),
    CoffreAnime(),
    AnneauDeVie(),
    BottesDeVitesse(),
    Randotion(),
    LameDeLHarmonie(),
    ChampignonVeneneux(),
    BouletDeCanon(),
    PotionOuPoison(),
    CoquilleSalvatrice(),
    LameDraconique(),
    FouetDuFourbe(),
    CraneDuRoiLiche(),
    SeringueDuDocteurFou(),
    CorneDAbordage(),
    FeuilleEternelle(),
    PatteDuRatLiche(),
    LivreSacre(),
    PendentifDuNovice(),
    PistoletPirate(),
    ArmureArdente(),
    SceptreActif(),
    CapeVaudou(),
    FerACheval(),
    DeDuTricheur(),
    EspritDuDonjon(),
    SabreMecanique(),
    CouronneEnMousse(),
    KatanaEnMousse(),
    MarteauFlamboyant(), 
    TreizeASeize(), 
    Scaphandre(),
    BouclierDeLInventeur(), 
    EpeeMystique(),
    DelicieusePizza(), 
    BoiteAButin(),
    PlatreeDeBerniques(),
    AnneauOceanique(),
    BoomerangMystique(),   
    CoiffeDeSorcier(),
    ArmureDuRoiLiche(),
    ElixirDeChance(),
    ChapeauStyle(),
    Chameau(),
    PotionDeFeuLiquide(),
    CasquePlus(),
    AnkhDeReincarnation(),
    CoffreDuRoiSorcier(),
    CoeurDeDragon(),
    PotionDAdrenaline(),
    PeigneEnOr(),
    LampeMagique(),
    CanneAChep(),
    KitVaudou(),
    MarteauDeCombat(),
    AnneauVolcanique(),
    Dragoune(),
    EpeeMagiqueAleatoire(),
    FausseCouronne(),
    ArbaleteTropGrosse(),
    MasqueDeLInquisiteur(),
    PareBuffleDuPonceur(),
    FromagePuant(),
    MailletDArgile(),
    AllianceSanguine(),
    FauxDeLaMort(),
    QueueDuCharognard(),
    CasqueBerserk(),
    TentaculeDuKraken(),
    # HamacReposant(),
    # SacDeCouchette(),
    CorbeilleDOr(),
    OsseletsDeResurrection(),
    LunettesDuBricoleur(),
    AttrapeReves(),
    DeMaudit(),
    Harpe(),
    BouclierMagique(),
    ViandeCrue(),
    MailletDuRoiLiche(),
    CouteauEntreLesDents(),
    GriffesDeLArracheur(),
    AnneauDesSquelettes(),
    PateDAnge(),
    PelleDuFossoyeur(),
    PainMaudit(), 
    PierreDuNaga(),
    CapeDePlumes(),
    SetDeCoeurs(),
    FruitDuDestin(),
    CocktailMolotov(),
    ParcheminDePonçage(),
    AraigneeDomestique(),
    Exterminator(),
    CodexDiabolus(),
    LanceDuDestin(),
    TorcheEnMousse(),
    GrelotDuBouffon(),
    AspisHeracles(),
    BouillonDAmes(),
    ConcentreDeFun(),
]



__all__ = [
            "objets_disponibles",
            "MainDeMidas",
            "MainDeMidasB",
            "HacheExecution",
            "MarteauDeGuerre",
            "FleauDesLiches",
            "EpauletteDuBourrin",
            "Item6PV",
            "ArmureEnCuir",
            "CotteDeMailles",
            "ParcheminDeBahn",
            "SingeDore",
            "GateauSpatial",
            "CouteauSuisse",
            "CaisseEnchantee",
            "BouclierGolemique",
            "Barde",
            "BouclierDragon",
            "PotionDeMana",
            "KebabRevigorant",
            "ArcEnflamme",
            "ParcheminDeTeleportation",
            "GrosBoulet",
            "PotionFeerique",
            "PotionDeGlace",
            "PotionDraconique",
            "PiocheDeDiamant",
            "Katana",
            "ChapeauDuNovice",
            "MasqueDeLaPeste",
            "TorcheRouge",
            "RobeDeMage",
            "ValisesDeCash",
            "AnneauDuFeu",
            "TronconneuseEnflammee",
            "TuniqueClasse",
            "AnneauMagique",
            "TroisPV",
            "TroisPV_",
            "ArmureDHonneur",
            "CoeurDeGolem",
            "PierreDAme",
            "CouronneDEpines",
            "MasqueAGaz",
            "BouclierCameleon",
            "YoYoProtecteur",
            "TalismanIncertain",
            "ChapeletDeVitalite",
            "GlaiveDArgent",
            "BouclierCasse",
            "PlanPresqueParfait",
            "GraalEnMousse",
            "ItemUseless",
            "AnneauDesSurmulots",
            "ArmureDamnee",
            "PatinsAGlace",
            "CoquillageMagique",
            "MasqueDragon",
            "PiedDeBiche",
            "MarmiteGelatineuse",
            "GrimoireInconnu",
            "GantsDeCombat",
            "GantsDeGaia",
            "ChampDeForceEnMousse",
            "BoiteDePandore",
            "TorcheBleue",
            "AnneauPlussain",
            "GetasDuNovice",
            "MarteauDEternite",
            "CaliceDuRoiSorcier",
            "PerceuseABreche",
            "EnclumeInstable",
            "CoffreAnime",
            "AnneauDeVie",
            "BottesDeVitesse",
            "Randotion",
            "LameDeLHarmonie",
            "ChampignonVeneneux",
            "BouletDeCanon",
            "PotionOuPoison",
            "CoquilleSalvatrice",
            "LameDraconique",
            "FouetDuFourbe",
            "CraneDuRoiLiche",
            "SeringueDuDocteurFou",
            "CorneDAbordage",
            "FeuilleEternelle",
            "PatteDuRatLiche",
            "LivreSacre",
            "PendentifDuNovice",
            "PistoletPirate",
            "ArmureArdente",
            "SceptreActif",
            "CapeVaudou",
            "FerACheval",
            "DeDuTricheur",
            "EspritDuDonjon",
            "SabreMecanique",
            "CouronneEnMousse",
            "KatanaEnMousse",
            "MarteauFlamboyant",
            "TreizeASeize",
            "Scaphandre",
            "BouclierDeLInventeur", 
            "EpeeMystique",
            "DelicieusePizza",
            "BoiteAButin",
            "PlatreeDeBerniques",
            "AnneauOceanique",
            "BoomerangMystique",
            "CoiffeDeSorcier",
            "ArmureDuRoiLiche",
            "ElixirDeChance",
            "ChapeauStyle",
            "Chameau",
            "PotionDeFeuLiquide",
            "CasquePlus",
            "AnkhDeReincarnation",
            "CoffreDuRoiSorcier",
            "CoeurDeDragon",
            "PotionDAdrenaline",
            "PeigneEnOr",
            "LampeMagique",
            "CanneAChep",
            "AnneauVolcanique",
            "Dragoune",
            "KitVaudou",
            "MarteauDeCombat",
            "EpeeMagiqueAleatoire", 
            "FausseCouronne",
            "ArbaleteTropGrosse",
            "MasqueDeLInquisiteur",
            "PareBuffleDuPonceur",
            "FromagePuant",
            "MailletDArgile",
            "AllianceSanguine",
            "FauxDeLaMort",
            "QueueDuCharognard",
            "CasqueBerserk",
            "DeMaudit",
            "TentaculeDuKraken",
            # "HamacReposant",
            # "SacDeCouchette",
            "CorbeilleDOr",
            "OsseletsDeResurrection",
            "LunettesDuBricoleur",
            "AttrapeReves",
            "Harpe",
            "BouclierMagique",
            "ViandeCrue",
            "MailletDuRoiLiche",
            "CouteauEntreLesDents",
            "GriffesDeLArracheur",
            "AnneauDesSquelettes",
            "PateDAnge",
            "PelleDuFossoyeur",
            "PainMaudit",
            "PierreDuNaga",
            "CapeDePlumes",
            "SetDeCoeurs",
            "FruitDuDestin",
            "CocktailMolotov",
            "ParcheminDePonçage",
            "AraigneeDomestique",
            "Exterminator",
            "CodexDiabolus",
            "LanceDuDestin",
            "TorcheEnMousse",
            "GrelotDuBouffon",
            "AspisHeracles",
            "BouillonDAmes",
            "ConcentreDeFun"
        ]
