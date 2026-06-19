"""Distill the real-engine ISMCTS teacher (real_search) into a FAST policy+value net that
plays simudonjon's real ordonnanceur, then measure both vs the real ai_policy.py.

Teacher: ISMCTS by determinized re-simulation with a PUCT heuristic prior (p_heur=0.75) at
1500 iters -> beats ai_policy. It emits, at each of its gameplay decisions, (observation ->
visit distribution over the action vocab, game outcome). A small embedding net is trained
to match it and then plays one-forward-per-decision (fast). Toy CONTENT on the real engine
(the 14-object TOY_OBJECT_POOL + ToyDonjon); the real ai_policy.py is the opponent.

Usage: python real_distill.py [iters] [games] [workers] [epochs] [p_heur]
"""
import multiprocessing as mp
import sys
import time

import numpy as np

import real_search as rs
from rl_toy_env import TOY_OBJECT_POOL, build_toy_match, make_dungeon

# --- catalogue (built from the toy content, not hardcoded lists) -------------
CATALOG = [c.__name__ for c in TOY_OBJECT_POOL]          # 14 object classes
CAT_IDX = {n: i for i, n in enumerate(CATALOG)}
CARD_TITLES = sorted({c.titre for c in make_dungeon('toy').cartes})   # distinct dungeon cards
KINDS = ['SHOULD_FLEE', 'SHOULD_REPLAY', 'CHOOSE_COMBAT_OBJECT',
         'CHOOSE_OBJECT_TO_SACRIFICE', 'CHOOSE_OBJECT_TO_REPAIR']
STRUCT = ['flee_no', 'flee_yes', 'replay_no', 'replay_yes', 'resolve', 'none']
VOCAB = STRUCT + ['use_' + c for c in CATALOG]
VIDX = {a: i for i, a in enumerate(VOCAB)}
NACT = len(VOCAB)
EMB = 16


def _inv(j):
    held = {type(o).__name__ for o in j.objets if o.intact}
    return [1. if n in held else 0. for n in CATALOG]


def encode_ctx(ctx):
    """Observation = LEGAL info: own/opp pv-score-status, both inventories, the faced card
    (power + identity), the remaining-deck composition, and the decision kind."""
    p = ctx.actor
    g = ctx.game
    opp = next(j for j in g.joueurs if j is not p)
    d = g.donjon
    rem = [0.] * len(CARD_TITLES)
    for idx in d.ordre[d.index:]:
        rem[CARD_TITLES.index(d.cartes[idx].titre)] += 1.
    card = ctx.subject
    cp = getattr(card, 'puissance', 0) or 0
    ctitre = [1. if card is not None and getattr(card, 'titre', None) == t else 0. for t in CARD_TITLES]
    phase = [1. if ctx.kind.name == k else 0. for k in KINDS]
    feats = [p.pv_total / 30., len(p.pile_monstres_vaincus) / 30., min(p.tour, 9) / 9.,
             opp.pv_total / 30., len(opp.pile_monstres_vaincus) / 30.,
             float(not opp.vivant), float(opp.fuite_reussie),
             cp / 10., *ctitre, *[c / 4. for c in rem], *phase, *_inv(p), *_inv(opp)]
    return np.asarray(feats, dtype=np.float32)


def key_to_vocab(ctx, key):
    t = key[0]
    if t == 'b':
        yes = key[1]
        return ('flee_yes' if yes else 'flee_no') if ctx.kind.name == 'SHOULD_FLEE' \
            else ('replay_yes' if yes else 'replay_no')
    if t == 'r':
        return 'resolve'
    if t == 'n':
        return 'none'
    if t == 'o':
        return 'use_' + type(list(ctx.options)[key[1]]).__name__
    return None


def legal_pairs(ctx):
    """[(key, vocab_token)] for the current decision's legal actions."""
    out = []
    for k in rs.legal_keys(ctx):
        v = key_to_vocab(ctx, k)
        if v is not None:
            out.append((k, v))
    return out


# --- parallel data generation (teacher@iters vs ai_policy; no torch in workers) ---
def _gen_worker(arg):
    from collections import defaultdict
    lo, hi, iters, p_heur = arg
    out, st = [], defaultdict(int)
    for seed in range(lo, hi):
        seat = seed % 2
        recs, z, outcome = _gen_game(seed, seat, iters, p_heur)
        out += recs
        st['games'] += 1
        st['w'] += outcome == 1
        st['d'] += outcome == 0
        st['l'] += outcome == -1
    return out, dict(st)


def _gen_game(seed, seat, iters, p_heur):
    """Drive a real game: searcher seat = ISMCTS teacher, opponent = ai_policy. Record
    (encoded obs, visit-policy over VOCAB, legal-mask) at each searcher gameplay decision,
    then stamp the game outcome z."""
    import random
    from ai_policy import DefaultDungeonPolicy
    from real_driver import RealGameDriver
    random.seed(seed)
    np.random.seed(seed & 0x7FFFFFFF)
    joueurs, reserve = build_toy_match(seed, deck='toy')
    donjon = make_dungeon('toy')
    heur = DefaultDungeonPolicy()
    drv = RealGameDriver(joueurs, donjon, reserve)
    s = joueurs[seat]
    prefix = []
    recs = []
    while not drv.terminal:
        ctx = drv.context
        if ctx.actor is s and ctx.kind.name in rs.TREE_KINDS:
            st1, st2 = random.getstate(), np.random.get_state()
            best, visits = rs.ismcts_decide(seed, seat, prefix, iters, p_heur=p_heur)
            random.setstate(st1)
            np.random.set_state(st2)
            if best is None:
                best = rs.action_key(ctx, heur.decide(ctx))
            pol = np.zeros(NACT, dtype=np.float32)
            mask = np.zeros(NACT, dtype=bool)
            for k, v in legal_pairs(ctx):
                mask[VIDX[v]] = True
            tot = sum(visits.values()) or 1
            for k, c in visits.items():
                v = key_to_vocab(ctx, k)
                if v is not None:
                    pol[VIDX[v]] += c / tot
            recs.append([encode_ctx(ctx), pol, mask])
            prefix.append(best)
            drv.step(rs.action_from_key(ctx, best, heur, lambda: heur.decide(ctx)))
        else:
            drv.step(heur.decide(ctx))
    w = drv.result[0] if drv.result else None
    outcome = 1 if w is s else (0 if w is None else -1)
    z = float(outcome)
    return [(f, p, m, z) for f, p, m in recs], z, outcome


def gen_data(games, iters, workers, p_heur):
    chunk = max(1, min(10, games // (workers * 4) or 1))
    chunks, lo = [], 0
    while lo < games:
        chunks.append((lo, min(lo + chunk, games), iters, p_heur))
        lo += chunk
    from collections import defaultdict
    data, st = [], defaultdict(int)
    t0 = time.perf_counter()
    done = 0

    def absorb(res):
        nonlocal done
        out, cst = res
        data.extend(out)
        for k, v in cst.items():
            st[k] += v
        done += cst.get('games', 0)
        el = time.perf_counter() - t0
        eta = el / done * (games - done) if done else 0
        print(f"    ... {done}/{games} games | {len(data)} decisions | {el:.0f}s | ETA {eta:.0f}s", flush=True)

    if workers <= 1:
        for c in chunks:
            absorb(_gen_worker(c))
    else:
        with mp.get_context('spawn').Pool(workers) as pool:
            for res in pool.imap_unordered(_gen_worker, chunks):
                absorb(res)
    return data, dict(st)


# --- net: object + card embeddings, shared pointer scorer over usable objects ---
def make_net():
    import torch
    import torch.nn as nn
    NCARD = len(CARD_TITLES)
    NOBJ = len(CATALOG)
    # encode layout: own3 opp2 status2 power1 ctitre(NCARD) deck(NCARD) phase(5) owninv(NOBJ) oppinv(NOBJ)
    o0 = 3 + 2 + 2 + 1 + NCARD                            # start of deck block
    p0 = o0 + NCARD                                       # start of phase
    i0 = p0 + 5                                           # start of own inv
    j0 = i0 + NOBJ                                        # start of opp inv

    class Net(nn.Module):
        def __init__(s):
            super().__init__()
            s.obj_emb = nn.Embedding(NOBJ, EMB)
            s.card_emb = nn.Embedding(NCARD, EMB)
            scal = 7 + 1 + 5                              # own/opp scalars + power + phase
            s.trunk = nn.Sequential(nn.Linear(scal + 4 * EMB, 128), nn.ReLU(),
                                    nn.Linear(128, 128), nn.ReLU())
            s.struct = nn.Linear(128, 6)                 # flee_no/yes, replay_no/yes, resolve, none
            s.scorer = nn.Sequential(nn.Linear(128 + EMB + EMB + 1, 64), nn.ReLU(), nn.Linear(64, 1))
            s.val = nn.Linear(128, 1)
            s.register_buffer('oids', torch.arange(NOBJ))

        def forward(s, x):
            own = x[:, 0:7]
            power = x[:, 7:8]
            ctitre = x[:, 8:8 + NCARD]
            deck = x[:, o0:o0 + NCARD]
            phase = x[:, p0:p0 + 5]
            owninv = x[:, i0:i0 + NOBJ]
            oppinv = x[:, j0:j0 + NOBJ]
            faced = ctitre @ s.card_emb.weight
            decke = deck @ s.card_emb.weight
            oe = owninv @ s.obj_emb.weight
            pe = oppinv @ s.obj_emb.weight
            h = s.trunk(torch.cat([own, power, phase, faced, decke, oe, pe], 1))
            struct = s.struct(h)
            B = h.shape[0]
            allobj = s.obj_emb(s.oids)
            obj_in = torch.cat([h.unsqueeze(1).expand(B, NOBJ, 128),
                                allobj.unsqueeze(0).expand(B, NOBJ, EMB),
                                faced.unsqueeze(1).expand(B, NOBJ, EMB),
                                power.unsqueeze(1).expand(B, NOBJ, 1)], 2)
            obj = s.scorer(obj_in).squeeze(-1)
            return torch.cat([struct, obj], 1), s.val(h).squeeze(-1)
    return Net()


def train(net, data, epochs, val_frac=0.1):
    """CE-to-visits + MSE-to-outcome; hold out a decision split and keep the best-val
    checkpoint (the student overfits past a few dozen epochs on this little data)."""
    import copy

    import torch
    import torch.nn.functional as F
    X = torch.from_numpy(np.stack([d[0] for d in data]))
    P = torch.from_numpy(np.stack([d[1] for d in data]))
    M = torch.from_numpy(np.stack([d[2] for d in data]))
    Z = torch.from_numpy(np.asarray([d[3] for d in data], dtype=np.float32))
    n = len(data)
    g = torch.Generator().manual_seed(0)
    perm0 = torch.randperm(n, generator=g)
    nval = max(1, int(n * val_frac))
    vi, ti = perm0[:nval], perm0[nval:]
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)

    def losses(idx):
        logits, val = net(X[idx])
        logits = logits.masked_fill(~M[idx], -1e9)
        lp = -(P[idx] * F.log_softmax(logits, 1)).sum(1).mean()
        lv = F.mse_loss(val, Z[idx])
        return lp, lv

    best_val, best_state, best_ep = float('inf'), None, -1
    for ep in range(epochs):
        net.train()
        perm = ti[torch.randperm(len(ti))]
        for i in range(0, len(ti), 512):
            idx = perm[i:i + 512]
            lp, lv = losses(idx)
            opt.zero_grad()
            (lp + lv).backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            vlp, vlv = losses(vi)
            v = (vlp + vlv).item()
        if v < best_val:
            best_val, best_state, best_ep = v, copy.deepcopy(net.state_dict()), ep
    if best_state is not None:
        net.load_state_dict(best_state)
    net.eval()
    print(f"    best val loss {best_val:.3f} @ epoch {best_ep} (of {epochs})", flush=True)


def net_action(net, ctx, heur):
    import torch
    pairs = legal_pairs(ctx)
    if not pairs:
        return heur.decide(ctx)
    with torch.no_grad():
        logits, _ = net(torch.from_numpy(encode_ctx(ctx)).unsqueeze(0))
    logits = logits[0].numpy()
    best_k, _ = max(pairs, key=lambda kv: logits[VIDX[kv[1]]])
    return rs.action_from_key(ctx, best_k, heur, lambda: heur.decide(ctx))


def eval_net(net, n, seed0=500_000):
    import random
    from ai_policy import DefaultDungeonPolicy
    from real_driver import RealGameDriver
    heur = DefaultDungeonPolicy()
    w = l = d = 0
    for g in range(n):
        seat = g % 2
        random.seed(seed0 + g)
        np.random.seed((seed0 + g) & 0x7FFFFFFF)
        joueurs, reserve = build_toy_match(seed0 + g, deck='toy')
        donjon = make_dungeon('toy')
        drv = RealGameDriver(joueurs, donjon, reserve)
        s = joueurs[seat]
        while not drv.terminal:
            ctx = drv.context
            use_net = ctx.actor is s and ctx.kind.name in rs.TREE_KINDS
            drv.step(net_action(net, ctx, heur) if use_net else heur.decide(ctx))
        winner = drv.result[0] if drv.result else None
        w += winner is s
        d += winner is None
        l += winner not in (s, None)
    return w / n, l / n, d / n


if __name__ == '__main__':
    import torch
    torch.set_num_threads(1)
    ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    GAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    WORKERS = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    EPOCHS = int(sys.argv[4]) if len(sys.argv) > 4 else 200
    P_HEUR = float(sys.argv[5]) if len(sys.argv) > 5 else 0.75

    print(f"[1] gen data: {GAMES} teacher games @ {ITERS} iters, p_heur={P_HEUR}, {WORKERS} workers...", flush=True)
    data, st = gen_data(GAMES, ITERS, WORKERS, P_HEUR)
    n = st.get('games', 1)
    print(f"    {len(data)} decisions; TEACHER@{ITERS} vs ai_policy: "
          f"win {st['w']/n*100:.0f}% / lose {st['l']/n*100:.0f}% / draw {st['d']/n*100:.0f}%  (N={n})", flush=True)

    print("[2] training the policy+value net...", flush=True)
    net = make_net()
    train(net, data, EPOCHS)
    torch.save(net.state_dict(), 'artifacts/real_distill.pt')

    print("[3] STUDENT (fast net) vs ai_policy, seat-rotated...", flush=True)
    w, l, dr = eval_net(net, 400)
    print(f"  STUDENT vs ai_policy: win {w:.1%} / lose {l:.1%} / draw {dr:.1%}  (N=400)")
    print(f"  TEACHER@{ITERS} vs ai_policy: ~{st['w']/n*100:.0f}% (from {n} gen games)")
