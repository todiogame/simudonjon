import random

class Objet:
    def __init__(self, nom, actif=False, pv_bonus=0, modificateur_de=0, effet=None, intact=True):
        self.nom = nom
        self.pv_bonus = pv_bonus
        self.modificateur_de = modificateur_de
        self.effet = effet
        self.intact = intact
        self.actif = actif

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
    def rencontre_event_effet(self, joueur, carte, Jeu, log_details):
        pass
    def vaincu_effet(self, joueur, carte, Jeu, log_details):
        pass
    def survie_effet(self, joueur, carte, Jeu, log_details):
        pass
    def decompte_effet(self,joueur, joueurs_final, log_details):
        pass
    def debut_tour(self, joueur, Jeu, log_details):
        pass
    def fin_tour(self):
        pass
    def score_effet(self, joueur, log_details):
        pass



    def en_rencontre(self, joueur, carte, Jeu, log_details):
        # attention, check si les items sont intacts
        self.rencontre_effet(joueur, carte, Jeu, log_details)

    def en_fuite(self, joueur, Jeu, log_details):
        # attention, check si les items sont intacts
        pass

    def en_rencontre_event(self, joueur, carte, Jeu, log_details):
        # attention, check si les items sont intacts
        self.rencontre_event_effet(joueur, carte, Jeu, log_details)    
    

    def en_combat(self, joueur, carte, Jeu, log_details):
        if self.condition(joueur, carte, Jeu, log_details):
            self.combat_effet(joueur, carte, Jeu, log_details)

    
    def en_vaincu(self, joueur, carte, Jeu, log_details):
        # attention, check si les items sont intacts
        self.vaincu_effet(joueur, carte, Jeu, log_details) 
    
    def en_survie(self, joueur, carte, Jeu, log_details):
        if self.intact:
            self.survie_effet(joueur, carte, Jeu, log_details)

    def en_score(self, joueur, log_details):
        if self.intact:
            self.score_effet(joueur, log_details)

    def en_decompte(self, joueur, joueurs_final, log_details):
        if self.intact:
            self.decompte_effet(joueur, joueurs_final, log_details)

    def reset_intact(self, log_details):
        log_details.append(f"Reparé {self.nom}")
        self.intact = True
    def destroy(self):
        self.intact = False
    
    def execute(self, joueur, carte, log_details):
        carte.executed = True
        joueur.pile_monstres_vaincus.append(carte)
        log_details.append(f"Utilisé {self.nom} pour exécuter {carte.titre}")

    def executeEtDefausse(self, joueur, carte, Jeu, log_details):
        carte.executed = True
        Jeu.defausse.append(carte)
        log_details.append(f"Utilisé {self.nom} pour exécuter et défausser {carte.titre}")

    def absorbe(self, joueur, carte, log_details):
        carte.executed = True
        joueur.pv_total += carte.puissance  # Absorber les PV
        joueur.pile_monstres_vaincus.append(carte)
        log_details.append(f"Utilisé {self.nom} sur {carte.titre} pour absorber {carte.puissance} PV. Total {joueur.pv_total} PV.")

    def reduc_damage(self, value, joueur, carte, log_details):
        carte.dommages = max(carte.dommages - value, 0)
        log_details.append(f"Utilisé {self.nom} sur {carte.titre} pour réduire les dommages de {value}.")

    def add_damage(self, value, joueur, carte, log_details):
        carte.dommages = carte.dommages + value
        log_details.append(f"Utilisé {self.nom} sur {carte.titre} pour augmenter les dommages de {value}.")

    def gagnePV(self, value, joueur, log_details):
        joueur.pv_total += value
        log_details.append(f"Utilisé {self.nom} pour gagner {value} PV. Total {joueur.pv_total} PV.")

    def perdPV(self, value, joueur, log_details):
        joueur.pv_total -= value
        log_details.append(f"Utilisé {self.nom} et perd {value} PV. Total {joueur.pv_total} PV.")
        if(joueur.pv_total <= 0): joueur.mort()

    def survit(self, value, joueur, carte, log_details):
        joueur.pv_total = value
        joueur.pile_monstres_vaincus.append(carte)
        log_details.append(f"Utilisé {self.nom} pour survivre avec {value} PV et vaincre {carte.titre}")

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
        super().__init__("Hache d'Exécution", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.destroy()
        self.execute(joueur, carte, log_details)

class MarteauDeGuerre(Objet):
    def __init__(self):
        super().__init__("Marteau de Guerre",False, 0, -1)
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Golem" in carte.types or "Squelette" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        
class EpauletteDuBourrin(Objet):
    def __init__(self):
        super().__init__("Epaulette du Bourrin", False, 5, -2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(1, joueur, carte, log_details)

class MainDeMidas(Objet):
    def __init__(self):
        super().__init__("Main de Midas", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance <= 5 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.destroy()
        self.absorbe(joueur, carte, log_details)
class Item6PV(Objet):
    def __init__(self):
        super().__init__("Item 6PV", False, 6)
class ArmureEnCuir(Objet):
    def __init__(self):
        super().__init__("Armure en cuir", False, 5)
class CotteDeMailles(Objet):
    def __init__(self):
        super().__init__("Cotte de mailles", False, 4)

class ParcheminDeBahn(Objet):
    def __init__(self):
        super().__init__("Parchemin de Bahn", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.destroy()
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        self.gagnePV(1, joueur, log_details)

class SingeDore(Objet):
    def __init__(self):
        super().__init__("Singe doré", False, 0, -2)
    def score_effet(self, joueur, log_details):
        self.scoreChange(random.randint(1, 6), joueur, log_details)
class GateauSpatial(Objet):
    def __init__(self):
        super().__init__("Gâteau spatial", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.destroy()
        jet_gateau = random.randint(1, 6)
        if jet_gateau == 1:
            joueur.fuite()
            log_details.append(f"Utilisé Gâteau spatial, jet de {jet_gateau}, fuite immédiate du Donjon.\n")
        else:
            self.gagnePV(jet_gateau, joueur, log_details)

class CouteauSuisse(Objet):
    def __init__(self):
        super().__init__("Couteau Suisse", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return len([obj for obj in joueur.objets if not obj.intact])
    def combat_effet(self, joueur, carte, Jeu, log_details):
        objets_brisés = [obj for obj in joueur.objets if (not obj.intact and not obj.nom == "Couteau Suisse")]
        self.destroy()
        if objets_brisés:
            objet_repare = random.choice(objets_brisés)
            objet_repare.intact = True
            log_details.append(f"Utilisé Couteau Suisse pour réparer {objet_repare.nom}.")
            if objet_repare.pv_bonus: self.gagnePV(objet_repare.pv_bonus, joueur, log_details)

class CaisseEnchantee(Objet):
    def __init__(self):
        super().__init__("Caisse enchantée", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance < 6 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet_caisse = random.randint(1, 6)
        log_details.append(f"Utilisé Caisse enchantée sur {carte.titre}, jet de {jet_caisse}")
        if jet_caisse == 1:
            self.destroy()
            log_details.append(f"Caisse enchantée brisée.")
        elif jet_caisse > carte.puissance:
            self.execute(joueur, carte, log_details)
        else:
            log_details.append(f"Pas assez !")

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
        self.destroy()
        self.perdPV(self.pv_bonus, joueur, log_details)
        self.execute(joueur, carte, log_details)

class BouclierDragon(Objet):
    def __init__(self):
        super().__init__("Bouclier Dragon", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.destroy()
        jet1 = random.randint(1, 6)
        jet2 = random.randint(1, 6)
        self.reduc_damage(jet1+jet2, joueur, carte, log_details)
    def rencontre_effet(self, joueur, carte, Jeu, log_details):
        if ("Dragon" in carte.types):
            self.reset_intact(log_details)

class PotionDeMana(Objet):
    def __init__(self):
        super().__init__("Potion de Mana", True)
    def survie_effet(self, joueur, carte, Jeu, log_details):
        if len(joueur.pile_monstres_vaincus):
            self.destroy()
            self.survit(1, joueur, carte, log_details)

class KebabRevigorant(Objet):
    def __init__(self):
        super().__init__("Kebab revigorant", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return joueur.tour >= 3
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.destroy()
        self.gagnePV(7, joueur, log_details)

class ArcEnflamme(Objet):
    def __init__(self):
        super().__init__("Arc enflammé", False, 7)
    def vaincu_effet(self, joueur, carte, Jeu, log_details):
        if self.intact and (carte.puissance %2 ==1):
            self.add_damage(1, joueur, carte, log_details)

class ParcheminDeTeleportation(Objet):
    def __init__(self):
        super().__init__("Parchemin de Téléportation", True)
    def vaincu_effet(self, joueur, carte, Jeu, log_details):
        if self.intact and (joueur.pv_total <= 6 and sum(objet.actif and objet.intact for objet in joueur.objets) <= 2):
            log_details.append(f"Utilisé {self.nom} pour fuir le donjon !")
            self.destroy()
            joueur.fuite()

class GrosBoulet(Objet):
    def __init__(self):
        super().__init__("Gros boulet", False, 7, -1)

class PotionFeerique(Objet):
    def __init__(self):
        super().__init__("Potion féérique", True)
    def rencontre_effet(self, joueur, carte, Jeu, log_details):
        if not self.intact and ("Fée" == carte.titre):
            self.reset_intact(log_details)
    def survie_effet(self, joueur, carte, Jeu, log_details):
        self.survit(1, joueur, carte, log_details)
        self.destroy()

class PotionDeGlace(Objet):
    def __init__(self):
        super().__init__("Potion de Glace", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.destroy()
        log_details.append(f"Utilisé {self.nom} pour fuir le réduire à 0 {carte.titre} !")
        carte.puissance = 0
        carte.dommages = 0

class PotionDraconique(Objet):
    def __init__(self):
        super().__init__("Potion draconique", True)
    def survie_effet(self, joueur, carte, Jeu, log_details):
        if ("Dragon" in carte.types):
            self.survit(9, joueur, carte, log_details)
        else:
            self.survit(1, joueur, carte, log_details)
        self.destroy()
        
class PiocheDeDiamant(Objet):
    def __init__(self):
        super().__init__("Pioche de diamant", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and carte.puissance % 2 == 1 and ("Golem" in carte.types or carte.dommages >= (joueur.pv_total / 2))
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if not ("Golem" in carte.types):
            self.destroy()
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

class TorcheRose(Objet):
    def __init__(self):
        super().__init__("Torche Rose", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Squelette" in carte.types or "Orc" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
    def score_effet(self, joueur, log_details):
        self.scoreChange(-1, joueur, log_details)

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
        return carte.dommages >= 3
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
        super().__init__("TroisPV", False, 3)
class TroisPV_(Objet):
    def __init__(self):
        super().__init__("TroisPV 2", False, 3)
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
        self.destroy()
        self.perdPV(self.pv_bonus, joueur, log_details)
        self.executeEtDefausse(joueur, carte, Jeu, log_details)

class BouclierCameleon(Objet):
    def __init__(self):
        super().__init__("Bouclier caméléon", False, 0, 0)
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
        self.destroy()
        jet_yoyo = random.randint(1, 6)
        if jet_yoyo >= 4:
            self.reset_intact(log_details)

class BouclierCasse(Objet):
    def __init__(self):
        super().__init__("Bouclier cassé", False)
    
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance >= 6
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet_bouclier = random.randint(1, 6)
        self.reduc_damage(jet_bouclier, joueur, carte, log_details)

class GlaiveDArgent(Objet):
    def __init__(self):
        super().__init__("Glaive d'argent", False)
    
    def rules(self, joueur, carte, Jeu, log_details):
        return "Vampire" in carte.types and not Jeu.traquenard_actif
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        if any("Vampire" in monstre.types for monstre in joueur.pile_monstres_vaincus):
            self.gagnePV(4, joueur, log_details)

class ChapeletDeVitalite(Objet):
    def __init__(self):
        super().__init__("Chapelet de Vitalité", False, 3)
    def debut_tour(self, joueur, Jeu, log_details):
        jet_chapelet = random.randint(1, 6)
        if jet_chapelet == 6:
            self.gagnePV(1, joueur, log_details)

class TalismanIncertain(Objet):
    def __init__(self):
        super().__init__("Talisman Incertain", False, 2)
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet_talisman = random.randint(1, 6)
        if jet_talisman == 6:
            self.execute(joueur, carte, log_details)
            
class PlanPresqueParfait(Objet):
    def __init__(self):
        super().__init__("Plan presque parfait", False, 3)
    
    def rencontre_event_effet(self, joueur, carte, Jeu, log_details):
        Jeu.execute_next_monster = True
        log_details.append(f"Effet {self.nom} actif: la prochaine carte monstre peut être exécutée. Sauf si...")

class GraalEnMousse(Objet):
    def __init__(self):
        super().__init__("Graal en Mousse", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance % 2 == 0 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
    def vaincu_effet(self, joueur, carte, Jeu, log_details):
        if len(joueur.pile_monstres_vaincus) >= 7:
            self.destroy()

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


# Liste des objets
objets_disponibles = [ 
    MainDeMidas(), 
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
    TorcheRose(),
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
]



__all__ = [
            "objets_disponibles",
            "MainDeMidas",
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
            "TorcheRose",
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
            "PatinsAGlace"
        ]