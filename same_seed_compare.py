"""Apples-to-apples teacher-vs-student comparison on ONE held-out seed bank, same seats.

Memory lesson [[same-seed-comparison]]: never compare winrates across different seed banks.
The main run reports the teacher on seeds 0..N (its gen games) and the student on 500000+;
those are sound population estimates but not a controlled head-to-head. Here BOTH play the
exact same held-out seeds with the exact same seat assignment (seat = seed % 2), vs ai_policy.

Usage: python same_seed_compare.py [iters] [n_seeds] [seed0:even] [workers] [net_path]
"""
import multiprocessing as mp
import sys

import numpy as np

import real_distill as rd
import real_search as rs


def _teacher_chunk(arg):
    lo, hi, iters = arg
    w = l = d = 0
    for seed in range(lo, hi):
        _, _, o = rd._gen_game(seed, seed % 2, iters, 0.75)
        w += o == 1
        d += o == 0
        l += o == -1
    return w, l, d, hi - lo


def teacher_winrate(seed0, n, iters, workers):
    chunk = max(1, n // (workers * 3) or 1)
    chunks = [(lo, min(lo + chunk, seed0 + n), iters)
              for lo in range(seed0, seed0 + n, chunk)]
    w = l = d = 0
    with mp.get_context('spawn').Pool(workers) as pool:
        for cw, cl, cd, _ in pool.imap_unordered(_teacher_chunk, chunks):
            w += cw
            l += cl
            d += cd
    return w, l, d


if __name__ == '__main__':
    import torch
    torch.set_num_threads(1)
    ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    SEED0 = int(sys.argv[3]) if len(sys.argv) > 3 else 600000          # even -> seats match eval_net
    WORKERS = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    NET = sys.argv[5] if len(sys.argv) > 5 else 'artifacts/real_distill.pt'
    assert SEED0 % 2 == 0, "seed0 must be even so eval_net's seat (seed-seed0)%2 == seed%2"

    print(f"held-out bank: seeds {SEED0}..{SEED0+N-1} (N={N}), same seats, vs ai_policy\n", flush=True)

    net = rd.make_net()
    net.load_state_dict(torch.load(NET))
    net.eval()
    sw, sl, sd = rd.eval_net(net, N, seed0=SEED0)
    print(f"STUDENT  vs ai_policy: win {sw:.1%} / lose {sl:.1%} / draw {sd:.1%}", flush=True)

    tw, tl, td = teacher_winrate(SEED0, N, ITERS, WORKERS)
    print(f"TEACHER@{ITERS} vs ai_policy: win {tw/N:.1%} / lose {tl/N:.1%} / draw {td/N:.1%}", flush=True)
    print(f"\nsame {N} seeds, same seats -> teacher {tw/N:.1%} vs student {sw:.1%}")
