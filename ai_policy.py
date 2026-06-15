import math
import random
from collections import Counter

from ai_decisions import DecisionKind

class DefaultDungeonPolicy:
    """Default behavior-preserving dungeon AI policy.

    The engine applies returned decisions; this class should only choose.
    """

    def decide(self, context):
        method_name = f"decide_{context.kind.name.lower()}"
        method = getattr(self, method_name, None)
        if method is None:
            raise NotImplementedError(f"No policy handler for {context.kind}")
        return method(context)

    def decide_should_replay(self, context):
        return self.should_replay(context.actor, context.game, context.meta('log_details', []))

    def decide_should_flee(self, context):
        return self.should_flee(context.actor, context.game, context.meta('log_details', []))

    def decide_use_object_in_combat(self, context):
        objet = context.meta('objet') or (context.options[0] if context.options else None)
        return bool(objet.worthit(context.actor, context.subject, context.game, context.meta('log_details', [])))

    def decide_use_hero_ability(self, context):
        phase = context.phase
        actor = context.actor
        subject = context.subject
        if phase in {
            'ninja_flee_bonus',
            'princess_draw',
            'tricheur_debut_tour',
            'chevalier_dragon',
            'docteur_de_peste',
            'inventeur_genial',
            'flutiste',
            'berserker_survive',
        }:
            return True
        if phase == 'avatar':
            return subject.dommages > (actor.pv_total / 2)
        if phase == 'prophete':
            hero = actor.perso_obj
            seuil = 4 if getattr(hero, 'level', 1) == 2 else 6
            return actor.pv_total <= seuil
        if phase == 'shaman_reroll':
            return (
                not context.meta('rerolled', False)
                and not context.meta('reversed', False)
                and context.meta('jet') <= 2
                and context.meta('jet') < context.meta('jet_voulu')
            )
        if phase == 'lapin_skip_turn':
            prochaine = context.meta('prochaine')
            return (
                hasattr(prochaine, 'types')
                and not getattr(prochaine, 'event', False)
                and prochaine.puissance >= actor.pv_total
            )
        return True

    def decide_use_active_object(self, context):
        return True

    def decide_should_face_special_card(self, context):
        effect = getattr(context.subject, 'effet', None)
        if effect == 'KRAKEN':
            return any(objet.intact and 10 in objet.puissance_tags for objet in context.actor.objets)
        if effect == 'GUARDIAN_ANGEL':
            return any(
                objet.intact and (8 in objet.puissance_tags or objet.nom == "Attrape-RÃªves")
                for objet in context.actor.objets
            )
        return True

    def decide_should_keep_special_monster(self, context):
        return True

    def decide_pay_traquenard(self, context):
        return self.should_pay_traquenard(
            context.actor,
            context.subject,
            context.game,
            context.meta('candidate'),
            context.meta('log_details', []),
        )

    def decide_choose_object(self, context):
        phase = context.phase
        options = context.options
        if not options:
            return None
        if phase in {'couteau_suisse_repair', 'enclume_instable', 'canne_a_chep'}:
            return random.choice(list(options))
        if phase == 'draw_two_keep_one':
            return max(options, key=lambda o: o.priorite)
        if phase == 'repair_object':
            return max(options, key=lambda o: o.pv_bonus)
        if phase == 'shop_discard':
            echangeables = [o for o in options if o.pv_bonus <= 2]
            if not echangeables or not len(context.game.objets_dispo):
                return None
            return min(echangeables, key=lambda o: o.priorite)
        if phase == 'imprimante':
            return max(options, key=lambda o: o.priorite)
        if phase == 'coursier_volant_discard':
            inutiles = [o for o in options if o.priorite < 40]
            return min(inutiles, key=lambda o: o.priorite) if inutiles else None
        if phase in {'kraken_confidence_object', 'guardian_angel_confidence_object'}:
            power = 10 if phase.startswith('kraken') else 8
            for objet in options:
                if objet.intact and (power in objet.puissance_tags or objet.nom == "Attrape-RÃªves"):
                    return objet
            return None
        return options[0]

    def decide_choose_objects(self, context):
        options = context.options
        phase = context.phase
        if phase == 'gants_de_gaia_discards':
            count = context.meta('count', 0)
            return tuple(list(options)[-count:][::-1])
        if phase == 'inventeur_discards':
            return tuple(random.sample(list(options), min(2, len(options))))
        return tuple(options)

    def decide_choose_object_to_sacrifice(self, context):
        options = context.options
        if not options:
            return None
        if context.meta('reason') == 'limon' or context.phase == 'object_sacrifice_limon':
            game = context.game

            def value(objet):
                if not (objet.types_tags or objet.puissance_tags):
                    return objet.priorite
                donjon = game.donjon
                restants = [donjon.cartes[i] for i in donjon.ordre[donjon.index:]]
                cibles = sum(
                    1
                    for carte in restants
                    if any(t in getattr(carte, 'types_initiaux', ()) for t in objet.types_tags)
                    or getattr(carte, 'puissance_initiale', None) in objet.puissance_tags
                )
                return objet.priorite * cibles / (1 + cibles)

            return min(options, key=lambda o: (o.pv_bonus >= context.actor.pv_total, value(o)))
        return min(options, key=lambda o: (o.pv_bonus, o.priorite))

    def decide_choose_object_to_repair(self, context):
        return max(context.options, key=lambda o: o.pv_bonus) if context.options else None

    def decide_choose_monster(self, context):
        options = context.options
        if not options:
            return None
        phase = context.phase
        if phase in {'repair_payment_monster', 'fortune_wheel_monster', 'crane_du_necromancien'}:
            return min(options, key=lambda m: m.puissance)
        if phase == 'soulstorm_monster':
            joueur = context.actor
            couverts = [m for m in options if self._passive_line_covers_card(joueur, m)]
            if couverts:
                return max(
                    couverts,
                    key=lambda m: (
                        joueur._degats_attendus(m, context.game),
                        getattr(m, 'puissance_initiale', getattr(m, 'puissance', 0)),
                        len(getattr(m, 'types_initiaux', getattr(m, 'types', ()))),
                    ),
                )
            return min(
                options,
                key=lambda m: (
                    joueur._degats_attendus(m, context.game),
                    getattr(m, 'puissance_initiale', getattr(m, 'puissance', 0)),
                    len(getattr(m, 'types_initiaux', getattr(m, 'types', ()))),
                ),
            )
        return random.choice(list(options))

    def decide_choose_monsters(self, context):
        options = context.options
        if context.phase == 'pelle_du_fossoyeur':
            max_count = context.meta('max_count', len(options))
            golem_or = []
            dragons = []
            others = []
            for monster in options:
                if getattr(monster, 'effet', None) == "GOLD":
                    golem_or.append(monster)
                elif "Dragon" in getattr(monster, 'types', ()):
                    dragons.append(monster)
                else:
                    others.append(monster)

            chosen = []
            if golem_or:
                chosen.append(golem_or[0])
            random.shuffle(dragons)
            while len(chosen) < max_count and dragons:
                chosen.append(dragons.pop())
            random.shuffle(others)
            while len(chosen) < max_count and others:
                chosen.append(others.pop())
            return tuple(chosen)
        return tuple(options)

    def decide_choose_card(self, context):
        options = context.options
        if not options:
            return None
        if context.phase == 'sceptre_changeur':
            score_key = context.meta('score_key')
            current_card = context.subject
            best = min(options, key=score_key)
            return best if score_key(best) < score_key(current_card) else None
        if context.phase == 'event_beast_target':
            preferred_effects = context.meta('preferred_effects', ())
            level = context.meta('level', 1)
            if level == 2:
                for effet in preferred_effects:
                    candidats = [c for c in options if c.effet == effet]
                    if candidats:
                        return candidats[-1]
                return None
            return options[-1] if options and options[-1].effet in preferred_effects else None
        return options[0]

    def decide_choose_cards(self, context):
        return tuple(context.options)

    def decide_choose_cards_split(self, context):
        actor = context.actor
        discard = []
        repose = []
        for card in context.options:
            if hasattr(card, 'types') and not getattr(card, 'event', False) and card.puissance >= actor.pv_total:
                discard.append(card)
            else:
                repose.append(card)
        return tuple(discard), tuple(repose)

    def decide_choose_player(self, context):
        if not context.options:
            return None
        if context.phase == 'dague_de_brutus':
            return min(context.options, key=lambda j: len(j.pile_monstres_vaincus))
        return context.options[0]

    def decide_choose_power(self, context):
        counts = context.meta('counts') or {}
        scores = context.meta('scores') or counts
        covered = context.meta('covered_powers') or set()
        if not scores:
            return None if context.phase == 'boule_de_cristal' else 5
        candidates = [p for p in scores if p not in covered] or list(scores)
        if context.phase == 'boule_de_cristal':
            return max(candidates, key=lambda p: (counts[p] * p, p, counts[p]))
        return max(candidates, key=lambda p: (scores[p], p, counts[p]))

    def decide_choose_type(self, context):
        scores = context.meta('scores') or {}
        counts = context.meta('counts') or {}
        covered = context.meta('covered_types') or set()
        if not scores:
            return "Golem"
        candidates = [t for t in scores if t not in covered] or list(scores)
        return max(candidates, key=lambda t: (scores[t], counts[t], t == "Golem", t))

    def decide_choose_category(self, context):
        return context.options[0] if context.options else None

    def decide_choose_destination(self, context):
        if context.phase == 'anneau_du_vent':
            return 'bottom'
        return context.options[0] if context.options else None

    def decide_choose_order(self, context):
        return tuple(context.options)

    def decide_order_objects(self, context):
        return tuple(sorted(context.options, key=lambda obj: obj.priorite, reverse=True))

    def decide_order_cards(self, context):
        return tuple(context.options)

    def should_replay(self, joueur, Jeu, log_details):
        if not joueur.dans_le_dj or Jeu.donjon.vide or Jeu.traquenard_actif or joueur.doit_passer:
            return False

        carte_connue = joueur.connait_prochaine_carte(Jeu)
        if carte_connue is not None:
            if getattr(carte_connue, 'event', False):
                log_details.append(f"{joueur.nom} sait qu'un evenement arrive et continue de piocher.")
                return True
            if not getattr(carte_connue, 'is_X', False):
                if joueur.peut_executer_facilement(carte_connue):
                    log_details.append(f"{joueur.nom} sait que {carte_connue.titre} arrive et peut le gerer: il continue.")
                    return True
                if carte_connue.puissance <= 1 and joueur.pv_total >= 4:
                    return True
            return False

        couverture = joueur._couverture_objets()
        donjon = Jeu.donjon
        for i in donjon.ordre[donjon.index:]:
            c = donjon.cartes[i]
            if getattr(c, 'event', False):
                continue
            if joueur._degats_attendus(c, Jeu) > 2 and not joueur.peut_executer_facilement(c, couverture):
                return False

        for objet in joueur.objets:
            objectif = getattr(objet, 'objectif_multi_kill', 0)
            if objet.intact and objectif:
                besoin = objectif - joueur.monstres_ajoutes_ce_tour
                if 0 < besoin <= 2 and joueur.monstres_ajoutes_ce_tour >= 1:
                    log_details.append(f"{joueur.nom} continue de piocher pour activer {objet.nom}.")
                    return True

        log_details.append(f"{joueur.nom} ne risque plus rien et continue de poncer le Donjon.")
        return True

    def should_flee(self, joueur, Jeu, log_details):
        if joueur.tour == 1:
            return False

        if joueur.pv_total < 6 and any(getattr(objet, 'bloque_fuite_pv_bas', False) and objet.intact for objet in joueur.objets):
            return False

        carte_connue = joueur.connait_prochaine_carte(Jeu)
        if carte_connue is not None and not getattr(carte_connue, 'is_X', False):
            if getattr(carte_connue, 'event', False):
                return False
            if joueur.peut_executer_facilement(carte_connue) or carte_connue.puissance <= 2:
                return False
            if carte_connue.puissance >= joueur.pv_total and joueur._nb_options_combat() <= 1:
                log_details.append(f"==> {joueur.nom} sait que {carte_connue.titre} arrive et TENTE LA FUITE.")
                return True

        joueurs_vivants_compte = sum(1 for j in Jeu.joueurs if j.vivant)
        if joueurs_vivants_compte <= 1 and joueur.vivant:
            log_details.append(f"==> {joueur.nom} DECIDE DE TENTER LA FUITE (car dernier joueur vivant).")
            return True

        if joueur.politique_fuite == 'ev':
            veut_fuir = self._decision_fuite_ev(joueur, Jeu)
        else:
            veut_fuir = self._decision_fuite_seuils(joueur, Jeu)
        if not veut_fuir:
            return False

        a_battre = max((j.getScoreActuel(log_details) for j in Jeu.joueurs
                        if j is not joueur and j.fuite_reussie), default=-1)
        if a_battre >= 0:
            mes_monstres = joueur.getScoreActuel(log_details)
            if a_battre > mes_monstres:
                return False
            log_details.append(f"--> {joueur.nom} DECIDE DE TENTER LA FUITE (Un fuyard a {a_battre} MV, il a {mes_monstres} MV)")
        else:
            log_details.append(f"--> {joueur.nom} DECIDE DE TENTER LA FUITE (Aucun score n'a encore ete pose)")
        return True

    def _decision_fuite_seuils(self, joueur, Jeu):
        import joueurs as joueurs_module

        pv_decision = joueur.pv_total - sum(getattr(objet, 'malus_pv_decision_fuite', 0)
                                            for objet in joueur.objets if objet.intact)
        seuil_pv = joueur.pv_min_fuite + joueurs_module.PRUDENCE_PV_PAR_MEDAILLE * joueur.medailles
        if joueur._nb_options_combat() > 1:
            return False
        if pv_decision <= seuil_pv:
            return True
        donjon = Jeu.donjon
        restantes = donjon.ordre[donjon.index:]
        if not len(restantes):
            return False
        couverture = joueur._couverture_objets()
        mortelles = 0
        for i in restantes:
            c = donjon.cartes[i]
            if getattr(c, 'event', False):
                continue
            if (joueur._degats_attendus(c, Jeu) >= joueur.pv_total
                    and not joueur.peut_executer_facilement(c, couverture)):
                mortelles += 1
        seuil_risque = max(0.10, 0.25 - joueurs_module.PRUDENCE_RISQUE_PAR_MEDAILLE * joueur.medailles)
        return mortelles / len(restantes) >= seuil_risque

    def _decision_fuite_ev(self, joueur, Jeu):
        import joueurs as joueurs_module

        donjon = Jeu.donjon
        n = donjon.nb_cartes - donjon.index
        if n <= 0:
            return False
        total_medailles = sum(j.medailles for j in Jeu.joueurs)
        nb_dans_dj = sum(1 for j in Jeu.joueurs if j.dans_le_dj) or 1
        borne_degats = max(11, total_medailles, len(joueur.pile_monstres_vaincus),
                           sum(1 for o in joueur.objets if o.intact),
                           2 * nb_dans_dj) + 2 * joueur.medailles
        if joueur.pv_total > borne_degats:
            return False
        mod = joueur.calculer_modificateurs()
        if (joueur.pv_total > 6 + mod + max(2, 2 * joueur.medailles)
                and joueur._score_rapide() < 6):
            return False

        profils, n, poids_events = joueur._profil_cartes_restantes(Jeu)
        if not n:
            return False
        horizon = min(joueurs_module.FUITE_EV_HORIZON, max(1, -(-n // nb_dans_dj)))
        masse_mortelle = sum(w for (degats, _, _, peut_tuer), w in profils.items()
                             if peut_tuer and degats >= joueur.pv_total) / n
        if masse_mortelle == 0.0:
            return False

        score_actuel = joueur._score_rapide()
        meilleur_adverse = 0.0
        for j in Jeu.joueurs:
            if j is joueur or not j.vivant:
                continue
            s_j = j._score_rapide()
            if j.dans_le_dj:
                s_j += joueurs_module.TAUX_GAIN_PAR_PIOCHE * n / nb_dans_dj
            meilleur_adverse = max(meilleur_adverse, s_j)
        poids_verrou = 1.0 / (1.0 + math.exp(-(score_actuel - meilleur_adverse) / 2.0))

        cout_mort = joueurs_module.VALEUR_SURVIE_PTS + score_actuel * poids_verrou
        if joueur.medailles and not any(getattr(o, 'protege_medailles', False) and o.intact
                                        for o in joueur.objets):
            cout_mort += joueurs_module.VALEUR_MEDAILLE_PTS

        couverture_options = min(1.0, joueurs_module.EFFICACITE_OPTION * joueur._nb_options_combat()
                                 / (masse_mortelle * horizon))

        piocher_imm = fuir_imm = 0.0
        rester_p = rester_f = poids_events / n
        for (degats, puissance, gain, peut_tuer), w in profils.items():
            p = w / n
            p_esc = min(1.0, max(0.0, (7 + mod - puissance) / 6.0))
            if peut_tuer and degats >= joueur.pv_total:
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

        V = joueurs_module.BONUS_PONCEUR_PTS
        F = 0.0
        for _ in range(horizon):
            W = max(F, V)
            V = piocher_imm + rester_p * W
            F = fuir_imm + rester_f * W
        return F > V

    def choose_object_to_break(self, joueur, Jeu, log_details, reason='limon'):
        objets_intacts = [o for o in joueur.objets if o.intact]
        if not objets_intacts:
            return None

        donjon = Jeu.donjon
        restants = [donjon.cartes[i] for i in donjon.ordre[donjon.index:]]

        def valeur(o):
            if not (o.types_tags or o.puissance_tags):
                return o.priorite
            cibles = sum(1 for c in restants
                         if any(t in getattr(c, 'types_initiaux', ()) for t in o.types_tags)
                         or getattr(c, 'puissance_initiale', None) in o.puissance_tags)
            return o.priorite * cibles / (1 + cibles)

        return min(objets_intacts, key=lambda o: (o.pv_bonus >= joueur.pv_total, valeur(o)))

    def choose_repair_payment_monster(self, joueur, Jeu, log_details, monsters):
        return min(monsters, key=lambda m: m.puissance) if monsters else None

    def choose_repair_object(self, joueur, Jeu, log_details, broken_objects):
        return max(broken_objects, key=lambda o: o.pv_bonus) if broken_objects else None

    def should_use_fortune_wheel(self, joueur, Jeu, log_details, free, discardable_monsters):
        return free or (discardable_monsters and joueur.pv_total <= 6)

    def choose_fortune_wheel_monster(self, joueur, Jeu, log_details, monsters):
        return min(monsters, key=lambda m: m.puissance) if monsters else None

    def choose_soulstorm_monster(self, joueur, Jeu, log_details):
        if not joueur.pile_monstres_vaincus:
            return None
        couverts = [m for m in joueur.pile_monstres_vaincus if self._passive_line_covers_card(joueur, m)]
        if couverts:
            return max(
                couverts,
                key=lambda m: (
                    joueur._degats_attendus(m, Jeu),
                    getattr(m, 'puissance_initiale', getattr(m, 'puissance', 0)),
                    len(getattr(m, 'types_initiaux', getattr(m, 'types', ()))),
                ),
            )
        return min(
            joueur.pile_monstres_vaincus,
            key=lambda m: (
                joueur._degats_attendus(m, Jeu),
                getattr(m, 'puissance_initiale', getattr(m, 'puissance', 0)),
                len(getattr(m, 'types_initiaux', getattr(m, 'types', ()))),
            ),
        )

    def _passive_line_covers_card(self, joueur, carte):
        if getattr(carte, 'non_executable', False):
            return False
        types = getattr(carte, 'types_initiaux', getattr(carte, 'types', None))
        puissance = getattr(carte, 'puissance_initiale', getattr(carte, 'puissance', None))
        if types is None:
            return False
        for objet in joueur.objets:
            if not objet.intact or objet.actif:
                continue
            if not types and objet.nom == "Attrape-Rêves":
                return True
            if puissance in getattr(objet, 'puissance_tags', ()):
                return True
            if any(t in getattr(objet, 'types_tags', ()) for t in types):
                return True
        return False

    def choose_shop_discard(self, joueur, Jeu, log_details, intact_objects):
        echangeables = [o for o in intact_objects if o.pv_bonus <= 2]
        if not echangeables or not len(Jeu.objets_dispo):
            return None
        return min(echangeables, key=lambda o: o.priorite)

    def order_player_objects(self, joueur, objects, phase='inventory'):
        from ai_decisions import DecisionContext, DecisionKind
        return self.decide(DecisionContext(
            kind=DecisionKind.ORDER_OBJECTS,
            actor=joueur,
            game=None,
            phase=phase,
            options=tuple(objects),
        ))

    # Object decisions. Object hooks define legal timing/options; policy chooses.
    def should_use_object_in_combat(self, view, objet, carte, log_details):
        return objet.worthit(view.player, carte, view._jeu, log_details)

    def choose_couteau_suisse_repair(self, view, broken_objects):
        return random.choice(list(broken_objects)) if broken_objects else None

    def choose_gants_de_gaia_discards(self, view, broken_objects, count):
        return tuple(list(broken_objects)[-count:][::-1])

    def choose_enclume_instable_object(self, view, broken_objects):
        return random.choice(list(broken_objects)) if broken_objects else None

    def choose_corne_dabordage_monster(self, view, victim, monsters):
        return random.choice(list(monsters)) if monsters else None

    def choose_esprit_du_donjon_monster(self, view, victim, monsters):
        return random.choice(list(monsters)) if monsters else None

    def choose_canne_a_chep_object(self, view, dead_player, intact_objects):
        return random.choice(list(intact_objects)) if intact_objects else None

    def choose_sac_de_constantinople_dragon(self, view, victim, dragons):
        return random.choice(list(dragons)) if dragons else None

    def choose_pelle_du_fossoyeur_monsters(self, view, discard_monsters, max_count):
        golem_or = []
        dragons = []
        others = []
        for monster in discard_monsters:
            if getattr(monster, 'effet', None) == "GOLD":
                golem_or.append(monster)
            elif "Dragon" in getattr(monster, 'types', ()):
                dragons.append(monster)
            else:
                others.append(monster)

        chosen = []
        if golem_or:
            chosen.append(golem_or[0])
        random.shuffle(dragons)
        while len(chosen) < max_count and dragons:
            chosen.append(dragons.pop())
        random.shuffle(others)
        while len(chosen) < max_count and others:
            chosen.append(others.pop())
        return tuple(chosen)

    def choose_draw_two_keep_object(self, view, choices, source):
        return max(choices, key=lambda o: o.priorite) if choices else None

    def choose_sceptre_changeur_target(self, view, current_card, candidates, score_key):
        if not candidates:
            return None
        best = min(candidates, key=score_key)
        return best if score_key(best) < score_key(current_card) else None

    def choose_epee_vengeresse_power(self, view, scores, counts, covered_powers):
        if not scores:
            return 5
        candidates = [p for p in scores if p not in covered_powers] or list(scores)
        return max(candidates, key=lambda p: (scores[p], p, counts[p]))

    def choose_dague_vengeresse_type(self, view, scores, counts, covered_types):
        if not scores:
            return "Golem"
        candidates = [t for t in scores if t not in covered_types] or list(scores)
        return max(candidates, key=lambda t: (scores[t], counts[t], t == "Golem", t))

    def choose_imprimante_model(self, view, models):
        return max(models, key=lambda o: o.priorite) if models else None

    def choose_object_to_sacrifice(self, view, candidates):
        return min(candidates, key=lambda o: (o.pv_bonus, o.priorite)) if candidates else None

    def choose_object_to_sacrifice_like_limon(self, view, candidates):
        if not candidates:
            return None
        jeu = view._jeu

        def value(objet):
            if not (objet.types_tags or objet.puissance_tags):
                return objet.priorite
            donjon = jeu.donjon
            restants = [donjon.cartes[i] for i in donjon.ordre[donjon.index:]]
            cibles = sum(
                1
                for carte in restants
                if any(t in getattr(carte, 'types_initiaux', ()) for t in objet.types_tags)
                or getattr(carte, 'puissance_initiale', None) in objet.puissance_tags
            )
            return objet.priorite * cibles / (1 + cibles)

        return min(candidates, key=value)

    def choose_anneau_du_vent_destination(self, view, card):
        return 'bottom'

    def choose_boule_de_cristal_power(self, view, counts, covered_powers):
        if not counts:
            return None
        candidates = [p for p in counts if p not in covered_powers] or list(counts)
        return max(candidates, key=lambda p: (counts[p] * p, p, counts[p]))

    def choose_crane_du_necromancien_monster(self, view, candidates):
        return min(candidates, key=lambda m: m.puissance) if candidates else None

    def choose_coursier_volant_discard(self, view, candidates):
        inutiles = [o for o in candidates if o.priorite < 40]
        return min(inutiles, key=lambda o: o.priorite) if inutiles else None

    def should_keep_sceptre_du_maharal_monster(self, view, card):
        return True

    def choose_dague_de_brutus_beneficiary(self, view, opponents):
        return min(opponents, key=lambda j: len(j.pile_monstres_vaincus)) if opponents else None

    # Hero ability decisions. Hero hooks define legal timing/options; policy chooses.
    def should_use_ninja_flee_bonus(self, view):
        return True

    def should_use_princess_draw(self, view):
        return True

    def choose_princess_keep_object(self, view, choices):
        return max(choices, key=lambda o: o.priorite)

    def should_use_tricheur(self, view):
        return True

    def should_use_chevalier_dragon(self, view, carte):
        return True

    def should_use_docteur_de_peste(self, view, carte):
        return True

    def should_use_inventeur_genial(self, view, carte, broken_objects):
        return True

    def choose_inventeur_discards(self, view, broken_objects):
        return tuple(random.sample(list(broken_objects), 2))

    def should_use_flutiste(self, view, carte):
        return True

    def should_use_avatar(self, view, carte):
        joueur = view.player
        return carte.dommages > (joueur.pv_total / 2)

    def should_use_berserker_survive(self, view, carte):
        return True

    def should_use_prophete(self, view):
        joueur = view.player
        hero = joueur.perso_obj
        seuil = 4 if getattr(hero, 'level', 1) == 2 else 6
        return joueur.pv_total <= seuil

    def choose_prophete_cards(self, view, cards):
        joueur = view.player
        discard = []
        repose = []
        for card in cards:
            if hasattr(card, 'types') and not getattr(card, 'event', False) and card.puissance >= joueur.pv_total:
                discard.append(card)
            else:
                repose.append(card)
        return tuple(discard), tuple(repose)

    def should_shaman_reroll(self, view, jet, jet_voulu, reversed, rerolled):
        return not rerolled and not reversed and jet <= 2 and jet < jet_voulu

    def should_lapin_skip_turn(self, view, prochaine):
        joueur = view.player
        return (hasattr(prochaine, 'types') and not getattr(prochaine, 'event', False)
                and prochaine.puissance >= joueur.pv_total)

    def choose_event_beast_target(self, view, events, preferred_effects, level):
        if level == 2:
            for effet in preferred_effects:
                candidats = [c for c in events if c.effet == effet]
                if candidats:
                    return candidats[-1]
            return None
        return events[-1] if events and events[-1].effet in preferred_effects else None

    def should_face_kraken(self, joueur, carte, Jeu, log_details):
        for objet in joueur.objets:
            if objet.intact and 10 in objet.puissance_tags:
                return True, objet
        return False, None

    def should_face_guardian_angel(self, joueur, carte, Jeu, log_details):
        for objet in joueur.objets:
            if objet.intact and (8 in objet.puissance_tags or objet.nom == "Attrape-Rêves"):
                return True, objet
        return False, None

    def should_pay_traquenard(self, joueur, carte, Jeu, candidate, log_details):
        hp_gain = candidate['hp_gain']
        hp_cost = candidate['hp_cost']
        resource_cost = candidate['resource_cost']
        success_prob = candidate['success_prob']
        pv_depart = joueur.pv_total
        pv_succes = pv_depart - hp_cost + hp_gain - 3
        pv_echec = pv_depart - hp_cost - carte.dommages

        if pv_succes <= 0 or (success_prob < 1.0 and pv_echec <= 0):
            log_details.append(f"{joueur.nom} refuse de payer Traquenard: ligne suicidaire via {type(candidate['source']).__name__}.")
            return False

        gain_net = success_prob * (carte.dommages + hp_gain - 3) - hp_cost - resource_cost
        strategie = getattr(joueur, 'strategie_traquenard', 'baseline')
        if strategie == 'baseline':
            decision = pv_depart > 4 and carte.dommages > 3
        elif strategie == 'degats_purs':
            decision = carte.dommages >= 3
        elif strategie == 'net_gain':
            decision = gain_net > 0
        elif strategie == 'net_gain_prudent':
            seuil = 1.0 if resource_cost <= 1.0 else 2.0
            decision = carte.dommages >= 3 and gain_net >= seuil
        else:
            decision = pv_depart > 4 and carte.dommages > 3

        if decision:
            log_details.append(
                f"{joueur.nom} paie Traquenard via {type(candidate['source']).__name__} "
                f"[{strategie}] gain_net={gain_net:.2f}, PV succes={pv_succes:.1f}."
            )
        return decision


class DefaultDraftPolicy:
    def decide(self, context):
        method_name = f"decide_{context.kind.name.lower()}"
        method = getattr(self, method_name, None)
        if method is None:
            raise NotImplementedError(f"No policy handler for {context.kind}")
        return method(context)

    def decide_draft_pick(self, context):
        if context.phase == 'fast_draft':
            return self.choose_fast_draft_object(
                context.options,
                context.meta('perso'),
                context.meta('priors'),
                context.meta('epsilon', 0.0),
            )
        if context.phase == 'party_draft':
            return self.choose_party_draft_object(
                context.options,
                context.meta('perso'),
                context.meta('priors'),
                context.meta('mes_medailles'),
                context.meta('medailles_adverses'),
            )
        if context.phase == 'legacy_draft':
            return self.choose_draft_object(
                context.meta('player_index'),
                context.meta('objets_joueurs'),
                context.meta('mains_joueurs'),
                context.meta('personnages_assigner'),
                context.meta('log'),
            )
        return context.options[0]

    def choose_fast_draft_object(self, hand, perso, priors, epsilon=0.0):
        if epsilon and random.random() < epsilon:
            return random.choice(hand)
        import draft
        return max(hand, key=lambda o: draft.score_pick(o, perso, priors))

    def choose_party_draft_object(self, hand, perso, priors, mes_medailles, medailles_adverses):
        import party
        return max(hand, key=lambda o: party.score_pick_soiree(o, perso, priors, mes_medailles, medailles_adverses))

    def choose_draft_object(self, i, objets_joueurs, mains_joueurs, personnages_assigner, log):
        import draft
        return draft._choisirObjet_legacy(i, objets_joueurs, mains_joueurs, personnages_assigner, log)


_DEFAULT_DUNGEON_POLICY = DefaultDungeonPolicy()
_DEFAULT_DRAFT_POLICY = DefaultDraftPolicy()


def default_dungeon_policy():
    return _DEFAULT_DUNGEON_POLICY


def default_draft_policy():
    return _DEFAULT_DRAFT_POLICY
