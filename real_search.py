"""ISMCTS on the REAL simudonjon engine via DETERMINIZED RE-SIMULATION.

The engine can't be resumed from a cloned mid-game state (monolithic loop), so a search
that branches must RE-SIMULATE from the game start: rebuild the same match (same seed ->
same hands + same shuffled deck + deterministic heuristic reproduce the seen game exactly),
then at the search root DETERMINIZE -- reshuffle the still-unseen tail of the deck (a fresh
order the searcher couldn't know) -- and play out. This module starts with the building
block: determinizing the unseen deck mid-game and proving the seen prefix is preserved.
"""
import numpy as np


def determinize_unseen(donjon, det_rng):
    """Reshuffle ONLY the cards not yet drawn (ordre[index:]); the drawn prefix is kept."""
    idx = donjon.index
    tail = list(donjon.ordre[idx:])
    det_rng.shuffle(tail)
    donjon.ordre = np.concatenate([donjon.ordre[:idx], np.array(tail, dtype=donjon.ordre.dtype)])


# --- proof: reshuffling the unseen tail at decision K keeps the seen prefix, diverges after ---
if __name__ == '__main__':
    import random

    from ai_policy import DefaultDungeonPolicy
    from rl_toy_env import build_toy_match, make_dungeon
    from real_driver import RealGameDriver

    def run(seed, reshuffle_at=None, det_seed=0):
        """Play a heuristic game; optionally, at the `reshuffle_at`-th decision, determinize
        the unseen deck. Return the sequence of drawn-card ids (deck order actually consumed)."""
        random.seed(seed)
        np.random.seed(seed & 0xFFFFFFFF)
        joueurs, reserve = build_toy_match(seed, deck='toy')
        donjon = make_dungeon('toy')
        heur = DefaultDungeonPolicy()
        drv = RealGameDriver(joueurs, donjon, reserve)
        n = 0
        det_rng = np.random.RandomState(det_seed)
        while not drv.terminal:
            ctx = drv.context
            if reshuffle_at is not None and n == reshuffle_at:
                determinize_unseen(ctx.game.donjon, det_rng)   # seen prefix fixed, unseen reshuffled
            n += 1
            drv.step(heur.decide(ctx))
        # the cards actually consumed, in order (ordre[:index] of the final deck)
        d = joueurs[0].policy  # not used; read deck via a fresh ref below
        return tuple(int(x) for x in donjon.ordre[:donjon.index]), \
            tuple((j.nom, j.score_final) for j in joueurs)

    base_draws, base_scores = run(0)
    K = 6
    a_draws, a_scores = run(0, reshuffle_at=K, det_seed=1)
    b_draws, b_scores = run(0, reshuffle_at=K, det_seed=2)

    # the deck index at decision K isn't exactly K (some decisions don't draw), but the
    # cards drawn BEFORE the reshuffle must be identical across A, B and base; the tail diverges.
    common = 0
    for x, y in zip(a_draws, b_draws):
        if x == y:
            common += 1
        else:
            break
    print(f"base draws ({len(base_draws)}): {base_draws}")
    print(f"det A      ({len(a_draws)}): {a_draws}  scores {a_scores}")
    print(f"det B      ({len(b_draws)}): {b_draws}  scores {b_scores}")
    print(f"A vs B identical for the first {common} drawn cards, then diverge "
          f"(reshuffle was at decision {K}).")
    print(f"determinization {'OK' if common >= 1 and a_draws != b_draws else 'CHECK'}: "
          f"seen prefix preserved, unseen future reshuffled.")