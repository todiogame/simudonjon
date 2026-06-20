"""Full-game match setup (canonical _simuler_batch style) for the teacher/student pipeline.

3-4 players, real heroes (random from the 34-instance pool), 6 random objects per hand drawn
without replacement from the full 271-object pool, a fresh full DonjonDeck (57 cards). Each
build resets the shared global object/hero state (repare + priorite + capacite) so consecutive
games are clean and a given seed is reproducible.

The teacher uses the CLONE-based search (fast_search), which deep-copies the live state -- so we
never rebuild a match mid-search and don't depend on global-state reproducibility beyond one
clean game per seed.
"""
import json
import os
import random

import numpy as np

from heros import persos_disponibles
from joueurs import Joueur
from monstres import DonjonDeck
from objets import objets_disponibles

_NAMES = ["Sagarex", "Francis", "Mastho", "Mr.Adam"]
_PRIOR = None


def _priorites():
    global _PRIOR
    if _PRIOR is None:
        path = os.path.join(os.path.dirname(__file__), 'priorites_objets.json')
        try:
            with open(path) as f:
                _PRIOR = json.load(f)
        except Exception:
            _PRIOR = {}
    return _PRIOR


def build_full_match(seed):
    """Deterministic from `seed`. Returns (joueurs, reserve). Resets shared global state."""
    random.seed(seed)
    np.random.seed(seed & 0x7FFFFFFF)
    prior = _priorites()
    pool = list(objets_disponibles)
    for o in pool:
        o.repare()
        o.priorite = min(100, max(0, prior.get(o.nom, 49.5) + random.uniform(-20, 20)))
    for p in persos_disponibles:
        p.capacite_utilisee = False
    nb = random.choice([3, 4])
    persos = random.sample(persos_disponibles, nb)
    joueurs = []
    for i in range(nb):
        hand = random.sample(pool, 6)
        for o in hand:
            pool.remove(o)
        joueurs.append(Joueur(_NAMES[i], persos[i], hand))
    return joueurs, pool


def make_full_dungeon():
    return DonjonDeck()


# --- sanity: full games run cleanly + heuristic winrate is ~balanced across seats -----
if __name__ == '__main__':
    import sys
    from collections import Counter

    from ai_policy import DefaultDungeonPolicy
    from simu import ordonnanceur

    N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    wins = Counter()
    nbc = Counter()
    none_winner = 0
    for s in range(N):
        random.seed(s)
        np.random.seed(s & 0x7FFFFFFF)
        joueurs, reserve = build_full_match(s)
        nbc[len(joueurs)] += 1
        w, js = ordonnanceur(joueurs, make_full_dungeon(), reserve, log=False, policy=DefaultDungeonPolicy())
        if w is None:
            none_winner += 1
        else:
            wins[js.index(w)] += 1
    print(f"{N} full games ran cleanly. player-count mix: {dict(nbc)}")
    print(f"winner by seat: {dict(sorted(wins.items()))}  (none: {none_winner})")
    print(f"-> baseline single-seat winrate ~ {sum(wins.values())/N/ (sum(k*v for k,v in nbc.items())/N):.2%} "
          f"(1/avg_players)")
