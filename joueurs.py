from objets import *
from objets import SANS_HOOK_OBJET
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
        self.rejoue = False # doit rejouer, reset en debut de tour
        self.doit_passer = False # a trigger un effet qui le force a passer
        self.passe_son_tour = False # saute completement son tour sans piocher (Lapin Blanc)
        self.monstres_ajoutes_ce_tour = 0
        self.tiebreaker = False
        self.cartes_connues = set()  # cartes du Donjon vues via les objets de divination

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

    def mort(self, log_details):
        self.vivant = False
        self.dans_le_dj = False
        if self.medailles > 0:
            if any(getattr(objet, 'protege_medailles', False) and objet.intact for objet in self.objets):
                log_details.append(f"{self.nom} garde sa medaille (Totem d'immunité) !")
            else:
                log_details.append(f"{self.nom} a perdu une medaille !")
                self.medailles -= 1
            
    
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

    def getScoreActuel(self, log_details):
        current_score = len(self.pile_monstres_vaincus)
        if any(getattr(monstre, 'effet', None) and "GOLD" in monstre.effet for monstre in self.pile_monstres_vaincus):
            current_score += 1

        dummy_log_details = []
        original_score_final = self.score_final
        self.score_final = current_score

        if hasattr(self, 'perso_obj'):
             self.perso_obj.en_score(self, dummy_log_details)
        for objet in self.objets:
            if getattr(objet, 'intact', False):
                objet.en_score(self, dummy_log_details)

        score_calcule_par_effets = self.score_final
        self.score_final = original_score_final
        # log_details.append(f"[debug] Score final de {self.nom} : {score_calcule_par_effets}, original_score_final {original_score_final}")
        return score_calcule_par_effets

    def trier_objets_par_priorite(self):
        self.objets = sorted(self.objets, key=lambda obj: obj.priorite, reverse=True)

    def rollDice(self, Jeu, log_details, jet_voulu=4, reversed=False, rerolled=False): #de base on se considere content avec un 4.
        jet_voulu = min(6,max(1, jet_voulu))
        jet = random.randint(1, 6)
        log_details.append(f"{self.nom} roll un {jet}")
        if hasattr(self, 'perso_obj'):
            jet = self.perso_obj.en_roll(self, jet, jet_voulu, reversed, rerolled, Jeu, log_details)
        
        sans_roll = SANS_HOOK_OBJET['en_roll']
        for objet in self.objets:
            if type(objet) in sans_roll:
                continue
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
        


    def connait_prochaine_carte(self, Jeu):
        """Retourne la prochaine carte du Donjon si le joueur l'a deja vue (Journal du futur,
        Binocles, Pomme d'Adam...), sinon None. L'identite de l'objet carte suffit: si la carte
        vue a ete piochee ou deplacee entre-temps, elle n'est plus 'la prochaine' et on retombe sur None."""
        donjon = Jeu.donjon
        if donjon.vide or not self.cartes_connues:
            return None
        prochaine = donjon.cartes[donjon.ordre[donjon.index]]
        return prochaine if prochaine in self.cartes_connues else None

    def _couverture_objets(self):
        """Types et puissances que les objets intacts du joueur savent gerer (tags)."""
        types_couverts = set()
        puissances_couvertes = set()
        for objet in self.objets:
            if objet.intact:
                types_couverts.update(objet.types_tags)
                puissances_couvertes.update(objet.puissance_tags)
        return types_couverts, puissances_couvertes

    def peut_executer_facilement(self, carte, couverture=None):
        """Heuristique: un objet intact tague pour ce type ou cette puissance peut gerer la carte."""
        types = getattr(carte, 'types', None)
        if types is None:
            return False
        types_couverts, puissances_couvertes = couverture if couverture is not None else self._couverture_objets()
        return carte.puissance in puissances_couvertes or any(t in types_couverts for t in types)

    def deciderDeRejouer(self, Jeu, log_details):
        """IA: decide de repiocher volontairement au lieu de passer son tour."""
        if not self.dans_le_dj or Jeu.donjon.vide or Jeu.traquenard_actif or self.doit_passer:
            return False

        # 1) la prochaine carte est connue (objets de divination): decision informee
        carte_connue = self.connait_prochaine_carte(Jeu)
        if carte_connue is not None:
            if getattr(carte_connue, 'event', False):
                log_details.append(f"{self.nom} sait qu'un évènement arrive et continue de piocher.")
                return True
            if not getattr(carte_connue, 'is_X', False):
                if self.peut_executer_facilement(carte_connue):
                    log_details.append(f"{self.nom} sait que {carte_connue.titre} arrive et peut le gérer: il continue.")
                    return True
                if carte_connue.puissance <= 1 and self.pv_total >= 4:
                    return True
            return False  # la suite est connue et mauvaise: on passe

        # Repioche a l'aveugle: seulement si la pioche est quasi gratuite (aucune carte
        # restante ne fait plus de 2 degats). Encaisser des degats pour du tempo declenche
        # la fuite anticipee et fait perdre plus de points qu'il n'en rapporte.
        # Early-exit: on s'arrete a la premiere carte dangereuse (cas ultra-majoritaire).
        couverture = self._couverture_objets()
        donjon = Jeu.donjon
        for i in donjon.ordre[donjon.index:]:
            c = donjon.cartes[i]
            if getattr(c, 'event', False):
                continue
            d = 10 if c.is_X else c.puissance_initiale
            if c.effet and "ADD_2_DOM" in c.effet:
                d += 2
            if d > 2 and not self.peut_executer_facilement(c, couverture):
                return False

        # 2) objets qui recompensent plusieurs monstres vaincus dans le meme tour
        for objet in self.objets:
            objectif = getattr(objet, 'objectif_multi_kill', 0)
            if objet.intact and objectif:
                besoin = objectif - self.monstres_ajoutes_ce_tour
                if 0 < besoin <= 2 and self.monstres_ajoutes_ce_tour >= 1:
                    log_details.append(f"{self.nom} continue de piocher pour activer {objet.nom}.")
                    return True

        # 3) la pioche est quasi gratuite pour nous: continuer a poncer le Donjon
        log_details.append(f"{self.nom} ne risque plus rien et continue de poncer le Donjon.")
        return True

    def deciderDeFuir(self, Jeu, log_details):
        # --- NOUVELLE Condition : Interdiction de fuir au Tour 1 ---
        # On vérifie l'attribut 'tour' du joueur lui-même
        if self.tour == 1:
            # Pas besoin de vérifier les autres conditions si c'est le tour 1
            # log_details.append(f"--> {self.nom} NE TENTE PAS LA FUITE (Tour 1).")
            return False # On ne fuit jamais au premier tour
        # --- Fin Nouvelle Condition ---

        # Certains objets (Ceinture du Ponceur) interdisent de tenter la fuite avec moins de 6 PV
        if self.pv_total < 6 and any(getattr(objet, 'bloque_fuite_pv_bas', False) and objet.intact for objet in self.objets):
            return False

        # La prochaine carte est connue (objets de divination): decision informee
        carte_connue = self.connait_prochaine_carte(Jeu)
        if carte_connue is not None and not getattr(carte_connue, 'is_X', False):
            if getattr(carte_connue, 'event', False):
                return False  # un evenement nous attend: aucune raison de fuir
            if self.peut_executer_facilement(carte_connue) or carte_connue.puissance <= 2:
                return False  # la prochaine carte est gerable
            if (carte_connue.puissance >= self.pv_total
                    and sum(getattr(o, 'actif', False) and o.intact for o in self.objets) <= 1):
                log_details.append(f"==> {self.nom} sait que {carte_connue.titre} arrive et TENTE LA FUITE.")
                return True

        # Si on est au tour 2 ou plus, on applique la logique précédente :

        # Condition 1: PV faibles et peu d'options actives restantes
        # Certains objets (Ceinture du Ponceur) doivent anticiper la fuite: leurs PV "de decision"
        # sont reduits pour fuir a temps (avant que la fuite ne devienne interdite)
        pv_decision = self.pv_total - sum(getattr(objet, 'malus_pv_decision_fuite', 0)
                                          for objet in self.objets if objet.intact)
        peu_options = sum(getattr(objet, 'actif', False) and getattr(objet, 'intact', False)
                          for objet in self.objets) <= 1
        pv_faible_et_peu_options = peu_options and pv_decision <= self.pv_min_fuite
        if peu_options and not pv_faible_et_peu_options:
            # Risque concret: proportion des cartes restantes du Donjon qui nous tueraient.
            # Seuil 0.25 choisi par balayage: meilleur score moyen/median pose, morts 42% -> 32%
            donjon = Jeu.donjon
            restantes = donjon.ordre[donjon.index:]
            if len(restantes):
                couverture = self._couverture_objets()
                mortelles = 0
                for i in restantes:
                    c = donjon.cartes[i]
                    if getattr(c, 'event', False):
                        continue
                    d = 10 if c.is_X else c.puissance_initiale
                    if c.effet and "ADD_2_DOM" in c.effet:
                        d += 2
                    if d >= self.pv_total and not self.peut_executer_facilement(c, couverture):
                        mortelles += 1
                pv_faible_et_peu_options = mortelles / len(restantes) >= 0.25
        # if pv_faible_et_peu_options:
            #  log_details.append(f"--> {self.nom} Condition Fuite 1 (PV Faible/Opt): VRAI (PV {self.pv_total} <= Seuil {self.pv_min_fuite})")

        # Condition 2: Est-on le dernier joueur encore vivant ?
        joueurs_vivants_compte = sum(1 for j in Jeu.joueurs if j.vivant)
        dernier_joueur_vivant = (joueurs_vivants_compte <= 1 and self.vivant)
        # if dernier_joueur_vivant:
            #  log_details.append(f"--> {self.nom} Condition Fuite 2 (Dernier Vivant): VRAI")

        # Si on est le dernier vivant (et tour > 1), on tente de fuir.
        if dernier_joueur_vivant:
            log_details.append(f"==> {self.nom} DECIDE DE TENTER LA FUITE (car dernier joueur vivant).")
            return True

        # Si on n'est PAS le dernier vivant (et tour > 1), on évalue la fuite pour PV faibles
        if pv_faible_et_peu_options:
            # Vérifier s'il faut continuer à cause d'un fuyard
            force_a_continuer = False
            monstres_fuyard = -1
            a_battre = -1
            fuyard_existe = False
            for autre_joueur in Jeu.joueurs:
                if autre_joueur is not self and autre_joueur.fuite_reussie:
                    monstres_fuyard = autre_joueur.getScoreActuel(log_details)
                    fuyard_existe = True
                    a_battre = max(monstres_fuyard, a_battre)

            if fuyard_existe:
                mes_monstres = self.getScoreActuel(log_details)
                if a_battre > mes_monstres:
                    force_a_continuer = True
                    # log_details.append(f"--> {self.nom} Condition Fuite 3 (Blocage Fuyard): {force_a_continuer} (Un fuyard a {a_battre} MV vs soi {mes_monstres} MV)")
                log_details.append(f"--> {self.nom} DECIDE DE TENTER LA FUITE (Un fuyard a {a_battre} MV, il a {mes_monstres} MV)")
            else: log_details.append(f"--> {self.nom} DECIDE DE TENTER LA FUITE (Aucun score n'a encore ete posé)")
            # Décision basée sur PV faibles ET non-blocage
            if not force_a_continuer:
                # log_details.append(f"==> {self.nom} DECIDE DE TENTER LA FUITE (PV faible/opt et pas de blocage fuyard).")
                return True
            else:
                # log_details.append(f"==> {self.nom} NE TENTE PAS LA FUITE (PV faible/opt mais bloqué par fuyard).")
                return False
        else:
            # Ni dernier vivant (vérifié avant), ni PV faibles (vérifié ici)
            # log_details.append(f"==> {self.nom} NE TENTE PAS LA FUITE (PV ok et pas dernier vivant).")
            return False
        
    def _gerer_pv_bonus(self, objet, log_details):
        """Gère la perte des PV bonus lors de la destruction d'un objet"""
        if objet.pv_bonus:
            self.pv_total -= objet.pv_bonus
            log_details.append(f"L'objet casse {objet.nom} donnait {objet.pv_bonus}PV ca fait ca de moins. PV restant {self.pv_total}PV")

    def decideBriseObjet(self, jeu, log_details):
        """Décide quel objet briser en évitant de se tuer si possible."""
        # On ne garde que les objets intacts
        objets_intacts = [objet for objet in reversed(self.objets) if objet.intact]
        if not objets_intacts:
            return None

        # On cherche un objet qui ne nous tue pas
        for objet in objets_intacts:
            if objet.pv_bonus < self.pv_total:
                objet.destroy(self, jeu, log_details)
                self._gerer_pv_bonus(objet, log_details)
                return objet

        # Si aucun ne convient, on prend le premier (qui est le dernier de la liste originale)
        objets_intacts[0].destroy(self, jeu, log_details)
        self._gerer_pv_bonus(objets_intacts[0], log_details)
        return objets_intacts[0]
        