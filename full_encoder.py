"""Encoder v2 -- expose the FULL visible state (perfect-information game).

Per player (self + up to 3 opponents): pv, score proxy (pile size + pile power), status
(in-dungeon / fled / dead), hero (one-hot) + ability-used, hand (present & intact vs broken,
both pooled via object embeddings), full pile (pooled via card embeddings). Plus the faced
card's CURRENT power/types/effet/identity, the remaining-deck composition, the DISCARD pile,
and the decision phase. (Medals skipped -- we simulate without them.)

encode_ctx returns a flat float32 vector of indicator/count blocks; the net pools the multi-hot
blocks through learned embeddings (obj_emb / card_emb) in forward(), so encode stays torch-free
(runs in data-gen workers). Action vocab (struct + use_<object>) is reused from full_distill.
"""
import numpy as np

from full_distill import (CARD_IDX, CARD_TITLES, CAT_IDX, CATALOG, EMB, NACT, NCARD,
                          NOBJ, VIDX, VOCAB, key_to_vocab, legal_pairs)  # noqa: F401 (re-exported)
from heros import persos_disponibles
from monstres import DonjonDeck

KINDS = ['SHOULD_FLEE', 'SHOULD_REPLAY', 'CHOOSE_COMBAT_OBJECT',
         'CHOOSE_OBJECT_TO_SACRIFICE', 'CHOOSE_OBJECT_TO_REPAIR']

_deck = DonjonDeck().cartes
TYPES = sorted({t for c in _deck for t in (getattr(c, 'types_initiaux', None) or getattr(c, 'types', []) or [])})
TYPE_IDX = {t: i for i, t in enumerate(TYPES)}
EFFETS = sorted({c.effet for c in _deck if getattr(c, 'effet', None)})
EFFET_IDX = {e: i for i, e in enumerate(EFFETS)}
HEROES = sorted({type(p).__name__ for p in persos_disponibles})
HERO_IDX = {h: i for i, h in enumerate(HEROES)}
NTYPE, NEFFET, NHERO = len(TYPES), len(EFFETS), len(HEROES)
NOPP = 3                                              # opponent slots (3-4 player games)

# --- per-player block layout (raw indicators; net embeds the multi-hots) ---
P_SCAL = 8                                            # pv, n_pile, pile_pow, in_dj, fled, dead, hero_used, (tour|present)
PB_HERO = P_SCAL
PB_HI = PB_HERO + NHERO                               # hand intact (NOBJ)
PB_HB = PB_HI + NOBJ                                  # hand broken (NOBJ)
PB_PILE = PB_HB + NOBJ                                # pile counts (NCARD)
PLAYER_W = PB_PILE + NCARD

SELF0 = 0
OPP0 = PLAYER_W                                       # 3 opponent blocks follow self
FACED0 = PLAYER_W * (1 + NOPP)
F_POW = FACED0
F_TYPES = F_POW + 1
F_EFFET = F_TYPES + NTYPE
F_TITLE = F_EFFET + NEFFET
GLOB0 = F_TITLE + NCARD
G_DECK = GLOB0
G_DISC = G_DECK + NCARD
G_PHASE = G_DISC + NCARD
NFEAT = G_PHASE + len(KINDS)


def _objvecs(objets):
    hi = np.zeros(NOBJ, dtype=np.float32)
    hb = np.zeros(NOBJ, dtype=np.float32)
    for o in objets:
        i = CAT_IDX.get(type(o).__name__)
        if i is None:
            continue
        (hi if o.intact else hb)[i] = 1.
    return hi, hb


def _pilevec(pile):
    v = np.zeros(NCARD, dtype=np.float32)
    pw = 0
    for m in pile:
        i = CARD_IDX.get(getattr(m, 'titre', None))
        if i is not None:
            v[i] += 1.
        pw += getattr(m, 'puissance', 0) or 0
    return v, pw


def _player_block(j, last_scalar):
    blk = np.zeros(PLAYER_W, dtype=np.float32)
    pilev, pw = _pilevec(j.pile_monstres_vaincus)
    hi, hb = _objvecs(j.objets)
    blk[0] = j.pv_total / 30.
    blk[1] = len(j.pile_monstres_vaincus) / 20.
    blk[2] = pw / 60.
    blk[3] = float(j.dans_le_dj)
    blk[4] = float(j.fuite_reussie)
    blk[5] = float(not j.vivant)
    blk[6] = float(getattr(j.perso_obj, 'capacite_utilisee', False))
    blk[7] = last_scalar
    hi_idx = HERO_IDX.get(type(j.perso_obj).__name__)
    if hi_idx is not None:
        blk[PB_HERO + hi_idx] = 1.
    blk[PB_HI:PB_HI + NOBJ] = hi
    blk[PB_HB:PB_HB + NOBJ] = hb
    blk[PB_PILE:PB_PILE + NCARD] = pilev
    return blk


def encode_ctx(ctx):
    p = ctx.actor
    g = ctx.game
    js = g.joueurs
    k = js.index(p)
    x = np.zeros(NFEAT, dtype=np.float32)

    x[SELF0:SELF0 + PLAYER_W] = _player_block(p, min(getattr(p, 'tour', 0), 9) / 9.)
    opps = [js[(k + 1 + d) % len(js)] for d in range(len(js) - 1)]
    for slot in range(NOPP):
        if slot < len(opps):
            blk = _player_block(opps[slot], 1.)           # last scalar = present flag
            x[OPP0 + slot * PLAYER_W:OPP0 + (slot + 1) * PLAYER_W] = blk

    card = ctx.subject
    if card is not None:
        x[F_POW] = (getattr(card, 'puissance', 0) or 0) / 10.
        for t in (getattr(card, 'types', []) or []):
            ti = TYPE_IDX.get(t)
            if ti is not None:
                x[F_TYPES + ti] = 1.
        ei = EFFET_IDX.get(getattr(card, 'effet', None))
        if ei is not None:
            x[F_EFFET + ei] = 1.
        ci = CARD_IDX.get(getattr(card, 'titre', None))
        if ci is not None:
            x[F_TITLE + ci] = 1.

    d = g.donjon
    for idx in d.ordre[d.index:]:
        ci = CARD_IDX.get(d.cartes[idx].titre)
        if ci is not None:
            x[G_DECK + ci] += 1. / 4.
    for c in getattr(g, 'defausse', []):
        ci = CARD_IDX.get(getattr(c, 'titre', None))
        if ci is not None:
            x[G_DISC + ci] += 1. / 4.
    for i, kd in enumerate(KINDS):
        if ctx.kind.name == kd:
            x[G_PHASE + i] = 1.
    return x


def make_net():
    import torch
    import torch.nn as nn

    def player_out_dim():
        return P_SCAL + NHERO + EMB + EMB + EMB     # scalars + hero + hand_intact + hand_broken + pile

    class Net(nn.Module):
        def __init__(s):
            super().__init__()
            s.obj_emb = nn.Embedding(NOBJ, EMB)
            s.card_emb = nn.Embedding(NCARD, EMB)
            trunk_in = player_out_dim() * (1 + NOPP) + (1 + NTYPE + NEFFET + EMB) + EMB + EMB + len(KINDS)
            s.trunk = nn.Sequential(nn.Linear(trunk_in, 256), nn.ReLU(), nn.Linear(256, 256), nn.ReLU())
            s.struct = nn.Linear(256, 6)
            s.scorer = nn.Sequential(nn.Linear(256 + EMB + EMB + 1, 64), nn.ReLU(), nn.Linear(64, 1))
            s.val = nn.Linear(256, 1)
            s.register_buffer('oids', torch.arange(NOBJ))

        def _player(s, blk):
            scal = blk[:, 0:P_SCAL]
            hero = blk[:, PB_HERO:PB_HERO + NHERO]
            hi = blk[:, PB_HI:PB_HI + NOBJ] @ s.obj_emb.weight
            hb = blk[:, PB_HB:PB_HB + NOBJ] @ s.obj_emb.weight
            pile = blk[:, PB_PILE:PB_PILE + NCARD] @ s.card_emb.weight
            return torch.cat([scal, hero, hi, hb, pile], 1)

        def forward(s, x):
            parts = [s._player(x[:, SELF0:SELF0 + PLAYER_W])]
            for slot in range(NOPP):
                o = OPP0 + slot * PLAYER_W
                parts.append(s._player(x[:, o:o + PLAYER_W]))
            power = x[:, F_POW:F_POW + 1]
            types = x[:, F_TYPES:F_TYPES + NTYPE]
            effet = x[:, F_EFFET:F_EFFET + NEFFET]
            faced = x[:, F_TITLE:F_TITLE + NCARD] @ s.card_emb.weight
            deck = x[:, G_DECK:G_DECK + NCARD] @ s.card_emb.weight
            disc = x[:, G_DISC:G_DISC + NCARD] @ s.card_emb.weight
            phase = x[:, G_PHASE:G_PHASE + len(KINDS)]
            h = s.trunk(torch.cat(parts + [power, types, effet, faced, deck, disc, phase], 1))
            struct = s.struct(h)
            B = h.shape[0]
            allobj = s.obj_emb(s.oids)
            obj_in = torch.cat([h.unsqueeze(1).expand(B, NOBJ, 256),
                                allobj.unsqueeze(0).expand(B, NOBJ, EMB),
                                faced.unsqueeze(1).expand(B, NOBJ, EMB),
                                power.unsqueeze(1).expand(B, NOBJ, 1)], 2)
            obj = s.scorer(obj_in).squeeze(-1)
            return torch.cat([struct, obj], 1), s.val(h).squeeze(-1)
    return Net()


if __name__ == '__main__':
    print(f"v2 encoder: {NFEAT} features | {NOBJ} obj, {NCARD} cards, {NTYPE} types, "
          f"{NEFFET} effets, {NHERO} heroes, {NOPP} opp slots")
