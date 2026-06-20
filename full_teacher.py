"""Run the clone-based ISMCTS teacher on the FULL game and measure its winrate vs the heuristic.

Teacher = one seat plays fast_search's clone-based ISMCTS (current TREE_KINDS: flee / replay /
combat-object / sacrifice / repair); every other seat + all structural decisions = the real
ai_policy heuristic. We compare, on the SAME seeds and the SAME (rotated) seat, the teacher's
win fraction against the all-heuristic baseline -- neutralizing seat/seed effects.

Usage: python full_teacher.py [n_games] [iters] [seed0]
"""
import random
import sys
import time

import numpy as np

import fast_search
from ai_policy import DefaultDungeonPolicy
from full_env import build_full_match, make_full_dungeon
from simu import ordonnanceur


def teacher_win(seed, n_iters, c=1.4, p_heur=0.75):
    random.seed(seed)
    np.random.seed(seed & 0x7FFFFFFF)
    joueurs, reserve = build_full_match(seed)
    seat = seed % len(joueurs)
    donjon = make_full_dungeon()
    live = fast_search._LivePolicy(seat, seed, n_iters, c=c, p_heur=p_heur)
    winner, js = ordonnanceur(joueurs, donjon, reserve, log=False,
                              policy=live, on_turn_start=live.on_turn_start)
    return 1 if winner is js[seat] else 0


def heuristic_win(seed):
    random.seed(seed)
    np.random.seed(seed & 0x7FFFFFFF)
    joueurs, reserve = build_full_match(seed)
    seat = seed % len(joueurs)
    winner, js = ordonnanceur(joueurs, make_full_dungeon(), reserve, log=False,
                              policy=DefaultDungeonPolicy())
    return 1 if winner is js[seat] else 0


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    ITERS = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    SEED0 = int(sys.argv[3]) if len(sys.argv) > 3 else 700000
    print(f"FULL game, teacher@{ITERS} iters vs heuristic, same seeds/seats, N={N}\n", flush=True)

    tw = 0
    t0 = time.perf_counter()
    for g in range(N):
        tw += teacher_win(SEED0 + g, ITERS)
    t_teacher = time.perf_counter() - t0

    hw = sum(heuristic_win(SEED0 + g) for g in range(N))

    print(f"TEACHER  (ISMCTS@{ITERS}) wins its seat: {tw}/{N} = {tw/N:.1%}  | {t_teacher/N:.1f}s/game")
    print(f"HEURISTIC baseline same seat/seed:       {hw}/{N} = {hw/N:.1%}")
    print(f"-> teacher edge over heuristic: {(tw-hw)/N:+.1%}")
