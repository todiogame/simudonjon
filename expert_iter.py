"""Expert iteration on the toy: bootstrap a NET that beats the heuristic, then
plays FAST (no search) so it can simulate millions of games.

Warmstarted from the heuristic clone, then loop:
  1. self-play: a DETERMINISED 1-ply search whose ROLLOUT TAIL is the CURRENT net
     plays vs the heuristic; record (state -> the search's chosen move, outcome).
     Determinised => the search uses only LEGAL info, so its moves are learnable
     (unlike the clairvoyant teacher, which failed to distill).
  2. train: behaviour-clone the net toward the search's moves (policy head) and the
     game outcome (value head).
  3. eval: the net's GREEDY policy (no search) vs the heuristic.

As the net improves, the rollout tail improves -> the search improves -> the net
improves: the bootstrap that should break the 1-ply-with-heuristic-tail parity
ceiling. The final net plays one-forward-per-decision -> millions of games.

Usage: python expert_iter.py [iterations] [selfplay_games] [k_samples]
"""
import contextlib
import io
import sys

import torch

torch.set_num_threads(1)  # batch-1 net forwards are faster single-threaded

import rl_toy
import rl_toy_env as env
import rollout_search as rs
from ai_policy import default_dungeon_policy
from simu import ordonnanceur

DECK = 'toy'
EVAL_GAMES = 600


def build(seed):
    return env.build_toy_match(seed, deck=DECK)


def net_tail(model, encoder):
    """Factory for the rollout-tail policy = the current net, greedy (shares model)."""
    return lambda: rl_toy._make_toy_policy(model, encoder, sample=False, record=False)


def selfplay_collect(model, encoder, n, seed0, k):
    model.eval()
    tail = net_tail(model, encoder)
    samples = []
    for i in range(n):
        s = seed0 + i
        seat = s % 2
        joueurs, objets = build(s)
        search = rs.DetSearchPolicy(s, seat, build, objective=rs.outcome_win,
                                    k_samples=k, tail_factory=tail)
        # structural_kinds=() so the search sees EVERY decision (replay alignment);
        # only TOY_MANAGED_KINDS are recorded for cloning.
        rec = rl_toy._DemoRecorder(encoder, managed_kinds=env.TOY_MANAGED_KINDS, structural_kinds=())
        rec.heuristic = search
        pols = {seat: rec, 1 - seat: default_dungeon_policy()}
        routed = env.routed_toy_policy(pols, joueurs)
        with contextlib.redirect_stdout(io.StringIO()):
            winner, _ = ordonnanceur(joueurs, env.make_dungeon(DECK), objets, False, policy=routed)
        ret = rl_toy._terminal_reward(joueurs[seat], winner, joueurs, mode='margin')
        for sm in rec.samples:
            sm['return'] = ret
        samples.extend(rec.samples)
    return samples


def eval_net(model, encoder):
    bank = list(range(900_000, 900_000 + EVAL_GAMES))
    res = rl_toy.evaluate_toy(model, encoder, bank, baseline='default', deck=DECK, num_workers=6)
    return res['winrate'], res['loss_rate'], res['draw_rate']


def main():
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    n_self = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 8

    model, encoder = rl_toy.build_toy_model()
    print("[warmstart] cloning the heuristic (policy + value)...", flush=True)
    demos = rl_toy.collect_heuristic_demonstrations(encoder, num_games=1500, deck=DECK, reward_mode='margin')
    rl_toy.behavior_clone(model, demos, epochs=15, device='cpu')
    w, l, d = eval_net(model, encoder)
    print(f"[warmstart] net greedy vs heuristic: {w:.1%} / {l:.1%} / {d:.1%}", flush=True)

    # Accumulating replay buffer of SELF-PLAY (search) decisions -- NOT the heuristic
    # demos (which would anchor us to the heuristic and cap improvement). Gentle
    # fine-tuning (few epochs, low LR) so each iteration nudges, never overwrites.
    buf = []
    for it in range(1, iters + 1):
        new = selfplay_collect(model, encoder, n_self, seed0=it * 100_000, k=k)
        buf = (buf + new)[-12000:]
        rl_toy.behavior_clone(model, buf, epochs=3, lr=3e-4, device='cpu')
        w, l, d = eval_net(model, encoder)
        print(f"[iter {it}] +{len(new)} decisions (buf {len(buf)}) | "
              f"net greedy vs heuristic: {w:.1%} / {l:.1%} / {d:.1%}", flush=True)


if __name__ == '__main__':
    main()
