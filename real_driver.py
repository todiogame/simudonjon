"""Steppable adapter over the REAL simudonjon engine (simu.ordonnanceur).

`ordonnanceur` is a monolithic loop that calls `policy.decide(context)` at every decision
(deep inside nested loops and object/hero hooks), so it can't be paused with a generator.
We instead run it in a background thread whose policy BLOCKS on a queue: the outside world
drives it decision-by-decision.

    drv = RealGameDriver(joueurs, donjon, objets_dispo)
    while not drv.terminal:
        ctx = drv.context           # the pending DecisionContext (kind, actor, options, ...)
        drv.step(my_action)         # supply the chosen action, advance to the next decision
    winner = drv.result             # ordonnanceur's return value

This makes the real engine OBSERVABLE/CONTROLLABLE with zero rewrite -- the substrate for
a net policy, for measuring vs the real ai_policy.py, and for ISMCTS re-simulation. (It
gives forward stepping of ONE trajectory; branching for search is done by re-running fresh
drivers with a determinized deck, since a paused thread can't be cloned.)
"""
import queue
import threading

from simu import ordonnanceur


class _QueuePolicy:
    """A policy whose decide() hands the context to the driver and blocks for the action."""

    def __init__(self, out_q, in_q):
        self._out, self._in = out_q, in_q

    def decide(self, context):
        self._out.put(('decide', context))
        action = self._in.get()
        if isinstance(action, _Abort):
            raise action                      # let us tear the engine thread down cleanly
        return action


class _Abort(BaseException):
    pass


class RealGameDriver:
    def __init__(self, joueurs, donjon, objets_dispo, log=False):
        self._out = queue.Queue()             # engine thread -> driver
        self._in = queue.Queue()              # driver -> engine thread
        policy = _QueuePolicy(self._out, self._in)

        def _run():
            try:
                res = ordonnanceur(joueurs, donjon, objets_dispo, log=log, policy=policy)
                self._out.put(('done', res))
            except _Abort:
                pass
            except BaseException as e:        # surface engine errors to the driver side
                self._out.put(('error', e))

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        self._pending = self._out.get()

    @property
    def terminal(self):
        return self._pending[0] != 'decide'

    @property
    def context(self):
        return self._pending[1] if self._pending[0] == 'decide' else None

    @property
    def result(self):
        if self._pending[0] == 'error':
            raise self._pending[1]
        return self._pending[1] if self._pending[0] == 'done' else None

    def step(self, action):
        if self._pending[0] != 'decide':
            raise RuntimeError("game already finished")
        self._in.put(action)
        self._pending = self._out.get()
        return self._pending

    def close(self):
        """Abandon an unfinished game (unblock and stop the engine thread)."""
        if self._pending[0] == 'decide':
            self._in.put(_Abort())
            self._thread.join(timeout=1.0)


# --- self-test: the driver must reproduce a direct ordonnanceur run exactly ---------
if __name__ == '__main__':
    import random

    import numpy as np

    from ai_policy import DefaultDungeonPolicy
    from rl_toy_env import build_toy_match, make_dungeon

    def _seed(s):
        random.seed(s)
        np.random.seed(s & 0xFFFFFFFF)

    def _snapshot(joueurs, winner):
        w = winner.nom if winner is not None else None
        return (w, tuple((j.nom, j.score_final, j.vivant, j.dans_le_dj) for j in joueurs))

    def direct(s):
        _seed(s)
        joueurs, reserve = build_toy_match(s, deck='toy')
        donjon = make_dungeon('toy')
        winner, _ = ordonnanceur(joueurs, donjon, reserve, log=False, policy=DefaultDungeonPolicy())
        return _snapshot(joueurs, winner)

    def via_driver(s):
        _seed(s)
        joueurs, reserve = build_toy_match(s, deck='toy')
        donjon = make_dungeon('toy')
        heur = DefaultDungeonPolicy()
        drv = RealGameDriver(joueurs, donjon, reserve)
        steps = 0
        while not drv.terminal:
            drv.step(heur.decide(drv.context))    # relay the real heuristic's decision
            steps += 1
        winner = drv.result[0] if drv.result else None
        return _snapshot(joueurs, winner), steps

    ok = 0
    for s in range(40):
        d = direct(s)
        v, steps = via_driver(s)
        match = (d == v)
        ok += match
        if not match:
            print(f"seed {s}: MISMATCH\n  direct={d}\n  driver={v}")
    print(f"driver reproduces direct ordonnanceur: {ok}/40 seeds match")