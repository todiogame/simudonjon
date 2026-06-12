from objets import *
from objets import SANS_HOOK_OBJET
import math
import random

# Mode soiree (party.py) : prudence des detenteurs de Medailles (mourir en coute une).
# Sans Medaille (donjon.py, draft.py), ces constantes sont sans effet.
# (utilisees par l'ancienne politique de fuite a seuils, politique_fuite='seuils')
PRUDENCE_PV_PAR_MEDAILLE = 2        # le seuil de PV declenchant la fuite monte d'autant par Medaille
PRUDENCE_RISQUE_PAR_MEDAILLE = 0.05 # la part de cartes mortelles toleree baisse d'autant par Medaille

# Politique de fuite par esperance (politique_fuite='ev', la politique par defaut) :
# "fuir ou piocher" est un probleme d'arret optimal, resolu par programmation dynamique
# sur la composition exacte du Donjon restant, le long d'une trajectoire de PV attendue.
# Les valeurs sont en points de score equivalents ; mourir coute le score deja pose,
# plus une Medaille (mode soiree) et un petit bonus de survie.
VALEUR_MEDAILLE_PTS = 6.0   # cout en points d'une Medaille perdue a la mort
VALEUR_SURVIE_PTS = 1.0     # valeur de survivre au-dela du score (heros N2, egalites...)
BONUS_PONCEUR_PTS = 1.5     # finir le Donjon vivant exclut les fuyards du decompte
FUITE_EV_HORIZON = 10       # nb max de pioches futures considerees par la DP
EFFICACITE_OPTION = 0.8     # chance qu'un objet actif de combat/survie neutralise
                            # une carte mortelle (au-dela des tags type/puissance)
TAUX_GAIN_PAR_PIOCHE = 0.7  # points qu'un adversaire encore dans le Donjon marquera
                            # par pioche restante (projection du score a battre)

# codes d'effets pour le profil de Donjon de la politique EV (les comparaisons de
# chaines dans la boucle chaude coutaient cher ; le profil statique est mis en
# cache sur chaque carte sous _profil_ev)
(_C_KRAKEN, _C_ANGE, _C_SLEEPING, _C_MEDAIL, _C_MIMIC, _C_SINGES, _C_FAUCHEUSE,
 _C_CHAROGNARD, _C_MIROIR, _C_NOOB, _C_LORD, _C_MAUDIT, _C_ARRA, _C_GOLD,
 _C_RAT, _C_TROLL) = range(1, 17)
_PROFIL_CODES = {
    "KRAKEN": _C_KRAKEN, "GUARDIAN_ANGEL": _C_ANGE, "SLEEPING": _C_SLEEPING,
    "MEDAIL": _C_MEDAIL, "MIMIC": _C_MIMIC, "MONKEY_TEAM": _C_SINGES,
    "REAPER": _C_FAUCHEUSE, "SCAVENGER": _C_CHAROGNARD, "MIROIR": _C_MIROIR,
    "NOOB": _C_NOOB, "LORD": _C_LORD, "MAUDIT": _C_MAUDIT, "ARRA": _C_ARRA,
    "GOLD": _C_GOLD, "ADD_2_DOM": _C_RAT, "TROLL": _C_TROLL,
}

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
        self.partie_joueurs = None   # tous les joueurs de la partie (pose par l'ordonnanceur, pour le Parfum de Scandale)

    def ajouter_objet(self, objet):
        self.objets.append(objet)
        self.pv_total += objet.pv_bonus
        self.trier_objets_par_priorite() # maintenir les objets tries dans le bon ordre d'utilisation

    def appliquer_panoplies(self, log_details):
        # Panoplie : +2 PV par groupe de 3 objets de meme couleur au debut de la partie.
        # Bonus fige : il n'est ni perdu ni gagne quand des objets sont detruits/pioches
        # en cours de partie. Cumulable (2 panoplies, ou 6 objets de la meme couleur = +4).
        compte = {}
        for objet in self.objets:
            if objet.couleur:
                compte[objet.couleur] = compte.get(objet.couleur, 0) + 1
        bonus = 2 * sum(n // 3 for n in compte.values())
        if bonus:
            self.pv_total += bonus
            log_details.append(f"Panoplie ! {self.nom} a 3 objets de même couleur et gagne {bonus} PV (total {self.pv_total}).")

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
        self.perdre_medaille(log_details, mort=True)

    def perdre_medaille(self, log_details, mort=False):
        """Perte d'une Medaille (mort, Rongeur de medaille...). Le Totem d'immunité ne
        protège que contre la perte à la mort ; un adversaire vivant avec un Parfum de
        Scandale intact récupère directement la Medaille perdue."""
        if self.medailles <= 0:
            return
        if mort and any(getattr(objet, 'protege_medailles', False) and objet.intact for objet in self.objets):
            log_details.append(f"{self.nom} garde sa medaille (Totem d'immunité) !")
            return
        self.medailles -= 1
        log_details.append(f"{self.nom} a perdu une medaille ! ({self.medailles} restante(s))")
        for autre in (self.partie_joueurs or []):
            if autre is not self and autre.vivant and any(
                    getattr(objet, 'vole_medailles_perdues', False) and objet.intact for objet in autre.objets):
                autre.medailles += 1
                log_details.append(f"{autre.nom} récupère la medaille perdue (Parfum de Scandale) ! ({autre.medailles})")
                break

    def changer_niveau_perso(self, niveau, log_details):
        """Parchemin d'XP / Potion de Jouvence : le héros passe (ou reste) au niveau demandé.
        Instance fraîche (la capacité une-fois-par-partie redevient disponible) ;
        pv_base suit le nouveau niveau, les PV en jeu ne bougent que via le soin
        explicite de la carte qui appelle ce changement."""
        if getattr(self.perso_obj, 'level', 1) == niveau:
            return
        try:
            nouveau = type(self.perso_obj)(niveau)
        except TypeError:
            return  # héros sans variante de niveau
        self.perso_obj = nouveau
        self.personnage_nom = nouveau.nom
        self.pv_base = nouveau.pv_bonus
        log_details.append(f"Le héros de {self.nom} devient {self.personnage_nom}.")


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

    def _degats_attendus(self, carte, Jeu):
        """Dégâts anticipés d'une carte du Donjon pour CE joueur (scans de fuite/repioche).
        Tient compte des effets liés aux Médailles (mode soirée de party.py)."""
        if carte.is_X:
            if carte.effet and "MEDAIL" in carte.effet:
                # Rongeur de medaille : puissance = total des Médailles en jeu
                return sum(j.medailles for j in Jeu.joueurs)
            return 10
        d = carte.puissance_initiale
        if carte.effet:
            if "NOOB" in carte.effet and self.medailles:
                return 2  # Empaleur d'imprudent : puissance 2 si on a une Médaille
            if "ADD_2_DOM" in carte.effet:
                d += 2
            if "LORD" in carte.effet:
                d += 2 * self.medailles  # Saigneur Vampire : +2 dommages par Médaille
        return d

    def _couverture_objets(self):
        """Types et puissances que les objets intacts du joueur savent gerer (tags).
        Mis en cache tant que la liste d'objets intacts ne change pas (boucle chaude)."""
        signature = tuple(id(o) for o in self.objets if o.intact)
        cache = self.__dict__.get('_couverture_cache')
        if cache is not None and cache[0] == signature:
            return cache[1]
        types_couverts = set()
        puissances_couvertes = set()
        for objet in self.objets:
            if objet.intact:
                types_couverts.update(objet.types_tags)
                puissances_couvertes.update(objet.puissance_tags)
        resultat = (types_couverts, puissances_couvertes)
        self._couverture_cache = (signature, resultat)
        return resultat

    def peut_executer_facilement(self, carte, couverture=None):
        """Heuristique: un objet intact tague pour ce type ou cette puissance peut gerer la carte."""
        if getattr(carte, 'non_executable', False):
            return False  # Troll
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
            if self._degats_attendus(c, Jeu) > 2 and not self.peut_executer_facilement(c, couverture):
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

    def _nb_options_combat(self):
        # Objets actifs intacts qui peuvent reellement proteger: hook de combat ou
        # de survie. Les actifs sans aucun des deux (Parachute dore, Potion
        # d'escampette, Pelle du Fossoyeur...) ou marques non_combattant (usage
        # trop situationnel) ne protegent pas: les compter retardait la fuite et
        # faisait mourir l'IA.
        return sum(1 for o in self.objets
                   if o.actif and o.intact
                   and not getattr(o, 'non_combattant', False)
                   and (type(o) not in SANS_HOOK_OBJET['en_combat']
                        or type(o) not in SANS_HOOK_OBJET['en_survie']))

    def _score_rapide(self):
        """Score actuel approxime (sans les effets en_score des objets) : pour la
        boucle chaude de la politique EV, ou getScoreActuel serait trop couteux."""
        s = len(self.pile_monstres_vaincus)
        if any(m.effet == "GOLD" for m in self.pile_monstres_vaincus):
            s += 1
        return s

    def _profil_cartes_restantes(self, Jeu):
        """Profil probabiliste des cartes restantes du Donjon pour CE joueur.
        Retourne (profils, n, poids_events) ou profils agrege les cartes par issue
        identique : {(degats, puissance_fuite, gain, peut_tuer): poids}. La puissance
        des cartes X est anticipee comme a la rencontre ; 'gain' est en points de score
        (2 pour le Golem d'or, 0 pour le Gobelin Fantome et l'Arracheur qui reprend
        une carte) ; la Faucheuse divise les PV et n'est donc jamais letale."""
        donjon = Jeu.donjon
        types_couverts, puissances_couvertes = self._couverture_objets()
        total_medailles = sum(j.medailles for j in Jeu.joueurs)
        nb_dans_dj = sum(1 for j in Jeu.joueurs if j.dans_le_dj)
        nb_intacts = sum(1 for o in self.objets if o.intact)
        pile = self.pile_monstres_vaincus
        medailles = self.medailles
        profils = {}
        poids_events = 0.0
        get = profils.get
        cartes = donjon.cartes
        restantes = donjon.ordre[donjon.index:].tolist()  # ints natifs (boucle chaude)
        kraken_refusable = not Jeu.kraken_vu and 10 not in puissances_couvertes
        ange_refusable = 8 not in puissances_couvertes

        for i in restantes:
            c = cartes[i]
            # profil statique par carte, mis en cache sur l'instance (boucle chaude) :
            # (est_event, code d'effet, puissance initiale, types initiaux)
            pstat = c.__dict__.get('_profil_ev')
            if pstat is None:
                est_event = getattr(c, 'event', False)
                if est_event:
                    pstat = (True, 0, 0, ())
                else:
                    code = _PROFIL_CODES.get(c.effet or "", 0)
                    p_init = c.puissance_initiale
                    if code == 0 and c.is_X:
                        p_init = 10  # carte X sans estimation dediee : forfait prudent
                    pstat = (False, code, p_init, tuple(c.types_initiaux))
                c._profil_ev = pstat
            est_event, code, p_est, types_init = pstat
            if est_event:
                poids_events += 1.0
                continue
            if code:
                # cartes refusables sans combat (la tentative de fuite, elle, se joue
                # contre leur puissance pleine avant de pouvoir les remettre/defausser)
                if code == _C_KRAKEN and kraken_refusable:
                    cle = (0, 10, 0.0, False)
                    profils[cle] = get(cle, 0.0) + 1.0
                    continue
                if code == _C_ANGE and ange_refusable:
                    cle = (0, 8, 0.0, False)
                    profils[cle] = get(cle, 0.0) + 1.0
                    continue
                if code == _C_SLEEPING:
                    # le jet a lieu a la rencontre : 50% puissance 9, 50% puissance 0
                    for p_x, poids in ((9, 0.5), (0, 0.5)):
                        executable = (p_x in puissances_couvertes
                                      or not types_couverts.isdisjoint(types_init))
                        cle = (0 if executable else p_x, p_x, 1.0, not executable)
                        profils[cle] = get(cle, 0.0) + poids
                    continue
                # puissance attendue a la rencontre (les X se calculent a la pioche)
                if code == _C_MEDAIL:
                    p_est = total_medailles
                elif code == _C_MIMIC:
                    p_est = nb_intacts
                elif code == _C_SINGES:
                    p_est = 2 * nb_dans_dj
                elif code == _C_FAUCHEUSE:
                    p_est = self.pv_total // 2
                elif code == _C_CHAROGNARD:
                    p_est = len(pile)
                elif code == _C_MIROIR:
                    p_est = pile[-1].puissance if pile else 0
                elif code == _C_TROLL:
                    p_est = pile[0].puissance if pile else 0  # copie le DESSOUS de la pile
            # le Troll ne peut pas etre execute, quels que soient nos objets
            if code != _C_TROLL and (p_est in puissances_couvertes
                                     or not types_couverts.isdisjoint(types_init)):
                cle = (0, p_est, 2.0 if code == _C_GOLD else 1.0, False)
                profils[cle] = get(cle, 0.0) + 1.0
                continue
            degats = p_est
            gain = 1.0
            if code:
                if code == _C_RAT:
                    degats += 2
                elif code == _C_LORD:
                    degats += 2 * medailles
                elif code == _C_NOOB and medailles:
                    degats = 2  # "inflige seulement 2 dommages" (la puissance reste 7)
                elif code == _C_GOLD:
                    gain = 2.0
                elif code == _C_MAUDIT or code == _C_ARRA:
                    gain = 0.0  # defausse apres victoire / reprend le dessus de la pile
            cle = (degats, p_est, gain, code != _C_FAUCHEUSE)
            profils[cle] = get(cle, 0.0) + 1.0
        return profils, len(restantes), poids_events

    def _decision_fuite_ev(self, Jeu):
        """Fuir maintenant ou continuer ? On compare par DP F (tenter la fuite a chaque
        tour jusqu'a reussite) et V (piocher puis re-decider), sur la composition exacte
        du Donjon restant. La fuite se joue d6+modificateurs contre la puissance de la
        carte piochee : echouer = la combattre, comme dans le moteur.
        La letalite est evaluee aux PV ACTUELS, sans trajectoire projetee : la decision
        est re-evaluee a chaque tour, et projeter une baisse deterministe des PV detruit
        la valeur d'option du re-choix (le modele fuyait des 12 PV)."""
        donjon = Jeu.donjon
        n = donjon.nb_cartes - donjon.index
        if n <= 0:
            return False
        # Court-circuit (boucle chaude) : borne superieure des degats encore possibles ;
        # si nos PV la depassent, aucune carte ne peut nous tuer et on ne fuit jamais.
        total_medailles = sum(j.medailles for j in Jeu.joueurs)
        nb_dans_dj = sum(1 for j in Jeu.joueurs if j.dans_le_dj) or 1
        borne_degats = max(11, total_medailles, len(self.pile_monstres_vaincus),
                           sum(1 for o in self.objets if o.intact),
                           2 * nb_dans_dj) + 2 * self.medailles
        if self.pv_total > borne_degats:
            return False
        # Second filtre : F > V exige une carte a la fois mortelle ET esquivable au jet
        # (puissance <= 6+mod), sauf cas extreme d'un gros score a verrouiller face a
        # des tueurs inesquivables. Hors de ces deux cas, continuer domine : on
        # s'epargne le profilage du deck (boucle chaude).
        mod = self.calculer_modificateurs()
        if (self.pv_total > 6 + mod + max(2, 2 * self.medailles)
                and self._score_rapide() < 6):
            return False

        profils, n, poids_events = self._profil_cartes_restantes(Jeu)
        if not n:
            return False
        # mes pioches restantes : le Donjon est partage entre les joueurs encore dedans
        horizon = min(FUITE_EV_HORIZON, max(1, -(-n // nb_dans_dj)))
        masse_mortelle = sum(w for (degats, _, _, peut_tuer), w in profils.items()
                             if peut_tuer and degats >= self.pv_total) / n
        if masse_mortelle == 0.0:
            return False  # rien ne peut nous tuer : continuer domine toujours la fuite

        # Position competitive : seul le meilleur score compte. Un score verrouille en
        # fuyant ne vaut que s'il bat la table (en retard : fuir = perdre quand meme,
        # mourir ne coute guere plus ; en tete : mourir coute la victoire probable).
        score_actuel = self._score_rapide()
        meilleur_adverse = 0.0
        for j in Jeu.joueurs:
            if j is self or not j.vivant:
                continue
            s_j = j._score_rapide()
            if j.dans_le_dj:
                s_j += TAUX_GAIN_PAR_PIOCHE * n / nb_dans_dj  # ses pioches restantes
            meilleur_adverse = max(meilleur_adverse, s_j)
        poids_verrou = 1.0 / (1.0 + math.exp(-(score_actuel - meilleur_adverse) / 2.0))

        # cout de la mort, en points de score (relatif a une fuite reussie : score garde)
        cout_mort = VALEUR_SURVIE_PTS + score_actuel * poids_verrou
        if self.medailles and not any(getattr(o, 'protege_medailles', False) and o.intact
                                      for o in self.objets):
            cout_mort += VALEUR_MEDAILLE_PTS

        # Les objets actifs de combat/survie sans tags (potions, armes a usage unique...)
        # peuvent neutraliser une carte mortelle chacun : on couvre une fraction des
        # rencontres mortelles attendues sur l'horizon, avec une efficacite forfaitaire.
        couverture_options = min(1.0, EFFICACITE_OPTION * self._nb_options_combat()
                                 / (masse_mortelle * horizon))

        # quantites par pioche (stationnaires) : esperance immediate et masse qui reste
        piocher_imm = fuir_imm = 0.0
        rester_p = rester_f = poids_events / n  # un event ne coute rien et on reste,
        for (degats, puissance, gain, peut_tuer), w in profils.items():  # fuite gaspillee
            p = w / n
            p_esc = min(1.0, max(0.0, (7 + mod - puissance) / 6.0))
            if peut_tuer and degats >= self.pv_total:
                # part neutralisee par un objet (executee : gain), part mortelle
                c = couverture_options
                issue = c * gain - (1.0 - c) * cout_mort
                piocher_imm += p * issue
                rester_p += p * c
                fuir_imm += p * (1.0 - p_esc) * issue
                rester_f += p * (1.0 - p_esc) * c
            else:
                piocher_imm += p * gain
                rester_p += p
                fuir_imm += p * (1.0 - p_esc) * gain
                rester_f += p * (1.0 - p_esc)

        V = BONUS_PONCEUR_PTS  # vivant au bout du Donjon : les fuyards sont exclus du decompte
        F = 0.0                # sorti du Donjon : on ne marque plus rien
        for _ in range(horizon):
            W = max(F, V)
            V = piocher_imm + rester_p * W
            F = fuir_imm + rester_f * W
        return F > V

    def _decision_fuite_seuils(self, Jeu):
        """Ancienne politique a seuils (conservee pour comparaison, politique_fuite='seuils')."""
        # Certains objets (Ceinture du Ponceur) doivent anticiper la fuite: leurs PV "de decision"
        # sont reduits pour fuir a temps (avant que la fuite ne devienne interdite)
        # Mode soiree: mourir avec des Medailles en coute une, on fuit donc plus tot.
        pv_decision = self.pv_total - sum(getattr(objet, 'malus_pv_decision_fuite', 0)
                                          for objet in self.objets if objet.intact)
        seuil_pv = self.pv_min_fuite + PRUDENCE_PV_PAR_MEDAILLE * self.medailles
        if self._nb_options_combat() > 1:
            return False
        if pv_decision <= seuil_pv:
            return True
        # Risque concret: proportion des cartes restantes du Donjon qui nous tueraient.
        # Seuil 0.25 choisi par balayage: meilleur score moyen/median pose, morts 42% -> 32%
        # (abaisse par Medaille detenue : un detenteur prend moins de risques)
        donjon = Jeu.donjon
        restantes = donjon.ordre[donjon.index:]
        if not len(restantes):
            return False
        couverture = self._couverture_objets()
        mortelles = 0
        for i in restantes:
            c = donjon.cartes[i]
            if getattr(c, 'event', False):
                continue
            if (self._degats_attendus(c, Jeu) >= self.pv_total
                    and not self.peut_executer_facilement(c, couverture)):
                mortelles += 1
        seuil_risque = max(0.10, 0.25 - PRUDENCE_RISQUE_PAR_MEDAILLE * self.medailles)
        return mortelles / len(restantes) >= seuil_risque

    politique_fuite = 'ev'  # attribut de classe : 'ev' (esperance) ou 'seuils' (ancienne)

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
                    and self._nb_options_combat() <= 1):
                log_details.append(f"==> {self.nom} sait que {carte_connue.titre} arrive et TENTE LA FUITE.")
                return True

        # Dernier joueur encore vivant : fuir verrouille la victoire.
        joueurs_vivants_compte = sum(1 for j in Jeu.joueurs if j.vivant)
        if joueurs_vivants_compte <= 1 and self.vivant:
            log_details.append(f"==> {self.nom} DECIDE DE TENTER LA FUITE (car dernier joueur vivant).")
            return True

        # Coeur de la decision, selon la politique du joueur
        if self.politique_fuite == 'ev':
            veut_fuir = self._decision_fuite_ev(Jeu)
        else:
            veut_fuir = self._decision_fuite_seuils(Jeu)
        if not veut_fuir:
            return False

        # Blocage fuyard : fuir avec moins de points qu'un fuyard = defaite assuree,
        # autant continuer a marquer (ou mourir en essayant).
        a_battre = max((j.getScoreActuel(log_details) for j in Jeu.joueurs
                        if j is not self and j.fuite_reussie), default=-1)
        if a_battre >= 0:
            mes_monstres = self.getScoreActuel(log_details)
            if a_battre > mes_monstres:
                # log_details.append(f"==> {self.nom} NE TENTE PAS LA FUITE (bloqué par un fuyard à {a_battre} MV).")
                return False
            log_details.append(f"--> {self.nom} DECIDE DE TENTER LA FUITE (Un fuyard a {a_battre} MV, il a {mes_monstres} MV)")
        else:
            log_details.append(f"--> {self.nom} DECIDE DE TENTER LA FUITE (Aucun score n'a encore ete posé)")
        return True
        
    def _gerer_pv_bonus(self, objet, log_details):
        """Gère la perte des PV bonus lors de la destruction d'un objet"""
        if objet.pv_bonus:
            self.pv_total -= objet.pv_bonus
            log_details.append(f"L'objet casse {objet.nom} donnait {objet.pv_bonus}PV ca fait ca de moins. PV restant {self.pv_total}PV")

    def decideBriseObjet(self, jeu, log_details):
        """Brise l'objet le moins utile, sans se tuer si possible.

        La valeur d'un objet cibleur (types_tags/puissance_tags) fond avec le
        nombre de proies restantes au Donjon : un Glaive d'argent sans Vampire
        restant ne vaut plus rien, quelle que soit sa priorite. Valide par A/B
        en self-play contre les formes additives et les malus mousse/PV,
        qui n'apportent rien."""
        objets_intacts = [o for o in self.objets if o.intact]
        if not objets_intacts:
            return None

        donjon = jeu.donjon
        restants = [donjon.cartes[i] for i in donjon.ordre[donjon.index:]]

        def valeur(o):
            if not (o.types_tags or o.puissance_tags):
                return o.priorite
            cibles = sum(1 for c in restants
                         if any(t in getattr(c, 'types_initiaux', ()) for t in o.types_tags)
                         or getattr(c, 'puissance_initiale', None) in o.puissance_tags)
            return o.priorite * cibles / (1 + cibles)

        objet = min(objets_intacts, key=lambda o: (o.pv_bonus >= self.pv_total, valeur(o)))
        objet.destroy(self, jeu, log_details)
        self._gerer_pv_bonus(objet, log_details)
        return objet
        