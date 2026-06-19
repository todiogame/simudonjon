"""Distill the slow ISMCTS teacher into a FAST policy+value net (AlphaZero-style) on
the faithful toy engine.

Design choices (after review):
  - NO per-object hardcoding. The card is given RAW (power + monster-type one-hot); the
    network must LEARN which objects handle what, from the inventory + outcomes.
  - Policy head (B): each object is a LEARNED EMBEDDING; a SHARED scorer ranks every
    usable held object from [state, object-embedding, monster]. This generalises to any
    item set (grow the embedding table) -- no fixed per-object weights.
  - 100% legal info: both players' inventories (objects are face-up), PV uncapped, the
    remaining-deck composition, etc.
  - Object use is ONE looping decision (use an object / resolve): heal/save/execute are
    all "use an object", and several may be used in a row.

Usage: python distill_toy.py [iters] [games] [workers] [epochs]
"""
import multiprocessing as mp
import sys
import time

import numpy as np

import ismcts
import toy_engine as te

HAND_SIZE = 5
OBJ = list(te.POOL)                         # 14-object catalogue (each gets an embedding)
OBJ_IDX = {n: i for i, n in enumerate(OBJ)}
# every object is a poolable action: used in the object loop, or a break/repair TARGET
ACTION_OBJS = tuple(OBJ)
ACTIONS = ['flee_no', 'flee_yes', 'replay_no', 'replay_yes', 'resolve'] \
    + ['use_' + o for o in ACTION_OBJS]
AIDX = {a: i for i, a in enumerate(ACTIONS)}
NACT = len(ACTIONS)                         # 5 + 14 = 19
EMB_DIM = 16
NTYPES = len(te.TYPES)                       # 9 card types (incl. Limon)


def _action_index(kind, action):
    if kind == 'flee':
        return AIDX['flee_yes'] if action else AIDX['flee_no']
    if kind == 'replay':
        return AIDX['replay_yes'] if action else AIDX['replay_no']
    return AIDX['resolve'] if action == 'resolve' else AIDX['use_' + action]


def encode(s):
    """Observation = LEGAL info only; NO per-object/per-card rule features. Cards and
    objects are categorical ids (the net embeds them). Layout:
      own(4) opp(4) phase(5) power(1) facedtype(9) deck(9) known(3) owninv(14) oppinv(14) = 63
    """
    p = s.players[s.to_move]
    o = s.players[1 - s.to_move]
    deck = [0.0] * NTYPES
    for i in s.order[s.idx:]:
        deck[te.TYPES.index(te.DECK[i][1])] += 1.0
    cur = s.current
    cq = cur[0] if cur else 0
    ftype = [1. if cur is not None and cur[1] == ty else 0. for ty in te.TYPES]
    ku = s.known_until[s.to_move]                                  # cards a pomme revealed to us
    known = [(te.DECK[s.order[s.idx + k]][0] / 10. if s.idx + k < min(ku, len(s.order)) else 0.0)
             for k in range(te.POMME_LOOKAHEAD)]
    own_inv = [1. if p.objs.get(n) else 0. for n in OBJ]
    opp_inv = [1. if o.objs.get(n) else 0. for n in OBJ]
    feats = [p.pv / 30., p.score / 30., min(p.turn, 9) / 9., min(p.kills_turn, 5) / 5.,
             o.pv / 30., o.score / 30., float(o.status == 'dead'), float(o.status == 'fled'),
             float(s.phase == 'flee'), float(s.phase == 'object'), float(s.phase == 'break'),
             float(s.phase == 'repair'), float(s.phase == 'replay'),
             cq / 10., *ftype, *[c / 4. for c in deck], *known, *own_inv, *opp_inv]
    return np.asarray(feats, dtype=np.float32)


def _targets(kind, opts, visits):
    tgt = np.zeros(NACT, dtype=np.float32)
    mask = np.zeros(NACT, dtype=bool)
    tot = sum(visits.values()) or 1
    for a in opts:
        i = _action_index(kind, a)
        mask[i] = True
        tgt[i] = visits.get(a, 0) / tot
    return tgt, mask


# --- parallel ISMCTS data generation (no torch in the workers) ---------------
def _gen_worker(arg):
    """Teacher (ISMCTS) vs heuristic games -> training records + free teacher stats."""
    from collections import defaultdict
    lo, hi, iters = arg
    out, st = [], defaultdict(int)
    for seed in range(lo, hi):
        seat = seed % 2
        s = te.new_game(seed, te.sample_hand(seed, HAND_SIZE))
        recs = []
        while not s.terminal:
            if s.to_move == seat:
                kind, opts = te.legal(s)
                best, visits = ismcts.ismcts_decide(s, seat, iters, return_visits=True)
                tgt, mask = _targets(kind, opts, visits)
                recs.append((encode(s), tgt, mask))
                ag = s.players[seat]
                bpv, bobj, bcur = ag.pv, dict(ag.objs), s.current
                s = te.step(s, best)
                ag = s.players[seat]
                if kind == 'object':
                    if best in ('osselets', 'coquille'):
                        st['save_' + best] += 1
                    elif best in OBJ:
                        st['use_' + best] += 1
                elif kind in ('break', 'repair'):
                    st[kind] += 1
            else:
                s = te.step(s, te.heuristic_action(s))
        ag, op = s.players[seat], s.players[1 - seat]
        st['games'] += 1
        st['w'] += s.winner == seat
        st['d'] += s.winner is None
        st['l'] += s.winner not in (seat, None)
        st['ag_score'] += ag.score
        st['op_score'] += op.score
        for who, pl in (('ag', ag), ('op', op)):
            st[who + '_fled'] += pl.status == 'fled'
            st[who + '_dead'] += pl.status == 'dead'
            st[who + '_ponce'] += pl.status == 'in'
        z = 1. if s.winner == seat else (0. if s.winner is None else -1.)
        out += [(f, t, m, z) for f, t, m in recs]
    st['_lo'], st['_hi'] = lo, hi                # seed range covered (for resume bookkeeping)
    return out, dict(st)


def gen_data(games, iters, workers, cache=None):
    """Generate the ISMCTS training set, RESUMABLE: state is checkpointed to `cache`
    after every chunk, so the run can be interrupted (Ctrl-C / shutdown) and relaunched
    -- it picks up where it left off. Safe to interrupt anytime."""
    import os
    import pickle
    from collections import defaultdict
    data, st, done = [], defaultdict(int), set()
    if cache and os.path.exists(cache):
        try:
            with open(cache, 'rb') as f:
                c = pickle.load(f)
            if c.get('iters') == iters and c.get('games') == games:
                data, st, done = c['data'], defaultdict(int, c['st']), set(c['done'])
                print(f"    resumed from cache: {len(done)}/{games} games already done", flush=True)
            else:
                print("    (cache is for a different config -> starting fresh)", flush=True)
        except Exception as e:
            print(f"    (cache unreadable, starting fresh: {e})", flush=True)

    chunk = max(1, min(15, games // (workers * 4) or 1))   # many small chunks -> live progress + frequent saves
    chunks, lo = [], 0
    while lo < games:
        hi = min(lo + chunk, games)
        if not all(seed in done for seed in range(lo, hi)):
            chunks.append((lo, hi, iters))
        lo = hi
    if not chunks:
        print("    nothing to do (fully cached)", flush=True)
        return data, dict(st)

    def save():
        if not cache:
            return
        tmp = cache + '.tmp'
        with open(tmp, 'wb') as f:
            pickle.dump({'iters': iters, 'games': games, 'data': data, 'st': dict(st), 'done': list(done)}, f)
        os.replace(tmp, cache)                     # atomic -> a crash mid-write can't corrupt the cache

    t0 = time.perf_counter()
    session = 0

    def absorb(res):
        nonlocal session
        out, cst = res
        clo, chi = cst.pop('_lo'), cst.pop('_hi')
        data.extend(out)
        for k, v in cst.items():
            st[k] += v
        done.update(range(clo, chi))
        session += chi - clo
        save()
        el = time.perf_counter() - t0
        eta = el / session * (games - len(done)) if session else 0
        print(f"    ... {len(done)}/{games} games | {len(data)} decisions | {el:.0f}s elapsed | ETA {eta:.0f}s",
              flush=True)

    if workers <= 1:
        for c in chunks:
            absorb(_gen_worker(c))
    else:
        with mp.get_context('spawn').Pool(workers) as pool:
            for res in pool.imap_unordered(_gen_worker, chunks):
                absorb(res)
    return data, dict(st)


def stats_from_gen(st):
    r = {k: st.get(k, 0) for k in ('w', 'l', 'd', 'ag_score', 'op_score',
                                   'ag_fled', 'ag_dead', 'ag_ponce', 'op_fled', 'op_dead', 'op_ponce')}
    r['ev'] = {k: v for k, v in st.items() if k.startswith('use_') or k.startswith('save_')}
    r['n'] = st.get('games', 1)
    return r


# --- net (design B): EVERYTHING is an entity with a learned embedding -----------
# Objects AND dungeon cards each get an embedding; a SHARED scorer ranks each usable
# held object from [state, object-embedding, FACED-CARD-embedding]. The card is an
# entity too (not raw power+type features) -> ready for cards with powers/effects.
# encode() is unchanged; we just read its slices and route the categorical ones
# (faced-card type, remaining-deck composition, both inventories) through embeddings.
# encode() slices: own4 | opp4 | phase5 | power1 | facedtype9 | deck9 | known3 | owninv14 | oppinv14
_PH0, _POW, _FT0, _DK0, _KN0, _OI0, _PI0 = 8, 13, 14, 14 + NTYPES, 14 + 2 * NTYPES, \
    14 + 2 * NTYPES + te.POMME_LOOKAHEAD, 14 + 2 * NTYPES + te.POMME_LOOKAHEAD + len(OBJ)
NOBJ = len(OBJ)


def make_net():
    import torch
    import torch.nn as nn

    class Net(nn.Module):
        def __init__(s):
            super().__init__()
            s.obj_emb = nn.Embedding(NOBJ, EMB_DIM)            # one embedding per object
            s.card_emb = nn.Embedding(NTYPES, EMB_DIM)         # one embedding per card (entity)
            scal = 4 + 4 + 5 + 1 + te.POMME_LOOKAHEAD          # own, opp, phase, power, known-cards
            s.trunk = nn.Sequential(nn.Linear(scal + 4 * EMB_DIM, 128), nn.ReLU(),
                                    nn.Linear(128, 128), nn.ReLU())
            s.struct = nn.Linear(128, 5)                       # flee_no/yes, replay_no/yes, resolve
            s.scorer = nn.Sequential(nn.Linear(128 + EMB_DIM + EMB_DIM + 1, 64), nn.ReLU(),
                                     nn.Linear(64, 1))         # [h, object-emb, faced-card-emb, power]
            s.val = nn.Linear(128, 1)
            s.register_buffer('act_ids', torch.tensor([OBJ_IDX[o] for o in ACTION_OBJS]))

        def forward(s, x):
            own, opp = x[:, 0:4], x[:, 4:8]
            phase = x[:, _PH0:_POW]
            power = x[:, _POW:_FT0]                             # faced card's current power (visible)
            ftype = x[:, _FT0:_DK0]                             # faced card one-hot (entity id)
            deck = x[:, _DK0:_KN0]                              # remaining-deck composition (per card)
            known = x[:, _KN0:_OI0]                             # powers of the pomme-revealed next cards
            owninv, oppinv = x[:, _OI0:_PI0], x[:, _PI0:]
            own_oe = owninv @ s.obj_emb.weight                 # pooled held-object embeddings
            opp_oe = oppinv @ s.obj_emb.weight
            faced_ce = ftype @ s.card_emb.weight               # the faced card's embedding
            deck_ce = deck @ s.card_emb.weight                 # pooled remaining-deck embedding
            h = s.trunk(torch.cat([own, opp, phase, power, known, own_oe, opp_oe, faced_ce, deck_ce], 1))
            struct = s.struct(h)
            B = h.shape[0]
            oe = s.obj_emb(s.act_ids)                          # (14,EMB) all object embeddings
            obj_in = torch.cat([h.unsqueeze(1).expand(B, NOBJ, 128),
                                oe.unsqueeze(0).expand(B, NOBJ, EMB_DIM),
                                faced_ce.unsqueeze(1).expand(B, NOBJ, EMB_DIM),
                                power.unsqueeze(1).expand(B, NOBJ, 1)], 2)
            obj = s.scorer(obj_in).squeeze(-1)                 # (B,14) pointer scores over every object
            return torch.cat([struct, obj], 1), s.val(h).squeeze(-1)
    return Net()


def train(net, data, epochs, log_every=0, val_seeds=None):
    import torch
    import torch.nn.functional as F
    X = torch.from_numpy(np.stack([d[0] for d in data]))
    P = torch.from_numpy(np.stack([d[1] for d in data]))
    M = torch.from_numpy(np.stack([d[2] for d in data]))
    Z = torch.from_numpy(np.asarray([d[3] for d in data], dtype=np.float32))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    n = len(data)
    best = (-1.0, None)
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(n)
        for i in range(0, n, 512):
            idx = perm[i:i + 512]
            logits, value = net(X[idx])
            logits = logits.masked_fill(~M[idx], -1e9)
            logp = F.log_softmax(logits, dim=1)
            loss_p = -(P[idx] * logp).sum(1).mean()
            loss_v = F.mse_loss(value, Z[idx])
            opt.zero_grad()
            (loss_p + loss_v).backward()
            opt.step()
        if log_every and (ep + 1) % log_every == 0:
            net.eval()
            wr = _quick_winrate(net, val_seeds) if val_seeds else 0.0
            print(f"      epoch {ep+1}/{epochs}  held-out win {wr:.1%}", flush=True)
            if wr >= best[0]:                                  # keep the best checkpoint
                best = (wr, {k: v.clone() for k, v in net.state_dict().items()})
    if best[1] is not None:
        net.load_state_dict(best[1])
        print(f"      -> kept best checkpoint ({best[0]:.1%})", flush=True)
    net.eval()


def net_action(net, s):
    import torch
    kind, opts = te.legal(s)
    if not opts:
        return None
    idxs = [_action_index(kind, a) for a in opts]
    with torch.no_grad():
        logits, _ = net(torch.from_numpy(encode(s)).unsqueeze(0))
    logits = logits[0].numpy()
    return opts[max(range(len(opts)), key=lambda i: logits[idxs[i]])]


def _quick_winrate(net, seeds):
    w = 0
    for g in seeds:
        seat = g % 2
        s = te.new_game(g, te.sample_hand(g, HAND_SIZE))
        while not s.terminal:
            a = net_action(net, s) if s.to_move == seat else te.heuristic_action(s)
            s = te.step(s, a)
        w += s.winner == seat
    return w / len(seeds)


# --- stats (agent vs heuristic, seat-rotated) --------------------------------
def _run_collect(agent_fn, seed, seat, ev):
    s = te.new_game(seed, te.sample_hand(seed, HAND_SIZE))
    while not s.terminal:
        if s.to_move != seat:
            s = te.step(s, te.heuristic_action(s))
            continue
        kind, _ = te.legal(s)
        a = agent_fn(s)
        s = te.step(s, a)
        if kind == 'object':
            if a in ('osselets', 'coquille'):
                ev['save_' + a] += 1
            elif a in OBJ:
                ev['use_' + a] += 1
        elif kind in ('break', 'repair'):
            ev[kind] += 1
    return s


def collect_stats(agent_fn, n, seed0):
    from collections import defaultdict
    ev = defaultdict(int)
    r = {k: 0 for k in ('w', 'l', 'd', 'ag_score', 'op_score',
                        'ag_fled', 'ag_dead', 'ag_ponce', 'op_fled', 'op_dead', 'op_ponce')}
    for g in range(n):
        seat = g % 2
        s = _run_collect(agent_fn, seed0 + g, seat, ev)
        ag, op = s.players[seat], s.players[1 - seat]
        r['w'] += s.winner == seat
        r['d'] += s.winner is None
        r['l'] += s.winner not in (seat, None)
        r['ag_score'] += ag.score
        r['op_score'] += op.score
        for who, pl in (('ag', ag), ('op', op)):
            r[who + '_fled'] += pl.status == 'fled'
            r[who + '_dead'] += pl.status == 'dead'
            r[who + '_ponce'] += pl.status == 'in'
    r['ev'] = dict(ev)
    r['n'] = n
    return r


def print_stats(label, r):
    n = r['n']
    pc = lambda k: f"{r[k] / n * 100:.1f}%"
    print(f"\n  === {label} vs heuristic  (N={n}, seat-rotated) ===")
    print(f"    win / lose / draw    : {pc('w')} / {pc('l')} / {pc('d')}")
    print(f"    avg score            : {label} {r['ag_score']/n:.2f}  |  heuristic {r['op_score']/n:.2f}")
    print(f"    {label:<10} fled/dead/ponce : {r['ag_fled']/n*100:.0f}% / {r['ag_dead']/n*100:.0f}% / {r['ag_ponce']/n*100:.0f}%")
    print(f"    heuristic  fled/dead/ponce : {r['op_fled']/n*100:.0f}% / {r['op_dead']/n*100:.0f}% / {r['op_ponce']/n*100:.0f}%")
    ev = r['ev']
    per = lambda k: ev.get(k, 0) / n
    print(f"    saves/game  : osselets {per('save_osselets'):.2f}, coquille {per('save_coquille'):.2f}"
          f"   |  break {per('break'):.2f}, repair {per('repair'):.2f}")
    print(f"    uses/game   : " + ", ".join(
        f"{o}={per('use_' + o):.2f}" for o in
        ('marteau', 'torche', 'hache', 'midas', 'barde', 'calumet', 'bombe', 'kebab', 'pomme', 'couteau')))


def _peek_roll(s):
    import copy
    return copy.deepcopy(s.rng).randint(1, 6)


def verbose_game(agent_fn, seed, tag0='NET '):
    name = [tag0, 'HEUR']
    hand = te.sample_hand(seed, HAND_SIZE)
    s = te.new_game(seed, hand)
    print(f"\n===== seed {seed} | {tag0.strip()}=seat0 vs HEURISTIC=seat1 | hand={hand} =====")
    last = None
    while not s.terminal:
        mv = s.to_move
        if mv != last:
            print(f"  -- turn {s.players[mv].turn}: {name[mv]} (pv{s.players[mv].pv} sc{s.players[mv].score}) "
                  f"faces {s.current[1]}({s.current[0]}) --")
            last = mv
        kind, _ = te.legal(s)
        cur = s.current
        a = agent_fn(s) if mv == 0 else te.heuristic_action(s)
        bpv, bsc = s.players[mv].pv, s.players[mv].score
        line = None
        if kind == 'flee' and a:
            roll = _peek_roll(s)
            line = f"{name[mv]} flees {cur[1]}({cur[0]}): roll {roll} -> {'ESCAPE (passes it on)' if roll >= cur[0] else 'FAIL'}"
        elif kind == 'object':
            line = f"{name[mv]} vs {cur[1]}({cur[0]}): {a}"
        elif kind == 'break':
            line = f"{name[mv]} breaks {a}"
        elif kind == 'repair':
            line = f"{name[mv]} repairs {a}"
        elif kind == 'replay':
            line = f"{name[mv]} {'REPLAY' if a else 'pass turn'}"
        s = te.step(s, a)
        if kind == 'object':
            ag = s.players[mv]
            if a == 'kebab':
                line += f"  -> heal (pv {bpv}->{ag.pv})"
            elif a == 'pomme':
                line += f"  -> +{ag.pv - bpv}pv, peeks next 3"
            elif a == 'bombe':
                line += "  -> (must break an object...)"
            elif a == 'couteau':
                line += "  -> (repair...)"
            elif a == 'osselets':
                line += "  -> survive @1 (+1)"
            elif a == 'coquille':
                line += "  -> survive @3 (+1)"
            elif a == 'resolve' and ag.status == 'dead':
                line += "  -> DIED (passes it on)"
            elif ag.score > bsc:
                d = ag.pv - bpv
                tail = " [ends turn]" if a == 'calumet' else ""
                dd = f", {'+' if d >= 0 else ''}{d}pv" if d else ""
                line += f"  -> defeat{dd} (sc {ag.score}){tail}"
        if line:
            print("  " + line)
        if s.players[mv].status != 'in' and not s.terminal:
            print(f"     [{name[mv]} leaves ({s.players[mv].status})]")
            last = None
    out = lambda i: f"{name[i]} {s.players[i].score} ({s.players[i].status})"
    win = name[s.winner].strip() if s.winner is not None else 'DRAW'
    print(f"  RESULT: {out(0)} vs {out(1)} -> {win}")


if __name__ == '__main__':
    import os
    import torch
    os.makedirs('artifacts', exist_ok=True)         # so cache/checkpoint saving works on a fresh clone
    torch.set_num_threads(1)
    ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    GAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 900
    WORKERS = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    EPOCHS = int(sys.argv[4]) if len(sys.argv) > 4 else 200

    cache = f'artifacts/gen_{ITERS}_{GAMES}.pkl'
    print(f"[1] generating data: {GAMES} ISMCTS games @ {ITERS} iters, {WORKERS} workers "
          f"(resumable; cache={cache})...", flush=True)
    data, teacher_st = gen_data(GAMES, ITERS, WORKERS, cache=cache)
    print(f"    done: {len(data)} decisions", flush=True)

    print("[2] training the policy+value net (best-checkpoint by held-out WR)...", flush=True)
    net = make_net()
    train(net, data, EPOCHS, log_every=max(1, EPOCHS // 15), val_seeds=range(400_000, 401_000))
    torch.save(net.state_dict(), 'artifacts/toy_distill.pt')
    student = lambda s: net_action(net, s)

    print(f"\n[3] TEACHER ISMCTS@{ITERS} stats (free, from the {GAMES} data-gen games):", flush=True)
    print_stats(f'teacher@{ITERS}', stats_from_gen(teacher_st))
    print("\n[4] STUDENT (fast net) on HELD-OUT seeds:", flush=True)
    print_stats('student', collect_stats(student, 2000, 300_000))
    print("\n[5] one example game (student vs heuristic):", flush=True)
    verbose_game(student, 900_001)
