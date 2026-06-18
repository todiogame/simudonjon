"""Distill the strong-but-slow ISMCTS into a FAST policy+value net (AlphaZero-style)
on the faithful toy engine.

ISMCTS plays games vs the heuristic and emits, at each of its decisions,
(observation -> its visit distribution over the legal moves, game outcome). A small
net is trained to match the policy (cross-entropy to visits) and the value (MSE to
outcome). The net then plays one-forward-per-decision -> fast enough for millions
of games. The teacher's moves come from LEGAL info only, so they're learnable
(unlike the clairvoyant teacher that failed to distill).

Usage: python distill_toy.py [iters] [games] [workers] [epochs]
"""
import multiprocessing as mp
import sys
import time

import numpy as np

import ismcts
import toy_engine as te

HAND = ['marteau', 'torche', 'hache', 'osselets', 'kebab']
POWERS = [1, 2, 3, 4, 5, 6, 7, 9]
OBJ = ['marteau', 'torche', 'hache', 'armure', 'osselets', 'kebab']
VOCAB = ['d1', 'd0', 'h1', 'h0', 'f1', 'f0', 'o_marteau', 'o_torche', 'o_hache', 'o_none']
VIDX = {a: i for i, a in enumerate(VOCAB)}


def _tok(kind, action):
    if kind == 'descend':
        return 'd1' if action else 'd0'
    if kind == 'heal':
        return 'h1' if action else 'h0'
    if kind == 'flee':
        return 'f1' if action else 'f0'
    return 'o_' + (action if action in ('marteau', 'torche', 'hache') else 'none')


def _untok(kind, t):
    if kind == 'descend':
        return t == 'd1'
    if kind == 'heal':
        return t == 'h1'
    if kind == 'flee':
        return t == 'f1'
    return t[2:]                              # object: marteau/torche/hache/none


def encode(s):
    """Observation = LEGAL info only (no deck order)."""
    p = s.players[s.to_move]
    o = s.players[1 - s.to_move]
    rem = [0.0] * len(POWERS)
    for i in s.order[s.idx:]:
        rem[POWERS.index(te.DECK[i][0])] += 1.0
    cur = s.current
    feats = [p.pv / 15., p.pv_max / 15., p.score / 26.,
             *[1. if p.objs.get(n) else 0. for n in OBJ],
             o.pv / 15., o.score / 26., float(o.status == 'dead'), float(o.status == 'done'),
             *[c / 4. for c in rem],
             (cur[0] / 10. if cur else 0.),
             float(cur is not None and cur[1] in ('Golem', 'Squelette')),
             float(cur is not None and cur[0] <= 2),
             float(s.phase == 'descend'), float(s.phase == 'heal'),
             float(s.phase == 'flee'), float(s.phase == 'object')]
    return np.asarray(feats, dtype=np.float32)


NFEAT = len(encode(te.new_game(0, HAND)))


# --- parallel ISMCTS data generation (no torch in the workers) ---------------
def _gen_worker(arg):
    lo, hi, iters = arg
    out = []
    for seed in range(lo, hi):
        seat = seed % 2
        s = te.new_game(seed, HAND)
        recs = []
        while not s.terminal:
            if s.to_move == seat:
                kind, _ = te.legal(s)
                best, visits = ismcts.ismcts_decide(s, seat, iters, return_visits=True)
                pol = np.zeros(len(VOCAB), dtype=np.float32)
                tot = sum(visits.values()) or 1
                for a, v in visits.items():
                    pol[VIDX[_tok(kind, a)]] = v / tot
                recs.append((encode(s), pol))
                s = te.step(s, best)
            else:
                s = te.step(s, te.heuristic_action(s))
        z = 1. if s.winner == seat else (0. if s.winner is None else -1.)
        out += [(f, p, z) for f, p in recs]
    return out


def gen_data(games, iters, workers):
    per = max(1, games // workers)
    chunks, lo = [], 0
    while lo < games:
        chunks.append((lo, min(lo + per, games), iters))
        lo += per
    if workers <= 1:
        res = [_gen_worker(c) for c in chunks]
    else:
        with mp.get_context('spawn').Pool(workers) as pool:
            res = pool.map(_gen_worker, chunks)
    return [r for chunk in res for r in chunk]


# --- net (torch imported lazily so workers don't load it) --------------------
def make_net():
    import torch.nn as nn

    class Net(nn.Module):
        def __init__(s):
            super().__init__()
            s.body = nn.Sequential(nn.Linear(NFEAT, 128), nn.ReLU(),
                                   nn.Linear(128, 128), nn.ReLU())
            s.pol = nn.Linear(128, len(VOCAB))
            s.val = nn.Linear(128, 1)

        def forward(s, x):
            h = s.body(x)
            return s.pol(h), s.val(h).squeeze(-1)
    return Net()


def train(net, data, epochs):
    import torch
    import torch.nn.functional as F
    X = torch.from_numpy(np.stack([d[0] for d in data]))
    P = torch.from_numpy(np.stack([d[1] for d in data]))
    Z = torch.from_numpy(np.asarray([d[2] for d in data], dtype=np.float32))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    n = len(data)
    for ep in range(epochs):
        perm = torch.randperm(n)
        for i in range(0, n, 512):
            idx = perm[i:i + 512]
            logits, value = net(X[idx])
            loss_p = -(P[idx] * F.log_softmax(logits, dim=1)).sum(1).mean()
            loss_v = F.mse_loss(value, Z[idx])
            opt.zero_grad()
            (loss_p + loss_v).backward()
            opt.step()
    net.eval()


def net_action(net, s):
    import torch
    kind, opts = te.legal(s)
    if not opts:
        return None
    with torch.no_grad():
        logits, _ = net(torch.from_numpy(encode(s)).unsqueeze(0))
    logits = logits[0].numpy()
    best_tok = max((_tok(kind, a) for a in opts), key=lambda t: logits[VIDX[t]])
    return _untok(kind, best_tok)


def eval_net(net, n=2000):
    w = l = d = 0
    for g in range(n):
        seat = g % 2
        s = te.new_game(g + 500_000, HAND)            # eval seeds disjoint from training
        while not s.terminal:
            a = net_action(net, s) if s.to_move == seat else te.heuristic_action(s)
            s = te.step(s, a)
        if s.winner == seat:
            w += 1
        elif s.winner is None:
            d += 1
        else:
            l += 1
    return w / n, l / n, d / n


if __name__ == '__main__':
    import torch
    torch.set_num_threads(1)
    ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    GAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    WORKERS = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    EPOCHS = int(sys.argv[4]) if len(sys.argv) > 4 else 60

    t0 = time.perf_counter()
    print(f"[1] generating data: {GAMES} ISMCTS games @ {ITERS} iters, {WORKERS} workers...", flush=True)
    data = gen_data(GAMES, ITERS, WORKERS)
    print(f"    {len(data)} decisions in {time.perf_counter()-t0:.0f}s", flush=True)

    print("[2] training the policy+value net...", flush=True)
    net = make_net()
    train(net, data, EPOCHS)

    print("[3] evaluating the FAST net (no search) vs heuristic, seat-rotated...", flush=True)
    w, l, dr = eval_net(net)
    print(f"\n  teacher ISMCTS@{ITERS} vs heuristic : ~54% (from the sweep)")
    print(f"  distilled NET (fast)  vs heuristic : {w:.1%} win / {l:.1%} loss / {dr:.1%} draw")
    print(f"  heuristic baseline                 : ~45%")
