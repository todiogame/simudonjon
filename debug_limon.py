"""Reproduce the break_object_limon crash and dump the exact decision/action."""
import random
import sys
import traceback

import numpy as np

import real_search as rs
from ai_policy import DefaultDungeonPolicy
from real_driver import RealGameDriver
from rl_toy_env import build_toy_match, make_dungeon

ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
LO = int(sys.argv[2]) if len(sys.argv) > 2 else 120
HI = int(sys.argv[3]) if len(sys.argv) > 3 else 135


def drive(seed):
    seat = seed % 2
    random.seed(seed)
    np.random.seed(seed & 0x7FFFFFFF)
    joueurs, reserve = build_toy_match(seed, deck='toy')
    donjon = make_dungeon('toy')
    heur = DefaultDungeonPolicy()
    drv = RealGameDriver(joueurs, donjon, reserve)
    s = joueurs[seat]
    prefix = []
    while not drv.terminal:
        ctx = drv.context
        if ctx.actor is s and ctx.kind.name in rs.TREE_KINDS and rs.legal_keys(ctx):
            st1, st2 = random.getstate(), np.random.get_state()
            best, visits = rs.ismcts_decide(seed, seat, prefix, ITERS, p_heur=0.75)
            random.setstate(st1)
            np.random.set_state(st2)
            if best is None:
                best = rs.action_key(ctx, heur.decide(ctx))
            act = rs.action_from_key(ctx, best, heur, lambda: heur.decide(ctx))
            if ctx.phase == 'break_object_limon' or ctx.kind.name == 'CHOOSE_OBJECT_TO_SACRIFICE':
                print(f"  [seed {seed}] LIMON searcher decision: kind={ctx.kind.name} phase={ctx.phase}")
                print(f"    options={[type(o).__name__ for o in ctx.options]} allow_none_meta={ctx.meta('allow_none')}")
                print(f"    best_key={best} -> action={act!r} (visits={visits})")
            prefix.append(best)
            drv.step(act)
        else:
            if ctx.phase == 'break_object_limon':
                act = heur.decide(ctx)
                print(f"  [seed {seed}] LIMON opponent decision: options={[type(o).__name__ for o in ctx.options]} -> {act!r}")
                drv.step(act)
            else:
                drv.step(heur.decide(ctx))
    return drv.result[0] if drv.result else None


if __name__ == '__main__':
    for seed in range(LO, HI):
        try:
            w = drive(seed)
            print(f"seed {seed}: OK winner={getattr(w,'nom',None)}")
        except Exception as e:
            print(f"seed {seed}: CRASH {type(e).__name__}: {e}")
            traceback.print_exc()
            break
