from objets import *
from objets import COULEUR_NOMS, SANS_HOOK_OBJET
from ia_strategies import DEFAULT_STRATEGY_NAME, get_strategy
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
    default_strategy = DEFAULT_STRATEGY_NAME

    def __init__(self, nom, perso_instance, objets=None, medailles=0, strategy=None,
                 control="ai", decision_provider=None):
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
        self.strategy = strategy if strategy is not None else self.default_strategy
        self.control = control
        self.decision_provider = decision_provider
        self.strategie_traquenard = self.ia_strategy().traquenard_strategy
        self.traquenard_opportunites = 0
        self.traquenard_payes = 0
        self.traquenard_execs = 0

    def is_human(self):
        return self.control == "human"

    def _decision_option_label(self, value):
        if hasattr(value, "nom"):
            return value.nom
        if hasattr(value, "titre"):
            return value.titre
        return str(value)

    def _decision_option_description(self, value):
        parts = []
        if getattr(value, "pv_bonus", 0):
            parts.append(f"PV {value.pv_bonus:+}")
        if hasattr(value, "modificateur_de") and value.modificateur_de:
            parts.append(f"fuite {value.modificateur_de:+}")
        if hasattr(value, "puissance"):
            parts.append(f"power {value.puissance}")
        if hasattr(value, "types") and value.types:
            parts.append(", ".join(value.types))
        desc = getattr(value, "description", None) or getattr(value, "effet", None)
        if desc:
            parts.append(str(desc).replace("<b>", "").replace("</b>", "").replace("\n", " "))
        return " | ".join(parts)

    def _decision_option_metadata(self, value):
        metadata = {}
        color_code = getattr(value, "couleur", None)
        if color_code:
            try:
                color_code = int(color_code)
            except (TypeError, ValueError):
                color_code = None
        if color_code:
            metadata["colorCode"] = color_code
            metadata["colorName"] = globals().get("COULEUR_NOMS", {}).get(color_code, "")
        if hasattr(value, "pv_bonus"):
            metadata["pv"] = getattr(value, "pv_bonus", 0)
        if hasattr(value, "modificateur_de"):
            metadata["flee"] = getattr(value, "modificateur_de", 0)
        if hasattr(value, "actif"):
            metadata["active"] = bool(getattr(value, "actif", False))
        return metadata

    def demander_choix(self, kind, prompt, candidats, default=None, label_func=None,
                       context=None):
        candidats = list(candidats)
        if not candidats:
            return None
        if default is None or default not in candidats:
            default = candidats[0]
        default_index = candidats.index(default)
        options = []
        for idx, candidat in enumerate(candidats):
            label = label_func(candidat) if label_func else self._decision_option_label(candidat)
            options.append({
                "id": str(idx),
                "label": label,
                "description": self._decision_option_description(candidat),
                **self._decision_option_metadata(candidat),
            })
        provider = getattr(self, "decision_provider", None)
        if provider is None:
            return default
        selected = provider.choose(
            self,
            kind=kind,
            prompt=prompt,
            options=options,
            default_id=str(default_index),
            context=context or {},
        )
        try:
            return candidats[int(selected)]
        except (TypeError, ValueError, IndexError):
            return default

    def demander_oui_non(self, kind, prompt, default=False, context=None):
        provider = getattr(self, "decision_provider", None)
        if provider is None:
            return bool(default)
        default_id = "yes" if default else "no"
        selected = provider.choose(
            self,
            kind=kind,
            prompt=prompt,
            options=[
                {"id": "yes", "label": "Yes", "description": ""},
                {"id": "no", "label": "No", "description": ""},
            ],
            default_id=default_id,
            context=context or {},
        )
        return selected == "yes"

    def enregistrer_decision_bot(self, kind, prompt, result, label=None, context=None):
        provider = getattr(self, "decision_provider", None)
        if provider is not None and hasattr(provider, "record"):
            provider.record(
                self,
                kind=kind,
                prompt=prompt,
                result=result,
                label=label,
                context=context or {},
            )

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
        modificateur_de = sum(objet.modificateur_de for objet in self.objets if objet.intact)
        return modificateur_de + modificateur_perso
    
    def reset_objets_intacts(self):
        for objet in self.objets:
            objet.repare()

    def fuite(self):
        if not self.vivant or self.pv_total <= 0:
            return
        self.fuite_reussie = True
        self.dans_le_dj = False

    def mort(self, log_details):
        if not self.vivant:
            return
        self.vivant = False
        self.fuite_reussie = False
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
        if self.ia_strategy().draw_item_policy == "strategic":
            self.objets = sorted(self.objets, key=lambda obj: self.valeur_objet(obj, None), reverse=True)
        else:
            self.objets = sorted(self.objets, key=lambda obj: obj.priorite, reverse=True)

    def ia_strategy(self):
        return get_strategy(self.strategy)

    def prochaine_carte_strategy(self, Jeu, strategy=None):
        strategy = strategy or self.ia_strategy()
        if not getattr(strategy, 'use_exact_next', False):
            return self.connait_prochaine_carte(Jeu)
        donjon = Jeu.donjon
        if donjon.vide:
            return None
        return donjon.cartes[donjon.ordre[donjon.index]]

    def prochain_adversaire_dans_donjon(self, Jeu):
        joueurs = getattr(Jeu, 'joueurs', ())
        if not joueurs:
            return None
        try:
            depart = getattr(Jeu, 'index_joueur')
        except AttributeError:
            try:
                depart = joueurs.index(self)
            except ValueError:
                return None
        for offset in range(1, len(joueurs) + 1):
            autre = joueurs[(depart + offset) % len(joueurs)]
            if autre is not self and autre.dans_le_dj:
                return autre
        return None

    def valeur_objet(self, objet, jeu):
        """Heuristic object value used only for AI ordering/choice, not rules."""
        valeur = float(getattr(objet, 'priorite', 49.5))
        valeur += 2.0 * getattr(objet, 'pv_bonus', 0)
        valeur += 4.0 * getattr(objet, 'modificateur_de', 0)
        if getattr(objet, 'actif', False):
            valeur -= 2.0
        if getattr(objet, 'protege_medailles', False) and self.medailles:
            valeur += 12.0
        if not (getattr(objet, 'types_tags', None) or getattr(objet, 'puissance_tags', None)):
            return valeur
        if jeu is None:
            return valeur
        donjon = jeu.donjon
        cibles = 0
        danger = 0.0
        for idx in donjon.ordre[donjon.index:]:
            carte = donjon.cartes[idx]
            if getattr(carte, 'event', False):
                continue
            cible = (
                any(t in getattr(carte, 'types_initiaux', ()) for t in getattr(objet, 'types_tags', ()))
                or getattr(carte, 'puissance_initiale', None) in getattr(objet, 'puissance_tags', ())
            )
            if cible:
                cibles += 1
                danger += self._degats_attendus(carte, jeu)
        return valeur * cibles / (1 + cibles) + 0.15 * danger

    def objets_pour_combat(self, carte, Jeu, hooks_sans_effet):
        objets = [o for o in self.objets if type(o) not in hooks_sans_effet]
        if self.ia_strategy().item_order_policy != "dynamic":
            return objets

        def score(objet):
            s = self.valeur_objet(objet, Jeu)
            if not objet.intact:
                return -10000.0
            if getattr(carte, 'puissance', None) in getattr(objet, 'puissance_tags', ()):
                s += 80.0
            if any(t in getattr(carte, 'types', ()) for t in getattr(objet, 'types_tags', ())):
                s += 80.0
            if getattr(objet, 'actif', False):
                s -= 5.0
                if getattr(carte, 'dommages', 0) >= self.pv_total:
                    s += 60.0
            return s

        return sorted(objets, key=score, reverse=True)

    def _ai_decide_utiliser_source(self, objet, carte, Jeu, log_details, baseline_worth):
        strategy = self.ia_strategy()
        if strategy.item_use_policy == "baseline":
            return baseline_worth
        if strategy.item_use_policy == "lethal_only":
            return baseline_worth and getattr(carte, 'dommages', 0) >= self.pv_total
        if strategy.item_use_policy == "conserve":
            if not baseline_worth:
                return False
            if not getattr(objet, 'actif', False):
                return True
            dommages = getattr(carte, 'dommages', 0)
            if dommages >= self.pv_total:
                return True
            if self.pv_total - dommages <= strategy.item_conserve_min_pv:
                return True
            gain = 2 if getattr(carte, 'effet', None) == "GOLD" else 1
            cible = self._score_a_battre_strategy(Jeu, strategy) + strategy.replay_target_lead
            return self._score_estime_strategy(strategy) < cible and gain > 1
        if baseline_worth:
            return True
        if strategy.item_use_policy == "aggressive":
            dommages = getattr(carte, 'dommages', 0)
            seuil = max(strategy.item_aggressive_min_damage,
                        int(max(1, self.pv_total) * strategy.item_aggressive_damage_ratio))
            if dommages >= self.pv_total or dommages >= seuil:
                return True
        if strategy.item_use_policy == "combat_value":
            dommages = getattr(carte, 'dommages', 0)
            seuil = max(strategy.item_aggressive_min_damage,
                        int(max(1, self.pv_total) * strategy.item_aggressive_damage_ratio))
            noms = set(getattr(type(objet).combat_effet, "__code__", None).co_names
                       if getattr(type(objet).combat_effet, "__code__", None) else ())
            protecteur = bool(noms & {
                "execute", "executeEtDefausse", "remetDansDonjon", "absorbe",
                "reduc_damage", "survit", "_utiliser",
            })
            if protecteur and (dommages >= self.pv_total or dommages >= seuil):
                return True
        if strategy.item_use_policy == "score_value":
            dommages = getattr(carte, 'dommages', 0)
            code = getattr(type(objet).combat_effet, "__code__", None)
            noms = set(code.co_names if code else ())
            protecteur = bool(noms & {
                "execute", "executeEtDefausse", "remetDansDonjon", "absorbe",
                "reduc_damage", "survit", "_utiliser",
            })
            if not protecteur:
                return False
            score_actuel = self._score_estime_strategy(strategy)
            cible = self._score_a_battre_strategy(Jeu, strategy) + strategy.replay_target_lead
            gain = 2 if getattr(carte, 'effet', None) == "GOLD" else 1
            seuil = max(strategy.item_aggressive_min_damage,
                        int(max(1, self.pv_total) * strategy.item_aggressive_damage_ratio))
            if dommages >= self.pv_total or dommages >= seuil:
                return True
            if score_actuel < cible and (gain > 1 or dommages >= 2):
                return True
        return False

    def decide_utiliser_source(self, source, carte, Jeu, log_details, baseline_worth):
        source_name = self._decision_option_label(source)
        card_name = self._decision_option_label(carte)
        prompt = f"Use {source_name} against {card_name}?"
        context = {
            "source": source_name,
            "card": card_name,
            "baseline": bool(baseline_worth),
            "pv": self.pv_total,
            "damage": getattr(carte, "dommages", None),
            "power": getattr(carte, "puissance", None),
        }
        if self.is_human():
            return self.demander_oui_non(
                "combat_source",
                prompt,
                default=bool(baseline_worth),
                context=context,
            )
        decision = self._ai_decide_utiliser_source(source, carte, Jeu, log_details, baseline_worth)
        if decision:
            self.enregistrer_decision_bot(
                "combat_source",
                prompt,
                decision,
                label="use",
                context=context,
            )
        return decision

    def decide_utiliser_objet(self, objet, carte, Jeu, log_details, baseline_worth):
        return self.decide_utiliser_source(objet, carte, Jeu, log_details, baseline_worth)

    def _combat_source_score(self, source, carte, Jeu, baseline_worth):
        dommages = getattr(carte, "dommages", 0) or 0
        score = 100.0 if baseline_worth else 0.0
        if dommages >= self.pv_total:
            score += 80.0
        elif dommages >= max(3, int(max(1, self.pv_total) * 0.45)):
            score += 35.0

        code = getattr(type(source).combat_effet, "__code__", None)
        names = set(code.co_names if code else ())
        if names & {"execute", "executeEtDefausse", "absorbe", "remetDansDonjon"}:
            score += 45.0
        if names & {"reduc_damage", "survit", "gagnePV"}:
            score += min(30.0, float(dommages) * 4.0)
        if getattr(carte, "puissance", None) in getattr(source, "puissance_tags", ()):
            score += 30.0
        if any(t in getattr(carte, "types", ()) for t in getattr(source, "types_tags", ())):
            score += 30.0

        # Spending a high-value active object is a cost; passive lines are cheap.
        if getattr(source, "actif", False):
            score -= 0.12 * self.valeur_objet(source, Jeu)
        return score

    def _best_combat_source(self, candidats, carte, Jeu, log_details, require_use=True):
        scored = []
        for source in candidats:
            try:
                baseline = source.worthit(self, carte, Jeu, log_details)
            except Exception:
                baseline = False
            use_it = self._ai_decide_utiliser_source(source, carte, Jeu, log_details, baseline)
            if require_use and not use_it:
                continue
            scored.append((self._combat_source_score(source, carte, Jeu, baseline), source))
        if not scored:
            return None
        return max(scored, key=lambda item: item[0])[1]

    def choisir_source_combat(self, candidats, carte, Jeu, log_details):
        candidats = list(candidats)
        if not candidats:
            return None

        card_name = self._decision_option_label(carte)
        context = {
            "card": card_name,
            "pv": self.pv_total,
            "damage": getattr(carte, "dommages", None),
            "power": getattr(carte, "puissance", None),
            "options": [self._decision_option_label(c) for c in candidats],
        }

        if self.is_human():
            default_source = self._best_combat_source(candidats, carte, Jeu, log_details, require_use=True)
            options = [
                {
                    "id": str(idx),
                    "label": self._decision_option_label(source),
                    "description": self._decision_option_description(source),
                }
                for idx, source in enumerate(candidats)
            ]
            options.append({
                "id": "resolve",
                "label": "Resolve now",
                "description": "Take the card as-is without using another item.",
            })
            default_id = str(candidats.index(default_source)) if default_source in candidats else "resolve"
            provider = getattr(self, "decision_provider", None)
            if provider is None:
                return default_source
            selected = provider.choose(
                self,
                kind="choose_combat_source",
                prompt=f"Choose an item to use against {card_name}.",
                options=options,
                default_id=default_id,
                context=context,
            )
            if selected == "resolve":
                return None
            try:
                return candidats[int(selected)]
            except (TypeError, ValueError, IndexError):
                return default_source

        choice = self._best_combat_source(candidats, carte, Jeu, log_details, require_use=True)
        self.enregistrer_decision_bot(
            "choose_combat_source",
            f"Choose an item against {card_name}.",
            choice is not None,
            label=self._decision_option_label(choice) if choice is not None else "resolve",
            context=context,
        )
        return choice

    def choisir_objet(self, candidats, jeu, usage="generic"):
        if not candidats:
            return None
        strategy = self.ia_strategy()
        if usage == "repair":
            if strategy.repair_policy == "strategic":
                choix = max(candidats, key=lambda o: (self.valeur_objet(o, jeu), getattr(o, 'pv_bonus', 0)))
            else:
                choix = max(candidats, key=lambda o: getattr(o, 'pv_bonus', 0))
            return self.demander_choix(
                f"choose_object_{usage}",
                "Choose an object.",
                candidats,
                default=choix,
                context={"usage": usage},
            ) if self.is_human() else choix
        if usage in ("draw_keep", "copy"):
            if ((usage == "draw_keep" and strategy.draw_item_policy == "strategic")
                    or (usage == "copy" and strategy.copy_policy == "strategic")):
                choix = max(candidats, key=lambda o: self.valeur_objet(o, jeu))
            else:
                choix = max(candidats, key=lambda o: o.priorite)
            return self.demander_choix(
                f"choose_object_{usage}",
                "Choose an object.",
                candidats,
                default=choix,
                context={"usage": usage},
            ) if self.is_human() else choix
        if usage.startswith("sacrifice") and strategy.sacrifice_policy == "future_value":
            choix = min(candidats, key=lambda o: (
                getattr(o, 'pv_bonus', 0) >= self.pv_total,
                self.valeur_objet(o, jeu) + 8.0 * getattr(o, 'pv_bonus', 0),
            ))
        else:
            choix = min(candidats, key=lambda o: (getattr(o, 'pv_bonus', 0), o.priorite))
        if self.is_human():
            return self.demander_choix(
                f"choose_object_{usage}",
                "Choose an object.",
                candidats,
                default=choix,
                context={"usage": usage},
            )
        return choix

    def choisir_monstre(self, candidats, jeu=None, usage="generic", default=None):
        if not candidats:
            return None
        if default is None:
            default = min(candidats, key=lambda m: (0 if getattr(m, "is_X", False) else getattr(m, "puissance", 0)))
        if self.is_human():
            return self.demander_choix(
                f"choose_monster_{usage}",
                "Choose a monster.",
                candidats,
                default=default,
                context={"usage": usage},
            )
        return default

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

    def _degats_carte_connue(self, carte, Jeu):
        if not getattr(carte, 'is_X', False):
            return self._degats_attendus(carte, Jeu)
        effet = getattr(carte, 'effet', None)
        if effet == "MEDAIL":
            d = sum(j.medailles for j in Jeu.joueurs)
        elif effet == "MIMIC":
            d = sum(1 for objet in self.objets if objet.intact)
        elif effet == "MONKEY_TEAM":
            d = 2 * sum(1 for j in Jeu.joueurs if j.dans_le_dj)
        elif effet == "REAPER":
            d = self.pv_total // 2
        elif effet == "SCAVENGER":
            d = len(self.pile_monstres_vaincus)
        elif effet == "MIROIR":
            d = self.pile_monstres_vaincus[-1].puissance if self.pile_monstres_vaincus else 0
        elif effet == "TROLL":
            d = self.pile_monstres_vaincus[0].puissance if self.pile_monstres_vaincus else 0
        elif effet == "SLEEPING":
            d = 9
        else:
            d = 10
        if effet and "ADD_2_DOM" in effet:
            d += 2
        if effet == "LORD" and self.medailles:
            d += 2 * self.medailles
        if effet == "NOOB" and self.medailles:
            d = 2
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
        if not types and any(o.intact and o.nom == "Attrape-Rêves" for o in self.objets):
            return True
        types_couverts, puissances_couvertes = couverture if couverture is not None else self._couverture_objets()
        return carte.puissance in puissances_couvertes or any(t in types_couverts for t in types)

    def _carte_est_mortelle_pour(self, joueur, carte, Jeu):
        if getattr(carte, 'event', False):
            return False
        return (joueur._degats_attendus(carte, Jeu) >= joueur.pv_total
                and not joueur.peut_executer_facilement(carte))

    def _score_a_battre_rapide(self, Jeu):
        meilleur = 0
        for autre in getattr(Jeu, 'joueurs', ()):
            if autre is self or not autre.vivant:
                continue
            meilleur = max(meilleur, autre._score_rapide())
        return meilleur

    def _score_a_battre_strategy(self, Jeu, strategy):
        policy = getattr(strategy, 'score_target_policy', 'alive')
        joueurs = getattr(Jeu, 'joueurs', ())
        if policy == "dungeon_only":
            candidats = [j for j in joueurs if j is not self and j.dans_le_dj]
        elif policy == "contextual":
            joueurs_dj = [j for j in joueurs if j is not self and j.dans_le_dj]
            candidats = joueurs_dj or [j for j in joueurs if j is not self and j.vivant]
        else:
            candidats = [j for j in joueurs if j is not self and j.vivant]
        return max((j._score_estime_strategy(strategy) for j in candidats), default=0)

    def _event_connue_interessante(self, carte, Jeu, strategy):
        effet = getattr(carte, 'effet', None)
        policy = getattr(strategy, 'event_policy', 'strict')
        loose = policy in ("loose", "greedy")
        greedy = policy == "greedy"
        resource = policy == "resource"
        if resource:
            loose = True
        if effet == "HEAL":
            return loose or self.pv_total <= 8
        if effet == "ALLY":
            prochaine = self._carte_apres_position(Jeu, 1)
            return prochaine is not None and not getattr(prochaine, 'event', False)
        if effet == "REPAIR":
            return any(not o.intact for o in self.objets)
        if effet == "SHOP":
            intacts = [o for o in self.objets if o.intact]
            if len(intacts) < (5 if loose else 4):
                return True
            return greedy and any(o.pv_bonus <= 1 and o.priorite < 45 for o in intacts)
        if effet == "FORTUNE_WHEEL":
            return self.pv_total <= (10 if greedy else 8 if loose else 5) and any(
                not (getattr(m, 'effet', None) and "GOLD" in m.effet)
                for m in self.pile_monstres_vaincus
            )
        if effet == "INJECTION":
            mes_golems = sum(1 for m in self.pile_monstres_vaincus if "Golem" in getattr(m, 'types', ()))
            adv_golems = max(
                (sum(1 for m in j.pile_monstres_vaincus if "Golem" in getattr(m, 'types', ()))
                 for j in getattr(Jeu, 'joueurs', ()) if j is not self and j.dans_le_dj),
                default=0,
            )
            return mes_golems > 0 and (greedy or mes_golems >= adv_golems)
        if effet == "SOULSTORM":
            return self._score_estime_strategy(strategy) + strategy.replay_target_lead < self._score_a_battre_strategy(Jeu, strategy)
        if loose and effet == "INCEPTION":
            return True
        if resource and effet == "DRAG":
            mes_dragons = sum(1 for m in self.pile_monstres_vaincus if "Dragon" in getattr(m, 'types', ()))
            intacts = sum(1 for o in self.objets if getattr(o, 'intact', False))
            return (
                mes_dragons > 0
                and (self.pv_total <= strategy.resource_drag_max_pv
                     or intacts < strategy.resource_drag_min_intacts)
            )
        if greedy and effet == "DRAG":
            mes_dragons = sum(1 for m in self.pile_monstres_vaincus if "Dragon" in getattr(m, 'types', ()))
            adv_dragons = sum(
                1 for j in getattr(Jeu, 'joueurs', ()) if j is not self and j.dans_le_dj
                for m in j.pile_monstres_vaincus if "Dragon" in getattr(m, 'types', ())
            )
            return adv_dragons > mes_dragons
        return False

    def _carte_apres_position(self, Jeu, offset):
        donjon = Jeu.donjon
        pos = donjon.index + offset
        if pos >= donjon.nb_cartes:
            return None
        return donjon.cartes[donjon.ordre[pos]]

    def _decision_rejouer_strategy(self, Jeu, log_details, strategy):
        if strategy.replay_policy not in ("oracle_safe", "greedy_safe", "oracle_predatory", "oracle_score"):
            return None
        carte = self.prochaine_carte_strategy(Jeu, strategy)
        if carte is None:
            return None
        if getattr(carte, 'event', False):
            if strategy.replay_policy == "oracle_score":
                decision = self._event_connue_interessante(carte, Jeu, strategy)
                if decision:
                    log_details.append(f"{self.nom} continue sur un evenement utile ({strategy.name}).")
                return decision
            if strategy.replay_allow_events:
                log_details.append(f"{self.nom} continue de piocher selon sa strategie ({strategy.name}).")
                return True
            return False
        if not getattr(carte, 'is_X', False) or getattr(strategy, 'replay_allow_estimated_x', False):
            if strategy.replay_policy == "oracle_score":
                score_actuel = self._score_estime_strategy(strategy)
                cible = self._score_a_battre_strategy(Jeu, strategy) + strategy.replay_target_lead
                besoin_score = score_actuel < cible
                executable = strategy.replay_allow_executable and self.peut_executer_facilement(carte)
                degats = self._degats_carte_connue(carte, Jeu)
                gain = 2 if getattr(carte, 'effet', None) == "GOLD" else 1
                prend_safe = getattr(strategy, 'replay_take_safe_when_ahead', False)
                if getattr(strategy, 'replay_predatory_pass', False) and not besoin_score and gain <= 1:
                    adversaire = self.prochain_adversaire_dans_donjon(Jeu)
                    if (adversaire is not None
                            and self._carte_est_mortelle_pour(adversaire, carte, Jeu)
                            and not self._carte_est_mortelle_pour(self, carte, Jeu)):
                        log_details.append(f"{self.nom} passe une carte dangereuse a l'adversaire ({strategy.name}).")
                        return False
                if executable and (prend_safe or besoin_score or gain > 1 or degats >= strategy.replay_safe_damage):
                    log_details.append(f"{self.nom} continue pour prendre un monstre gerable ({strategy.name}).")
                    return True
                if degats <= strategy.replay_safe_damage and self.pv_total - degats >= 2:
                    return prend_safe or besoin_score or gain > 1
                if besoin_score and self.pv_total - degats >= strategy.replay_score_margin:
                    log_details.append(f"{self.nom} continue pour rattraper le score ({strategy.name}).")
                    return True
                if (not besoin_score
                        and getattr(strategy, 'replay_take_margin_when_ahead', False)
                        and self.pv_total - degats >= strategy.replay_score_margin):
                    log_details.append(f"{self.nom} continue avec une grosse marge de PV ({strategy.name}).")
                    return True
                if (besoin_score and strategy.replay_use_options_for_score
                        and self._nb_options_combat() > 0
                        and self.pv_total + strategy.replay_option_buffer - degats >= strategy.replay_score_margin):
                    log_details.append(f"{self.nom} continue avec options pour rattraper le score ({strategy.name}).")
                    return True
                return False
            if strategy.replay_policy == "oracle_predatory":
                adversaire = self.prochain_adversaire_dans_donjon(Jeu)
                mortel_pour_adv = (
                    adversaire is not None and self._carte_est_mortelle_pour(adversaire, carte, Jeu)
                )
                mortel_pour_moi = self._carte_est_mortelle_pour(self, carte, Jeu)
                if mortel_pour_adv and not mortel_pour_moi:
                    if (strategy.replay_hunt_setup
                            and self._score_rapide() >= strategy.oracle_hunt_min_score
                            and self._proba_fuite_sur(carte, Jeu) >= strategy.oracle_hunt_min_escape):
                        log_details.append(f"{self.nom} continue pour fuir et passer la menace ({strategy.name}).")
                        return True
                    log_details.append(f"{self.nom} passe une carte dangereuse a l'adversaire ({strategy.name}).")
                    return False
            if strategy.replay_allow_executable and self.peut_executer_facilement(carte):
                log_details.append(f"{self.nom} continue sur une carte gerable ({strategy.name}).")
                return True
            degats = self._degats_attendus(carte, Jeu)
            marge = strategy.replay_greedy_margin if strategy.replay_policy == "greedy_safe" else strategy.replay_safe_margin
            if degats <= strategy.replay_safe_damage or self.pv_total - degats >= marge:
                log_details.append(f"{self.nom} continue sur une carte acceptable ({strategy.name}).")
                return True
            if self._nb_options_combat() > 0 and self.pv_total + strategy.replay_option_buffer > degats:
                log_details.append(f"{self.nom} continue avec des options de combat ({strategy.name}).")
                return True
            if strategy.replay_flee_setup and degats >= self.pv_total and self._proba_fuite_sur(carte, Jeu) >= strategy.oracle_flee_min_escape:
                log_details.append(f"{self.nom} continue pour tenter une fuite preparee ({strategy.name}).")
                return True
            return False
        return None

    def deciderDeRejouer(self, Jeu, log_details):
        """IA: decide de repiocher volontairement au lieu de passer son tour."""
        if not self.dans_le_dj or Jeu.donjon.vide or Jeu.traquenard_actif or self.doit_passer:
            return False

        if self.is_human():
            carte_connue = self.connait_prochaine_carte(Jeu)
            return self.demander_oui_non(
                "replay",
                "Draw another card this turn?",
                default=False,
                context={
                    "pv": self.pv_total,
                    "score": self._score_rapide(),
                    "remaining_cards": max(0, Jeu.donjon.nb_cartes - Jeu.donjon.index),
                    "known_next": self._decision_option_label(carte_connue) if carte_connue is not None else None,
                    "known_next_power": getattr(carte_connue, "puissance", None),
                },
            )

        strategy = self.ia_strategy()
        decision_strategy = self._decision_rejouer_strategy(Jeu, log_details, strategy)
        if decision_strategy is not None:
            return decision_strategy

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

    def _score_estime_strategy(self, strategy):
        score = self._score_rapide()
        if getattr(strategy, 'score_estimate_policy', 'rapid') != "static":
            return score

        pile = self.pile_monstres_vaincus
        objets = [o for o in self.objets if getattr(o, 'intact', False)]
        score_fixe = {
            "Katana": -1,
            "ValisesDeCash": 3,
            "TuniqueClasse": 1,
            "ArmureDamnee": -1,
            "AnneauPlussain": 1,
            "MarteauDEternite": -1,
            "BourseGarnie": 1,
            "ParfumDeScandale": 1,
            "PerleRare": 2,
            "RoseDOr": 2,
        }
        for objet in objets:
            nom_classe = type(objet).__name__
            score += score_fixe.get(nom_classe, 0)
            if nom_classe == "PierreDAme" and any("Dragon" in m.types for m in pile):
                score += 3
            elif nom_classe == "PeigneEnOr":
                score += sum(1 for m in pile if "Gobelin" in m.types)
            elif nom_classe == "LampeMagique":
                score += 2 * sum(1 for m in pile if "Démon" in m.types)
            elif nom_classe == "CorbeilleDOr":
                score += sum(1 for o in self.objets if not getattr(o, 'intact', False))
            elif nom_classe == "BagouzeDuParrain":
                if sum(1 for o in self.objets if getattr(o, 'intact', False)) == 4:
                    score += 2
            elif nom_classe == "MainInvisible":
                gros_types = ("Liche", "Démon", "Dragon")
                score += sum(1 for m in pile if any(t in m.types for t in gros_types))
        return score

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
        a_attrape_reves = any(o.intact and o.nom == "Attrape-Rêves" for o in self.objets)
        ange_refusable = 8 not in puissances_couvertes and not a_attrape_reves

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

    def _decision_fuite_ev(self, Jeu, strategy=None):
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
        strategy = strategy or self.ia_strategy()
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
        horizon = min(int(strategy.fuite_ev_horizon), max(1, -(-n // nb_dans_dj)))
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
                s_j += strategy.taux_gain_par_pioche * n / nb_dans_dj  # ses pioches restantes
            meilleur_adverse = max(meilleur_adverse, s_j)
        poids_verrou = 1.0 / (1.0 + math.exp(-(score_actuel - meilleur_adverse) / 2.0))

        # cout de la mort, en points de score (relatif a une fuite reussie : score garde)
        cout_mort = strategy.valeur_survie_pts + score_actuel * poids_verrou
        if self.medailles and not any(getattr(o, 'protege_medailles', False) and o.intact
                                      for o in self.objets):
            cout_mort += strategy.valeur_medaille_pts

        # Les objets actifs de combat/survie sans tags (potions, armes a usage unique...)
        # peuvent neutraliser une carte mortelle chacun : on couvre une fraction des
        # rencontres mortelles attendues sur l'horizon, avec une efficacite forfaitaire.
        couverture_options = min(1.0, strategy.efficacite_option * self._nb_options_combat()
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

        V = strategy.bonus_ponceur_pts  # vivant au bout du Donjon : les fuyards sont exclus du decompte
        F = 0.0                # sorti du Donjon : on ne marque plus rien
        for _ in range(horizon):
            W = max(F, V)
            V = piocher_imm + rester_p * W
            F = fuir_imm + rester_f * W
        return F > V

    def _decision_fuite_seuils(self, Jeu, strategy=None):
        """Ancienne politique a seuils (conservee pour comparaison, politique_fuite='seuils')."""
        strategy = strategy or self.ia_strategy()
        # Certains objets (Ceinture du Ponceur) doivent anticiper la fuite: leurs PV "de decision"
        # sont reduits pour fuir a temps (avant que la fuite ne devienne interdite)
        # Mode soiree: mourir avec des Medailles en coute une, on fuit donc plus tot.
        pv_decision = self.pv_total - sum(getattr(objet, 'malus_pv_decision_fuite', 0)
                                          for objet in self.objets if objet.intact)
        seuil_pv = self.pv_min_fuite + strategy.prudence_pv_par_medaille * self.medailles
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
        seuil_risque = max(0.10, 0.25 - strategy.prudence_risque_par_medaille * self.medailles)
        return mortelles / len(restantes) >= seuil_risque

    politique_fuite = 'ev'  # attribut de classe : 'ev' (esperance) ou 'seuils' (ancienne)

    def _proba_fuite_sur(self, carte, Jeu):
        puissance = getattr(carte, 'puissance', getattr(carte, 'puissance_initiale', 0))
        if getattr(carte, 'is_X', False):
            puissance = self._degats_attendus(carte, Jeu)
        mod = self.calculer_modificateurs()
        return min(1.0, max(0.0, (7 + mod - puissance) / 6.0))

    def _decision_fuite_oracle(self, Jeu, log_details, strategy):
        carte = self.prochaine_carte_strategy(Jeu, strategy)
        if carte is None:
            return None
        if getattr(carte, 'event', False):
            return False
        if self.peut_executer_facilement(carte):
            return False

        degats = self._degats_attendus(carte, Jeu)
        p_fuite = self._proba_fuite_sur(carte, Jeu)
        if strategy.oracle_flee_on_lethal and degats >= self.pv_total:
            return p_fuite >= strategy.oracle_flee_min_escape
        adversaire = self.prochain_adversaire_dans_donjon(Jeu)
        if (adversaire is not None
                and self._score_rapide() >= strategy.oracle_hunt_min_score
                and self._carte_est_mortelle_pour(adversaire, carte, Jeu)
                and p_fuite >= strategy.oracle_hunt_min_escape):
            return True
        if degats >= max(1, self.pv_total) * strategy.oracle_flee_danger_ratio:
            return p_fuite >= strategy.oracle_flee_danger_escape
        return False

    def _decision_fuite_exact_score(self, Jeu, strategy):
        carte = self.prochaine_carte_strategy(Jeu, strategy)
        if carte is None:
            return None
        if getattr(carte, 'event', False):
            return False
        if getattr(Jeu, 'execute_next_monster', False) or self.peut_executer_facilement(carte):
            return False
        if getattr(carte, 'is_X', False):
            return None

        degats = self._degats_attendus(carte, Jeu)
        gain = 2 if getattr(carte, 'effet', None) == "GOLD" else 1
        if degats <= strategy.replay_safe_damage and self.pv_total - degats >= 2:
            return False
        if gain > 1 and self.pv_total - degats >= strategy.replay_score_margin:
            return False

        score_actuel = self._score_estime_strategy(strategy)
        cible = self._score_a_battre_strategy(Jeu, strategy) + strategy.oracle_flee_min_score_lead
        if score_actuel < cible:
            return None

        p_fuite = self._proba_fuite_sur(carte, Jeu)
        if p_fuite < strategy.oracle_flee_min_escape:
            return None
        if degats >= self.pv_total:
            return True
        if (degats >= max(1, self.pv_total) * strategy.oracle_flee_danger_ratio
                and self.pv_total - degats < strategy.replay_score_margin):
            return True
        return None

    def _devrait_prendre_carte_connue_pour_score(self, Jeu, strategy):
        carte = self.prochaine_carte_strategy(Jeu, strategy)
        if carte is None:
            return False
        if getattr(carte, 'event', False):
            return self._event_connue_interessante(carte, Jeu, strategy)
        if getattr(Jeu, 'execute_next_monster', False):
            return True
        if getattr(carte, 'is_X', False):
            return False
        score_actuel = self._score_estime_strategy(strategy)
        cible = self._score_a_battre_strategy(Jeu, strategy) + strategy.replay_target_lead
        besoin_score = score_actuel < cible
        degats = self._degats_attendus(carte, Jeu)
        gain = 2 if getattr(carte, 'effet', None) == "GOLD" else 1
        prend_safe = getattr(strategy, 'replay_take_safe_when_ahead', False)
        if self.peut_executer_facilement(carte):
            return prend_safe or besoin_score or gain > 1
        if degats <= strategy.replay_safe_damage and self.pv_total - degats >= 2:
            return prend_safe or besoin_score or gain > 1
        if (not besoin_score
                and getattr(strategy, 'replay_take_margin_when_ahead', False)
                and self.pv_total - degats >= strategy.replay_score_margin):
            return True
        return besoin_score and self.pv_total - degats >= strategy.replay_score_margin

    def _devrait_verrouiller_score(self, Jeu, strategy):
        if getattr(strategy, 'score_lock_only_last', False):
            if any(j is not self and j.dans_le_dj for j in getattr(Jeu, 'joueurs', ())):
                return False
        if self._score_estime_strategy(strategy) < strategy.score_lock_min_score:
            return False
        if self._score_estime_strategy(strategy) < self._score_a_battre_strategy(Jeu, strategy) + strategy.score_lock_lead:
            return False
        carte = self.prochaine_carte_strategy(Jeu, strategy)
        if carte is not None:
            if getattr(carte, 'event', False):
                return False
            if self._proba_fuite_sur(carte, Jeu) < strategy.score_lock_min_escape:
                return False
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

        if self.is_human():
            carte = getattr(Jeu, 'carte_courante', None)
            return self.demander_oui_non(
                "flee",
                "Try to flee before resolving this card?",
                default=False,
                context={
                    "pv": self.pv_total,
                    "score": self._score_rapide(),
                    "card": self._decision_option_label(carte) if carte is not None else None,
                    "power": getattr(carte, "puissance", None),
                    "modifier": self.calculer_modificateurs(),
                },
            )

        strategy = self.ia_strategy()

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
        if strategy.flee_policy == 'oracle_next':
            decision_oracle = self._decision_fuite_oracle(Jeu, log_details, strategy)
            veut_fuir = decision_oracle if decision_oracle is not None else self._decision_fuite_ev(Jeu, strategy)
        elif strategy.flee_policy == 'ev_hunter':
            decision_oracle = self._decision_fuite_oracle(Jeu, log_details, strategy)
            veut_fuir = True if decision_oracle else self._decision_fuite_ev(Jeu, strategy)
        elif strategy.flee_policy == 'ev_score':
            if self._devrait_verrouiller_score(Jeu, strategy):
                veut_fuir = True
            elif self._devrait_prendre_carte_connue_pour_score(Jeu, strategy):
                veut_fuir = False
            else:
                veut_fuir = self._decision_fuite_ev(Jeu, strategy)
        elif strategy.flee_policy == 'ev_lock':
            if self._devrait_verrouiller_score(Jeu, strategy):
                veut_fuir = True
            else:
                veut_fuir = self._decision_fuite_ev(Jeu, strategy)
        elif strategy.flee_policy == 'ev_exact':
            decision_exacte = self._decision_fuite_exact_score(Jeu, strategy)
            if decision_exacte is not None:
                veut_fuir = decision_exacte
            elif self._devrait_verrouiller_score(Jeu, strategy):
                veut_fuir = True
            else:
                veut_fuir = self._decision_fuite_ev(Jeu, strategy)
        elif strategy.flee_policy == 'ev':
            veut_fuir = self._decision_fuite_ev(Jeu, strategy)
        elif strategy.flee_policy == 'seuils':
            veut_fuir = self._decision_fuite_seuils(Jeu, strategy)
        elif strategy.flee_policy == 'never':
            veut_fuir = False
        elif self.politique_fuite == 'ev':
            veut_fuir = self._decision_fuite_ev(Jeu, strategy)
        else:
            veut_fuir = self._decision_fuite_seuils(Jeu, strategy)
        if not veut_fuir:
            return False

        rival_block = getattr(strategy, 'flee_rival_block_lead', -999)
        if rival_block > -999 and any(j is not self and j.dans_le_dj for j in getattr(Jeu, 'joueurs', ())):
            cible_rivaux = max(
                (j._score_estime_strategy(strategy) for j in getattr(Jeu, 'joueurs', ())
                 if j is not self and j.dans_le_dj),
                default=0,
            )
            if self._score_estime_strategy(strategy) < cible_rivaux + rival_block:
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

        if self.is_human():
            objet = self.demander_choix(
                "choose_object_sacrifice_limon",
                "Choose an intact object to break.",
                objets_intacts,
                default=min(objets_intacts, key=lambda o: (o.pv_bonus >= self.pv_total, getattr(o, "priorite", 0))),
                context={"usage": "sacrifice_limon"},
            )
            objet.destroy(self, jeu, log_details)
            self._gerer_pv_bonus(objet, log_details)
            return objet

        donjon = jeu.donjon
        restants = [donjon.cartes[i] for i in donjon.ordre[donjon.index:]]

        def valeur(o):
            if not (o.types_tags or o.puissance_tags):
                return o.priorite
            cibles = sum(1 for c in restants
                         if any(t in getattr(c, 'types_initiaux', ()) for t in o.types_tags)
                         or getattr(c, 'puissance_initiale', None) in o.puissance_tags)
            return o.priorite * cibles / (1 + cibles)

        if self.ia_strategy().sacrifice_policy == "future_value":
            objet = self.choisir_objet(
                [o for o in objets_intacts],
                jeu,
                usage="sacrifice_limon",
            )
        else:
            objet = min(objets_intacts, key=lambda o: (o.pv_bonus >= self.pv_total, valeur(o)))
        objet.destroy(self, jeu, log_details)
        self._gerer_pv_bonus(objet, log_details)
        return objet
        
