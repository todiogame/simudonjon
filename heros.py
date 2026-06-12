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
        # reset de l'etat une-fois-par-partie (les instances Perso sont partagees entre les parties)
        self.capacite_utilisee = False
        self.compteur = 0
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
        if carte not in joueur.pile_monstres_vaincus:  # deja vaincue (ex: executee plus tot dans le meme combat)
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


def _suffixe(level):
    return " N2" if level == 2 else ""


class Ninja(Perso):
    def __init__(self, level=1):
        super().__init__("Ninja" + _suffixe(level), 3)
        self.level = level

    def en_fuite(self, joueur, Jeu, log_details):
        # Une fois par partie: jet de fuite +3 (N2: +5) jusqu'a la fin du tour
        if not self.capacite_utilisee:
            self.capacite_utilisee = True
            bonus = 5 if self.level == 2 else 3
            joueur.jet_fuite += bonus
            log_details.append(f"{joueur.nom} ({self.nom}) utilise sa capacité: jet de fuite +{bonus} => {joueur.jet_fuite}.")

class Princesse(Perso):
    def __init__(self, level=1):
        super().__init__("Princesse" + _suffixe(level), 1)
        self.level = level

    def debut_tour(self, joueur, Jeu, log_details):
        # Une fois par partie: pioche un objet (N2: pioche 2, defausse 1)
        if not self.capacite_utilisee:
            self.capacite_utilisee = True
            if self.level == 2 and len(Jeu.objets_dispo) >= 2:
                choix = random.sample(Jeu.objets_dispo, 2)
                garde = max(choix, key=lambda o: o.priorite)
                jete = choix[0] if garde is choix[1] else choix[1]
                Jeu.objets_dispo.remove(garde)
                Jeu.objets_dispo.remove(jete)
                joueur.ajouter_objet(garde)
                log_details.append(f"{joueur.nom} ({self.nom}) pioche 2 objets, garde {garde.nom} et défausse {jete.nom}.")
            else:
                log_details.append(f"{joueur.nom} ({self.nom}) utilise sa capacité pour piocher un objet")
                self.piocheItem(joueur, Jeu, log_details)


class MercenaireOrc(Perso):
    def __init__(self, level=1):
        # Pas de capacite, juste des PV (N1: 5, N2: 7)
        super().__init__("Mercenaire Orc" + _suffixe(level), 7 if level == 2 else 5)
        self.level = level


class ChevalierDragon(Perso):
    def __init__(self, level=1):
        super().__init__(nom="Chevalier Dragon" + _suffixe(level), pv_bonus=3)
        self.level = level

    def combat_effet(self, joueur, carte, Jeu, log_details):
        # N1: execute les Dragons (et les garde) si pas de Dragon dans la pile. N2: sans condition.
        if "Dragon" in getattr(carte, 'types', []) and not Jeu.traquenard_actif and not carte.executed:
            if self.level == 2 or not any("Dragon" in m.types for m in joueur.pile_monstres_vaincus):
                self.execute(joueur, carte, log_details)

class PersoUseless2PV(Perso):
    def __init__(self):
        # Le PV de base (5) est géré par la classe Joueur
        super().__init__("Perso Useless 2PV", 2)

class PersoUseless3PV(Perso):
    def __init__(self):
        # Le PV de base (5) est géré par la classe Joueur
        super().__init__("Perso Useless 3PV", 3)

class Tricheur(Perso):
    def __init__(self, level=1):
        super().__init__("Tricheur" + _suffixe(level), 3)
        self.level = level

    def debut_tour(self, joueur, Jeu, log_details):
        # Une fois par partie: pioche une carte cachee (N2: deux). Si monstre -> sa pile, sinon repose.
        # (simplification IA : resolution immediate au lieu de garder la carte cachee)
        if not self.capacite_utilisee and not Jeu.donjon.vide:
            self.capacite_utilisee = True
            nb = 2 if self.level == 2 else 1
            a_reposer = []
            for _ in range(nb):
                if Jeu.donjon.vide:
                    break
                c = Jeu.donjon.prochaine_carte()
                if hasattr(c, 'types') and not getattr(c, 'event', False):
                    joueur.ajouter_monstre_vaincu(c)
                    log_details.append(f"{joueur.nom} ({self.nom}) triche et ajoute {c.titre} à sa pile !")
                else:
                    a_reposer.append(c)
            for c in reversed(a_reposer):
                Jeu.donjon.rajoute_en_haut_de_la_pile(c)
                log_details.append(f"{joueur.nom} ({self.nom}) repose {c.titre} sur le Donjon.")

class DocteurDePeste(Perso):
    def __init__(self, level=1):
        super().__init__(nom="DocteurDePeste" + _suffixe(level), pv_bonus=3 if level == 2 else 2)
        self.level = level

    def combat_effet(self, joueur, carte, Jeu, log_details):
        if "Rat" in getattr(carte, 'types', []) and not Jeu.traquenard_actif and not carte.executed:
            self.execute(joueur, carte, log_details)

    def en_fuite(self, joueur, Jeu, log_details):
        # N2: jet de fuite +1 par Rat dans la pile
        if self.level == 2:
            rats = sum(1 for m in joueur.pile_monstres_vaincus if "Rat" in m.types)
            if rats:
                joueur.jet_fuite += rats
                log_details.append(f"{joueur.nom} ({self.nom}) gagne +{rats} au jet de fuite grâce à ses Rats => {joueur.jet_fuite}.")

class RoiSorcier(Perso):
    def __init__(self, level=1):
        super().__init__("Roi Sorcier" + _suffixe(level), 2)
        self.level = level
        self.seuil = 3 if level == 2 else 4

    def subit_dommages_effet(self,joueur_proprietaire, joueur, carte, Jeu, log_details):
        # seulement le joueur avant ou apres lui dans l'ordre du tour
        if carte.dommages >= self.seuil and joueur is not joueur_proprietaire:
            idx_p = Jeu.joueurs.index(joueur_proprietaire)
            idx_j = Jeu.joueurs.index(joueur)
            n = len(Jeu.joueurs)
            if (idx_j - idx_p) % n in (1, n - 1):
                self.gagnePV(1, joueur_proprietaire, log_details)

class InventeurGenial(Perso):
    def __init__(self, level=1):
        super().__init__(nom="Inventeur génial" + _suffixe(level), pv_bonus=3, modificateur_de=0)
        self.level = level  # N1: 1 utilisation par partie, N2: 2

    def combat_effet(self, joueur, carte, Jeu, log_details):
        # Vérifier si capacité dispo et conditions remplies
        if self.compteur < self.level:
            # Trouver les objets brisés (non intacts)
            objets_brises = [o for o in joueur.objets if not getattr(o, 'intact', True)]

            # Condition: au moins 2 objets brisés
            if len(objets_brises) >= 2:
                # Décision IA : on utilise dès que possible
                self.compteur += 1
                log_details.append(f"{joueur.nom} ({self.nom}) utilise sa capacité ({self.compteur}/{self.level}).")

                # Choisir 2 objets brisés au hasard à défausser
                objets_a_defausser = random.sample(objets_brises, 2)
                noms_defausse = [o.nom for o in objets_a_defausser]
                log_details.append(f"--> Défausse {noms_defausse}.")

                # Les retirer de l'inventaire du joueur
                for obj in objets_a_defausser:
                    joueur.objets.remove(obj)

                self.piocheItem(joueur, Jeu, log_details)



class Flutiste(Perso):
    def __init__(self, level=1):
        super().__init__(nom="Flutiste" + _suffixe(level), pv_bonus=3 if level == 2 else 2)
        self.level = level
        self.dommages_suppl = 2 if level == 2 else 1

    def rencontre_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        if "Gobelin" in carte.types and joueur_proprietaire.dans_le_dj:
            carte.dommages += self.dommages_suppl
            log_details.append(f"{carte.titre} est booste de {self.dommages_suppl} dommages par {joueur_proprietaire.nom} ({self.nom})")

    def rules(self, joueur, carte, Jeu, log_details):
        return ("Gobelin" in carte.types) and not Jeu.traquenard_actif

    def combat_effet(self, joueur, carte, Jeu, log_details):
        self.execute(joueur, carte, log_details)
        self.gagnePV(1, joueur, log_details)

class SavantFou(Perso):
    def __init__(self, level=1):
        super().__init__("Savant Fou" + _suffixe(level), 3)
        self.level = level
        self.seuil = 4 if level == 2 else 5
        self.pv_gagne_ce_tour = False

    def debut_tour(self, joueur, Jeu, log_details):
        self.pv_gagne_ce_tour = False

    def vaincu_effet(self, joueur_proprietaire, joueur, carte, Jeu, log_details):
        # Sur 5+ (N2: 4+), gagnez 1 PV (maximum 1 PV par tour)
        if joueur.nom == joueur_proprietaire.nom and not self.pv_gagne_ce_tour:
            jet_savant = joueur.rollDice(Jeu, log_details, self.seuil)
            if jet_savant >= self.seuil:
                self.gagnePV(1, joueur_proprietaire, log_details)
                self.pv_gagne_ce_tour = True

class Avatar(Perso):
    def __init__(self, level=1):
        super().__init__(nom="Avatar" + _suffixe(level), pv_bonus=3 if level == 2 else 2)
        self.level = level

    def combat_effet_late(self, joueur, carte, Jeu, log_details):
        # Une fois par partie: execute et defausse un monstre (N2: execute et le garde)
        if not self.capacite_utilisee and not Jeu.traquenard_actif and not carte.executed and carte.dommages > (joueur.pv_total / 2) :
            self.capacite_utilisee = True
            if self.level == 2:
                self.execute(joueur, carte, log_details)
            else:
                self.executeEtDefausse(joueur, carte, Jeu, log_details)

class Berserker(Perso):
    def __init__(self, level=1):
        super().__init__("Berserker" + _suffixe(level), 3)
        self.level = level

    def survie_effet(self, joueur, carte, Jeu, log_details):
        # Une fois par partie, survivez avec 1 PV (N2: 3 PV)
        if not self.capacite_utilisee and joueur.pv_total <= 0:
            self.capacite_utilisee = True
            self.survit(3 if self.level == 2 else 1, joueur, carte, log_details)

class Prophete(Perso):
    def __init__(self, level=1):
        super().__init__("Prophète" + _suffixe(level), 2)
        self.level = level
    def debut_tour(self, joueur, Jeu, log_details):
        # N2: deux fois par partie, regarde les 2 prochaines cartes et peut les defausser ou les reposer.
        # IA: utilise quand ses PV sont bas, defausse les monstres qui le tueraient.
        if self.level == 2 and self.compteur < 2 and joueur.pv_total <= 4 and not Jeu.donjon.vide:
            self.compteur += 1
            log_details.append(f"{joueur.nom} ({self.nom}) consulte les 2 prochaines cartes du Donjon ({self.compteur}/2).")
            a_reposer = []
            for _ in range(2):
                if Jeu.donjon.vide:
                    break
                c = Jeu.donjon.prochaine_carte()
                if hasattr(c, 'types') and not getattr(c, 'event', False) and c.puissance >= joueur.pv_total:
                    Jeu.defausse.append(c)
                    log_details.append(f"{joueur.nom} ({self.nom}) défausse {c.titre} (trop dangereux).")
                else:
                    a_reposer.append(c)
            for c in reversed(a_reposer):
                Jeu.donjon.rajoute_en_haut_de_la_pile(c)
                joueur.cartes_connues.add(c)  # il sait ce qui arrive (exploite par l'IA de fuite/repioche)
        elif self.level == 1 and self.compteur < 2 and joueur.pv_total <= 6 and not Jeu.donjon.vide:
            # N1: deux fois par partie, regarde secretement les 2 prochaines cartes
            # (memorisees dans cartes_connues, exploitees par l'IA de fuite/repioche)
            self.compteur += 1
            donjon = Jeu.donjon
            for i in range(donjon.index, min(donjon.index + 2, donjon.nb_cartes)):
                joueur.cartes_connues.add(donjon.cartes[donjon.ordre[i]])
            log_details.append(f"{joueur.nom} ({self.nom}) consulte secrètement les 2 prochaines cartes ({self.compteur}/2).")

class Shaman(Perso):
    def __init__(self, level=1):
        super().__init__("Shaman" + _suffixe(level), 3)
        self.level = level

    def en_roll(self, joueur, jet, jet_voulu, reversed, rerolled, Jeu, log_details):
        # N2: quand vous obtenez un 6, gagnez 1 PV
        if self.level == 2 and jet == 6:
            self.gagnePV(1, joueur, log_details)
        # Quand vous obtenez 1 ou 2 avec le de, vous pouvez le relancer une fois
        if not rerolled and not reversed and jet <= 2 and jet < jet_voulu:
            log_details.append(f"{joueur.nom} ({self.nom}) relance son dé de {jet}.")
            return joueur.rollDice(Jeu, log_details, jet_voulu, reversed, True)
        return jet

class LapinBlanc(Perso):
    def __init__(self, level=1):
        super().__init__("Lapin Blanc" + _suffixe(level), 4 if level == 2 else 3)
        self.level = level

    def debut_tour(self, joueur, Jeu, log_details):
        if self.level == 2:
            # N2: au debut des 3 premiers tours, si la pile est vide, regarde la 1ere carte
            # du Donjon et peut passer son tour (enfin une utilisation de l'info !)
            if joueur.tour <= 3 and not joueur.pile_monstres_vaincus and not Jeu.donjon.vide:
                prochaine = Jeu.donjon.cartes[Jeu.donjon.ordre[Jeu.donjon.index]]
                if hasattr(prochaine, 'types') and not getattr(prochaine, 'event', False) and prochaine.puissance >= joueur.pv_total:
                    joueur.passe_son_tour = True
                    log_details.append(f"{joueur.nom} ({self.nom}) voit {prochaine.titre} arriver et passe son tour.")
        elif joueur.tour == 1:
            # N1: Sautez votre premier tour. (le coup d'oeil tour 2 est de l'info pure, non simulee)
            joueur.passe_son_tour = True
            log_details.append(f"{joueur.nom} ({self.nom}) saute son premier tour.")

class Ponceur(Perso):
    def __init__(self, level=1):
        super().__init__("Ponceur" + _suffixe(level), 4)
        self.level = level
    # "vous entrez en premier dans le Donjon" : l'ordre de tour n'est pas simule (ordre aleatoire)

    def _bonus_si_en_tete(self, joueur, Jeu, log_details):
        # si vous avez vaincu le plus de monstres, gagnez 1 PV
        autres = [len(j.pile_monstres_vaincus) for j in Jeu.joueurs if j is not joueur]
        if autres and len(joueur.pile_monstres_vaincus) > max(autres):
            self.gagnePV(1, joueur, log_details)

    def debut_tour(self, joueur, Jeu, log_details):
        if self.level == 1:
            self._bonus_si_en_tete(joueur, Jeu, log_details)

    def fin_tour(self, joueur, Jeu, log_details):
        if self.level == 2:
            self._bonus_si_en_tete(joueur, Jeu, log_details)

class BeteDeLEvenement(Perso):
    def __init__(self, level=1):
        super().__init__("Bête de l'Evénement" + _suffixe(level), 3)
        self.level = level
        self.ignore_cout_evenements = True  # ne defausse pas de monstre a cause des evenements

    def debut_tour(self, joueur, Jeu, log_details):
        # Une fois par partie, remet le dernier evenement de la defausse sur le Donjon (N2: au choix)
        # IA : seulement si cet evenement est benefique
        if not self.capacite_utilisee:
            bons = ("HEAL", "SHOP", "INJECTION", "REPAIR", "FORTUNE_WHEEL")
            events = [c for c in Jeu.defausse if getattr(c, 'event', False)]
            if self.level == 2:
                candidats = [c for c in events if c.effet in bons]
                cible = min(candidats, key=lambda c: bons.index(c.effet)) if candidats else None
            else:
                cible = events[-1] if events and events[-1].effet in bons else None
            if cible:
                self.capacite_utilisee = True
                Jeu.defausse.remove(cible)
                Jeu.donjon.rajoute_en_haut_de_la_pile(cible)
                log_details.append(f"{joueur.nom} ({self.nom}) remet {cible.titre} sur le Donjon.")

# --- Table de dispatch des hooks (optimisation, voir objets.py) ---------------
# NB: debut_partie n'y figure pas car la version de base fait le reset d'etat
# (elle doit TOUJOURS etre appelee).
from objets import _table_sans_hook
_HOOKS_PERSO = {
    'en_rencontre': ('en_rencontre', 'rencontre_effet'),
    'en_rencontre_event': ('en_rencontre_event', 'rencontre_event_effet'),
    'en_vaincu': ('en_vaincu', 'vaincu_effet'),
    'en_subit_dommages': ('en_subit_dommages', 'subit_dommages_effet'),
    'en_mort': ('en_mort', 'mort_effet'),
    'en_survie': ('en_survie', 'survie_effet'),
    'en_combat': ('combat_effet',),
    'en_combat_late': ('combat_effet_late',),
    'en_roll': ('en_roll',),
    'en_fuite': ('en_fuite',),
    'debut_tour': ('debut_tour',),
    'fin_tour': ('fin_tour',),
}
SANS_HOOK_PERSO = _table_sans_hook(Perso, _HOOKS_PERSO)

_classes_persos = [
    Ninja,
    Princesse,
    MercenaireOrc,
    ChevalierDragon,
    Tricheur,
    DocteurDePeste,
    RoiSorcier,
    InventeurGenial,
    Flutiste,
    SavantFou,
    Avatar,
    Berserker,
    Prophete,
    Shaman,
    LapinBlanc,
    Ponceur,
    BeteDeLEvenement,
]

# chaque perso existe en niveau 1 et en niveau 2 ("... N2")
persos_disponibles = [cls(level) for level in (1, 2) for cls in _classes_persos]

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
    "SavantFou",
    "Avatar",
    "Berserker",
    "Prophete",
    "Shaman",
    "LapinBlanc",
    "Ponceur",
    "BeteDeLEvenement",
    # "PersoUseless2PV",
    # "PersoUseless3PV",
]
