import random
import json
import numpy as np
from monstres import CarteMonstre
# Lire le fichier JSON une fois au début
with open('priorites_objets.json', 'r') as json_file:
    priorites_objets = json.load(json_file)

# Couleurs des objets (tableur, colonne Color) : 1=rouge, 2=vert, 3=bleu, 4=violet, 5=jaune
COULEUR_NOMS = {1: 'rouge', 2: 'vert', 3: 'bleu', 4: 'violet', 5: 'jaune'}

def _cle_nom(nom):
    # cle de lookup insensible a la casse et aux accents (les titres du tableur varient)
    import unicodedata
    s = unicodedata.normalize('NFD', nom)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return ''.join(c for c in s.lower() if c.isalnum())

with open('item_visuals.json', 'r', encoding='utf-8') as json_file:
    couleurs_objets = {_cle_nom(nom): data.get('color_code')
                       for nom, data in json.load(json_file).items()}

def nb_couleurs(objets, intacts_seulement=False):
    return len({o.couleur for o in objets
                if o.couleur and (o.intact or not intacts_seulement)})

class ExecutionImpossible(Exception):
    """Levee quand un objet tente d'executer une carte non executable (Troll).
    Attrapee dans Objet.en_combat : l'objet n'est pas consomme, le combat continue."""


class Objet:
    def __init__(self, nom, actif=False, pv_bonus=0, modificateur_de=0, effet=None, intact=True, types_tags=None, puissance_tags=None):
        self.nom = nom
        self.pv_bonus = pv_bonus
        self.modificateur_de = modificateur_de
        self.effet = effet
        self.intact = intact
        self.actif = actif
        self.priorite = priorites_objets.get(nom, 49.5)  # Utilise la priorité du JSON ou 0 par défaut
        self.couleur = couleurs_objets.get(_cle_nom(nom))  # 1-5 (cf. COULEUR_NOMS), None si hors tableur
        self.compteur = 0
        self.types_tags = types_tags if types_tags is not None else []
        self.puissance_tags = puissance_tags if puissance_tags is not None else []

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

    def en_rencontre(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        # attention, check si les items sont intacts
        self.rencontre_effet(joueur_proprietaire, joueur, carte, Jeu, log_details)

    def en_fuite(self, joueur, Jeu, log_details):
        # attention, check si les items sont intacts
        pass

    def en_rencontre_event(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        # attention, check si les items sont intacts
        self.rencontre_event_effet(joueur_proprietaire, joueur, carte, Jeu, log_details)    

    

    def en_combat(self, joueur, carte, Jeu, log_details):
        if self.condition(joueur, carte, Jeu, log_details):
            try:
                self.combat_effet(joueur, carte, Jeu, log_details)
            except ExecutionImpossible:
                # Troll : la carte ne peut pas etre executee, l'objet reste range
                log_details.append(f"{carte.titre} ne peut pas être exécuté : {joueur.nom} n'utilise pas {self.nom}.")

    
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
        return jet
            
    def repare(self):
        self.intact = True
        self.compteur = 0
    def destroy(self, joueur, Jeu, log_details):
        if self.intact:
            self.intact = False
            sans_hook = SANS_HOOK_OBJET['en_activated']
            for joueur_proprietaire in Jeu.joueurs:
                # comprehension = copie filtree: certains effets retirent des objets (Trou Noir Portatif)
                for objet in [o for o in joueur_proprietaire.objets if type(o) not in sans_hook]:
                    objet.en_activated(joueur_proprietaire, joueur, self, Jeu, log_details)
    
    def execute(self, joueur, carte, log_details):
        if getattr(carte, 'non_executable', False):
            raise ExecutionImpossible(carte.titre)  # Troll
        carte.executed = True
        joueur.ajouter_monstre_vaincu(carte)
        log_details.append(f"{joueur.nom} utilise {self.nom} pour exécuter {carte.titre}")

    def executeEtDefausse(self, joueur, carte, Jeu, log_details):
        if getattr(carte, 'non_executable', False):
            raise ExecutionImpossible(carte.titre)  # Troll
        carte.executed = True
        joueur.monstres_ajoutes_ce_tour += 1
        Jeu.defausse.append(carte)
        log_details.append(f"{joueur.nom} utilise {self.nom} pour exécuter et défausser {carte.titre}")

    def remetDansDonjon(self, joueur, carte, Jeu, log_details, en_bas=False, melange=False):
        # La carte quitte le combat sans etre executee: pas de combo execute,
        # pas de penalite Traquenard, et l'effet marche contre Troll.
        Jeu.carte_ignoree = True
        if en_bas:
            Jeu.donjon.rajoute_en_bas_de_la_pile(carte)
            log_details.append(f"{joueur.nom} utilise {self.nom} pour remettre {carte.titre} sous le Donjon.")
        else:
            Jeu.donjon.rajoute_en_haut_de_la_pile(carte)
            log_details.append(f"{joueur.nom} utilise {self.nom} pour remettre {carte.titre} sur le Donjon.")
        if melange:
            Jeu.donjon.remelange()
            log_details.append(f"Le Donjon est remélangé ({self.nom}).")

    def absorbe(self, joueur, carte, log_details, value=None):
        if getattr(carte, 'non_executable', False):
            raise ExecutionImpossible(carte.titre)  # Troll
        value = value or carte.puissance
        carte.executed = True
        joueur.pv_total += value  # Absorber les PV
        joueur.ajouter_monstre_vaincu(carte)
        log_details.append(f"{joueur.nom} utilise {self.nom} sur {carte.titre} pour absorber {carte.puissance} PV. Total {joueur.pv_total} PV.")

    def reduc_damage(self, value, joueur, carte, log_details):
        if value <= 0:
            return
        if getattr(carte, 'reduction_dommages_bloquee', False):
            log_details.append(f"{joueur.nom} ne peut pas réduire davantage les dommages de {carte.titre} ({self.nom}).")
            return
        dommages_reference = max(getattr(carte, 'dommages_reference', carte.dommages), carte.dommages)
        dommages_minimum = max(0, getattr(carte, 'dommages_minimum', 0))
        dommages_avant = carte.dommages
        carte.dommages = max(dommages_avant - value, dommages_minimum)
        reduction_reelle = dommages_avant - carte.dommages
        carte.dommages_reference = dommages_reference
        if reduction_reelle:
            log_details.append(f"{joueur.nom} utilise {self.nom} sur {carte.titre} pour réduire les dommages de {reduction_reelle}.")

    def add_damage(self, value, joueur, carte, log_details):
        carte.dommages = carte.dommages + value
        carte.dommages_reference = getattr(carte, 'dommages_reference', carte.dommages) + value
        log_details.append(f"{joueur.nom} utilise {self.nom} sur {carte.titre} pour augmenter les dommages de {value}.")

    def fixe_dommages_minimum(self, value, carte):
        carte.dommages_minimum = max(getattr(carte, 'dommages_minimum', 0), value)

    def bloque_reduction_dommages(self, carte):
        carte.reduction_dommages_bloquee = True

    def fixe_reduction_totale(self, value, joueur, carte, log_details):
        if value <= 0:
            return
        if getattr(carte, 'reduction_dommages_bloquee', False):
            log_details.append(f"{joueur.nom} ne peut pas réduire davantage les dommages de {carte.titre} ({self.nom}).")
            return
        dommages_reference = max(getattr(carte, 'dommages_reference', carte.dommages), carte.dommages)
        dommages_minimum = max(0, getattr(carte, 'dommages_minimum', 0))
        dommages_avant = carte.dommages
        dommages_cibles = max(dommages_reference - value, dommages_minimum)
        if dommages_cibles >= dommages_avant:
            carte.dommages_reference = dommages_reference
            return
        carte.dommages = dommages_cibles
        carte.dommages_reference = dommages_reference
        log_details.append(f"{joueur.nom} utilise {self.nom} sur {carte.titre} pour réduire les dommages de {dommages_avant - carte.dommages}.")

    def degats_apres_reduction(self, value, carte, dommages_minimum=None):
        dommages_minimum = max(
            getattr(carte, 'dommages_minimum', 0),
            0 if dommages_minimum is None else dommages_minimum,
        )
        return max(carte.dommages - value, dommages_minimum)

    def degats_apres_reduction_totale(self, value, carte, dommages_minimum=None):
        dommages_reference = max(getattr(carte, 'dommages_reference', carte.dommages), carte.dommages)
        dommages_minimum = max(
            getattr(carte, 'dommages_minimum', 0),
            0 if dommages_minimum is None else dommages_minimum,
        )
        return max(dommages_reference - value, dommages_minimum)

    def gagnePV(self, value, joueur, log_details):
        joueur.pv_total += value
        log_details.append(f"{joueur.nom} utilise {self.nom} pour gagner {value} PV. Total {joueur.pv_total} PV.")

    def perdPV(self, value, joueur, log_details):
        joueur.pv_total -= value
        log_details.append(f"{joueur.nom} utilise {self.nom} et perd {value} PV. Total {joueur.pv_total} PV.")
        if(joueur.pv_total <= 0): joueur.mort(log_details)

    def survit(self, value, joueur, carte, log_details):
        joueur.pv_total = value
        if carte not in joueur.pile_monstres_vaincus:  # deja vaincue (ex: executee plus tot dans le meme combat)
            joueur.ajouter_monstre_vaincu(carte)
        log_details.append(f"{joueur.nom} utilise {self.nom} pour survivre avec {value} PV et vaincre {carte.titre}")

    def piocheItem(self, joueur, Jeu, log_details):
        if len(Jeu.objets_dispo):
            nouvel_objet = random.choice(Jeu.objets_dispo)
            Jeu.objets_dispo.remove(nouvel_objet)
            joueur.ajouter_objet(nouvel_objet)
            log_details.append(
                f"{joueur.nom} utilise {self.nom} pour piocher un nouvel objet: "
                f"{nouvel_objet.nom}, PV bonus: {nouvel_objet.pv_bonus}, "
                f"Jet de fuite: {nouvel_objet.modificateur_de}. Nouveau PV {joueur.nom}: {joueur.pv_total} PV."
            )
            
    def scoreChange(self, value, joueur, log_details):
        if value > 0:
            log_details.append(f"{self.nom} intact, gain de {value} points de victoire qui s'ajoutent aux {joueur.score_final} points, total {joueur.score_final + value}.")
        else:
            log_details.append(f"{self.nom} intact, perte de {value} points de victoire qui se soustraient aux {joueur.score_final} points, total {joueur.score_final + value}.")
        joueur.score_final += value

# Définir les objets spécifiques
class Egide(Objet):
    def __init__(self):
        super().__init__("Egide", True)

    def survie_effet(self, joueur, carte, Jeu, log_details):
        self.survit(joueur.pv_base, joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class FleauDesLiches(Objet):
    def __init__(self):
        super().__init__("Fleau des liches", types_tags=["Liche"])
    def rules(self, joueur, carte, Jeu, log_details):
        return "Liche" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.absorbe(joueur, carte, log_details, 6)

class Katana(Objet):
    def __init__(self):
        super().__init__("Katana", puissance_tags=[8])
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance >= 7 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
    def score_effet(self, joueur, log_details):
        self.scoreChange(-1,joueur,log_details)

class HacheDeGlace(Objet):
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

class CalumetDeLaPaix(Objet):
    def __init__(self):
        super().__init__("Calumet de la Paix", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
        joueur.doit_passer = True
        log_details.append(f"{joueur.nom} doit passer son tour apres avoir utilise {self.nom}")

class MarteauDeGuerre(Objet):
    def __init__(self):
        super().__init__("Marteau de Guerre", False, 0, -1, types_tags=["Golem", "Squelette"])
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Golem" in carte.types or "Squelette" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        
class EpauletteDuPonceur(Objet):
    def __init__(self):
        super().__init__("Epaulette du Ponceur", False, 3, -2)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(1, joueur, carte, log_details)

class MainDeMidas(Objet):
    def __init__(self):
        super().__init__("Main de Midas", True, puissance_tags=[ 5])
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance == 5 and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.puissance == 5
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.absorbe(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
class MidasDeBronze(Objet):
    def __init__(self):
        super().__init__("Midas de Bronze", True, puissance_tags=[1, 2, 3, 4])
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance <= 4 and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.puissance ==4 or carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.absorbe(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
class ArmureEnCuir(Objet):
    def __init__(self):
        super().__init__("Armure en cuir", False, 5)
class CotteDeMailles(Objet):
    def __init__(self):
        super().__init__("Cotte de mailles", False, 4)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance == 0 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
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
    def worthit(self, joueur, carte, Jeu, log_details):
        if carte.dommages != 0:
            return True
        return carte.effet not in (None, "FAIRY", "MEDAIL", "ARRA")
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
        super().__init__("Bouclier Golemique", False, 3, types_tags=["Golem"])
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
        super().__init__("Bouclier Dragon", True, types_tags=["Dragon"])
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total /2
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet1 = joueur.rollDice(Jeu, log_details)
        jet2 = joueur.rollDice(Jeu, log_details)
        self.reduc_damage(jet1+jet2, joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
    def rencontre_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if ("Dragon" in carte.types) and joueur_proprietaire==joueur:
            self.repare()

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
        super().__init__("Parchemin de Téléportation", False, 2, -100)
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
        super().__init__("Potion feerique", True)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if ("Fée" == carte.titre) and not self.intact:
            log_details.append(f"{self.nom} de {joueur_proprietaire.nom} se repare.")
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
        carte.dommages = carte.dommages - carte.puissance 
        if carte.dommages < 0:
            carte.dommages = 0
        carte.puissance = 0
        self.destroy(joueur, Jeu, log_details)

class PotionDraconique(Objet):
    def __init__(self):
        super().__init__("Potion draconique", True, types_tags=["Dragon"])
    def survie_effet(self, joueur, carte, Jeu, log_details):
        if ("Dragon" in carte.types):
            self.survit(9, joueur, carte, log_details)
        else:
            self.survit(1, joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
        
class PiocheDeDiamant(Objet):
    def __init__(self):
        super().__init__("Pioche de diamant", True, types_tags=["Golem"])
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
        super().__init__("Chapeau du novice", False, types_tags=["Orc"])
        self.bonus_sans_medaille = True
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Orc" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        if joueur.medailles == 0:
            Jeu.execute_next_monster = True
            log_details.append(f"Pas de medaille, la prochaine carte monstre peut être exécutée.")

class MasqueDeLaPeste(Objet):
    def __init__(self):
        super().__init__("Masque de la Peste", False, 3, types_tags=["Rat"])
    def rules(self, joueur, carte, Jeu, log_details):
        return "Rat" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class TorcheRouge(Objet):
    def __init__(self):
        super().__init__("Torche Rouge", False, types_tags=["Gobelin", "Squelette", "Orc"])
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Gobelin" in carte.types or "Squelette" in carte.types or "Orc" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class RobeDeMage(Objet):
    def __init__(self):
        super().__init__("Robe de mage", False, types_tags=["Démon"])
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
        super().__init__("Tronconneuse Enflammee", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= 3 and joueur.pv_total > 3
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.perdPV(3, joueur, log_details)
        self.execute(joueur, carte, log_details)
        joueur.rejoue = True
    
class TuniqueClasse(Objet):
    def __init__(self):
        super().__init__("Tunique classe", False, 4, -1)
    def score_effet(self, joueur, log_details):
        self.scoreChange(1,joueur,log_details)

class AnneauDuFeu(Objet):
    def __init__(self):
        super().__init__("Anneau du Feu", False, types_tags=["Vampire"])
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and "Vampire" in carte.types
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.gagnePV(2, joueur, log_details)

class AnneauMagique(Objet):
    def __init__(self):
        super().__init__("Anneau Magique", False, puissance_tags=[1, 2])
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and (carte.puissance == 1 or carte.puissance == 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.absorbe(joueur, carte, log_details)

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
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0 and any("Golem" in monstre.types for monstre in joueur.pile_monstres_vaincus)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if any("Golem" in monstre.types for monstre in joueur.pile_monstres_vaincus):    
            self.reduc_damage(1, joueur, carte, log_details)

class CouronneDEpines(Objet):
    def __init__(self):
        super().__init__("Couronne d'épines", False)
    def worthit(self, joueur, carte, Jeu, log_details):
        if carte.dommages <= 2:
            return False
        degats_couronne = self.degats_apres_reduction(2, carte, dommages_minimum=2)
        for objet in joueur.objets:
            if objet is self or not objet.intact or objet.nom != "Scaphandre":
                continue
            if objet.rules(joueur, carte, Jeu, log_details) and objet.worthit(joueur, carte, Jeu, log_details):
                if objet.degats_apres_reduction_totale(2, carte) <= degats_couronne:
                    return False
        return True
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.fixe_dommages_minimum(2, carte)
        self.reduc_damage(2, joueur, carte, log_details)
# note: le minimum de 2 persiste jusqu'a la resolution finale des degats.

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
        super().__init__("Bouclier caméléon", False, 0, 0)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and carte.puissance >= 7
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= 2 and joueur.pv_total > 2 
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.perdPV(2, joueur, log_details)
        self.execute(joueur, carte, log_details)

class YoYoProtecteur(Objet):
    def __init__(self):
        super().__init__("Yo-yo protecteur", True, puissance_tags=[8])
    
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance % 2 == 0 and not Jeu.traquenard_actif
    
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.puissance > 2 or carte.dommages >= joueur.pv_total / 2
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        jet_yoyo = joueur.rollDice(Jeu, log_details)
        if jet_yoyo < 4 and self in joueur.objets:
            self.destroy(joueur, Jeu, log_details)
            log_details.append(f"{joueur.nom} essaie de reparer {self.nom}... raté ({jet_yoyo})!")
        else:
            log_details.append(f"{joueur.nom} essaie de reparer {self.nom}... réussi ({jet_yoyo})!")

class BouclierCasse(Objet):
    def __init__(self):
        super().__init__("Bouclier cassé", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance >= 6
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet_bouclier = joueur.rollDice(Jeu, log_details)
        self.reduc_damage(jet_bouclier, joueur, carte, log_details)

class GlaiveDArgent(Objet):
    def __init__(self):
        super().__init__("Glaive d'argent", False, types_tags=["Vampire"])
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
        super().__init__("Graal en Mousse", False, puissance_tags=[0, 2, 4, 6])
    def rules(self, joueur, carte, Jeu, log_details):
        return ((carte.puissance == 0 or carte.puissance == 2 or carte.puissance == 4 or carte.puissance == 6 ) and not Jeu.traquenard_actif)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        if len(joueur.pile_monstres_vaincus) >= 5 and self.intact:
            self.destroy(joueur, Jeu, log_details)

class ArmureDamnee(Objet):
    def __init__(self):
        super().__init__("Armure Damnée", False, 7)
    def score_effet(self, joueur, log_details):
        self.scoreChange(-1, joueur, log_details)

class AnneauDesSurmulots(Objet):
    def __init__(self):
        super().__init__("Anneau des surmulots", False, types_tags=["Rat"])
    def rules(self, joueur, carte, Jeu, log_details):
        return "Rat" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.absorbe(joueur, carte, log_details, 3)
        
class PatinsAGlace(Objet):
    def __init__(self):
        super().__init__("Patins à Glace", False, 3, 3)
    def en_fuite(self, joueur, Jeu, log_details):
        if self.intact and joueur.jet_fuite >= 7:
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
        super().__init__("Masque Dragon", True, types_tags=["Dragon"])
    
    def rules(self, joueur, carte, Jeu, log_details):
        return "Dragon" in carte.types and not Jeu.traquenard_actif
    
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        _pioche_deux_objets_garde_le_meilleur(joueur, Jeu, log_details, self.nom)
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
        super().__init__("Grimoire Inconnu", False)
    
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact:
            jet_grimoire = joueur.rollDice(Jeu, log_details, 6)
            if jet_grimoire == 6:
                self.piocheItem(joueur,Jeu,log_details)

class GantsDeCombat(Objet):
    def __init__(self):
        super().__init__("Gants de combat", True, puissance_tags=[1, 2])
    
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
        super().__init__("Champ de force en mousse", False)
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
            for j_dans_le_dj in [j for j in Jeu.joueurs if j.dans_le_dj]:            
                self.piocheItem(j_dans_le_dj, Jeu, log_details)
            self.destroy(joueur, Jeu, log_details)

class TorcheBleue(Objet):
    def __init__(self):
        super().__init__("Torche Bleue", False, puissance_tags=[1, 2])
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
        super().__init__("Anneau Plussain", False, 1, 1, puissance_tags=[1])
    def score_effet(self, joueur, log_details):
        self.scoreChange(1,joueur,log_details)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance == 1 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        
class GetasDuNovice(Objet):
    def __init__(self):
        super().__init__("Getas du novice", False, 2, 2)
        self.bonus_sans_medaille = True
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
            objets_brisés_autres_joueurs = [obj for j in Jeu.joueurs if (j != joueur and j.dans_le_dj) for obj in j.objets if not obj.intact]
            if objets_brisés_autres_joueurs:
                objet_vole = random.choice(objets_brisés_autres_joueurs)
                ancien_proprietaire = next(j for j in Jeu.joueurs if objet_vole in j.objets)
                ancien_proprietaire.objets.remove(objet_vole)
                joueur.ajouter_objet(objet_vole)
                objet_vole.repare()
                log_details.append(f"{joueur.nom} utilise {self.nom} pour voler et réparer {objet_vole.nom} de {ancien_proprietaire.nom}")
                self.destroy(joueur, Jeu, log_details)

class CoffreAnime(Objet):
    def __init__(self):
        super().__init__("Coffre animé", False, 2)

    def activated_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if self.intact:
            if joueur_proprietaire != joueur and objet in joueur.objets and not objet.intact:
                jet_de = joueur_proprietaire.rollDice(Jeu, log_details, 6)
                if jet_de == 6:
                    joueur.objets.remove(objet)
                    objet.repare()
                    joueur_proprietaire.ajouter_objet(objet)
                    log_details.append(f"{joueur_proprietaire.nom} utilise {self.nom} pour voler et réparer {objet.nom} de {joueur.nom}")
            elif joueur_proprietaire != joueur:
                log_details.append(f" {joueur_proprietaire.nom} utilise {self.nom} pour essayer de voler et réparer {objet.nom} de {joueur.nom} MAIS cela ECHOUE!")
                            
class AnneauDeVie(Objet):
    def __init__(self):
        super().__init__("Anneau de Vie", False)
    def fin_tour(self, joueur, Jeu, log_details):
        if(joueur.pv_total >= 6) and self.intact:
            self.gagnePV(1,joueur,log_details)
                

class BottesDeVitesse(Objet):
    def __init__(self):
        super().__init__("Bottes de Vitesse", False, 2)
    def _maj_bonus_fuite(self, joueur):
        self.modificateur_de = len(joueur.pile_monstres_vaincus) if self.intact else 0
    def debut_tour(self, joueur, Jeu, log_details):
        self._maj_bonus_fuite(joueur)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if joueur_proprietaire == joueur:
            self._maj_bonus_fuite(joueur)

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
        super().__init__("Feuille Eternelle", False, 0, 0, types_tags=["Démon", "Dragon"])
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and ( "Démon" in carte.types or  "Dragon" in carte.types)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= 1 and joueur.pv_total > 1 
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.perdPV(1, joueur, log_details)

class PatteDuRatLiche(Objet):
    def __init__(self):
        super().__init__("Patte du RatLiche", False, types_tags=["Rat", "Liche"])
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Rat" in carte.types or "Liche" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class LameDraconique(Objet):
    def __init__(self):
        super().__init__("Lame Draconique", False, types_tags=["Dragon"])
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0 and ("Dragon" in carte.types
                or any("Dragon" in monstre.types for monstre in joueur.pile_monstres_vaincus))
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if "Dragon" in carte.types and not Jeu.traquenard_actif:
            self.execute(joueur, carte, log_details)
        elif any("Dragon" in monstre.types for monstre in joueur.pile_monstres_vaincus):    
            self.reduc_damage(1, joueur, carte, log_details)

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
        super().__init__("Crâne du Roi Liche", False, types_tags=["Liche"])

    def rules(self, joueur, carte, Jeu, log_details):
        return "Liche" in carte.types and not Jeu.traquenard_actif

    def combat_effet(self, joueur, carte, Jeu, log_details):
        if "Liche" in carte.types:
            self.execute(joueur, carte, log_details)

    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if "Liche" in carte.types and self.intact:
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
        super().__init__("Livre Sacré", False, 2, types_tags=["Squelette"])
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and "Squelette" in carte.types
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        
class PendentifDuNovice(Objet):
    def __init__(self):
        super().__init__("Pendentif du Novice", False, 3, types_tags=["Gobelin"])
        self.bonus_sans_medaille = True
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and "Gobelin" in carte.types and not joueur.medailles
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.gagnePV(1, joueur, log_details)
      
class PistoletPirate(Objet):
    def __init__(self):
        super().__init__("Pistolet Pirate", False, puissance_tags=[2, 3])
    def rules(self, joueur, carte, Jeu, log_details):
        return (carte.puissance == 2 or carte.puissance == 3) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class ArmureArdente(Objet):
    def __init__(self):
        super().__init__("Armure Ardente", False, 4, types_tags=["Dragon"])
    def rules(self, joueur, carte, Jeu, log_details):
        return "Dragon" in carte.types
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
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
    
    def rencontre_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if not self.intact and joueur_proprietaire==joueur:
            self.perdPV(1, joueur, log_details)
            
    def rencontre_event_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if not self.intact and joueur_proprietaire==joueur:
            self.perdPV(1, joueur, log_details)
            
class CorneDAbordage(Objet):
    def __init__(self):
        super().__init__("Corne d'abordage", True)

    def _activer_corne(self, joueur, Jeu, log_details, contexte=""):
        log_details.append(f"{joueur.nom} utilise {self.nom}{' en ' + contexte if contexte else ''}")
        autres_joueurs_dans_le_dj = [autre_joueur for autre_joueur in Jeu.joueurs if autre_joueur != joueur and autre_joueur.dans_le_dj]    
        for autre_joueur in autres_joueurs_dans_le_dj:
            if autre_joueur.pile_monstres_vaincus:
                monstre_volee = random.choice(autre_joueur.pile_monstres_vaincus)
                autre_joueur.pile_monstres_vaincus.remove(monstre_volee)
                joueur.ajouter_monstre_vaincu(monstre_volee)
                log_details.append(f"{joueur.nom} utilise {self.nom} pour voler {monstre_volee.titre} de {autre_joueur.nom}{' en ' + contexte if contexte else ''}")
        self.perdPV(2, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact:
            autres_joueurs_dans_le_dj = [autre_joueur for autre_joueur in Jeu.joueurs if autre_joueur != joueur and autre_joueur.dans_le_dj]
            if all(autre_joueur.pile_monstres_vaincus for autre_joueur in autres_joueurs_dans_le_dj) and joueur.pv_total > 2:
                self._activer_corne(joueur, Jeu, log_details)

    def fuite_definitive_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur:
            if joueur.pv_total > 2:
                self._activer_corne(joueur, Jeu, log_details, contexte="fuyant")

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
            if all(len(autre_joueur.pile_monstres_vaincus) >= 2 for autre_joueur in autres_joueurs_dans_le_dj):
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
        super().__init__("Sabre mécanique", False, 0, -1, types_tags=["Gobelin", "Golem"])
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Gobelin" in carte.types or "Golem" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class CouronneEnMousse(Objet):
    def __init__(self):
        super().__init__("Couronne en Mousse", False)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(2, joueur, carte, log_details)    
        if len(joueur.pile_monstres_vaincus) >= 5 and self.intact:
            self.destroy(joueur, Jeu, log_details)

class KatanaEnMousse(Objet):
    def __init__(self):
        super().__init__("Katana en Mousse", False, puissance_tags=[7, 8, 9, 10])
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance >= 7 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        if len(joueur.pile_monstres_vaincus) >= 5 and self.intact:
            self.destroy(joueur, Jeu, log_details)

class MarteauFlamboyant(Objet):
    def __init__(self):
        super().__init__("Marteau flamboyant", False, types_tags=["Golem", "Dragon"])
    def rules(self, joueur, carte, Jeu, log_details):
        return "Golem" in carte.types or "Dragon" in carte.types
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(4, joueur, carte, log_details)

class TreizeASeize(Objet):
    def __init__(self):
        super().__init__("Treize à Seize", False, puissance_tags=[1, 3, 6])
    def rules(self, joueur, carte, Jeu, log_details):
        if any("Dragon" in monstre.types for monstre in joueur.pile_monstres_vaincus):
            return (carte.puissance == 1 or carte.puissance == 6) and not Jeu.traquenard_actif
        return (carte.puissance == 1 or carte.puissance == 3) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class Scaphandre(Objet):
    def __init__(self):
        super().__init__("Scaphandre", False, 0, -3)
    def rules(self, joueur, carte, Jeu, log_details):
        return getattr(carte, 'dommages_reference', carte.dommages) >= carte.puissance
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.fixe_reduction_totale(2, joueur, carte, log_details)
        self.bloque_reduction_dommages(carte)
# note: verrouille toute reduction supplementaire sur ce combat.

class AnneauDeGlace(Objet):
    def __init__(self):
        super().__init__("Anneau de glace", False, 0)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if "Squelette" in carte.types:
            self.execute(joueur, carte, log_details)
        else:
            self.reduc_damage(1, joueur, carte, log_details)

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
        super().__init__("Anneau Oceanique", False, puissance_tags=[8, 9, 10])
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
        super().__init__("Coiffe de sorcier", False, types_tags=["Gobelin", "Vampire"])
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Gobelin" in carte.types or "Vampire" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class ArmureDuRoiLiche(Objet):
    def __init__(self):
        super().__init__("Armure du Roi Liche", False, 3, types_tags=["Liche"])
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
        if self.intact and ((jet < jet_voulu and not reversed) or (jet > jet_voulu and reversed)):
            self.gagnePV(3, joueur, log_details)
            self.destroy(joueur, Jeu, log_details)
            return 1 if reversed else 6


class ChapeauStyle(Objet):
    def __init__(self):
        super().__init__("Chapeau stylé", False, 3)
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
    def rencontre_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if not self.intact and "Dragon" in carte.types and joueur_proprietaire==joueur:
            log_details.append(f"{self.nom} de {joueur_proprietaire.nom} se repare.")
            self.repare()
            
class CasqueACornes(Objet):
    def __init__(self):
        super().__init__("Casque à cornes", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and self.compteur <= 2
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.compteur += 1
        # self.execute(joueur, carte, log_details)
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        log_details.append(f"Le Casque à cornes fait bing, utilisations: {self.compteur}")
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.compteur >= 2 and self.intact and joueur_proprietaire.dans_le_dj and joueur_proprietaire == joueur:
            log_details.append(f"Le Casque à cornes est detruit.")
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
            for objet in list(joueur.objets):  # copie: on retire des objets de la liste pendant l'iteration
                if objet.intact:
                    jet = joueur_proprietaire.rollDice(Jeu, log_details, 6)
                    if jet == 6:
                        log_details.append(f"{joueur_proprietaire.nom} récupère {objet.nom} de {joueur.nom} grâce à {self.nom}.")
                        joueur.objets.remove(objet)
                        joueur_proprietaire.ajouter_objet(objet)

class CoeurDeDragon(Objet):
    def __init__(self):
        super().__init__("Cœur de Dragon", False, types_tags=["Dragon"])
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if "Dragon" in carte.types and self.intact:
            self.gagnePV(4, joueur_proprietaire, log_details)

class ShotDAdrenaline(Objet):
    def __init__(self):
        super().__init__("Shot d'adrénaline", True)
    def shotDAdrenaline(self, joueur, Jeu, log_details):
        if self.intact:
            if joueur.pv_total == 1:
                self.gagnePV(10, joueur, log_details)
            else:
                self.gagnePV(2, joueur, log_details)
            self.destroy(joueur, Jeu, log_details)

    def debut_tour(self, joueur, Jeu, log_details):
        if joueur.pv_total == 1:
            self.shotDAdrenaline(joueur, Jeu, log_details)

    def combat_effet(self, joueur, carte, Jeu, log_details):
        if (joueur.pv_total <= carte.dommages and joueur.pv_total+2 > carte.dommages)  or joueur.pv_total == 1:
            self.shotDAdrenaline(joueur, Jeu, log_details)

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
        super().__init__("Marteau de combat", False, types_tags=["Golem"])
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
        return carte.puissance % 2 == 0
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
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
        super().__init__("Pare-Buffle du Ponceur", False, 0, 0)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance >= 6
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
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
            if dernier_monstre.puissance > 0:
                self.utiliser(dernier_monstre, joueur, Jeu, log_details)

class MailletDArgile(Objet):
    def __init__(self):
        super().__init__("Maillet D'Argile", False, 2, types_tags=["Golem"])
    def rules(self, joueur, carte, Jeu, log_details):
        return "Golem" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)

class AllianceSanguine(Objet):
    def __init__(self):
        super().__init__("Alliance Sanguine", False, 2)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if joueur.pv_total <= 4:
            self.reduc_damage(2, joueur, carte, log_details)

class FauxDeLaMort(Objet):
    def __init__(self):
        super().__init__("Faux De La Mort", False, 3)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance == joueur.pv_total and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class QueueDuCharognard(Objet):
    def __init__(self):
        super().__init__("Queue Du Charognard", False, 2)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance == len(joueur.pile_monstres_vaincus) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class CasqueBerserk(Objet):
    def __init__(self):
        super().__init__("CasqueBerserk", False, 7)
    def subit_dommages_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur and carte.puissance <= 2 and carte.dommages > 0:
            self.perdPV(1, joueur, log_details)
        
# 2025

class TentaculeDuKraken(Objet):
    def __init__(self):
        super().__init__("Tentacule du Kraken", True, puissance_tags=[ 8, 10])
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance % 2 == 0 
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(carte.puissance, joueur, log_details)
        self.remetDansDonjon(joueur, carte, Jeu, log_details, melange=True)
        self.destroy(joueur, Jeu, log_details)

class GrenadeSinge(Objet):
    def __init__(self):
        super().__init__("Grenade Singe", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.remetDansDonjon(joueur, carte, Jeu, log_details, melange=True)
        self.destroy(joueur, Jeu, log_details)

class SceptreChangeur(Objet):
    def __init__(self):
        super().__init__("Sceptre Changeur", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return (not Jeu.traquenard_actif
                and any(isinstance(Jeu.donjon.cartes[idx], CarteMonstre)
                        for idx in Jeu.donjon.ordre[Jeu.donjon.index:]))
    def worthit(self, joueur, carte, Jeu, log_details):
        return _choisir_cible_sceptre_changeur(joueur, carte, Jeu) is not None
    def combat_effet(self, joueur, carte, Jeu, log_details):
        cible = _choisir_cible_sceptre_changeur(joueur, carte, Jeu)
        if cible is None:
            return
        Jeu.defausse.append(carte)
        _retire_du_donjon_et_melange(Jeu, cible)
        Jeu.carte_forcee = cible
        log_details.append(
            f"{joueur.nom} utilise {self.nom} : {carte.titre} est défaussé, "
            f"puis {cible.titre} est choisi dans le Donjon pour être combattu à la place."
        )
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
        return carte.dommages >= joueur.pv_total and not getattr(carte, 'non_executable', False)
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
        if self.intact and joueur_proprietaire == joueur and joueur.rollDice(Jeu, log_details, 6) == 6:
            objet.repare()
            log_details.append(f"{self.nom} répare {objet.nom} automatiquement.")

class AttrapeReves(Objet):
    def __init__(self):
        super().__init__("Attrape-Rêves", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and not carte.types
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class DeMaudit(Objet):
    def __init__(self):
        super().__init__("Dé Maudit", False, 2)
    def rules(self, joueur, carte, Jeu, log_details):
        return 1 <= carte.puissance <= 6 and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet = joueur.rollDice(Jeu, log_details, carte.puissance)
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
        monstres_defausse = [c for c in Jeu.defausse if hasattr(c, 'types') and not getattr(c, 'event', False)]
        log_details.append(f"{joueur.nom} utilise {self.nom}")

        golem_or_dispo = []
        dragons_dispo = []
        autres_dispo = []
        for monstre in monstres_defausse:
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
        noms_choisis = [m.titre for m in monstres_choisis]
        log_details.append(f"--> Récupère {len(monstres_choisis)} monstres (priorité GolemOr>Dragon>Autre): {noms_choisis}")

        # Remove from discard
        ids_choisis = {id(m) for m in monstres_choisis}
        Jeu.defausse = [c for c in Jeu.defausse if id(c) not in ids_choisis]

        for monstre in monstres_choisis:
            joueur.ajouter_monstre_vaincu(monstre)
        self.destroy(joueur, Jeu, log_details)

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
        self.absorbe(joueur, carte, log_details, 3)

class HarpeCinglante(Objet):
    def __init__(self):
        super().__init__("Harpe Cinglante", False, 0, 0)
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
        return len(joueur.pile_monstres_vaincus) >= 7
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(1, joueur, carte, log_details)        

class ViandeCrue(Objet):
    def __init__(self):
        super().__init__("Viande Crue", True)
   
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total <= carte.dommages or any("Dragon" in monstre.types for monstre in joueur.pile_monstres_vaincus)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if any("Dragon" in monstre.types for monstre in joueur.pile_monstres_vaincus):    
            self.gagnePV(8, joueur, log_details)
        else:
            self.gagnePV(3, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)    

class MailletDuRoiLiche(Objet):
    def __init__(self):
        super().__init__("Maillet Du Roi Liche", True, types_tags=["Golem", "Liche", "Démon"])
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and ("Golem" in carte.types or "Liche" in carte.types or "Démon" in carte.types)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.gagnePV(3, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)    

class CouteauEntreLesDents(Objet):
    def __init__(self):
        super().__init__("Couteau Entre Les Dents", False, types_tags=["Vampire", "Orc"])
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Vampire" in carte.types or "Orc" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        if ("Vampire" in carte.types):
            self.perdPV(1, joueur, log_details)
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
            for j_dans_le_dj in [j for j in Jeu.joueurs if j.dans_le_dj]:
                for card in j_dans_le_dj.pile_monstres_vaincus[:]:
                    if hasattr(card, 'types') and ("Démon" in card.types or "Dragon" in card.types):
                        demons_dragons.append(card)
                        j_dans_le_dj.pile_monstres_vaincus.remove(card)
            
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
        super().__init__("Pierre du Naga", False, 1)  # False pour actif = non, et 2 pour le bonus de PV initial
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if carte.puissance >= 7:
            log_details.append(f"{self.nom} de {joueur_proprietaire.nom} se declenche car {joueur.nom} a vaincu un monstre de puissance 7 ou plus.")
            self.gagnePV(1, joueur_proprietaire, log_details)

class CapeDePlumes(Objet):
    def __init__(self):
        super().__init__("Cape de Plumes", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(8, joueur, carte, log_details)     
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
        if(joueur_proprietaire.dans_le_dj):
            self.gagnePV(1, joueur_proprietaire, log_details)

class FruitDuDestin(Objet):
    def __init__(self):
        super().__init__("Fruit du Destin", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        monsters = [c for c in Jeu.defausse if hasattr(c, 'types') and not getattr(c, 'event', False)]
        events = [c for c in Jeu.defausse if getattr(c, 'event', False)]
        return carte.dommages >= joueur.pv_total and (monsters or events) 
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

class ParcheminDePoncage(Objet):
    def __init__(self):
        super().__init__("Parchemin de poncage", True, 1)
    
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
        super().__init__("Araignée domestique", False, 0, -1)
        self.deja_vole_sur_mort = False
        self.deja_vole_sur_fuite = False
    def repare(self):
        super().repare()
        self.deja_vole_sur_mort = False
        self.deja_vole_sur_fuite = False
    def steal_monsters(self, owner, target, log_details):
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
    def en_mort(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if (self.intact and not self.deja_vole_sur_mort
                and joueur != joueur_proprietaire and joueur_proprietaire.dans_le_dj):
            self.deja_vole_sur_mort = True
            self.steal_monsters(joueur_proprietaire, joueur, log_details)
    
    def en_fuite_definitive(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if (self.intact and not self.deja_vole_sur_fuite
                and joueur != joueur_proprietaire and joueur_proprietaire.dans_le_dj):
            self.deja_vole_sur_fuite = True
            self.steal_monsters(joueur_proprietaire, joueur, log_details)


class Exterminator(Objet):
    def __init__(self):
        super().__init__("Exterminator", False, 0, -2, types_tags=["Dragon", "Rat"])
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Dragon" in carte.types or "Rat" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class CodexDiabolus(Objet):
    def __init__(self):
        super().__init__("Codex Diabolus", False, 0, 0, types_tags=["Démon"])
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Démon" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
    def rencontre_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if "Démon" in carte.types and joueur_proprietaire.dans_le_dj and joueur_proprietaire != joueur:
            dommages_suppl = 3
            carte.dommages+=dommages_suppl
            log_details.append(f"{carte.titre} est booste de {dommages_suppl} dommages (total {carte.dommages}) par {joueur_proprietaire.nom} ({self.nom})")

class SainteLance(Objet):
    def __init__(self):
        super().__init__("Sainte Lance", False, 0, 0, puissance_tags=[6, 8, 10])
    def rules(self, joueur, carte, Jeu, log_details):
        return (carte.puissance == 6 or carte.puissance == 8 or carte.puissance == 10) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        
class AspisHeracles(Objet):
    def __init__(self):
        super().__init__("Aspis d'Héraclès", True, puissance_tags=[8,])

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
            random.shuffle(monstres_a_remettre)
            for monstre in monstres_a_remettre:
                Jeu.donjon.rajoute_en_haut_de_la_pile(monstre)
        else:
            log_details.append(f"{joueur.nom} utilise {self.nom}, mais la défausse ne contient aucun monstre.")
        self.destroy(joueur, Jeu, log_details)       
         
class SacDeConstantinople(Objet):
    non_combattant = True  # utile seulement s'il y a des Dragons a voler: ne retarde pas la fuite

    def __init__(self):
        super().__init__("Sac de Constantinople", True)

    def _dragons_volables(self, joueur, Jeu):
        chez_les_autres = sum(
            1 for j in Jeu.joueurs if j is not joueur and j.dans_le_dj
            for monstre in j.pile_monstres_vaincus
            if any("Dragon" in type_carte for type_carte in monstre.types)
        )
        en_defausse = sum(1 for c in Jeu.defausse
                          if "Dragon" in getattr(c, 'types', []) and not getattr(c, 'event', False))
        return chez_les_autres + en_defausse

    def _activer_sac(self, joueur, Jeu, log_details, contexte=""):
        log_details.append(f"{joueur.nom} utilise {self.nom}{' en ' + contexte if contexte else ''}")
        
        # Voler un dragon chez chaque autre joueur
        for autre_joueur in [j for j in Jeu.joueurs if j != joueur and j.dans_le_dj]:
            dragons = [monstre for monstre in autre_joueur.pile_monstres_vaincus 
                       if any("Dragon" in type_carte for type_carte in monstre.types)]
            if dragons:
                monstre_volee = random.choice(dragons)
                autre_joueur.pile_monstres_vaincus.remove(monstre_volee)
                joueur.ajouter_monstre_vaincu(monstre_volee)
                log_details.append(f"{joueur.nom} vole {monstre_volee.titre} (Dragon) de {autre_joueur.nom}{' en ' + contexte if contexte else ''}")
        
        # Récupérer tous les dragons de la défausse
        monstres_defausse = [c for c in Jeu.defausse if hasattr(c, 'types') and not getattr(c, 'event', False)]
        dragons_defausse = [monstre for monstre in monstres_defausse if "Dragon" in getattr(monstre, 'types', [])]
        for dragon in dragons_defausse:
            Jeu.defausse.remove(dragon)
            joueur.ajouter_monstre_vaincu(dragon)
            log_details.append(f"{joueur.nom} récupère {dragon.titre} (Dragon) de la défausse")

        # "gagnez autant de PV que vous avez de Dragons dans votre pile"
        dragons_en_pile = sum(1 for m in joueur.pile_monstres_vaincus
                              if any("Dragon" in t for t in m.types))
        if dragons_en_pile:
            self.gagnePV(dragons_en_pile, joueur, log_details)

        self.destroy(joueur, Jeu, log_details)

    def debut_tour(self, joueur, Jeu, log_details):
        # Activation seulement s'il y a au moins 2 dragons a recuperer (autres joueurs + defausse)
        if self.intact and self._dragons_volables(joueur, Jeu) >= 2:
            self._activer_sac(joueur, Jeu, log_details)

    def worthit(self, joueur, carte, Jeu, log_details):
        # en urgence: les PV gagnes (dragons voles + deja en pile) peuvent sauver
        return carte.dommages >= joueur.pv_total and (
            self._dragons_volables(joueur, Jeu) > 0
            or any("Dragon" in t for m in joueur.pile_monstres_vaincus for t in m.types))

    def combat_effet(self, joueur, carte, Jeu, log_details):
        self._activer_sac(joueur, Jeu, log_details, contexte="urgence")

    def fuite_definitive_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur:
            # Pour fuite, on peut déclencher indépendamment du nombre de dragons chez les autres joueurs
            autres_joueurs = [j for j in Jeu.joueurs if j != joueur and j.dans_le_dj]
            if any(any("Dragon" in type_carte for type_carte in monstre.types)
                   for j in autres_joueurs 
                   for monstre in j.pile_monstres_vaincus) or \
               any("Dragon" in getattr(monstre, 'types', []) for monstre in Jeu.defausse if hasattr(monstre, 'types')):
                self._activer_sac(joueur, Jeu, log_details, contexte="fuyant")

class ConcentreDeFun(Objet):
    def __init__(self):
        super().__init__("Concentré de fun", True)

    def survie_effet(self, joueur, carte, Jeu, log_details):
        self.survit(2, joueur, carte, log_details)

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

class ForgePortative(Objet):
    def __init__(self):
        super().__init__("Forge Portative", False)

    def activated_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if self.intact:
            if objet in joueur.objets and not objet.intact:
                self.gagnePV(1, joueur_proprietaire, log_details)

class TrouNoirPortatif(Objet):
    def __init__(self):
        super().__init__("Trou Noir Portatif", False, 6)

    def activated_effet(self, joueur_proprietaire, joueur, objet, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur:
            for obj in joueur.objets:
                if obj.nom == objet.nom:
                    log_details.append(f"{objet.nom} est defaussé par {self.nom} !")
                    joueur.objets.remove(obj)
                    break

class Zulfikar(Objet):
    def __init__(self):
        super().__init__("Zulfikar", False, 0, 0, types_tags=["Vampire", "Liche"])
    def rules(self, joueur, carte, Jeu, log_details):
        return ("Vampire" in carte.types or "Liche" in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        jet = joueur.rollDice(Jeu, log_details, 5)
        if jet >= 5:
            self.execute(joueur, carte, log_details)
        else:
            self.executeEtDefausse(joueur, carte, Jeu, log_details)

# (Bonne vieille guinze: supprimee du jeu, barree dans le tableur)

# =============================================================================
# Objets ajoutes depuis le tableur (synchro juin 2026)
# Les objets non simulables sont listes dans ITEMS_A_REVOIR.md
# =============================================================================

def _peek_prochaine_carte(Jeu):
    # regarde la prochaine carte du Donjon sans la piocher
    donjon = Jeu.donjon
    if donjon.vide:
        return None
    return donjon.cartes[donjon.ordre[donjon.index]]

def _defausse_monstre_de_pile(joueur, Jeu, log_details, plus_puissant=False):
    # defausse un monstre de la pile du joueur (jamais le Golem d'or)
    candidats = [m for m in joueur.pile_monstres_vaincus if not (m.effet and "GOLD" in m.effet)]
    if not candidats:
        return None
    cle = lambda m: 0 if m.is_X else m.puissance
    monstre = max(candidats, key=cle) if plus_puissant else min(candidats, key=cle)
    joueur.pile_monstres_vaincus.remove(monstre)
    Jeu.defausse.append(monstre)
    return monstre

def _choisir_objet_a_sacrifier(joueur, exclus):
    # objet intact le moins precieux, sans tuer le joueur en perdant ses PV bonus
    candidats = [o for o in joueur.objets if o.intact and o not in exclus and o.pv_bonus < joueur.pv_total]
    if not candidats:
        return None
    return min(candidats, key=lambda o: (o.pv_bonus, o.priorite))


def _valeur_objet_sacrifie_comme_limon(joueur, objet, Jeu):
    # Meme heuristique que Joueur.decideBriseObjet / Limon glouton:
    # un objet de ligne perd de la valeur si ses cibles ont presque disparu.
    if not (objet.types_tags or objet.puissance_tags):
        return objet.priorite
    donjon = Jeu.donjon
    restants = [donjon.cartes[i] for i in donjon.ordre[donjon.index:]]
    cibles = sum(
        1
        for carte in restants
        if any(t in getattr(carte, 'types_initiaux', ()) for t in objet.types_tags)
        or getattr(carte, 'puissance_initiale', None) in objet.puissance_tags
    )
    return objet.priorite * cibles / (1 + cibles)


def _choisir_objet_a_sacrifier_comme_limon(joueur, Jeu, exclus):
    # Meme ordre de preference que le Limon glouton, mais on n'autorise pas
    # un sacrifice qui tuerait le joueur avant la resolution de l'objet.
    candidats = [o for o in joueur.objets if o.intact and o not in exclus and o.pv_bonus < joueur.pv_total]
    if not candidats:
        return None
    return min(candidats, key=lambda o: _valeur_objet_sacrifie_comme_limon(joueur, o, Jeu))


def _pioche_deux_objets_garde_le_meilleur(joueur, Jeu, log_details, source):
    if len(Jeu.objets_dispo) >= 2:
        choix = random.sample(Jeu.objets_dispo, 2)
        garde = max(choix, key=lambda o: o.priorite)
        jete = choix[0] if garde is choix[1] else choix[1]
        Jeu.objets_dispo.remove(garde)
        Jeu.objets_dispo.remove(jete)
        joueur.ajouter_objet(garde)
        log_details.append(f"{joueur.nom} utilise {source} pour piocher 2 objets, garde {garde.nom} et défausse {jete.nom}.")
    elif len(Jeu.objets_dispo):
        nouvel_objet = random.choice(Jeu.objets_dispo)
        Jeu.objets_dispo.remove(nouvel_objet)
        joueur.ajouter_objet(nouvel_objet)
        log_details.append(f"{joueur.nom} utilise {source} pour piocher un nouvel objet: {nouvel_objet.nom}.")

def _execute_carte_suivante(objet, joueur, suivante, Jeu, log_details):
    # consomme la carte regardee sur le Donjon et l'ajoute executee a la pile
    if getattr(suivante, 'non_executable', False):
        log_details.append(f"{suivante.titre} ne peut pas être exécuté : {objet.nom} le laisse sur le Donjon.")
        return
    Jeu.donjon.prochaine_carte()
    suivante.executed = True
    suivante.puissance = suivante.puissance_initiale
    suivante.types = list(suivante.types_initiaux)
    joueur.ajouter_monstre_vaincu(suivante)
    log_details.append(f"{joueur.nom} utilise {objet.nom} pour exécuter aussi {suivante.titre}.")

def _repare_un_objet(joueur, exclus, log_details, source):
    brises = [o for o in joueur.objets if not o.intact and o not in exclus]
    if not brises:
        return None
    objet_repare = max(brises, key=lambda o: o.pv_bonus)
    objet_repare.repare()
    if objet_repare.pv_bonus:
        joueur.pv_total += objet_repare.pv_bonus
    log_details.append(f"{joueur.nom} répare {objet_repare.nom} ({source}).")
    return objet_repare


def _estime_puissance_sceptre_changeur(carte, joueur, Jeu):
    if getattr(carte, 'event', False):
        return float('inf')
    effet = getattr(carte, 'effet', None)
    if effet == "SLEEPING":
        return 4.5
    if effet == "MIMIC":
        return sum(1 for objet in joueur.objets if objet.intact)
    if effet == "MONKEY_TEAM":
        return 2 * sum(1 for j in Jeu.joueurs if j.dans_le_dj)
    if effet == "REAPER":
        return joueur.pv_total // 2
    if effet == "MEDAIL":
        return sum(j.medailles for j in Jeu.joueurs)
    if effet == "SCAVENGER":
        return len(joueur.pile_monstres_vaincus)
    if effet == "MIROIR":
        return joueur.pile_monstres_vaincus[-1].puissance if joueur.pile_monstres_vaincus else 0
    if effet == "TROLL":
        return joueur.pile_monstres_vaincus[0].puissance if joueur.pile_monstres_vaincus else 0
    if getattr(carte, 'is_X', False):
        return 10
    return carte.puissance_initiale


def _a_ligne_ange_gardien(joueur):
    for objet in joueur.objets:
        if not objet.intact:
            continue
        if 8 in getattr(objet, 'puissance_tags', ()):
            return True
        if objet.nom == "Attrape-Rêves":
            return True
    return False


def _a_ligne_absorption(objet, joueur, carte, Jeu):
    if not objet.intact:
        return False
    if 'absorbe' not in type(objet).combat_effet.__code__.co_names:
        return False
    try:
        return objet.rules(joueur, carte, Jeu, [])
    except Exception:
        return False


def _score_sceptre_changeur(carte, joueur, Jeu):
    # Heuristique IA, pas regle brute: ordre de priorite pour choisir la cible
    # quand l'objet permet de choisir n'importe quel monstre du Donjon.
    puissance = _estime_puissance_sceptre_changeur(carte, joueur, Jeu)
    if carte.effet == "GUARDIAN_ANGEL" and _a_ligne_ange_gardien(joueur):
        return (0, 0, carte.titre)
    if any(_a_ligne_absorption(objet, joueur, carte, Jeu) for objet in joueur.objets):
        return (1, -puissance, carte.titre)
    if carte.titre == "Fée":
        return (2, 0, carte.titre)
    if joueur.peut_executer_facilement(carte):
        return (3, puissance, carte.titre)
    return (4, puissance, carte.titre)


def _choisir_cible_sceptre_changeur(joueur, carte_courante, Jeu):
    donjon = Jeu.donjon
    restants = [
        donjon.cartes[idx]
        for idx in donjon.ordre[donjon.index:]
        if isinstance(donjon.cartes[idx], CarteMonstre)
    ]
    if not restants:
        return None
    meilleure = min(restants, key=lambda c: _score_sceptre_changeur(c, joueur, Jeu))
    if _score_sceptre_changeur(meilleure, joueur, Jeu) < _score_sceptre_changeur(carte_courante, joueur, Jeu):
        return meilleure
    return None


def _retire_du_donjon_et_melange(Jeu, carte):
    donjon = Jeu.donjon
    prefixe = donjon.ordre[:donjon.index]
    suffixe = [idx for idx in donjon.ordre[donjon.index:] if idx != carte.index]
    suffixe = np.random.permutation(np.array(suffixe, dtype=donjon.ordre.dtype))
    donjon.ordre = np.concatenate((prefixe, suffixe))
    donjon.nb_cartes = len(donjon.ordre)


def _couverture_sans_objet(joueur, objet_exclu):
    types_couverts = set()
    puissances_couvertes = set()
    for objet in joueur.objets:
        if objet is objet_exclu or not objet.intact:
            continue
        types_couverts.update(getattr(objet, 'types_tags', ()))
        puissances_couvertes.update(getattr(objet, 'puissance_tags', ()))
    return types_couverts, puissances_couvertes


def _choisir_puissance_epee_vengeresse(joueur, Jeu, objet_exclu):
    # Heuristique IA, pas regle: choisit une ligne "rentable" non deja couverte
    # par le reste de la main, au lieu d'un vrai choix intelligent de long terme.
    _, puissances_couvertes = _couverture_sans_objet(joueur, objet_exclu)
    scores = {}
    comptes = {}
    for carte in Jeu.donjon.cartes:
        if not isinstance(carte, CarteMonstre) or carte.is_X:
            continue
        p = carte.puissance_initiale
        scores[p] = scores.get(p, 0) + joueur._degats_attendus(carte, Jeu)
        comptes[p] = comptes.get(p, 0) + 1
    if not scores:
        return 5
    candidates = [p for p in scores if p not in puissances_couvertes] or list(scores)
    return max(candidates, key=lambda p: (scores[p], p, comptes[p]))


def _choisir_type_dague_vengeresse(joueur, Jeu, objet_exclu):
    # Heuristique IA, pas regle: meme idee que l'Epee vengeresse mais par type.
    types_couverts, _ = _couverture_sans_objet(joueur, objet_exclu)
    scores = {}
    comptes = {}
    for carte in Jeu.donjon.cartes:
        if not isinstance(carte, CarteMonstre):
            continue
        danger = joueur._degats_attendus(carte, Jeu)
        for t in carte.types_initiaux:
            scores[t] = scores.get(t, 0) + danger
            comptes[t] = comptes.get(t, 0) + 1
    if not scores:
        return "Golem"
    candidates = [t for t in scores if t not in types_couverts] or list(scores)
    return max(candidates, key=lambda t: (scores[t], comptes[t], t == "Golem", t))

# --- 1ere edition ---

class CoeurDeTarasque(Objet):
    def __init__(self):
        super().__init__("Coeur de Tarasque", False, 3)
        self.objectif_multi_kill = 2  # l'IA repioche pour atteindre 2 monstres dans le tour
    def fin_tour(self, joueur, Jeu, log_details):
        if self.intact and joueur.monstres_ajoutes_ce_tour >= 2:
            self.gagnePV(1, joueur, log_details)

class CeintureDuPonceur(Objet):
    def __init__(self):
        super().__init__("Ceinture du Ponceur", False, 12)
        self.bloque_fuite_pv_bas = True  # consulte par Joueur.deciderDeFuir: fuite interdite sous 6 PV
        self.malus_pv_decision_fuite = 6  # l'IA anticipe: elle evalue la fuite comme si elle avait 6 PV de moins

class LinceulDeResurrection(Objet):
    def __init__(self):
        super().__init__("Linceul de Résurrection", True)
    def survie_effet(self, joueur, carte, Jeu, log_details):
        if _defausse_monstre_de_pile(joueur, Jeu, log_details):
            self.survit(joueur.pv_base, joueur, carte, log_details)
            self.destroy(joueur, Jeu, log_details)

class Imprimante(Objet):
    def __init__(self):
        super().__init__("Imprimante", False)
    def debut_tour(self, joueur, Jeu, log_details):
        # avant d'entrer dans le Donjon: devient la copie d'un autre objet (IA: le plus prioritaire)
        # garde-fous: elle peut avoir ete brisee ou defaussee (Gants de Gaia...) avant son premier tour
        if self.compteur or not self.intact or self not in joueur.objets:
            return
        self.compteur = 1
        autres = [o for o in joueur.objets if o is not self and o.intact and type(o) is not Imprimante]
        if not autres:
            return
        modele = max(autres, key=lambda o: o.priorite)
        copie = type(modele)()
        joueur.objets.remove(self)
        joueur.ajouter_objet(copie)
        log_details.append(f"L'Imprimante de {joueur.nom} devient une copie de {modele.nom}.")

class EpeeVengeresse(Objet):
    def __init__(self):
        super().__init__("Epée vengeresse", False, puissance_tags=[5])
    def debut_partie(self, joueur, Jeu, log_details):
        puissance = _choisir_puissance_epee_vengeresse(joueur, Jeu, self)
        self.puissance_tags = [puissance]
        log_details.append(f"{joueur.nom} prépare {self.nom} sur la puissance {puissance}.")
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance in self.puissance_tags and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class DagueVengeresse(Objet):
    def __init__(self):
        super().__init__("Dague vengeresse", False, types_tags=["Golem"])
    def debut_partie(self, joueur, Jeu, log_details):
        monster_type = _choisir_type_dague_vengeresse(joueur, Jeu, self)
        self.types_tags = [monster_type]
        log_details.append(f"{joueur.nom} prépare {self.nom} sur le type {monster_type}.")
    def rules(self, joueur, carte, Jeu, log_details):
        return any(t in self.types_tags for t in carte.types) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class TotemDImmunite(Objet):
    def __init__(self):
        super().__init__("Totem d'immunité", True)
        self.protege_medailles = True  # consulte par Joueur.mort
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        # garder le totem intact protege la Medaille: ne l'utiliser que si necessaire
        return carte.dommages >= joueur.pv_total or (carte.dommages > (joueur.pv_total / 2) and not joueur.medailles)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)

class CeintureDuNovice(Objet):
    def __init__(self):
        super().__init__("Ceinture du novice", False, 3)
        self.bonus_sans_medaille = True
    def debut_partie(self, joueur, Jeu, log_details):
        if joueur.medailles == 0:
            self.gagnePV(3, joueur, log_details)

class AnneauDuNovice(Objet):
    def __init__(self):
        super().__init__("Anneau du novice", True)
        self.bonus_sans_medaille = True
    def survie_effet(self, joueur, carte, Jeu, log_details):
        self.survit(joueur.pv_base if joueur.medailles == 0 else 1, joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class CapeDuNovice(Objet):
    def __init__(self):
        super().__init__("Cape du novice", True)
        self.bonus_sans_medaille = True
    def rules(self, joueur, carte, Jeu, log_details):
        return (carte.puissance % 2 == 1 or joueur.medailles == 0) and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class CoupeDesChampions(Objet):
    def __init__(self):
        super().__init__("Coupe des champions", False, 1)
        # lu par party.py a l'attribution de la Medaille de la manche (2 au lieu de 1)
        self.medailles_victoire = 2

class ParfumDeScandale(Objet):
    def __init__(self):
        super().__init__("Parfum de Scandale", False)
        self.vole_medailles_perdues = True  # consulte par Joueur.perdre_medaille
    def score_effet(self, joueur, log_details):
        self.scoreChange(1, joueur, log_details)

class ParcheminDXP(Objet):
    # "Votre héros passe (ou reste) niveau 2. Gagnez autant de PV que vos PV de héros."
    def __init__(self):
        super().__init__("Parchemin d'XP", True)
    def debut_tour(self, joueur, Jeu, log_details):
        # IA: la capacite N2 rapporte d'autant plus qu'elle arrive tot, et le soin
        # ne se perime pas -> upgrade immediat si le heros est encore niveau 1
        if self.intact and getattr(joueur.perso_obj, 'level', 1) == 1:
            self._utiliser(joueur, Jeu, log_details)
    def worthit(self, joueur, carte, Jeu, log_details):
        # heros deja N2 : garde comme soin d'urgence
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self._utiliser(joueur, Jeu, log_details)
    def _utiliser(self, joueur, Jeu, log_details):
        joueur.changer_niveau_perso(2, log_details)
        self.gagnePV(joueur.pv_base, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

class PotionDeJouvence(Objet):
    # "Votre héros passe (ou reste) niveau 1. Gagnez deux fois vos PV de héros."
    def __init__(self):
        super().__init__("Potion de Jouvence", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        # N1 : pur soin sans inconvenient, s'utilise des qu'un coup fait mal.
        # N2 : redescendre coute la capacite amelioree -> seulement pour eviter la mort.
        if getattr(joueur.perso_obj, 'level', 1) == 1:
            return carte.dommages > (joueur.pv_total / 2)
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        joueur.changer_niveau_perso(1, log_details)
        self.gagnePV(2 * joueur.pv_base, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

class PommeDAdam(Objet):
    def __init__(self):
        super().__init__("Pomme d'Adam", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total <= 6
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(3, joueur, log_details)
        donjon = Jeu.donjon
        for i in range(donjon.index, min(donjon.index + 3, donjon.nb_cartes)):
            joueur.cartes_connues.add(donjon.cartes[donjon.ordre[i]])
        log_details.append(f"{joueur.nom} consulte secrètement les 3 prochaines cartes ({self.nom}).")
        self.destroy(joueur, Jeu, log_details)

class BouclierDuPonceur(Objet):
    def __init__(self):
        super().__init__("Bouclier du Ponceur", False, 2, types_tags=["Orc"])
    def rules(self, joueur, carte, Jeu, log_details):
        return "Orc" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class TatouageMaudit(Objet):
    def __init__(self):
        super().__init__("Tatouage maudit", False, 6)
    def en_roll(self, joueur, jet, jet_voulu, reversed, rerolled, Jeu, log_details):
        if self.intact and jet == 1:
            self.perdPV(1, joueur, log_details)
        return jet

class PistoletLaser(Objet):
    def __init__(self):
        super().__init__("Pistolet Laser", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance % 2 == 1 and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        suivante = _peek_prochaine_carte(Jeu)
        if isinstance(suivante, CarteMonstre) and suivante.puissance_initiale < carte.puissance:
            _execute_carte_suivante(self, joueur, suivante, Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)

class TrousseDeSecours(Objet):
    def __init__(self):
        super().__init__("Trousse de secours", True)
    def subit_dommages_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur and joueur.pv_total > 0 and carte.dommages >= 4:
            self.gagnePV(carte.dommages, joueur, log_details)
            self.destroy(joueur, Jeu, log_details)

class ArmureDeMage(Objet):
    def __init__(self):
        super().__init__("Armure de mage", False, 0, 0, types_tags=["Liche", "Démon"])
    def rules(self, joueur, carte, Jeu, log_details):
        return "Liche" in carte.types or "Démon" in carte.types
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 0
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.reduc_damage(5, joueur, carte, log_details)

class BombePirate(Objet):
    def __init__(self):
        super().__init__("Bombe pirate", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and _choisir_objet_a_sacrifier_comme_limon(joueur, Jeu, [self]) is not None
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total and carte.puissance >= 5
    def combat_effet(self, joueur, carte, Jeu, log_details):
        sacrifie = _choisir_objet_a_sacrifier_comme_limon(joueur, Jeu, [self])
        log_details.append(f"{joueur.nom} brise {sacrifie.nom} avec {self.nom}.")
        sacrifie.destroy(joueur, Jeu, log_details)
        joueur._gerer_pv_bonus(sacrifie, log_details)
        self.execute(joueur, carte, log_details)

class AnneauDuVent(Objet):
    def __init__(self):
        super().__init__("Anneau du Vent", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        # remet le monstre dans le Donjon a la position de son choix (IA: tout en dessous)
        self.remetDansDonjon(joueur, carte, Jeu, log_details, en_bas=True)
        self.destroy(joueur, Jeu, log_details)

class BouleDeCristal(Objet):
    def __init__(self):
        super().__init__("Boule de cristal", False)
        self.annonce = None
    def debut_partie(self, joueur, Jeu, log_details):
        self.annonce = None
    def debut_tour(self, joueur, Jeu, log_details):
        # Heuristique IA, pas regle: annonce la puissance au plus gros "poids de
        # danger" parmi les cartes restantes (frequence * puissance), avec
        # tie-break sur la puissance brute, en evitant si possible une ligne
        # deja couverte par le reste de la main.
        if not self.intact:
            return
        comptes = {}
        donjon = Jeu.donjon
        for idx in donjon.ordre[donjon.index:]:
            c = donjon.cartes[idx]
            if isinstance(c, CarteMonstre) and not c.is_X:
                comptes[c.puissance_initiale] = comptes.get(c.puissance_initiale, 0) + 1
        _, puissances_couvertes = _couverture_sans_objet(joueur, self)
        candidates = [p for p in comptes if p not in puissances_couvertes] or list(comptes)
        self.annonce = max(candidates, key=lambda p: (comptes[p] * p, p, comptes[p])) if comptes else None
        if self.annonce is not None:
            log_details.append(f"{joueur.nom} annonce la puissance {self.annonce} avec {self.nom}.")
    def rules(self, joueur, carte, Jeu, log_details):
        return self.annonce is not None and carte.puissance == self.annonce and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.annonce = None
    def score_effet(self, joueur, log_details):
        self.scoreChange(-1, joueur, log_details)

class CraneDuNecromancien(Objet):
    def __init__(self):
        super().__init__("Crâne du Nécromancien", False)
    def _candidats(self, joueur, carte):
        return [m for m in joueur.pile_monstres_vaincus
                if (0 if m.is_X else m.puissance) > carte.puissance and not (m.effet and "GOLD" in m.effet)]
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and len(self._candidats(joueur, carte)) > 0
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= 3
    def combat_effet(self, joueur, carte, Jeu, log_details):
        monstre = min(self._candidats(joueur, carte), key=lambda m: m.puissance)
        joueur.pile_monstres_vaincus.remove(monstre)
        Jeu.defausse.append(monstre)
        log_details.append(f"{joueur.nom} défausse {monstre.titre} pour {self.nom}.")
        self.execute(joueur, carte, log_details)

class LanceDeSilence(Objet):
    non_combattant = True  # ne sert que contre les monstres X (rares): ne retarde pas la fuite
    def __init__(self):
        super().__init__("Lance de Silence", True)
    def rules(self, joueur, carte, Jeu, log_details):
        # (simplification: seul le cas "monstre a effet special" est simule, pas les evenements)
        return carte.is_X and carte.puissance > 0
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(3, joueur, log_details)
        log_details.append(f"{joueur.nom} utilise {self.nom} pour annuler l'effet de {carte.titre}.")
        carte.dommages = max(carte.dommages - carte.puissance, 0)
        carte.puissance = 0
        self.destroy(joueur, Jeu, log_details)

class HacheMystique(Objet):
    def __init__(self):
        super().__init__("Hache Mystique", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance % 2 == 0 and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        suivante = _peek_prochaine_carte(Jeu)
        if isinstance(suivante, CarteMonstre) and suivante.puissance_initiale % 2 == 0:
            _execute_carte_suivante(self, joueur, suivante, Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)

class ArmureVivante(Objet):
    def __init__(self):
        super().__init__("Armure vivante", False, 1)
    def debut_partie(self, joueur, Jeu, log_details):
        self.gagnePV(len(Jeu.joueurs), joueur, log_details)

# --- 2eme impression ---

class Donjondex(Objet):
    def __init__(self):
        super().__init__("Donjondex", True)
    def rules(self, joueur, carte, Jeu, log_details):
        meme_type = any(any(t in m.types for t in carte.types) for m in joueur.pile_monstres_vaincus)
        return not meme_type and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class TapisVolant(Objet):
    # "Fuyez le Donjon a tout moment" : tant que la pile n'est pas vide, il est
    # quasi impossible de mourir avec cet objet. L'IA ponce donc sans craindre
    # la mort et s'envole juste avant le coup fatal.
    def __init__(self):
        super().__init__("Tapis volant", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return any(not (m.effet and "GOLD" in m.effet) for m in joueur.pile_monstres_vaincus)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        # s'envole avant de subir le coup fatal (la carte retourne sur le Donjon)
        if _defausse_monstre_de_pile(joueur, Jeu, log_details):
            joueur.fuite()
            log_details.append(f"{joueur.nom} s'envole du Donjon avec {self.nom} !\n")
            self.destroy(joueur, Jeu, log_details)
    def en_fuite(self, joueur, Jeu, log_details):
        # fuite volontaire : le tapis remplace un jet mal parti par une sortie garantie
        if (self.intact and joueur.jet_fuite <= 5
                and _defausse_monstre_de_pile(joueur, Jeu, log_details)):
            joueur.jet_fuite = 100
            log_details.append(f"{joueur.nom} s'envole du Donjon avec {self.nom} (fuite garantie).")
            self.destroy(joueur, Jeu, log_details)

class MasqueMaudit(Objet):
    def __init__(self):
        super().__init__("Masque maudit", False, 7)
    def en_roll(self, joueur, jet, jet_voulu, reversed, rerolled, Jeu, log_details):
        if self.intact:
            log_details.append(f"{self.nom}: jet de {jet} réduit à {max(1, jet - 1)}.")
            return max(1, jet - 1)
        return jet

class ParfumRegenerant(Objet):
    def __init__(self):
        super().__init__("Parfum régénérant", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total <= 4
    def combat_effet(self, joueur, carte, Jeu, log_details):
        log_details.append(f"{joueur.nom} utilise {self.nom}: tous les joueurs remontent à 8 PV maximum.")
        for j in Jeu.joueurs:
            if j.dans_le_dj and j.pv_total < 8:
                j.pv_total = 8
                log_details.append(f"{j.nom} remonte à 8 PV.")
        self.destroy(joueur, Jeu, log_details)

class GriffesEclair(Objet):
    def __init__(self):
        super().__init__("Griffes éclair", False)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur and carte.executed:
            suivante = _peek_prochaine_carte(Jeu)
            if (isinstance(suivante, CarteMonstre) and suivante.puissance_initiale <= 5
                    and not suivante.non_executable):
                _execute_carte_suivante(self, joueur, suivante, Jeu, log_details)
                joueur.doit_passer = True
                log_details.append(f"{joueur.nom} doit passer son tour ({self.nom}).")

class PerleRare(Objet):
    def __init__(self):
        super().__init__("Perle rare", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        # garder la perle intacte vaut 2 Points de Victoire: dernier recours seulement
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)
    def score_effet(self, joueur, log_details):
        self.scoreChange(2, joueur, log_details)

class PaquetSurprise(Objet):
    def __init__(self):
        super().__init__("Paquet surprise", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total <= 4
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(joueur.pv_base, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)
        self.piocheItem(joueur, Jeu, log_details)
        jetable = _choisir_objet_a_sacrifier_comme_limon(joueur, Jeu, [self])
        if jetable:
            joueur.objets.remove(jetable)
            joueur.pv_total -= jetable.pv_bonus
            log_details.append(
                f"{joueur.nom} défausse {jetable.nom} ({self.nom}), "
                f"perd {jetable.pv_bonus} PV bonus et retombe à {joueur.pv_total} PV."
            )

class BagouzeDuParrain(Objet):
    def __init__(self):
        super().__init__("Bagouze du parrain", False, 3)
    def score_effet(self, joueur, log_details):
        if sum(1 for o in joueur.objets if o.intact) == 4:
            self.scoreChange(2, joueur, log_details)

class TaserManuel(Objet):
    def __init__(self):
        super().__init__("Taser manuel", True)
        self.carte_a_defausser = None
    def debut_partie(self, joueur, Jeu, log_details):
        self.carte_a_defausser = None
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.carte_a_defausser = carte
        self.destroy(joueur, Jeu, log_details)
    def fin_tour(self, joueur, Jeu, log_details):
        if self.carte_a_defausser and joueur.dans_le_dj:
            if self.carte_a_defausser in joueur.pile_monstres_vaincus:
                joueur.pile_monstres_vaincus.remove(self.carte_a_defausser)
                Jeu.defausse.append(self.carte_a_defausser)
                log_details.append(f"{joueur.nom} défausse {self.carte_a_defausser.titre} ({self.nom}).")
            self.carte_a_defausser = None

class BarbecueDuPonceur(Objet):
    def __init__(self):
        super().__init__("Barbecue du Ponceur", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total <= 3 and any(
            not m.is_X and m.puissance >= 4 and not (m.effet and "GOLD" in m.effet)
            for m in joueur.pile_monstres_vaincus)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        monstre = _defausse_monstre_de_pile(joueur, Jeu, log_details, plus_puissant=True)
        if monstre:
            log_details.append(f"{joueur.nom} défausse {monstre.titre} ({self.nom}).")
            self.gagnePV(0 if monstre.is_X else monstre.puissance, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

class RoseDOr(Objet):
    non_combattant = True  # gardee pour ses +2 PV de fin de partie: ne retarde pas la fuite
    def __init__(self):
        super().__init__("Rose d'or", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        # garder la rose intacte vaut 2 Points de Victoire, mais mourir perd tout
        return joueur.pv_total <= 2 or carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(3, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)
    def score_effet(self, joueur, log_details):
        self.scoreChange(2, joueur, log_details)

class PotionDEscampette(Objet):
    def __init__(self):
        super().__init__("Potion d'escampette", True)
    def en_fuite(self, joueur, Jeu, log_details):
        if self.intact and joueur.jet_fuite <= 5:
            self.gagnePV(3, joueur, log_details)
            joueur.jet_fuite += 4
            log_details.append(f"{joueur.nom} utilise {self.nom}: jet de fuite porté à {joueur.jet_fuite}.")
            self.destroy(joueur, Jeu, log_details)

class MontreDuLapinBlanc(Objet):
    def __init__(self):
        super().__init__("Montre du Lapin blanc", False, 4)
    def debut_partie(self, joueur, Jeu, log_details):
        joueur.passe_son_tour = True
        log_details.append(f"{joueur.nom} sautera son premier tour ({self.nom}).")

# --- 4eme edition ---

class PorteBoulesDuPonceur(Objet):
    def __init__(self):
        super().__init__("Porte-Boules du Ponceur", False)
        self.objectif_multi_kill = 5  # l'IA repioche pour atteindre 5 monstres dans le tour
    def fin_tour(self, joueur, Jeu, log_details):
        if self.intact and joueur.monstres_ajoutes_ce_tour >= 5:
            self.gagnePV(5, joueur, log_details)
            self.compteur += 1
            if self.compteur >= 3:
                log_details.append(f"{self.nom} a servi 3 fois et se brise.")
                self.destroy(joueur, Jeu, log_details)

class ChevalierePirate(Objet):
    def __init__(self):
        super().__init__("Chevalière Pirate", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.gagnePV(3, joueur, log_details)
        self.destroy(joueur, Jeu, log_details)
    def en_roll(self, joueur, jet, jet_voulu, reversed, rerolled, Jeu, log_details):
        if not self.intact:
            return max(1, jet - 1)
        return jet

class TatouageDuPonceur(Objet):
    def __init__(self):
        super().__init__("Tatouage du Ponceur", False, 7)
    def _plafonne(self, joueur, log_details):
        if self.intact and joueur.pv_total > 12:
            joueur.pv_total = 12
            log_details.append(f"{joueur.nom} est plafonné à 12 PV ({self.nom}).")
    def debut_tour(self, joueur, Jeu, log_details):
        self._plafonne(joueur, log_details)
    def fin_tour(self, joueur, Jeu, log_details):
        self._plafonne(joueur, log_details)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if joueur_proprietaire == joueur:
            self._plafonne(joueur, log_details)

class PotageImprovise(Objet):
    def __init__(self):
        super().__init__("Potage Improvisé", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return len(joueur.pile_monstres_vaincus) >= 3
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total <= 4
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(len(joueur.pile_monstres_vaincus), joueur, log_details)
        monstre = _defausse_monstre_de_pile(joueur, Jeu, log_details)
        if monstre:
            log_details.append(f"{joueur.nom} défausse {monstre.titre} ({self.nom}).")
        self.destroy(joueur, Jeu, log_details)

class ClocheDuDejaVu(Objet):
    non_combattant = True  # son usage de combat (urgence) coute souvent 1 PV de score: pas une vraie option
    def __init__(self):
        super().__init__("La Cloche du Déjà-Vu", True)
    def _fodder(self, Jeu):
        return [c for c in Jeu.defausse
                if isinstance(c, CarteMonstre) and not c.is_X and c.puissance_initiale <= 1
                and not (c.effet and "GOLD" in c.effet)]
    def debut_tour(self, joueur, Jeu, log_details):
        # gagne 3 PV et remet un monstre facile de la defausse sur le Donjon (qu'il piochera lui-meme)
        if self.intact:
            faciles = self._fodder(Jeu)
            if faciles:
                monstre = faciles[0]
                Jeu.defausse.remove(monstre)
                Jeu.donjon.rajoute_en_haut_de_la_pile(monstre)
                self.gagnePV(3, joueur, log_details)
                log_details.append(f"{joueur.nom} remet {monstre.titre} sur le Donjon avec {self.nom}.")
                self.destroy(joueur, Jeu, log_details)
    def rules(self, joueur, carte, Jeu, log_details):
        return bool(self._fodder(Jeu)
                    or any(not (m.effet and "GOLD" in m.effet) for m in joueur.pile_monstres_vaincus))
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        # urgence: les +3 PV sauvent du coup fatal; remet le monstre le plus faible
        # (defausse de preference, sinon sa propre pile)
        faciles = self._fodder(Jeu)
        if faciles:
            monstre = faciles[0]
            Jeu.defausse.remove(monstre)
        else:
            candidats = [m for m in joueur.pile_monstres_vaincus if not (m.effet and "GOLD" in m.effet)]
            monstre = min(candidats, key=lambda m: 0 if m.is_X else m.puissance)
            joueur.pile_monstres_vaincus.remove(monstre)
        Jeu.donjon.rajoute_en_haut_de_la_pile(monstre)
        self.gagnePV(3, joueur, log_details)
        log_details.append(f"{joueur.nom} remet {monstre.titre} sur le Donjon avec {self.nom} (urgence).")
        self.destroy(joueur, Jeu, log_details)

class CapeDInvisibilite(Objet):
    def __init__(self):
        super().__init__("Cape d'invisibilité", True, puissance_tags=[6, 7, 8, 9, 10])
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance >= 6 and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        suivante = _peek_prochaine_carte(Jeu)
        if isinstance(suivante, CarteMonstre) and suivante.puissance_initiale >= 6:
            _execute_carte_suivante(self, joueur, suivante, Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)

class SlipDeLaResurgence(Objet):
    non_combattant = True  # +2 PV par autre actif intact: a 1 PV pres, ce n'est pas une option de combat
    def __init__(self):
        super().__init__("Slip de la Résurgence", True)
    def _compte(self, joueur):
        return sum(1 for o in joueur.objets if o is not self and o.actif and o.intact)
    def debut_tour(self, joueur, Jeu, log_details):
        # utiliser tot, pendant que les autres actifs sont encore intacts
        # (attendre des PV bas est perdant: les actifs se consomment plus vite que les PV)
        if self.intact and self._compte(joueur) >= 3:
            self.gagnePV(2 * self._compte(joueur), joueur, log_details)
            self.destroy(joueur, Jeu, log_details)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total and self._compte(joueur) >= 1
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(2 * self._compte(joueur), joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

class LanterneAbsorbante(Objet):
    def __init__(self):
        super().__init__("Lanterne Absorbante", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.donjon.vide
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total <= 5
    def combat_effet(self, joueur, carte, Jeu, log_details):
        suivante = Jeu.donjon.prochaine_carte()
        Jeu.defausse.append(suivante)
        if isinstance(suivante, CarteMonstre):
            log_details.append(f"{joueur.nom} défausse {suivante.titre} avec {self.nom}.")
            self.gagnePV(suivante.puissance_initiale, joueur, log_details)
            self.destroy(joueur, Jeu, log_details)
        else:
            log_details.append(f"{joueur.nom} défausse {suivante.titre} avec {self.nom} (sans la briser).")

class ArcDuNeant(Objet):
    def __init__(self):
        super().__init__("Arc du Néant", False, 7)
        self.dernier_tour_paye = None
    def debut_partie(self, joueur, Jeu, log_details):
        self.dernier_tour_paye = None
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if (self.intact and joueur_proprietaire == joueur and carte.executed
                and self.dernier_tour_paye != joueur.tour):
            self.dernier_tour_paye = joueur.tour
            self.perdPV(1, joueur, log_details)

class ConcoctionInstable(Objet):
    def __init__(self):
        super().__init__("Concoction instable", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        if joueur.tour == 3:
            # fixer ses PV sur la puissance du monstre est obligatoire au tour 3
            return carte.puissance > joueur.pv_total
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        # consommable: se brise a l'utilisation, ou en fin de 3eme tour si inutilisee
        self.execute(joueur, carte, log_details)
        if joueur.tour == 3 and carte.puissance > 0:
            joueur.pv_total = carte.puissance
            log_details.append(f"{joueur.nom} fixe ses PV à {carte.puissance} ({self.nom}).")
        self.destroy(joueur, Jeu, log_details)
    def fin_tour(self, joueur, Jeu, log_details):
        if self.intact and joueur.tour >= 3:
            log_details.append(f"{self.nom} se brise (fin du 3ème tour).")
            self.destroy(joueur, Jeu, log_details)

class BananeExperimentale(Objet):
    def __init__(self):
        super().__init__("Banane expérimentale", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        if joueur.pile_monstres_vaincus:
            monstre = random.choice(joueur.pile_monstres_vaincus)
            joueur.pile_monstres_vaincus.remove(monstre)
            Jeu.donjon.rajoute_en_haut_de_la_pile(monstre)
            log_details.append(f"{monstre.titre} retourne sur le Donjon ({self.nom}).")
        self.destroy(joueur, Jeu, log_details)

class KitDeSoin(Objet):
    def __init__(self):
        super().__init__("Kit de Soin", True)
    def subit_dommages_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if (self.intact and joueur_proprietaire == joueur and joueur.pv_total > 0
                and joueur.pv_total <= 5 and carte.dommages > 0):
            self.gagnePV(5, joueur, log_details)
            self.destroy(joueur, Jeu, log_details)

class CompasDuCapitaine(Objet):
    def __init__(self):
        super().__init__("Compas du Capitaine", True, puissance_tags=[6, 7])
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance <= 7 and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        prochaine = _peek_prochaine_carte(Jeu)
        if prochaine is not None:
            joueur.cartes_connues.add(prochaine)
            log_details.append(f"{joueur.nom} regarde secrètement la carte du dessus ({self.nom}).")
        self.destroy(joueur, Jeu, log_details)

class PotionAuTheVert(Objet):
    def __init__(self):
        super().__init__("Potion au Thé Vert", True)
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact and joueur.pv_total <= 3 and joueur.tour >= 2:
            self.gagnePV(4, joueur, log_details)
            joueur.passe_son_tour = True
            log_details.append(f"{joueur.nom} passe son tour ({self.nom}).")
            self.destroy(joueur, Jeu, log_details)

class UrneEnsorcelee(Objet):
    def __init__(self):
        super().__init__("Urne Ensorcelée", False)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur and carte.executed and joueur.pv_total <= 3:
            self.gagnePV(1, joueur, log_details)
            joueur.doit_passer = True

# --- v4b ---

class MainDuCreateur(Objet):
    def __init__(self):
        super().__init__("Main du Créateur", True)
    def survie_effet(self, joueur, carte, Jeu, log_details):
        # (la defausse d'un theme de Donjon n'est pas simulee)
        self.survit(2, joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class BotteDePandore(Objet):
    def __init__(self):
        super().__init__("Botte de Pandore", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total <= 3
    def combat_effet(self, joueur, carte, Jeu, log_details):
        log_details.append(f"{joueur.nom} utilise {self.nom}: tous les joueurs gagnent 5 PV.")
        for j in Jeu.joueurs:
            if j.dans_le_dj:
                j.pv_total += 5
        for j in Jeu.joueurs:
            if j is not joueur and j.dans_le_dj:
                j.decideBriseObjet(Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)

class ScotchDuSilencieux(Objet):
    def __init__(self):
        super().__init__("Scotch du Silencieux", False)
    def rencontre_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if (self.intact and joueur_proprietaire == joueur and isinstance(carte, CarteMonstre)
                and carte.is_X and carte.puissance > 0):
            log_details.append(f"{carte.titre} passe à puissance 0 ({self.nom}).")
            carte.dommages = max(carte.dommages - carte.puissance, 0)
            carte.puissance = 0
# --- v5 ---

class CouteauxDeLancer(Objet):
    def __init__(self):
        super().__init__("Couteaux de lancer", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        # defausse les 3 monstres restants les plus dangereux du Donjon, puis melange
        donjon = Jeu.donjon
        restants = list(donjon.ordre[donjon.index:])
        monstres = [(pos, donjon.cartes[idx]) for pos, idx in enumerate(restants)
                    if isinstance(donjon.cartes[idx], CarteMonstre)]
        cibles = sorted(monstres, key=lambda pc: pc[1].puissance_initiale, reverse=True)[:3]
        for pos in sorted([pos for pos, c in cibles], reverse=True):
            idx = restants.pop(pos)
            Jeu.defausse.append(donjon.cartes[idx])
            log_details.append(f"{donjon.cartes[idx].titre} est défaussé du Donjon ({self.nom}).")
        donjon.ordre = np.concatenate((donjon.ordre[:donjon.index],
                                       np.array(restants, dtype=donjon.ordre.dtype)))
        donjon.nb_cartes = len(donjon.ordre)
        donjon.remelange()
        self.destroy(joueur, Jeu, log_details)

class PierreDePressentiment(Objet):
    def __init__(self):
        super().__init__("Pierre de Pressentiment", True)
        self.en_attente = False
    def debut_partie(self, joueur, Jeu, log_details):
        self.en_attente = False
    def debut_tour(self, joueur, Jeu, log_details):
        # utilisation avant de piocher: 3 PV, et le prochain monstre pioche est execute
        if self.intact and joueur.pv_total <= 5 and not Jeu.traquenard_actif:
            log_details.append(f"{joueur.nom} utilise {self.nom} avant de piocher.")
            self.gagnePV(3, joueur, log_details)
            self.en_attente = True
            Jeu.execute_next_monster = True
            self.destroy(joueur, Jeu, log_details)
    def rencontre_event_effet(self, joueur_proprietaire, joueur_actif, carte, Jeu, log_details):
        if self.en_attente and joueur_proprietaire == joueur_actif:
            self.en_attente = False
            log_details.append(f"{self.nom} se répare (la carte piochée n'était pas un monstre).")
            self.repare()
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.en_attente and joueur_proprietaire == joueur:
            self.en_attente = False

class ToupieDuChaos(Objet):
    # (le melange du Donjon n'a pas d'effet mesurable en simulation)
    def __init__(self):
        super().__init__("Toupie du Chaos", False, 4)

# (Cerveau auxiliaire et Implant cérébral: supprimes du jeu, barres dans le tableur)

# --- fournee janvier 2025 ---

class CoursierVolant(Objet):
    def __init__(self):
        super().__init__("Coursier volant", False, 2)
    def fin_tour(self, joueur, Jeu, log_details):
        if self.intact and Jeu.objets_dispo:
            inutiles = [o for o in joueur.objets
                        if o.intact and o is not self and not o.actif and o.pv_bonus == 0 and o.priorite < 40]
            if inutiles:
                jete = min(inutiles, key=lambda o: o.priorite)
                joueur.objets.remove(jete)
                log_details.append(f"{joueur.nom} défausse {jete.nom} pour piocher ({self.nom}).")
                self.piocheItem(joueur, Jeu, log_details)

class SiegeDeTroie(Objet):
    def __init__(self):
        super().__init__("Siège de Troie", True)
        self.tour_activation = None
    def debut_partie(self, joueur, Jeu, log_details):
        self.tour_activation = None
    def rules(self, joueur, carte, Jeu, log_details):
        return any(j is not joueur and j.dans_le_dj for j in Jeu.joueurs)
    def worthit(self, joueur, carte, Jeu, log_details):
        return sum(1 for j in Jeu.joueurs if j is not joueur and j.dans_le_dj) >= 2
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.tour_activation = Jeu.tour
        log_details.append(f"{joueur.nom} active {self.nom} !")
        self.destroy(joueur, Jeu, log_details)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.tour_activation is None:
            return
        if Jeu.tour > self.tour_activation + len(Jeu.joueurs):
            self.tour_activation = None
            return
        if joueur is not joueur_proprietaire and carte in joueur.pile_monstres_vaincus:
            joueur.pile_monstres_vaincus.remove(carte)
            Jeu.defausse.append(carte)
            self.gagnePV(1, joueur_proprietaire, log_details)
            log_details.append(f"{carte.titre} de {joueur.nom} est défaussé ({self.nom}).")

class MiroirDeYata(Objet):
    def __init__(self):
        super().__init__("Miroir de Yata", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        # montre les 3 prochaines cartes a TOUS les joueurs
        donjon = Jeu.donjon
        for i in range(donjon.index, min(donjon.index + 3, donjon.nb_cartes)):
            for j in Jeu.joueurs:
                j.cartes_connues.add(donjon.cartes[donjon.ordre[i]])
        log_details.append(f"{joueur.nom} montre les 3 prochaines cartes à tous ({self.nom}).")
        joueur.doit_passer = True
        self.destroy(joueur, Jeu, log_details)

class SceptreDuMaharal(Objet):
    def __init__(self):
        super().__init__("Sceptre du Maharal", False, types_tags=["Golem"])
    def rules(self, joueur, carte, Jeu, log_details):
        return "Golem" in carte.types and joueur.pv_total > 1 and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > 1
    def combat_effet(self, joueur, carte, Jeu, log_details):
        # (IA: garde le Golem dans sa pile plutot que de le remettre sur le Donjon)
        self.perdPV(1, joueur, log_details)
        self.execute(joueur, carte, log_details)

class CleAmulette(Objet):
    def __init__(self):
        super().__init__("Clé Amulette", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        repare_perso = any(not o.intact for o in joueur.objets if o is not self)
        return carte.dommages > (joueur.pv_total / 2) and repare_perso
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        for j in Jeu.joueurs:
            if j.dans_le_dj:
                _repare_un_objet(j, [self], log_details, self.nom)
        # la Cle Amulette est defaussee apres usage
        self.destroy(joueur, Jeu, log_details)
        if self in joueur.objets:
            joueur.objets.remove(self)

class CleDeSalomon(Objet):
    def __init__(self):
        super().__init__("Clé de Salomon", False, types_tags=["Démon"])
    def rules(self, joueur, carte, Jeu, log_details):
        return "Démon" in carte.types and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        # apres un monstre de puissance 6+, regarde la prochaine carte du Donjon
        if self.intact and joueur_proprietaire == joueur and carte.puissance >= 6:
            prochaine = _peek_prochaine_carte(Jeu)
            if prochaine is not None:
                joueur.cartes_connues.add(prochaine)

class DagueDeBrutus(Objet):
    def __init__(self):
        super().__init__("Dague de Brutus", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and not getattr(carte, 'non_executable', False)
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total
    def combat_effet(self, joueur, carte, Jeu, log_details):
        carte.executed = True
        self.gagnePV(2, joueur, log_details)
        adversaires = [j for j in Jeu.joueurs if j is not joueur and j.dans_le_dj]
        if adversaires:
            beneficiaire = min(adversaires, key=lambda j: len(j.pile_monstres_vaincus))
            beneficiaire.ajouter_monstre_vaincu(carte)
            log_details.append(f"{joueur.nom} exécute {carte.titre} avec {self.nom} et l'offre à {beneficiaire.nom}.")
        else:
            joueur.ajouter_monstre_vaincu(carte)
            log_details.append(f"{joueur.nom} exécute {carte.titre} avec {self.nom}.")
        self.destroy(joueur, Jeu, log_details)

class RouletteInfernale(Objet):
    def __init__(self):
        super().__init__("Roulette infernale", False, 2)
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact and joueur.pv_total >= 7:
            jet = joueur.rollDice(Jeu, log_details)
            if jet % 2 == 0:
                self.gagnePV(jet, joueur, log_details)
            else:
                self.perdPV(jet, joueur, log_details)
            if jet == 6:
                log_details.append(f"{self.nom} se brise sur un 6.")
                self.destroy(joueur, Jeu, log_details)
                joueur._gerer_pv_bonus(self, log_details)

class DisqueDeVishnu(Objet):
    def __init__(self):
        super().__init__("Disque de Vishnu", True)
        self.carte_defaussee = None
    def debut_partie(self, joueur, Jeu, log_details):
        self.carte_defaussee = None
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        self.carte_defaussee = carte
        self.destroy(joueur, Jeu, log_details)
    def fin_tour(self, joueur, Jeu, log_details):
        if self.carte_defaussee and Jeu.defausse and Jeu.defausse[-1] is self.carte_defaussee:
            self.gagnePV(1, joueur, log_details)

class MasqueDeFer(Objet):
    def __init__(self):
        super().__init__("Masque de Fer", False, 6)
    def debut_partie(self, joueur, Jeu, log_details):
        # le heros perd sa capacite speciale (remplace par un perso neutre, memes PV)
        from heros import Perso
        if type(joueur.perso_obj) is not Perso:
            joueur.perso_obj = Perso(joueur.perso_obj.nom + " (muselé)", joueur.perso_obj.pv_bonus)
            log_details.append(f"{joueur.nom} ne peut plus utiliser la capacité de son héros ({self.nom}).")

class MainInvisible(Objet):
    GROS_TYPES = ("Liche", "Démon", "Dragon")
    def __init__(self):
        super().__init__("Main invisible", False)
    def _compte(self, joueur):
        return sum(1 for m in joueur.pile_monstres_vaincus
                   if any(t in m.types for t in MainInvisible.GROS_TYPES))
    def debut_tour(self, joueur, Jeu, log_details):
        self.modificateur_de = self._compte(joueur) if self.intact else 0
    def score_effet(self, joueur, log_details):
        compte = self._compte(joueur)
        if compte:
            self.scoreChange(compte, joueur, log_details)

class EventailMaudit(Objet):
    def __init__(self):
        super().__init__("Eventail Maudit", False, 2)
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact and any(j is not joueur and j.dans_le_dj for j in Jeu.joueurs):
            jet = joueur.rollDice(Jeu, log_details)
            if jet == 6:
                for j in Jeu.joueurs:
                    if j is not joueur and j.dans_le_dj and j.pv_total >= 2:
                        j.pv_total -= 1
                        log_details.append(f"{j.nom} perd 1 PV ({self.nom}).")

class EpeeDeDamocles(Objet):
    def __init__(self):
        super().__init__("Epée de Damocles", False, 9)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur and carte.executed:
            jet = joueur.rollDice(Jeu, log_details)
            if jet == 1:
                log_details.append(f"{self.nom} se brise !")
                self.destroy(joueur, Jeu, log_details)
                joueur._gerer_pv_bonus(self, log_details)

class VoileDIsis(Objet):
    def __init__(self):
        super().__init__("Voile d'Isis", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total <= 5
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.gagnePV(3, joueur, log_details)
        donjon = Jeu.donjon
        restantes = donjon.ordre[donjon.index:]
        if len(restantes) > 10:
            fond = np.array(restantes[-10:], copy=True)
            np.random.shuffle(fond)
            donjon.ordre = np.concatenate((donjon.ordre[:donjon.index], fond, restantes[:-10]))
            log_details.append(f"{joueur.nom} remet les 10 cartes du fond sur le Donjon ({self.nom}).")
        self.destroy(joueur, Jeu, log_details)

class TambourDeKui(Objet):
    def __init__(self):
        super().__init__("Tambour de Kui", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        return joueur.pv_total <= 5
    def combat_effet(self, joueur, carte, Jeu, log_details):
        # regarde les 4 premieres cartes, defausse les monstres trop dangereux, gagne 1 PV par carte gardee
        donjon = Jeu.donjon
        nb = min(4, donjon.nb_cartes - donjon.index)
        positions_a_defausser = []
        for i in range(nb):
            c = donjon.cartes[donjon.ordre[donjon.index + i]]
            if isinstance(c, CarteMonstre) and c.puissance_initiale >= joueur.pv_total + 3:
                positions_a_defausser.append(donjon.index + i)
                Jeu.defausse.append(c)
                log_details.append(f"{c.titre} est défaussé du Donjon ({self.nom}).")
        if positions_a_defausser:
            donjon.ordre = np.delete(donjon.ordre, positions_a_defausser)
            donjon.nb_cartes = len(donjon.ordre)
        self.gagnePV(nb - len(positions_a_defausser), joueur, log_details)
        self.destroy(joueur, Jeu, log_details)

# --- fournee novembre 2025 ---

class ParachuteDore(Objet):
    def __init__(self):
        super().__init__("Parachute doré", True)
    def en_fuite(self, joueur, Jeu, log_details):
        if self.intact:
            self.gagnePV(4, joueur, log_details)
            self.piocheItem(joueur, Jeu, log_details)
            self.destroy(joueur, Jeu, log_details)

class PoigneeDeMain(Objet):
    def __init__(self):
        super().__init__("Poignée de main", True)
    def survie_effet(self, joueur, carte, Jeu, log_details):
        nb = sum(1 for j in Jeu.joueurs if j.dans_le_dj)
        self.survit(max(1, nb), joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)

class Paratonnerre(Objet):
    def __init__(self):
        super().__init__("Paratonnerre", True)
    def survie_effet(self, joueur, carte, Jeu, log_details):
        self.survit(1, joueur, carte, log_details)
        self.destroy(joueur, Jeu, log_details)
        if carte.puissance >= 7:
            _repare_un_objet(joueur, [self], log_details, self.nom)

class EplucheDonjon(Objet):
    def __init__(self):
        super().__init__("Épluche-Donjon", False, 3)
    def debut_tour(self, joueur, Jeu, log_details):
        if self.intact and not Jeu.donjon.vide:
            carte = Jeu.donjon.prochaine_carte()
            Jeu.defausse.append(carte)
            log_details.append(f"{joueur.nom} défausse {carte.titre} du Donjon ({self.nom}).")

class CrocsEnflamees(Objet):
    def __init__(self):
        super().__init__("Crocs enflamées", False, 7)
    def en_fuite(self, joueur, Jeu, log_details):
        if self.intact:
            self.perdPV(1, joueur, log_details)

class GlandePineale(Objet):
    def __init__(self):
        super().__init__("Glande pinéale", False)
    def debut_tour(self, joueur, Jeu, log_details):
        self.modificateur_de = sum(1 for j in Jeu.joueurs if j.dans_le_dj) if self.intact else 0
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance == joueur.pv_base and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class OursinDodu(Objet):
    def __init__(self):
        super().__init__("Oursin dodu", False, 4)

class SceauDeLegalisation(Objet):
    def __init__(self):
        super().__init__("Sceau de Légalisation", False, 6)
    def fin_tour(self, joueur, Jeu, log_details):
        if self.intact and joueur.pv_total % 2 == 1:
            self.perdPV(1, joueur, log_details)

class MiroirDuRised(Objet):
    def __init__(self):
        super().__init__("Miroir du Riséd", False)
    def rules(self, joueur, carte, Jeu, log_details):
        if not joueur.pile_monstres_vaincus or Jeu.traquenard_actif:
            return False
        sommet = joueur.pile_monstres_vaincus[-1]
        return any(t in sommet.types for t in carte.types)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.gagnePV(2, joueur, log_details)

class SurinCrasseux(Objet):
    def __init__(self):
        super().__init__("Surin crasseux", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return carte.puissance % 2 == 1 and not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return "Gobelin" in carte.types or carte.dommages > (joueur.pv_total / 2)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        if "Gobelin" in carte.types:
            self.piocheItem(joueur, Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)

class BottesDePoncage(Objet):
    def __init__(self):
        super().__init__("Bottes de Ponçage", False, 6)
    def en_fuite(self, joueur, Jeu, log_details):
        if self.intact:
            for _ in range(3):
                if Jeu.donjon.vide:
                    break
                c = Jeu.donjon.prochaine_carte()
                Jeu.defausse.append(c)
                log_details.append(f"{c.titre} est défaussé du Donjon ({self.nom}).")

class BombeDeMidas(Objet):
    def __init__(self):
        super().__init__("Bombe de Midas", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif and _choisir_objet_a_sacrifier(joueur, [self]) is not None
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages >= joueur.pv_total and carte.puissance >= 5
    def combat_effet(self, joueur, carte, Jeu, log_details):
        sacrifie = _choisir_objet_a_sacrifier(joueur, [self])
        log_details.append(f"{joueur.nom} brise {sacrifie.nom} avec {self.nom}.")
        sacrifie.destroy(joueur, Jeu, log_details)
        joueur._gerer_pv_bonus(sacrifie, log_details)
        self.gagnePV(carte.puissance, joueur, log_details)
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        self.destroy(joueur, Jeu, log_details)

class CouteauQuiTombe(Objet):
    def __init__(self):
        super().__init__("Couteau qui Tombe", True)
        self.cartes_obligatoires = 0
    def debut_partie(self, joueur, Jeu, log_details):
        self.cartes_obligatoires = 0
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        return carte.dommages > (joueur.pv_total / 2) and joueur.pv_total >= 6
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        # 4 car le vaincu de cette carte decremente immediatement: 3 cartes supplementaires net
        self.cartes_obligatoires = 4
        log_details.append(f"{joueur.nom} devra piocher encore 3 cartes ({self.nom}).")
        self.destroy(joueur, Jeu, log_details)
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.cartes_obligatoires > 0 and joueur_proprietaire == joueur:
            self.cartes_obligatoires -= 1
            if self.cartes_obligatoires > 0:
                joueur.rejoue = True

class AvisDeRecherche(Objet):
    def __init__(self):
        super().__init__("Avis de recherche", False)
    def rules(self, joueur, carte, Jeu, log_details):
        return (carte.puissance >= 4 and len(carte.types) > 0 and carte.effet is not None
                and not Jeu.traquenard_actif)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class CarapaceBleue(Objet):
    def __init__(self):
        super().__init__("Carapace Bleue", True)
    def rules(self, joueur, carte, Jeu, log_details):
        return not Jeu.traquenard_actif
    def worthit(self, joueur, carte, Jeu, log_details):
        compte = {j: len(j.pile_monstres_vaincus) for j in Jeu.joueurs}
        leaders = [j for j in Jeu.joueurs if compte[j] == max(compte.values())]
        bon_moment = len(leaders) == 1 and leaders[0] is not joueur
        return carte.dommages > (joueur.pv_total / 2) and (bon_moment or carte.dommages >= joueur.pv_total)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.executeEtDefausse(joueur, carte, Jeu, log_details)
        compte = {j: len(j.pile_monstres_vaincus) for j in Jeu.joueurs}
        leaders = [j for j in Jeu.joueurs if compte[j] == max(compte.values()) and compte[j] > 0]
        if len(leaders) == 1:
            monstre = _defausse_monstre_de_pile(leaders[0], Jeu, log_details)
            if monstre:
                log_details.append(f"{leaders[0].nom} défausse {monstre.titre} ({self.nom}).")
        self.destroy(joueur, Jeu, log_details)

# --- objets de divination (utilisent joueur.cartes_connues, lu par l'IA de fuite/repioche) ---

class JournalDuFutur(Objet):
    def __init__(self):
        super().__init__("Journal du futur", False)
    def debut_tour(self, joueur, Jeu, log_details):
        # regarde secretement la 3eme carte du Donjon (memorisee jusqu'a ce qu'elle surface)
        donjon = Jeu.donjon
        if self.intact and donjon.index + 2 < donjon.nb_cartes:
            joueur.cartes_connues.add(donjon.cartes[donjon.ordre[donjon.index + 2]])

class BinoclesDeLInventeur(Objet):
    def __init__(self):
        super().__init__("Binocles de l'inventeur", False)
    def subit_dommages_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if self.intact and joueur_proprietaire == joueur and carte.dommages > 0:
            prochaine = _peek_prochaine_carte(Jeu)
            if prochaine is not None:
                joueur.cartes_connues.add(prochaine)
                log_details.append(f"{joueur.nom} regarde la prochaine carte ({self.nom}).")

class OeilDHorus(Objet):
    def __init__(self):
        super().__init__("Œil d'Horus", False)
        self.dernier_tour_utilise = None
    def debut_partie(self, joueur, Jeu, log_details):
        self.dernier_tour_utilise = None
    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        # une fois par tour apres un monstre vaincu: regarde la 1ere carte et la remet
        # sous le Donjon si elle est dangereuse (sinon la memorise)
        if (self.intact and joueur_proprietaire == joueur
                and self.dernier_tour_utilise != joueur.tour):
            self.dernier_tour_utilise = joueur.tour
            prochaine = _peek_prochaine_carte(Jeu)
            if prochaine is None:
                return
            if (isinstance(prochaine, CarteMonstre) and not prochaine.is_X
                    and prochaine.puissance_initiale >= max(4, joueur.pv_total)):
                Jeu.donjon.prochaine_carte()
                Jeu.donjon.rajoute_en_bas_de_la_pile(prochaine)
                log_details.append(f"{joueur.nom} remet {prochaine.titre} sous le Donjon ({self.nom}).")
            else:
                joueur.cartes_connues.add(prochaine)

class OiseauDeMauvaisAugure(Objet):
    def __init__(self):
        super().__init__("Oiseau de Mauvais Augure", False)
    def fin_tour(self, joueur, Jeu, log_details):
        # regarde la 1ere carte: envoie les bonnes cartes sous le Donjon (deni aux adversaires),
        # laisse les dangereuses sur le dessus pour le prochain joueur
        if self.intact and any(j is not joueur and j.dans_le_dj for j in Jeu.joueurs):
            prochaine = _peek_prochaine_carte(Jeu)
            if prochaine is None:
                return
            bonne_carte = getattr(prochaine, 'event', False) or (
                isinstance(prochaine, CarteMonstre) and not prochaine.is_X
                and prochaine.puissance_initiale <= 2)
            if bonne_carte:
                Jeu.donjon.prochaine_carte()
                Jeu.donjon.rajoute_en_bas_de_la_pile(prochaine)
                log_details.append(f"{joueur.nom} envoie {prochaine.titre} sous le Donjon ({self.nom}).")
            else:
                joueur.cartes_connues.add(prochaine)

class FilDuDestin(Objet):
    def __init__(self):
        super().__init__("Fil du destin", True)
    def debut_tour(self, joueur, Jeu, log_details):
        # regarde les 4 prochaines cartes et les reordonne: la plus simple pour soi d'abord,
        # les plus dangereuses ensuite (pour les adversaires)
        donjon = Jeu.donjon
        if not self.intact or joueur.tour < 2 or donjon.nb_cartes - donjon.index < 4:
            return
        positions = list(range(donjon.index, donjon.index + 4))
        cartes = [donjon.cartes[donjon.ordre[p]] for p in positions]
        def danger(c):
            if getattr(c, 'event', False):
                return -1
            if joueur.peut_executer_facilement(c):
                return 0
            return 4 if c.is_X else c.puissance_initiale
        tri = sorted(range(4), key=lambda i: danger(cartes[i]))
        nouvel_ordre = [tri[0]] + sorted(tri[1:], key=lambda i: -danger(cartes[i]))
        anciens = [donjon.ordre[p] for p in positions]
        for p, i in zip(positions, nouvel_ordre):
            donjon.ordre[p] = anciens[i]
        for c in cartes:
            joueur.cartes_connues.add(c)
        log_details.append(f"{joueur.nom} réordonne les 4 prochaines cartes du Donjon ({self.nom}).")
        self.destroy(joueur, Jeu, log_details)

# --- Maj tableur 12 juin 2026 : couleurs des objets ---------------------------

class BourseGarnie(Objet):
    def __init__(self):
        super().__init__("Bourse garnie", False, 3)
    def score_effet(self, joueur, log_details):
        self.scoreChange(1, joueur, log_details)

class LanterneChromatique(Objet):
    def __init__(self):
        super().__init__("Lanterne chromatique", False, 2)
    def rules(self, joueur, carte, Jeu, log_details):
        # puissance == nb de couleurs differentes dans ses objets, intacts ET brises
        return carte.puissance == nb_couleurs(joueur.objets) and not Jeu.traquenard_actif
    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)

class CinqPierresDeNuwa(Objet):
    def __init__(self):
        super().__init__("Cinq pierres de Nüwa", True)
    def worthit(self, joueur, carte, Jeu, log_details):
        # en urgence, ou des que les 5 couleurs sont reunies (PV max + l'objet est defausse, pas brise)
        return (carte.dommages >= joueur.pv_total
                or nb_couleurs(joueur.objets, intacts_seulement=True) == 5)
    def combat_effet(self, joueur, carte, Jeu, log_details):
        couleurs = nb_couleurs(joueur.objets, intacts_seulement=True)
        self.gagnePV(couleurs, joueur, log_details)
        if couleurs == 5:
            self.gagnePV(5, joueur, log_details)
            self.destroy(joueur, Jeu, log_details)
            # defausse : ne reste pas comme objet brise (sauf si une reaction l'a deja retire, ex: Trou Noir)
            if self in joueur.objets:
                joueur.objets.remove(self)
            log_details.append(f"Les {self.nom} sont défaussées.")
        else:
            self.destroy(joueur, Jeu, log_details)

# --- Table de dispatch des hooks (optimisation) ------------------------------
# Pour chaque hook, l'ensemble des CLASSES qui ne l'implementent PAS (ni le
# wrapper en_X ni l'effet X_effet) : on saute l'appel no-op dans les boucles
# chaudes de simu.py. Le filtrage se fait a l'iteration sur joueur.objets (en
# live, jamais de liste figee), donc les objets pioches/voles/ajoutes en cours
# de partie sont automatiquement pris en compte. Une classe inconnue de la
# table (definie ailleurs/plus tard) n'est dans aucun ensemble "SANS_" et sera
# donc toujours appelee : le defaut est sur.
_HOOKS_OBJET = {
    'en_rencontre': ('en_rencontre', 'rencontre_effet'),
    'en_rencontre_event': ('en_rencontre_event', 'rencontre_event_effet'),
    'en_vaincu': ('en_vaincu', 'vaincu_effet'),
    'en_subit_dommages': ('en_subit_dommages', 'subit_dommages_effet'),
    'en_activated': ('en_activated', 'activated_effet'),
    'en_mort': ('en_mort', 'mort_effet'),
    'en_fuite_definitive': ('en_fuite_definitive', 'fuite_definitive_effet'),
    'en_survie': ('en_survie', 'survie_effet'),
    'en_combat': ('combat_effet',),  # en_combat de base n'appelle que combat_effet
    'en_roll': ('en_roll',),
    'en_fuite': ('en_fuite',),
    'debut_tour': ('debut_tour',),
    'fin_tour': ('fin_tour',),
}

def _toutes_sous_classes(base):
    classes = []
    for cls in base.__subclasses__():
        classes.append(cls)
        classes.extend(_toutes_sous_classes(cls))
    return classes

def _table_sans_hook(base, hooks):
    classes = _toutes_sous_classes(base)
    return {
        hook: frozenset(cls for cls in classes
                        if all(getattr(cls, m) is getattr(base, m) for m in methodes))
        for hook, methodes in hooks.items()
    }

SANS_HOOK_OBJET = _table_sans_hook(Objet, _HOOKS_OBJET)

# Liste des objets
objets_disponibles = [
    MainDeMidas(),
    MidasDeBronze(),
    HacheDeGlace(),
    MarteauDeGuerre(),
    FleauDesLiches(),
    EpauletteDuPonceur(),
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
    CasqueACornes(),
    AnkhDeReincarnation(),
    CoffreDuRoiSorcier(),
    CoeurDeDragon(),
    ShotDAdrenaline(),
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
    HarpeCinglante(),
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
    ParcheminDePoncage(),
    AraigneeDomestique(),
    Exterminator(),
    CodexDiabolus(),
    SainteLance(),
    TorcheEnMousse(),
    GrelotDuBouffon(),
    AspisHeracles(),
    BouillonDAmes(),
    ConcentreDeFun(),
    ForgePortative(),
    SacDeConstantinople(),
    TrouNoirPortatif(),
    CalumetDeLaPaix(),
    Zulfikar(),
    AnneauDeGlace(),
    GrenadeSinge(),
    SceptreChangeur(),
    # --- synchro tableur juin 2026 ---
    CoeurDeTarasque(),
    CeintureDuPonceur(),
    LinceulDeResurrection(),
    Imprimante(),
    EpeeVengeresse(),
    DagueVengeresse(),
    TotemDImmunite(),
    CeintureDuNovice(),
    AnneauDuNovice(),
    CapeDuNovice(),
    PommeDAdam(),
    BouclierDuPonceur(),
    TatouageMaudit(),
    PistoletLaser(),
    TrousseDeSecours(),
    ArmureDeMage(),
    BombePirate(),
    AnneauDuVent(),
    BouleDeCristal(),
    CraneDuNecromancien(),
    LanceDeSilence(),
    HacheMystique(),
    ArmureVivante(),
    Donjondex(),
    TapisVolant(),
    MasqueMaudit(),
    ParfumRegenerant(),
    GriffesEclair(),
    PerleRare(),
    PaquetSurprise(),
    BagouzeDuParrain(),
    TaserManuel(),
    BarbecueDuPonceur(),
    RoseDOr(),
    PotionDEscampette(),
    MontreDuLapinBlanc(),
    PorteBoulesDuPonceur(),
    ChevalierePirate(),
    TatouageDuPonceur(),
    PotageImprovise(),
    ClocheDuDejaVu(),
    CapeDInvisibilite(),
    SlipDeLaResurgence(),
    LanterneAbsorbante(),
    ArcDuNeant(),
    ConcoctionInstable(),
    BananeExperimentale(),
    KitDeSoin(),
    CompasDuCapitaine(),
    PotionAuTheVert(),
    UrneEnsorcelee(),
    MainDuCreateur(),
    BotteDePandore(),
    ScotchDuSilencieux(),
    CouteauxDeLancer(),
    PierreDePressentiment(),
    ToupieDuChaos(),
    CoursierVolant(),
    SiegeDeTroie(),
    MiroirDeYata(),
    SceptreDuMaharal(),
    CleAmulette(),
    CleDeSalomon(),
    DagueDeBrutus(),
    RouletteInfernale(),
    DisqueDeVishnu(),
    MasqueDeFer(),
    MainInvisible(),
    EventailMaudit(),
    EpeeDeDamocles(),
    VoileDIsis(),
    TambourDeKui(),
    ParachuteDore(),
    PoigneeDeMain(),
    Paratonnerre(),
    EplucheDonjon(),
    CrocsEnflamees(),
    GlandePineale(),
    OursinDodu(),
    SceauDeLegalisation(),
    MiroirDuRised(),
    SurinCrasseux(),
    BottesDePoncage(),
    BombeDeMidas(),
    CouteauQuiTombe(),
    AvisDeRecherche(),
    CarapaceBleue(),
    JournalDuFutur(),
    BinoclesDeLInventeur(),
    OeilDHorus(),
    OiseauDeMauvaisAugure(),
    FilDuDestin(),
    # --- maj tableur 12 juin 2026 (couleurs) ---
    BourseGarnie(),
    LanterneChromatique(),
    CinqPierresDeNuwa(),
    # --- mode soiree (party.py) : Medailles inter-manches et niveaux de heros ---
    CoupeDesChampions(),
    ParfumDeScandale(),
    ParcheminDXP(),
    PotionDeJouvence(),
]



__all__ = [
            "objets_disponibles",
            "Egide",
            "MainDeMidas",
            "MidasDeBronze",
            "HacheDeGlace",
            "MarteauDeGuerre",
            "FleauDesLiches",
            "EpauletteDuPonceur",
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
            "CasqueACornes",
            "AnkhDeReincarnation",
            "CoffreDuRoiSorcier",
            "CoeurDeDragon",
            "ShotDAdrenaline",
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
            "HarpeCinglante",
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
            "ParcheminDePoncage",
            "AraigneeDomestique",
            "Exterminator",
            "CodexDiabolus",
            "SainteLance",
            "TorcheEnMousse",
            "GrelotDuBouffon",
            "AspisHeracles",
            "BouillonDAmes",
            "ConcentreDeFun",
            "ForgePortative",
            "SacDeConstantinople",
            "TrouNoirPortatif",
            "CalumetDeLaPaix",
            "Zulfikar",
            "AnneauDeGlace",
            "GrenadeSinge",
            "SceptreChangeur",
            # --- synchro tableur juin 2026 ---
            "CoeurDeTarasque",
            "CeintureDuPonceur",
            "LinceulDeResurrection",
            "Imprimante",
            "EpeeVengeresse",
            "DagueVengeresse",
            "TotemDImmunite",
            "CeintureDuNovice",
            "AnneauDuNovice",
            "CapeDuNovice",
            "PommeDAdam",
            "BouclierDuPonceur",
            "TatouageMaudit",
            "PistoletLaser",
            "TrousseDeSecours",
            "ArmureDeMage",
            "BombePirate",
            "AnneauDuVent",
            "BouleDeCristal",
            "CraneDuNecromancien",
            "LanceDeSilence",
            "HacheMystique",
            "ArmureVivante",
            "Donjondex",
            "TapisVolant",
            "MasqueMaudit",
            "ParfumRegenerant",
            "GriffesEclair",
            "PerleRare",
            "PaquetSurprise",
            "BagouzeDuParrain",
            "TaserManuel",
            "BarbecueDuPonceur",
            "RoseDOr",
            "PotionDEscampette",
            "MontreDuLapinBlanc",
            "PorteBoulesDuPonceur",
            "ChevalierePirate",
            "TatouageDuPonceur",
            "PotageImprovise",
            "ClocheDuDejaVu",
            "CapeDInvisibilite",
            "SlipDeLaResurgence",
            "LanterneAbsorbante",
            "ArcDuNeant",
            "ConcoctionInstable",
            "BananeExperimentale",
            "KitDeSoin",
            "CompasDuCapitaine",
            "PotionAuTheVert",
            "UrneEnsorcelee",
            "MainDuCreateur",
            "BotteDePandore",
            "ScotchDuSilencieux",
            "CouteauxDeLancer",
            "PierreDePressentiment",
            "ToupieDuChaos",
            "CoursierVolant",
            "SiegeDeTroie",
            "MiroirDeYata",
            "SceptreDuMaharal",
            "CleAmulette",
            "CleDeSalomon",
            "DagueDeBrutus",
            "RouletteInfernale",
            "DisqueDeVishnu",
            "MasqueDeFer",
            "MainInvisible",
            "EventailMaudit",
            "EpeeDeDamocles",
            "VoileDIsis",
            "TambourDeKui",
            "ParachuteDore",
            "PoigneeDeMain",
            "Paratonnerre",
            "EplucheDonjon",
            "CrocsEnflamees",
            "GlandePineale",
            "OursinDodu",
            "SceauDeLegalisation",
            "MiroirDuRised",
            "SurinCrasseux",
            "BottesDePoncage",
            "BombeDeMidas",
            "CouteauQuiTombe",
            "AvisDeRecherche",
            "CarapaceBleue",
            "JournalDuFutur",
            "BinoclesDeLInventeur",
            "OeilDHorus",
            "OiseauDeMauvaisAugure",
            "FilDuDestin",
        
            "BourseGarnie",
            "LanterneChromatique",
            "CinqPierresDeNuwa",

            "CoupeDesChampions",
            "ParfumDeScandale",
            "ParcheminDXP",
            "PotionDeJouvence",
]
