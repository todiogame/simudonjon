"""Compact engine for the TOY content -- a lean reimplementation of ordonnanceur's toy-exercised
path, validated byte-equivalent. The heavy ordonnanceur pays for branches/hook-dispatch the toy
never uses (the per-card effet if-chain, the en_rencontre/en_subit/en_vaincu/en_mort/en_fuite no-op
hook loops over every player x object, CarteEvent handling, traquenard, special cards). The toy
exercises only: alternating turns, flee (+roll), the combat-object phase, the LIMON sacrifice,
damage, the Coquille en_survie save, normal death, the Coeur fin_tour, and replay/pass + scoring.

We REUSE the real object/card/Joueur methods + _run_combat_object_phase (so the rules stay
identical) and only strip the dead control flow + no-op hook loops. Live hooks for the toy pool
are exactly: combat objects (via _run_combat_object_phase), en_survie (Coquille), fin_tour (Coeur);
no perso hooks; no en_rencontre/en_subit/en_vaincu/en_mort/en_fuite/debut_tour. If content changes,
re-validate with the harness in __main__.

Usage: python compact_engine.py [n_seeds]   (byte-equivalence vs ordonnanceur + speedup)
"""
import random
import sys
import time

import numpy as np

from ai_decisions import CombatObjectChoice, DecisionContext, DecisionKind, require_option
from simu import (GameState, SANS_HOOK_OBJET, _finaliser_mort_immediate,
                  _run_combat_object_phase)


def play(joueurs, donjon, reserve, policy, log_details=None):
    """Play one full toy game. Returns (vainqueur, joueurs). Byte-equivalent to
    simu.ordonnanceur for toy content (see __main__ harness)."""
    ld = log_details if log_details is not None else []
    donjon.melange()
    Jeu = GameState(joueurs, donjon, reserve, policy)
    for j in joueurs:
        j.partie_joueurs = joueurs
        j.ordonner_objets_pour_ia()
        j.appliquer_panoplies(ld)
        j.perso_obj.debut_partie(j, Jeu, ld)
        for o in j.objets:
            o.debut_partie(j, Jeu, ld)

    return _run_compact(Jeu, joueurs, donjon, 0, ld)


def _run_compact(Jeu, joueurs, donjon, index, ld):
    nb = len(joueurs)
    O_COMBAT = SANS_HOOK_OBJET['en_combat']
    O_SURVIE = SANS_HOOK_OBJET['en_survie']
    O_FIN = SANS_HOOK_OBJET['fin_tour']
    O_MORT = SANS_HOOK_OBJET['en_mort']

    while not donjon.vide:
        if not any(j.dans_le_dj for j in joueurs):
            break
        while not joueurs[index].dans_le_dj:
            index = (index + 1) % nb
        joueur = joueurs[index]

        # debut de tour: reset des drapeaux (les hooks debut_tour sont no-op pour le toy)
        for j in joueurs:
            j.rejoue = False
            j.doit_passer = False
            j.reset_monstres_ajoutes()

        carte = donjon.prochaine_carte()
        if carte is None:
            break
        # reset etat transient de la carte (CarteMonstre uniquement dans le toy)
        Jeu.carte_ignoree = False
        carte.executed = False
        carte.puissance = carte.puissance_initiale
        carte.types = list(carte.types_initiaux)
        carte.dommages_reference = 0
        carte.dommages_minimum = 0
        carte.reduction_dommages_bloquee = False

        joueur.jet_fuite_lance = False
        if joueur.deciderDeFuir(Jeu, ld):
            joueur.jet_fuite = joueur.rollDice(Jeu, ld) + joueur.calculer_modificateurs()
            joueur.jet_fuite_lance = True
            # hooks en_fuite: no-op pour le toy

        effet_carte = carte.effet            # None sauf "LIMON"
        carte_ignoree = False
        carte.dommages = carte.puissance     # pas d'effet modificateur de puissance dans le toy
        # hooks en_rencontre: no-op
        carte.dommages_reference = carte.dommages

        if joueur.jet_fuite_lance:
            if joueur.jet_fuite >= carte.puissance:
                joueur.fuite()
                donjon.rajoute_en_haut_de_la_pile(carte)
                joueur.jet_fuite_lance = False
                # hooks en_fuite_definitive: no-op
                continue
            joueur.jet_fuite_lance = False

        # phase objets de combat (execute_next_monster jamais actif dans le toy)
        if not carte_ignoree:
            carte, combat_ignoree, remplacement = _run_combat_object_phase(joueur, carte, Jeu, ld, O_COMBAT)
            if combat_ignoree:
                carte_ignoree = True
            if not joueur.vivant or joueur.pv_total <= 0:
                _finaliser_mort_immediate(joueur, carte, effet_carte, carte_ignoree, Jeu, donjon, ld, O_MORT)
                index = (index + 1) % nb
                continue
            if not joueur.dans_le_dj:
                if not carte.executed:
                    donjon.rajoute_en_haut_de_la_pile(carte)
                continue

        # degats
        if not carte_ignoree and not carte.executed:
            joueur.pv_total -= carte.dommages
            if joueur.vivant and joueur.pv_total > 0:
                joueur.ajouter_monstre_vaincu(carte)
            if effet_carte == "LIMON":
                options = tuple(o for o in joueur.objets if o.intact)
                avale = Jeu.policy.decide(DecisionContext(
                    kind=DecisionKind.CHOOSE_OBJECT_TO_SACRIFICE, actor=joueur, game=Jeu,
                    phase='break_object_limon', subject=carte, options=options,
                    metadata={'reason': 'limon', 'log_details': ld}))
                avale = require_option(avale, options, allow_none=True, decision_name='break_object_limon')
                if avale:
                    avale.destroy(joueur, Jeu, ld)
                    joueur._gerer_pv_bonus(avale, ld)
            # hooks en_subit_dommages: no-op

        # objets de survie (Coquille)
        if joueur.pv_total <= 0:
            for o in joueur.objets:
                if type(o) in O_SURVIE:
                    continue
                o.en_survie(joueur, carte, Jeu, ld)
                if joueur.pv_total > 0:
                    break
            if carte in joueur.pile_monstres_vaincus:
                if carte in Jeu.defausse or carte.index in Jeu.donjon.ordre[Jeu.donjon.index:]:
                    joueur.pile_monstres_vaincus.remove(carte)

        # mort
        if joueur.pv_total <= 0:
            joueur.mort(ld)
            # hooks en_mort: no-op
            if (not carte.executed and not carte_ignoree and effet_carte != "MAUDIT"
                    and carte not in joueur.pile_monstres_vaincus):
                donjon.rajoute_en_haut_de_la_pile(carte)
            index = (index + 1) % nb
            continue

        # hooks en_vaincu: no-op

        if (joueur.dans_le_dj and not joueur.rejoue and not Jeu.execute_next_monster
                and not joueur.doit_passer and joueur.deciderDeRejouer(Jeu, ld)):
            joueur.rejoue = True

        if joueur.dans_le_dj and (not joueur.rejoue and not Jeu.execute_next_monster):
            for o in joueur.objets:                       # fin_tour (Coeur de Tarasque)
                if type(o) not in O_FIN:
                    o.fin_tour(joueur, Jeu, ld)
            joueur.tour += 1
            if len([j for j in joueurs if j.dans_le_dj]) > 1:
                index = (index + 1) % nb
        else:
            joueur.rejoue = True

    return _score(joueurs, ld)


def _score(joueurs, ld):
    for j in joueurs:
        j.calculScoreFinal(ld)
    dans_dj = [j for j in joueurs if j.dans_le_dj]
    final = dans_dj if dans_dj else [j for j in joueurs if j.vivant]
    for j in joueurs:
        for o in j.objets:
            o.en_decompte(j, final, ld)
    for j in joueurs:
        j.compte_au_score = j in final
    final.sort(key=lambda j: j.score_final, reverse=True)
    if not final:
        return None, joueurs
    egal = [j for j in final if j.score_final == final[0].score_final]
    if len(egal) > 1:
        tb = [j for j in joueurs if j.tiebreaker and j.vivant]
        vainqueur = tb[0] if tb else random.choice(egal)
    else:
        vainqueur = egal[0]
    return vainqueur, joueurs


# --- byte-equivalence vs ordonnanceur + speedup ----------------------------------------
if __name__ == '__main__':
    from ai_policy import DefaultDungeonPolicy
    from rl_toy_env import build_toy_match, make_dungeon
    from simu import ordonnanceur

    N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000

    def _seed(s):
        random.seed(s)
        np.random.seed(s & 0x7FFFFFFF)

    def _result(winner, joueurs):
        w = winner.nom if winner is not None else None
        return (w, tuple((j.nom, j.score_final, j.vivant, j.dans_le_dj, j.pv_total,
                          len(j.pile_monstres_vaincus)) for j in joueurs))

    def run_ord(s):
        _seed(s)
        js, res = build_toy_match(s, deck='toy')
        d = make_dungeon('toy')
        w, _ = ordonnanceur(js, d, res, log=False, policy=DefaultDungeonPolicy())
        return _result(w, js)

    def run_compact(s):
        _seed(s)
        js, res = build_toy_match(s, deck='toy')
        d = make_dungeon('toy')
        w, _ = play(js, d, res, DefaultDungeonPolicy())
        return _result(w, js)

    same = 0
    mismatches = []
    for s in range(N):
        a, b = run_ord(s), run_compact(s)
        if a == b:
            same += 1
        elif len(mismatches) < 8:
            mismatches.append((s, a, b))
    print(f"byte-equivalence compact vs ordonnanceur: {same}/{N}")
    for s, a, b in mismatches:
        print(f"  seed {s}:\n    ord    ={a}\n    compact={b}")

    if same == N:
        REP = max(2000, N)
        t0 = time.perf_counter()
        for s in range(REP):
            run_ord(s)
        t_ord = time.perf_counter() - t0
        t0 = time.perf_counter()
        for s in range(REP):
            run_compact(s)
        t_cmp = time.perf_counter() - t0
        print(f"\nspeed over {REP} games: ordonnanceur {t_ord*1000/REP:.3f} ms/game | "
              f"compact {t_cmp*1000/REP:.3f} ms/game -> x{t_ord/t_cmp:.2f}")
    print("\nPASS" if same == N else "\nFAIL (fix divergences before trusting the compact engine)")
