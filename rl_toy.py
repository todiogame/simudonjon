"""Toy-mode RL harness: a minimal, fully-inspectable diagnostic for the PPO machinery.

Why this exists
---------------
Training on the full game failed without telling us *why*: 137 objects, a deep
dungeon, multiplayer, randomness and partially-scripted decisions all varied at
once. This module collapses the game to a tiny, hand-analysable duel so that if
learning fails here, the bug is in the RL machinery (``rl_train.py``) and nowhere
else.

It deliberately reuses *all* of ``rl_train``'s machinery unchanged -- the
``ObservationEncoder``, ``PolicyValueNet``, ``HybridNeuralPolicy`` and the PPO
update. The only things that change are the *match* (two players, four fixed
objects each, a fixed dungeon order, vanilla heroes, the network in control of
100% of the decisions with no heuristic fallback) and a game-aligned terminal
reward (your final score if you survive to be counted, a penalty otherwise; see
``collect_toy_rollouts`` for why the simpler duel rewards mislead here).

Toy specification
-----------------
* 2 players (duel), self-play.
* Fixed objects per player, identical every game:
    - ``Marteau de Guerre`` : type-tagged executor (Golem / Squelette), free, reusable
    - ``Torche Bleue``      : power-tagged executor (power <= 2), free, reusable
    - ``Hache de Glace`` x2 : two active ONE-SHOT executors of any monster (incl.
                              Dragon), each consumed on use -- two for the two
                              Dragons, so no game is unwinnable-by-structure and
                              good one-shot allocation can be *learned*, not hand-coded
    - ``Armure en cuir``    : pure passive +5 PV (start HP = 7 hero + 5 = 12)
* Fixed dungeon *composition* (the full standard monster set, Gobelin..Dragon --
  no rats, no special-rule / effect / X cards) but the order is **shuffled every
  game**, so the agent must learn a state-based policy (read the current card, HP
  and cards-left) rather than memorise a sequence. Only the encodable binary /
  1-of-N decision kinds are ever raised; randomness (shuffle + flee roll) is seeded.
* The planted skill: only the one-shot Hache de Glace can execute the big
  Hache-only monsters, and the Dragon (power 9) is the worst of them. The agent
  should *spend the Hache on a Dragon* (not waste it on a weakling it can kill
  for free), execute cheap monsters with Marteau / Torche, and flee before the
  cumulative damage of the late high-power monsters kills it. We know the
  intended line because we built it, so we can measure whether the agent finds it.

Decision control
----------------
Every gameplay decision the toy raises is handled by the network. Nothing is
routed to ``DefaultDungeonPolicy`` and no heuristic-derived feature
(``priorite``, ``worthit``, ...) is fed to the encoder -- the encoder purge in
``rl_train`` already guarantees the latter. The only non-network decision is the
structural ``ORDER_OBJECTS`` call the engine makes once per player at setup; the
ordering head is out of scope for v0, so it is resolved as identity (a fixed,
non-heuristic permutation), never via the heuristic policy. Every kind that
arises is logged and asserted to be in the allowed set.

Reward
------
Terminal: +1 for winning the game; a small flat negative (``DEATH_REWARD``) if you
die; otherwise a score credit (``SURVIVE_SCORE_COEF * score``, capped below a win)
for the monsters cleared. The shape was tuned against two failure modes:
  - A flat +1/0/-1 outcome reward leaves a flat valley -- while losing, every
    episode returns the same value, PPO sees no gradient, and it freezes at "flee
    immediately" (scaling the win reward does nothing: a win is ~never sampled).
  - So we credit *score* (drawing one more safe monster pays). But crediting score
    on death (e.g. /3) makes "die with a big pile" attractive -> draw-into-death.
A small *negative* death (forfeiting the score credit) is the balance: drawing is
worth it while safe, dying is mildly bad, so the optimal line is "draw while the
remaining deck is safe, stop before the risk" -- exactly what the deck-aware
observation lets the agent judge. The dungeon need not be clearable.

Diagnostic findings (what the toy taught us)
--------------------------------------------
1. The PPO machinery *learns* and is not the bottleneck. It reproduces the
   hand-derived optimal combat line on the controlled probe; the encoder /
   network / PPO update are sound. The hard part was the training regime.

2. The *reward shape* was the real lever, in three steps (see the Reward note):
   - Raw score -> the agent draws into death (a huge score upside against a tiny
     death penalty makes suicide EV-positive).
   - Flat +1 win / 0 lose / -1 die -> removes suicide but leaves a flat valley:
     while losing, every episode returns 0, so PPO sees no gradient and freezes
     at "flee immediately" (scaling the win reward does nothing -- a win is
     ~never sampled).
   - +1 / -1 / partial-credit-for-score-when-surviving -> a climb out of the
     valley, with death still strictly worst so no return to suicide.

3. With that reward, trained against the heuristic DefaultDungeonPolicy on the
   full (non-clearable) standard dungeon, the agent escapes "flee immediately"
   around iteration ~80 and converges to the intended line -- clear the cheap
   monsters, then flee before the deadly late ones -- beating BOTH baselines
   markedly: ~0.95 vs Random and ~0.95 vs the heuristic (death ~0.04). Pure
   self-play on this shared-queue duel does NOT get there (it over-fits to facing
   a clone); a fixed competent opponent (``--opponent default``) is what works.

(Iterated design -- objects, dungeon, skill metric and reward have all moved as
we probed difficulty. Re-run ``python rl_toy.py train --opponent default
--opponent-ratio 1.0 --entropy-coef 0.05 --iterations 220`` to reproduce.)

The point of the toy is exactly this: it isolated reward-design and
training-regime questions from the *machinery* (which provably learns), with
every decision inspectable.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from ai_decisions import CombatObjectChoice, DecisionContext, DecisionKind, require_permutation
from ai_policy import RandomPolicy, default_dungeon_policy
from monstres import CarteMonstre
from simu import ordonnanceur

from rl_toy_env import (  # torch-free toy environment
    TOY_ALLOWED_KINDS,
    TOY_MANAGED_KINDS,
    TOY_DECK_SIZE,
    TOY_PLAYER_NAMES,
    TOY_POWER_LEVELS,
    TOY_START_PV,
    TOY_STRUCTURAL_KINDS,
    ToyDonjon,
    ToyStructuralPolicy,
    build_toy_match,
    is_hache,
    is_hache_worthy,
    make_toy_hero,
    make_toy_objects,
    make_dungeon,
    routed_toy_policy,
)
from rl_train import (
    BINARY_KINDS,
    HybridNeuralPolicy,
    INITIAL_MANAGED_KINDS,
    MULTI_OBJECT_KINDS,
    OBJECT_TYPE_INDEX,
    ORDER_OBJECT_KINDS,
    ObservationEncoder,
    PolicyValueNet,
    PPOConfig,
    SINGLE_OBJECT_KINDS,
    _cpu_state_dict,
    _player_rank,
    _seed_bank,
    ppo_update,
)


NORMAL_MANAGED_KINDS = tuple(
    kind for kind in INITIAL_MANAGED_KINDS
    if kind is not DecisionKind.DRAFT_PICK
)

# Every decision kind that has a network head (one of the four shapes). On the
# full deck the agent MUST control all of them -- nothing may fall back to the
# heuristic -- so we manage this complete set and use a strict (non-heuristic)
# structural fallback that only ever resolves a forced permutation.
FULL_MANAGED_KINDS = tuple(dict.fromkeys(
    BINARY_KINDS + SINGLE_OBJECT_KINDS + MULTI_OBJECT_KINDS + ORDER_OBJECT_KINDS
))


def _context_with_choice_options(context):
    """Expose metadata-backed choices as regular options for pointer heads."""
    if context.options:
        return context
    if context.kind in (DecisionKind.CHOOSE_POWER, DecisionKind.CHOOSE_TYPE):
        choices = (
            context.meta('options')
            or context.meta('scores')
            or context.meta('counts')
            or {}
        )
        if isinstance(choices, dict):
            choices = tuple(choices.keys())
        else:
            choices = tuple(choices)
        if choices:
            return replace(context, options=choices)
    return context


# Terminal reward, tuned to make the EV-balanced line (the heuristic's) optimal:
#   win the game = +1
#   survive-lose = SURVIVE_SCORE_COEF * score (capped below a win) -- you keep a
#                  credit for the monsters you cleared, so drawing pays (this is
#                  what escapes the flat "flee immediately" valley)
#   die          = DEATH_REWARD (small flat negative) -- death FORFEITS the score
#                  credit and costs a little, so over-drawing is bad.
# The two earlier extremes both failed: death = -1 (flat) -> too scared to draw
# (flee immediately); death = +score/3 -> dying with a big pile is rewarded
# (draw into death). A small negative makes "draw while the remaining deck is
# safe, then stop before the risk" the best line -- exactly what the deck-aware
# observation lets the agent judge.
WIN_REWARD = 1.0
SURVIVE_SCORE_COEF = 0.05   # partial credit per monster scored while surviving
SURVIVE_REWARD_CAP = 0.5    # keep the score credit strictly below a win (+1)
DEATH_REWARD = -0.25        # small flat penalty for dying (forfeits the score credit)

# --- 'margin' (competitive) reward -------------------------------------------
# The 'shaped' reward above credits *absolute* survival, which we measured to
# reward fleeing more than winning (reward doubles while the win-rate stays
# flat). The 'margin' reward credits the *outcome of the score race*, and -- this
# is the key constraint -- a win is worth +1 NO MATTER THE LEAD. Winning by 1
# point is exactly as good as winning by 8, because the optimal line is to score
# one more than the opponent and then STOP (drawing further only risks death for
# no extra reward). So the reward must NOT keep rising with the margin:
#   win (you outscore the survivors / opponent died) -> +1, flat
#   no winner (both dead)                            -> 0, neither side won
#   you died and the opponent won                    -> MARGIN_LOSS (flat, bad:
#                                                       a big dead pile is not
#                                                       rewarded -> no draw-into-death)
#   you survived but were out-scored                 -> margin / MARGIN_NORM in
#                                                       (-1, 0): the ONLY graded
#                                                       region, a dense gradient to
#                                                       close the gap up to a win.
# Dense in the losing region (no flat "flee-immediately" valley) and un-gameable
# by fleeing (fleeing -> low own score -> deeper negative margin). It says *what*
# to optimise (just-beat the opponent), not *how* -- strategies must still emerge.
MARGIN_NORM = 8.0           # an 8-point deficit hits the -1 floor
MARGIN_LOSS = -1.0          # died while the opponent won (a clear loss)
MARGIN_DRAW = 0.0           # both dead / no winner: neither side won
# A same-score *survivor* tie: the engine breaks it by coinflip (simu.py), which
# injects uncontrollable noise into the reward (identical play -> +1 or 0 at
# random) and a back-door "a free tie is worth 0.5" incentive. We score it
# deterministically at its unbiased expected value instead -- half a win, still
# strictly below a clean win so the agent prefers to break the tie by scoring one
# more. (No coin -> no gradient noise.)
MARGIN_TIE = 0.5


# --- Guardrail policy --------------------------------------------------------

class ToyControlPolicy(HybridNeuralPolicy):
    """HybridNeuralPolicy specialised for the toy: records every decision kind,
    asserts it is in the allowed set, and tracks the key strategic skill --
    spending the one-shot Hache de Glace on a monster the free tools cannot kill
    rather than wasting it on a free kill."""

    def __init__(self, model, encoder, strict_allowed=True, **kwargs):
        kwargs.setdefault('managed_kinds', TOY_MANAGED_KINDS)
        kwargs.setdefault('fallback', ToyStructuralPolicy())
        super().__init__(model, encoder, **kwargs)
        self.strict_allowed = strict_allowed
        self._kinds_seen = Counter()
        self._skill = Counter()

    def decide(self, context):
        context = _context_with_choice_options(context)
        kind = context.kind
        self._kinds_seen[kind.name] += 1
        if self.strict_allowed and kind not in TOY_ALLOWED_KINDS:
            raise AssertionError(
                f"toy: unexpected decision kind {kind.name} (phase={context.phase!r}); "
                f"the fixed object/dungeon set must only raise {sorted(k.name for k in TOY_ALLOWED_KINDS)}"
            )

        decision = super().decide(context)

        # The scarce one-shot Hache de Glace: spending it on a monster the free
        # tools cannot execute is the skill; spending it on a free kill is a waste.
        if kind is DecisionKind.CHOOSE_COMBAT_OBJECT and is_hache(decision):
            self._skill['hache_uses'] += 1
            self._skill['hache_well_used' if is_hache_worthy(context.subject) else 'hache_wasted'] += 1
        return decision

    def clear_toy_stats(self):
        self._kinds_seen.clear()
        self._skill.clear()

    def export_kinds_seen(self):
        return dict(self._kinds_seen)

    def export_skill_stats(self):
        return dict(self._skill)


# --- Observation: deck awareness ---------------------------------------------

class ToyObservationEncoder(ObservationEncoder):
    """Extends the shared encoder so the network sees the *full* public state on
    BOTH the binary (flee/replay) and combat-object observations:
      - the exact remaining-deck composition (a count per monster power level),
        not a coarse summary -- this is what the heuristic computes its EV from,
        and it's public (composition only, never the upcoming order);
      - the opponent's state (score, HP, alive / fled / in-dungeon) and the score
        margin, so the agent knows whether it is ahead or behind;
      - the KNOWN next card, when the player legitimately knows it (a card put on
        top, or peeked via a divination object): a flag + its power + whether it is
        a Marteau-killable type. This is *legal* public knowledge (not the hidden
        deck order), so the agent can learn e.g. to replay when a free kill is on
        top. Zero/absent when the next card is unknown.
      - the FULL held inventory by object identity: two multi-hot counts over the
        object-type vocabulary (one for intact items the actor can still use, one
        for broken items). Without this the binary (flee/replay) observation only
        had aggregate object COUNTS + a few flags, so the network could not tell it
        holds e.g. a reusable Osselets vs a Kebab -- it now has its full hand at
        every decision (the player always knows their own objects).
    The shared rl_train encoder is untouched."""

    # deck histogram + [opp_score, opp_hp, opp_alive, opp_fled, opp_in_dj, margin]
    #               + [known_next, next_power, next_is_golem, next_is_squelette]
    # (the held-inventory multi-hot is sized from the vocab in __init__ and added on
    # top -- see self.extra_feature_size there.)
    base_extra_size = len(TOY_POWER_LEVELS) + 6 + 4

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Held inventory: intact multi-hot then broken multi-hot over the vocab.
        self.inv_base = self.base_extra_size
        self.inv_vocab = self.object_type_vocab_size
        self.extra_feature_size = self.base_extra_size + 2 * self.inv_vocab
        self.binary_size += self.extra_feature_size
        self.combat_global_size += self.extra_feature_size

    def _encode_binary(self, context):
        encoded = super()._encode_binary(context)
        encoded['obs'] = np.concatenate(
            [encoded['obs'], np.asarray(self._toy_extra_features(context), dtype=np.float32)]
        )
        return encoded

    def _encode_object_choice(self, context, mode=None):
        encoded = super()._encode_object_choice(context, mode=mode)
        encoded['global_obs'] = np.concatenate(
            [encoded['global_obs'], np.asarray(self._toy_extra_features(context), dtype=np.float32)]
        )
        return encoded

    def _toy_extra_features(self, context):
        """Exact remaining-deck histogram (per power level, normalised by deck
        size) + opponent state + score margin. Defensive: zeros for any piece
        whose info is missing (e.g. unit-test stubs)."""
        feats = [0.0] * self.extra_feature_size
        # Held inventory: two multi-hot counts (intact / broken) over the object
        # vocabulary. Depends only on the actor's own objects -- always known to
        # the player -- so it is filled even when game/board context is missing.
        actor = getattr(context, 'actor', None)
        if actor is not None:
            for objet in getattr(actor, 'objets', []) or []:
                slot = OBJECT_TYPE_INDEX.get(type(objet).__name__, 0)
                if getattr(objet, 'intact', True):
                    feats[self.inv_base + slot] += 1.0
                else:
                    feats[self.inv_base + self.inv_vocab + slot] += 1.0
        game = context.game
        if game is None:
            return feats
        donjon = getattr(game, 'donjon', None)
        cartes = getattr(donjon, 'cartes', None)
        ordre = getattr(donjon, 'ordre', None)
        if cartes and ordre is not None:
            index = getattr(donjon, 'index', 0)
            level_at = {p: i for i, p in enumerate(TOY_POWER_LEVELS)}
            for i in list(ordre)[index:]:
                p = getattr(cartes[i], 'puissance_initiale', getattr(cartes[i], 'puissance', None))
                if p in level_at:
                    feats[level_at[p]] += 1.0 / TOY_DECK_SIZE

        actor = context.actor
        opponents = [j for j in getattr(game, 'joueurs', []) if j is not actor]
        if opponents:
            opp = opponents[0]
            my_score = len(getattr(actor, 'pile_monstres_vaincus', []))
            opp_score = len(opp.pile_monstres_vaincus)
            base = len(TOY_POWER_LEVELS)
            feats[base + 0] = opp_score / 20.0
            feats[base + 1] = opp.pv_total / 20.0
            feats[base + 2] = float(opp.vivant)
            feats[base + 3] = float(opp.fuite_reussie)
            feats[base + 4] = float(opp.dans_le_dj)
            feats[base + 5] = (my_score - opp_score) / 10.0

        # Known next card (legal public knowledge only -- None if unknown).
        base2 = len(TOY_POWER_LEVELS) + 6
        known = None
        if hasattr(actor, 'connait_prochaine_carte'):
            try:
                known = actor.connait_prochaine_carte(game)
            except Exception:
                known = None
        if known is not None:
            types = getattr(known, 'types', ()) or ()
            power = getattr(known, 'puissance_initiale', getattr(known, 'puissance', 0)) or 0
            feats[base2 + 0] = 1.0
            feats[base2 + 1] = float(power) / 10.0
            feats[base2 + 2] = float('Golem' in types)
            feats[base2 + 3] = float('Squelette' in types)
        return feats


# --- Model / policy construction ---------------------------------------------

def build_toy_model(*, hidden_dim=128, device='cpu'):
    encoder = ToyObservationEncoder()
    model = PolicyValueNet(encoder, hidden_dim=hidden_dim).to(device)
    model.eval()
    return model, encoder


def _make_toy_policy(model, encoder, *, sample, record, device='cpu',
                     strict_allowed=True, fallback=None, managed_kinds=None):
    return ToyControlPolicy(
        model, encoder, sample=sample, record=record, device=device,
        managed_kinds=(managed_kinds or TOY_MANAGED_KINDS),
        strict_allowed=strict_allowed,
        fallback=(fallback or ToyStructuralPolicy()),
    )


def _toy_is_full_deck(deck):
    """Decks using the full simudonjon dungeon ('normal' = toy-pool hands, 'full' =
    hands from every game object). The network manages EVERY routable decision kind
    (FULL_MANAGED_KINDS), so no gameplay decision is ever made by the heuristic; the
    fallback is the strict structural guard (resolves only forced permutations and
    raises on anything else, which -- verified -- never happens)."""
    return deck in ('normal', 'full')


def _toy_agent_policy(model, encoder, *, sample, record, deck, device='cpu'):
    """Build the toy control policy with the right routing/fallback for ``deck``.

    NO decision falls back to the heuristic: on the full-dungeon decks the network
    owns all FULL_MANAGED_KINDS, and the fallback is the strict ToyStructuralPolicy
    (NOT the heuristic)."""
    full = _toy_is_full_deck(deck)
    return _make_toy_policy(
        model, encoder, sample=sample, record=record, device=device,
        strict_allowed=not full,
        managed_kinds=(FULL_MANAGED_KINDS if full else TOY_MANAGED_KINDS),
        fallback=None,  # -> ToyStructuralPolicy (strict guard, never the heuristic)
    )


def _soften_policy_heads(model, factor):
    """Scale the policy-head logits by ``factor`` (<1) to DE-PEAK the action
    distribution after behaviour cloning. The diagnosed failure: a 99%-accurate
    clone is so confident that the PPO entropy bonus barely moves it (entropy
    stuck ~0.09) -> no exploration -> it plateaus at the heuristic best-response.
    Shrinking only the policy-head logits raises the action entropy (so PPO can
    explore) while preserving (a) the per-state argmax action -- the greedy
    policy is unchanged -- and (b) the trunk features and warm value heads."""
    heads = ('binary_policy_head', 'combat_policy_head', 'combat_resolve_head',
             'multi_policy_head', 'order_policy_head')
    with torch.no_grad():
        for name in heads:
            head = getattr(model, name, None)
            if head is None:
                continue
            head.weight.mul_(factor)
            if head.bias is not None:
                head.bias.mul_(factor)


# --- Rollouts / evaluation (single process: deterministic and simple) --------

def _terminal_reward(joueur, winner, joueurs=None, mode='shaped'):
    """Game outcome from a player's view. Shared by RL rollouts and the value
    targets that warm the critic during cloning.

    mode='shaped' (default): +1 win / small negative if dead / else a score
        credit for the monsters cleared (see the Reward note). Credits absolute
        survival -- which we measured to over-reward fleeing.
    mode='margin': competitive outcome of the score race. A win is +1 FLAT (by 1
        point or by 8 -- same reward; overshooting only risks death). Same-score
        survivor tie = MARGIN_TIE (deterministic, no coinflip). Both-dead /
        excluded = 0. Died-and-lost = MARGIN_LOSS (flat, so a big dead pile is not
        rewarded). Survived-but-out-scored = (my_score - lead) / MARGIN_NORM in
        (-1, 0): the only graded region, a dense gradient to just close the gap.
        Needs ``joueurs`` to mirror the engine's finalist rule. (See the note.)
    """
    if mode == 'margin':
        # Mirror the engine's finalist rule (simu.py) so a tie is resolved by us,
        # deterministically, instead of by the engine's coinflip. Finalists are
        # the ponceurs if any, else all living players (successful fleers count).
        pool = joueurs if joueurs else [joueur]
        ponceurs = [j for j in pool if getattr(j, 'dans_le_dj', False)]
        finalists = ponceurs if ponceurs else [j for j in pool if j.vivant]
        if joueur not in finalists:
            # Excluded from the count: died, or fled while someone ponced.
            return MARGIN_DRAW if not finalists else MARGIN_LOSS
        top = max(float(j.score_final) for j in finalists)
        my_score = float(joueur.score_final)
        if my_score >= top:                   # at the top of the count
            tied = [j for j in finalists if float(j.score_final) == top]
            return MARGIN_TIE if len(tied) > 1 else WIN_REWARD  # +1 flat (any lead)
        # In the count but out-scored: dense gradient to close the gap to the lead.
        return min(0.0, max(MARGIN_LOSS, (my_score - top) / MARGIN_NORM))
    if joueur is winner:
        return WIN_REWARD
    if not joueur.vivant:
        return DEATH_REWARD
    return min(SURVIVE_REWARD_CAP, SURVIVE_SCORE_COEF * joueur.score_final)


def _opponent_policy(kind):
    """Fixed opponent for non-self-play episodes. The opponent may be the
    heuristic DefaultDungeonPolicy -- only the *agent* seat must avoid the
    heuristic (guardrail), the opponent is free to use it."""
    if kind == 'random':
        return RandomPolicy()
    if kind == 'default':
        return default_dungeon_policy()
    raise ValueError(f"Unknown toy opponent: {kind}")


# --- Parallel rollout / eval across CPU cores --------------------------------
# NN decisions are ~100x slower than the heuristic (batch-1 forward + Python
# encode), and the toy loops ran on a single core. Two cheap, safe wins:
#   1. ONE torch thread per process -- splitting a tiny batch-1 matmul across
#      cores is pure overhead (measured ~1.3x faster at 1 thread);
#   2. play many games at once, one chunk per core.
# We keep a PERSISTENT spawn pool because train_toy collects a fresh batch every
# iteration -- re-spawning torch workers each time would cost more than it saves.
# Each task carries the current weights (state_dict); workers rebuild the model
# and pin themselves to 1 thread. num_workers=1 keeps the original serial path
# untouched (so tests / library callers are unaffected).

_TOY_POOL = None
_TOY_POOL_SIZE = 0


def _close_toy_pool():
    global _TOY_POOL, _TOY_POOL_SIZE
    if _TOY_POOL is not None:
        _TOY_POOL.terminate()
        _TOY_POOL = None
        _TOY_POOL_SIZE = 0


def _get_toy_pool(num_workers):
    """Lazily create (and reuse across iterations) a spawn process pool."""
    global _TOY_POOL, _TOY_POOL_SIZE
    if _TOY_POOL is not None and _TOY_POOL_SIZE != num_workers:
        _close_toy_pool()
    if _TOY_POOL is None:
        import atexit
        import multiprocessing as mp
        _TOY_POOL = mp.get_context('spawn').Pool(processes=num_workers)
        _TOY_POOL_SIZE = num_workers
        atexit.register(_close_toy_pool)
    return _TOY_POOL


def _chunk_bounds(n, k):
    """Split range(n) into <=k balanced contiguous [lo, hi) chunks."""
    k = max(1, min(k, n))
    base, extra = divmod(n, k)
    bounds = []
    lo = 0
    for i in range(k):
        hi = lo + base + (1 if i < extra else 0)
        bounds.append((lo, hi))
        lo = hi
    return bounds


def _run_toy_rollout_chunk(policy, baseline, *, offsets, seed_start, opponent_period,
                           reward_mode, shuffle_objects, deck):
    """The per-episode rollout loop, over a set of GLOBAL episode offsets (so a
    chunk plays exactly the games it would have played serially)."""
    steps = []
    reward_sum = 0.0
    recorded_players = 0
    for offset in offsets:
        seed = seed_start + offset
        joueurs, objets = build_toy_match(seed, shuffle_objects=shuffle_objects, deck=deck)
        policy.clear_records()
        is_versus_opponent = opponent_period and (offset % opponent_period == 0)
        if is_versus_opponent:
            agent_seat = offset % len(joueurs)
            assignments = {i: (policy if i == agent_seat else baseline) for i in range(len(joueurs))}
            recorded = [joueurs[agent_seat]]
        else:
            assignments = {i: policy for i in range(len(joueurs))}
            recorded = list(joueurs)
        routed = routed_toy_policy(assignments, joueurs)
        winner, _ = ordonnanceur(joueurs, make_dungeon(deck), objets, False, policy=routed)
        for joueur in recorded:
            reward = _terminal_reward(joueur, winner, joueurs, mode=reward_mode)
            reward_sum += reward
            recorded_players += 1
            for step in policy.take_records(joueur):
                step['reward'] = reward
                steps.append(step)
    return steps, reward_sum, recorded_players


def _toy_rollout_worker(task):
    import torch as _torch
    _torch.set_num_threads(1)
    deck = task['deck']
    model, encoder = build_toy_model(hidden_dim=task['hidden_dim'])
    model.load_state_dict(task['state_dict'])
    model.eval()
    policy = _toy_agent_policy(model, encoder, sample=True, record=True, deck=deck)
    if task['opponent_state_dict'] is not None:
        opp_model, opp_encoder = build_toy_model(hidden_dim=task['hidden_dim'])
        opp_model.load_state_dict(task['opponent_state_dict'])
        opp_model.eval()
        baseline = _toy_agent_policy(opp_model, opp_encoder, sample=True, record=False, deck=deck)
    else:
        baseline = _opponent_policy(task['opponent'])
    steps, reward_sum, recorded = _run_toy_rollout_chunk(
        policy, baseline, offsets=range(task['offset_lo'], task['offset_hi']),
        seed_start=task['seed_start'], opponent_period=task['opponent_period'],
        reward_mode=task['reward_mode'], shuffle_objects=task['shuffle_objects'], deck=task['deck'])
    return {'steps': steps, 'reward_sum': reward_sum, 'recorded_players': recorded,
            'kinds_seen': policy.export_kinds_seen(), 'skill_stats': policy.export_skill_stats()}


def collect_toy_rollouts(model, encoder, *, episodes, seed_start,
                         opponent_ratio=0.0, opponent='random', device='cpu',
                         reward_mode='shaped', opponent_policy=None,
                         shuffle_objects=False, deck='toy', num_workers=1, hidden_dim=128):
    """Rollouts for one PPO batch.

    ``opponent_ratio`` is the fraction of episodes the agent plays against a
    fixed ``opponent`` ('random' or 'default'); the rest are self-play. On each
    such episode the agent occupies one rotated seat and only its steps are
    recorded. Pure self-play (ratio 0.0) over-fits to facing a clone on the
    shared dungeon queue; training against a fixed competent opponent (the
    heuristic 'default') mirrors what the real harness does.

    ``opponent_policy`` (if given) is used as the baseline instead of
    ``_opponent_policy(opponent)`` -- e.g. a frozen past-self snapshot for
    league-style self-play.

    ``num_workers`` > 1 fans the episodes out over a persistent spawn pool
    (contiguous offset chunks -> the same games as serial, just distributed).
    """
    opponent_period = max(1, round(1.0 / opponent_ratio)) if opponent_ratio > 0 else 0

    if num_workers and num_workers > 1 and episodes > 1:
        state_dict = _cpu_state_dict(model)
        opp_state = _cpu_state_dict(opponent_policy.model) if opponent_policy is not None else None
        tasks = [{
            'state_dict': state_dict, 'opponent_state_dict': opp_state,
            'hidden_dim': hidden_dim, 'opponent': opponent,
            'offset_lo': lo, 'offset_hi': hi, 'seed_start': seed_start,
            'opponent_period': opponent_period, 'reward_mode': reward_mode,
            'shuffle_objects': shuffle_objects, 'deck': deck,
        } for (lo, hi) in _chunk_bounds(episodes, num_workers)]
        results = _get_toy_pool(num_workers).map(_toy_rollout_worker, tasks)
        steps = []
        reward_sum = 0.0
        recorded_players = 0
        kinds = Counter()
        skill = Counter()
        for r in results:
            steps.extend(r['steps'])
            reward_sum += r['reward_sum']
            recorded_players += r['recorded_players']
            kinds.update(r['kinds_seen'])
            skill.update(r['skill_stats'])
        return {'steps': steps, 'episodes': episodes,
                'avg_reward_per_player': reward_sum / max(1, recorded_players),
                'kinds_seen': dict(kinds), 'skill_stats': dict(skill)}

    policy = _toy_agent_policy(model, encoder, sample=True, record=True, deck=deck, device=device)
    baseline = opponent_policy if opponent_policy is not None else _opponent_policy(opponent)
    steps, reward_sum, recorded_players = _run_toy_rollout_chunk(
        policy, baseline, offsets=range(episodes), seed_start=seed_start,
        opponent_period=opponent_period, reward_mode=reward_mode,
        shuffle_objects=shuffle_objects, deck=deck)
    return {
        'steps': steps,
        'episodes': episodes,
        'avg_reward_per_player': reward_sum / max(1, recorded_players),
        'kinds_seen': policy.export_kinds_seen(),
        'skill_stats': policy.export_skill_stats(),
    }


def _run_toy_eval_chunk(agent, baseline, seeds, *, index_start, shuffle_objects, deck):
    counts = dict(wins=0, opp_wins=0, draws=0, rank_sum=0.0,
                  deaths=0, flees=0, ponces=0, score_sum=0.0, games=0)
    for local_i, seed in enumerate(seeds):
        eval_index = index_start + local_i
        joueurs, objets = build_toy_match(seed, shuffle_objects=shuffle_objects, deck=deck)
        seat = eval_index % len(joueurs)
        assignments = {i: (agent if i == seat else baseline) for i in range(len(joueurs))}
        routed = routed_toy_policy(assignments, joueurs)
        winner, joueurs_finaux = ordonnanceur(joueurs, make_dungeon(deck), objets, False, policy=routed)
        target = joueurs_finaux[seat]
        counts['wins'] += int(target is winner)
        counts['opp_wins'] += int(winner is not None and target is not winner)
        counts['draws'] += int(winner is None)  # no winner (typically both dead)
        counts['rank_sum'] += _player_rank(joueurs_finaux, target)
        counts['deaths'] += int(not target.vivant)
        counts['flees'] += int(target.fuite_reussie)
        counts['ponces'] += int(target.dans_le_dj)
        counts['score_sum'] += float(target.score_final)
        counts['games'] += 1
    return counts, agent.export_kinds_seen(), agent.export_skill_stats()


def _toy_eval_worker(task):
    import torch as _torch
    _torch.set_num_threads(1)
    model, encoder = build_toy_model(hidden_dim=task['hidden_dim'])
    model.load_state_dict(task['state_dict'])
    model.eval()
    agent = _toy_agent_policy(model, encoder, sample=False, record=False, deck=task['deck'])
    counts, kinds, skill = _run_toy_eval_chunk(
        agent, _opponent_policy(task['baseline']), task['seeds'],
        index_start=task['index_start'], shuffle_objects=task['shuffle_objects'], deck=task['deck'])
    return {'counts': counts, 'kinds_seen': kinds, 'skill_stats': skill}


def evaluate_toy(model, encoder, seed_bank, *, baseline='random', device='cpu',
                 shuffle_objects=False, deck='toy', num_workers=1, hidden_dim=128):
    """Greedy agent vs a fixed baseline ('random' or 'default'), agent seat
    rotated across games. Also reports the agent's behaviour (death / flee /
    ponce / score) so the win-rate can be interpreted, not just read. Greedy =
    deterministic, so num_workers>1 yields the identical winrate, just faster."""
    seed_bank = list(seed_bank)

    if num_workers and num_workers > 1 and len(seed_bank) > 1:
        state_dict = _cpu_state_dict(model)
        tasks = [{
            'state_dict': state_dict, 'hidden_dim': hidden_dim, 'baseline': baseline,
            'seeds': seed_bank[lo:hi], 'index_start': lo,
            'shuffle_objects': shuffle_objects, 'deck': deck,
        } for (lo, hi) in _chunk_bounds(len(seed_bank), num_workers)]
        results = _get_toy_pool(num_workers).map(_toy_eval_worker, tasks)
        counts = dict(wins=0, opp_wins=0, draws=0, rank_sum=0.0,
                      deaths=0, flees=0, ponces=0, score_sum=0.0, games=0)
        kinds = Counter()
        skill = Counter()
        for r in results:
            for key, value in r['counts'].items():
                counts[key] += value
            kinds.update(r['kinds_seen'])
            skill.update(r['skill_stats'])
        kinds_seen, skill_stats = dict(kinds), dict(skill)
    else:
        agent = _toy_agent_policy(model, encoder, sample=False, record=False, deck=deck, device=device)
        counts, kinds_seen, skill_stats = _run_toy_eval_chunk(
            agent, _opponent_policy(baseline), seed_bank,
            index_start=0, shuffle_objects=shuffle_objects, deck=deck)

    games = max(1, counts['games'])
    return {
        'games': games,
        'winrate': counts['wins'] / games,
        'loss_rate': counts['opp_wins'] / games,      # opponent won
        'draw_rate': counts['draws'] / games,          # no winner (both excluded/dead)
        'avg_rank': counts['rank_sum'] / games,
        'chance_winrate': 1.0 / len(TOY_PLAYER_NAMES),
        'death_rate': counts['deaths'] / games,
        'flee_rate': counts['flees'] / games,
        'ponce_rate': counts['ponces'] / games,
        'avg_score': counts['score_sum'] / games,
        'kinds_seen': kinds_seen,
        'skill_stats': skill_stats,
    }


# --- Success criterion #2: a hand-checkable optimal decision -----------------

def _toy_game_namespace(actor, remaining_indices):
    from types import SimpleNamespace

    donjon = SimpleNamespace(ordre=list(remaining_indices), index=0, cartes=[])
    return SimpleNamespace(
        donjon=donjon,
        joueurs=[actor],
        tour=2,
        traquenard_actif=False,
        traquenard_paye=False,
        execute_next_monster=False,
    )


def probe_optimal_combat_decision(model, encoder, *, device='cpu'):
    """Controlled single-decision probes (criterion #2).

    The scarce one-shot Hache de Glace is the only tool that executes a Dragon.
    The greedy agent should (a) spend it on a Dragon when tanking would be lethal,
    and (b) NOT waste it on a weakling it can kill for free. We build the exact
    states -- using the real combat-candidate filter -- and read the argmax.
    """
    from joueurs import Joueur
    from objets import SANS_HOOK_OBJET

    o_combat = SANS_HOOK_OBJET['en_combat']
    policy = _make_toy_policy(model, encoder, sample=False, record=False, device=device)

    def choose(carte, hp):
        actor = Joueur(TOY_PLAYER_NAMES[0], make_toy_hero(), make_toy_objects())
        actor.pv_total = hp
        carte.dommages = carte.puissance
        carte.dommages_reference = carte.puissance
        game = _toy_game_namespace(actor, remaining_indices=[3, 4, 5])
        # Mirror simu's combat-candidate gathering: only objects that override
        # combat_effet and are legal right now (so the +5 armor is never offered).
        options = tuple(o for o in actor.objets
                        if type(o) not in o_combat and o.can_use_in_combat(actor, carte, game, []))
        context = DecisionContext(
            kind=DecisionKind.CHOOSE_COMBAT_OBJECT,
            actor=actor,
            game=game,
            phase='choose_combat_object',
            subject=carte,
            options=options,
            metadata={'allow_resolve_now': True, 'combat_step': 0, 'log_details': []},
        )
        return policy.decide(context)

    on_lethal_dragon = choose(CarteMonstre("Dragon", 9, ["Dragon"]), hp=6)   # 6 < 9: tanking kills
    on_weakling = choose(CarteMonstre("Squelette", 2, ["Squelette"]), hp=TOY_START_PV)
    return {
        'hache_on_lethal_dragon': is_hache(on_lethal_dragon),
        'hache_kept_on_weakling': not is_hache(on_weakling),
        'optimal_line': is_hache(on_lethal_dragon) and not is_hache(on_weakling),
    }


# --- Imitation: behaviour-clone the heuristic, then warmstart RL -------------
#
# Reward shaping alone cannot lift the agent out of the "flee immediately" basin
# on the shuffled deck (deviating mostly leads to death -> punished -> back to
# fleeing). So we first *copy the heuristic's decisions* with supervised learning
# (the heuristic already plays the good line: draw when the remaining deck is
# safe, Hache big monsters, flee in time), which puts the network in a competent
# region, then let PPO fine-tune from there. The heuristic is only an offline
# teacher; at play time the network still decides everything itself.

def _dragon_remains(game):
    donjon = getattr(game, 'donjon', None) if game is not None else None
    ordre = getattr(donjon, 'ordre', None)
    cartes = getattr(donjon, 'cartes', None)
    if ordre is None or not cartes:
        return False
    index = getattr(donjon, 'index', 0)
    return any('Dragon' in cartes[i].types for i in list(ordre)[index:])


class _DemoRecorder:
    """Plays the heuristic and records (encoded observation, chosen action) for
    each managed decision, to build a supervised dataset. ORDER_OBJECTS is
    resolved as identity (structural), like the toy.

    With ``correct_hache``, it demonstrates a *corrected* heuristic: it refuses to
    spend the one-shot Hache de Glace on a non-Dragon while a Dragon still remains
    in the deck (the heuristic wastes it ~69% of the time) -- it resolves the card
    instead, saving the Hache for the Dragon. Cloning this corrected teacher gives
    a policy that already out-plays the greedy heuristic on Hache management."""

    def __init__(self, encoder, correct_hache=False, managed_kinds=TOY_MANAGED_KINDS,
                 structural_kinds=TOY_STRUCTURAL_KINDS):
        self.encoder = encoder
        self.correct_hache = correct_hache
        self.managed_kinds = frozenset(managed_kinds)
        self.structural_kinds = frozenset(structural_kinds)
        self.heuristic = default_dungeon_policy()
        self.samples = []

    def decide(self, context):
        context = _context_with_choice_options(context)
        if context.kind in self.structural_kinds:
            return require_permutation(
                tuple(context.options), context.options, decision_name='toy_order_objects'
            )
        action = self.heuristic.decide(context)
        if (self.correct_hache and context.kind is DecisionKind.CHOOSE_COMBAT_OBJECT
                and is_hache(action)
                and 'Dragon' not in (getattr(context.subject, 'types', ()) or ())
                and _dragon_remains(context.game)
                and getattr(context.subject, 'dommages', 99) < getattr(context.actor, 'pv_total', 0)):
            # Save the Hache for the Dragon -- but only when tanking this monster
            # is survivable; still emergency-Hache a non-Dragon that would kill us.
            action = CombatObjectChoice.RESOLVE_NOW
        if context.kind in self.managed_kinds:
            self._record(context, action)
        return action

    def _record(self, context, action):
        encoded = self.encoder.encode(context)
        if encoded['mode'] == 'binary':
            self.samples.append({'mode': 'binary', 'obs': encoded['obs'], 'label': int(action)})
        elif encoded['mode'] in ('combat_object', 'single_object'):
            if action is CombatObjectChoice.RESOLVE_NOW or action is None:
                label = self.encoder.max_candidates  # the "resolve / none" slot
            else:
                options = context.options[:self.encoder.max_candidates]
                label = next(
                    (i for i, o in enumerate(options) if o is action or o == action),
                    self.encoder.max_candidates,
                )
            self.samples.append({
                'mode': encoded['mode'],
                'global_obs': encoded['global_obs'],
                'candidate_obs': encoded['candidate_obs'],
                'candidate_ids': encoded['candidate_ids'],
                'action_mask': encoded['action_mask'],
                'label': label,
            })
        elif encoded['mode'] == 'multi_object':
            selected = np.zeros(self.encoder.max_candidates, dtype=np.float32)
            chosen_ids = {id(value) for value in tuple(action or ())}
            for index, option in enumerate(context.options[:self.encoder.max_candidates]):
                selected[index] = float(id(option) in chosen_ids)
            self.samples.append({
                'mode': encoded['mode'],
                'global_obs': encoded['global_obs'],
                'candidate_obs': encoded['candidate_obs'],
                'candidate_ids': encoded['candidate_ids'],
                'action_mask': encoded['action_mask'],
                'multi_action': selected,
            })
        elif encoded['mode'] == 'order_objects':
            order = np.full(self.encoder.max_candidates, -1, dtype=np.int64)
            option_ids = {id(option): index for index, option in enumerate(context.options[:self.encoder.max_candidates])}
            for out_index, option in enumerate(tuple(action or ())[:self.encoder.max_candidates]):
                if id(option) in option_ids:
                    order[out_index] = option_ids[id(option)]
            self.samples.append({
                'mode': encoded['mode'],
                'global_obs': encoded['global_obs'],
                'candidate_obs': encoded['candidate_obs'],
                'candidate_ids': encoded['candidate_ids'],
                'action_mask': encoded['action_mask'],
                'action_sequence': order,
            })


def collect_heuristic_demonstrations(encoder, *, num_games, seed_start=1, correct_hache=False,
                                     reward_mode='shaped', deck='toy'):
    """Heuristic vs heuristic on shuffled decks; record both seats' managed
    decisions. Returns a flat list of supervised samples. ``reward_mode`` selects
    the value-target reward so the warmed critic matches the RL reward."""
    samples = []
    managed_kinds = FULL_MANAGED_KINDS if _toy_is_full_deck(deck) else TOY_MANAGED_KINDS
    structural_kinds = () if _toy_is_full_deck(deck) else TOY_STRUCTURAL_KINDS
    for offset in range(num_games):
        joueurs, objets = build_toy_match(seed_start + offset, deck=deck)
        recorders = [
            _DemoRecorder(
                encoder,
                correct_hache=correct_hache,
                managed_kinds=managed_kinds,
                structural_kinds=structural_kinds,
            )
            for _ in joueurs
        ]
        routed = routed_toy_policy({i: recorders[i] for i in range(len(joueurs))}, joueurs)
        winner, _ = ordonnanceur(joueurs, make_dungeon(deck), objets, False, policy=routed)
        for seat, rec in enumerate(recorders):
            ret = _terminal_reward(joueurs[seat], winner, joueurs, mode=reward_mode)  # value target to warm the critic
            for sample in rec.samples:
                sample['return'] = ret
            samples.extend(rec.samples)
    return samples


def behavior_clone(model, samples, *, epochs=12, lr=1e-3, batch_size=512, value_coef=0.5, device='cpu'):
    """Supervised: make the policy heads predict the heuristic's action AND warm
    the value head by regressing it to the demonstrations' game returns (so PPO
    fine-tuning starts with a meaningful critic, not random advantages). Returns
    per-mode action accuracy."""
    binary = [s for s in samples if s['mode'] == 'binary']
    combat = [s for s in samples if s['mode'] in ('combat_object', 'single_object')]
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    def binary_batch(batch):
        obs = torch.from_numpy(np.stack([s['obs'] for s in batch])).to(device)
        labels = torch.tensor([s['label'] for s in batch], dtype=torch.long, device=device)
        returns = torch.tensor([s.get('return', 0.0) for s in batch], dtype=torch.float32, device=device)
        logits, value = model.forward_binary(obs)
        loss = F.cross_entropy(logits, labels) + value_coef * F.mse_loss(value, returns)
        return loss, logits, labels

    def combat_batch(batch):
        g = torch.from_numpy(np.stack([s['global_obs'] for s in batch])).to(device)
        c = torch.from_numpy(np.stack([s['candidate_obs'] for s in batch])).to(device)
        ids = torch.from_numpy(np.stack([s['candidate_ids'] for s in batch])).to(device)
        mask = torch.from_numpy(np.stack([s['action_mask'] for s in batch])).to(device)
        labels = torch.tensor([s['label'] for s in batch], dtype=torch.long, device=device)
        returns = torch.tensor([s.get('return', 0.0) for s in batch], dtype=torch.float32, device=device)
        logits, value = model.forward_combat(g, c, ids, mask)
        loss = F.cross_entropy(logits, labels) + value_coef * F.mse_loss(value, returns)
        return loss, logits, labels

    model.train()
    rng = np.random.default_rng(0)
    for _ in range(epochs):
        for group, batcher in ((binary, binary_batch), (combat, combat_batch)):
            if not group:
                continue
            order = rng.permutation(len(group))
            for start in range(0, len(group), batch_size):
                batch = [group[i] for i in order[start:start + batch_size]]
                loss, _, _ = batcher(batch)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()
    model.eval()

    # Action accuracy on the full set (how faithfully it cloned the teacher).
    acc = {}
    with torch.no_grad():
        for name, group, batcher in (('binary', binary, binary_batch), ('combat', combat, combat_batch)):
            if not group:
                continue
            _, logits, labels = batcher(group)
            acc[name] = float((logits.argmax(dim=-1) == labels).float().mean())
    return {'binary_samples': len(binary), 'combat_samples': len(combat), 'accuracy': acc}


def _bc_anchor_step(model, optimizer, binary, combat, *, weight_binary, weight_combat,
                    batch_size=512, device='cpu', rng=None):
    """One supervised step pulling the policy toward the heuristic's actions --
    the 'leash' / KL-to-clone anchor. Cross-entropy only (no value term).

    DECISION-AWARE: a separate weight per decision group. We measured that the
    heuristic is *good* at flee/replay (binary) but *weak* at the object decisions
    (combat / repair / sacrifice) -- a uniform anchor therefore suppressed exactly
    the improvements we wanted. So anchor the binary group HARD (protect the good
    flee logic) and the object group LIGHTLY (let RL exploit the heuristic's weak
    object choices). This is still per-decision-TYPE, not per-object, so it stays
    scalable to the real game (a handful of decision groups, not hundreds of items).
    """
    rng = rng if rng is not None else np.random.default_rng()
    groups = []
    if weight_binary > 0 and binary:
        groups.append(('binary', binary, weight_binary))
    if weight_combat > 0 and combat:
        groups.append(('combat', combat, weight_combat))
    model.train()
    total = 0.0
    for mode, group, weight in groups:
        idx = rng.integers(0, len(group), size=min(batch_size, len(group)))
        batch = [group[i] for i in idx]
        labels = torch.tensor([s['label'] for s in batch], dtype=torch.long, device=device)
        if mode == 'binary':
            obs = torch.from_numpy(np.stack([s['obs'] for s in batch])).to(device)
            logits, _ = model.forward_binary(obs)
        else:
            g = torch.from_numpy(np.stack([s['global_obs'] for s in batch])).to(device)
            c = torch.from_numpy(np.stack([s['candidate_obs'] for s in batch])).to(device)
            ids = torch.from_numpy(np.stack([s['candidate_ids'] for s in batch])).to(device)
            mask = torch.from_numpy(np.stack([s['action_mask'] for s in batch])).to(device)
            logits, _ = model.forward_combat(g, c, ids, mask)
        loss = weight * F.cross_entropy(logits, labels)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        total += float(loss.detach())
    model.eval()
    return total


# --- Training loop -----------------------------------------------------------

@dataclass
class ToyTrainResult:
    iterations: int
    final_winrate_vs_random: float
    best_winrate_vs_random: float
    final_winrate_vs_default: float
    best_winrate_vs_default: float
    skill_rate: float  # fraction of Hache uses on a monster the free tools can't kill
    kinds_seen: dict
    optimal_line: bool
    behaviour: dict
    opponent: str
    opponent_ratio: float
    history: list


def train_toy(
    *,
    iterations=120,
    episodes_per_batch=256,
    eval_games=400,
    eval_every=10,
    hidden_dim=128,
    lr=3e-4,
    entropy_coef=0.01,
    entropy_coef_final=None,
    opponent='random',
    opponent_ratio=0.0,
    reward_mode='shaped',
    snapshot_every=25,
    freeze_binary=False,
    shuffle_objects=False,
    deck='toy',
    anchor_demos=None,
    bc_anchor_weight=0.0,
    bc_anchor_weight_combat=None,
    seed=20260616,
    device='cpu',
    run_dir=None,
    verbose=True,
    init_state_dict=None,
    num_workers=1,
):
    torch.manual_seed(seed)
    model, encoder = build_toy_model(hidden_dim=hidden_dim, device=device)
    if init_state_dict is not None:  # warmstart (e.g. from behaviour cloning)
        model.load_state_dict(init_state_dict)
    # Optionally freeze the flee/replay (binary) subnetwork so RL keeps the cloned
    # heuristic's well-tuned flee/replay EXACTLY and optimises ONLY the combat /
    # Hache decisions -- the part with proven headroom (SaveHache wins by keeping
    # the heuristic's flee logic and changing only Hache use). The agent still
    # *discovers* the Hache policy itself; it just can't wreck the good flee logic.
    if freeze_binary:
        for name, param in model.named_parameters():
            if name.startswith('binary_'):
                param.requires_grad_(False)
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.Adam(trainable, lr=lr)

    # League-style self-play: the opponent is a FROZEN past-self snapshot,
    # refreshed every ``snapshot_every`` iters. Unlike mirror self-play (which can
    # cycle) or a fixed opponent (which caps at that opponent's exploitability),
    # chasing a slowly-improving past self is a moving curriculum that tends to
    # produce robust, genuinely stronger play. The vs_default eval still selects
    # the saved checkpoint, so we harvest whatever is best against the heuristic.
    snapshot_opponent = None
    if opponent == 'snapshot':
        opp_model, _ = build_toy_model(hidden_dim=hidden_dim, device=device)
        opp_model.load_state_dict(model.state_dict())
        snapshot_opponent = _toy_agent_policy(opp_model, encoder, sample=True, record=False, deck=deck, device=device)
    ppo_config = PPOConfig(lr=lr, entropy_coef=entropy_coef, minibatch_size=2048)
    # Entropy annealing: explore early (high coef -> escape the BC-clone anchor /
    # premature collapse we diagnosed), exploit late (low coef -> sharpen the
    # discovered policy). Constant if entropy_coef_final is None.
    entropy_start = entropy_coef
    entropy_end = entropy_coef if entropy_coef_final is None else entropy_coef_final
    eval_bank = _seed_bank(seed ^ 0x5151, eval_games)

    # BC-anchor 'leash': pre-split the demos so each iter can pull the policy back
    # toward the heuristic's actions (see _bc_anchor_step). Decision-aware: a
    # separate weight for the binary (flee/replay) group vs the object group. If
    # the binary subnet is frozen, force its anchor weight to 0 (no grad).
    anchor_w_binary = 0.0 if freeze_binary else bc_anchor_weight
    anchor_w_combat = bc_anchor_weight if bc_anchor_weight_combat is None else bc_anchor_weight_combat
    anchor_binary = anchor_combat = None
    anchor_rng = None
    if anchor_demos and (anchor_w_binary > 0 or anchor_w_combat > 0):
        anchor_binary = [s for s in anchor_demos if s['mode'] == 'binary']
        anchor_combat = [s for s in anchor_demos if s['mode'] in ('combat_object', 'single_object')]
        anchor_rng = np.random.default_rng(seed ^ 0xA5A5)

    history = []
    best_vs_random = best_vs_default = 0.0
    last_vs_random = last_vs_default = 0.0
    last_skill_rate = 0.0
    last_kinds = {}
    last_behaviour = {}

    for iteration in range(1, iterations + 1):
        # Linearly anneal the entropy bonus across training.
        frac = (iteration - 1) / max(1, iterations - 1)
        ppo_config.entropy_coef = entropy_start + frac * (entropy_end - entropy_start)
        # Refresh the frozen self-play snapshot on schedule (moving curriculum).
        if snapshot_opponent is not None and iteration > 1 and (iteration - 1) % snapshot_every == 0:
            snapshot_opponent.model.load_state_dict(model.state_dict())
        rollout_seed = seed + iteration * episodes_per_batch
        rollout = collect_toy_rollouts(
            model, encoder, episodes=episodes_per_batch, seed_start=rollout_seed,
            opponent=opponent, opponent_ratio=opponent_ratio, device=device,
            reward_mode=reward_mode, opponent_policy=snapshot_opponent,
            shuffle_objects=shuffle_objects, deck=deck,
            # Rollouts stay serial on purpose: fanning them out is transfer-bound
            # (workers must ship back tens of MB of experience buffers, which eats
            # the parallel gain -- measured ~neutral). The real rollout speedup is
            # torch.set_num_threads(1) (set in main). Eval, returning only counts,
            # parallelises cleanly -- see the evaluate_toy calls below.
            num_workers=1, hidden_dim=hidden_dim,
        )
        steps_for_update = rollout['steps']
        if freeze_binary:
            # The frozen flee/replay (binary) steps carry no gradient; drop them
            # so PPO only updates the trainable combat/Hache parameters.
            steps_for_update = [s for s in steps_for_update if s.get('mode') != 'binary']
        update = ppo_update(model, optimizer, steps_for_update, ppo_config, device=device)
        # Leash: pull the policy back toward the heuristic's actions (skip binary
        # if it is frozen). RL overrides this only where the reward gradient wins.
        if anchor_rng is not None:
            _bc_anchor_step(model, optimizer, anchor_binary, anchor_combat,
                            weight_binary=anchor_w_binary, weight_combat=anchor_w_combat,
                            device=device, rng=anchor_rng)

        skill = rollout['skill_stats']
        skill_rate = skill.get('hache_well_used', 0) / max(1, skill.get('hache_uses', 0))
        last_skill_rate = skill_rate
        last_kinds = rollout['kinds_seen']

        if iteration % eval_every == 0 or iteration == iterations:
            eval_random = evaluate_toy(
                model, encoder, eval_bank, baseline='random', device=device,
                shuffle_objects=shuffle_objects, deck=deck,
                num_workers=num_workers, hidden_dim=hidden_dim)
            eval_default = evaluate_toy(
                model, encoder, eval_bank, baseline='default', device=device,
                shuffle_objects=shuffle_objects, deck=deck,
                num_workers=num_workers, hidden_dim=hidden_dim)
            last_vs_random = eval_random['winrate']
            last_vs_default = eval_default['winrate']
            best_vs_random = max(best_vs_random, last_vs_random)
            # Save the best-vs-heuristic checkpoint: PPO often peaks early then
            # drifts into the over-flee local optimum, so the final model is not
            # the strongest. Keep the peak so it can be evaluated/measured.
            if run_dir and last_vs_default > best_vs_default:
                _bp = Path(run_dir)
                _bp.mkdir(parents=True, exist_ok=True)
                torch.save(
                    {'model_state_dict': {k: v.detach().cpu() for k, v in model.state_dict().items()},
                     'hidden_dim': hidden_dim, 'iteration': iteration,
                     'vs_default': last_vs_default},
                    _bp / 'toy_best.pt',
                )
            best_vs_default = max(best_vs_default, last_vs_default)
            last_behaviour = {
                'winrate': eval_default['winrate'],
                'loss_rate': eval_default.get('loss_rate', 0.0),
                'draw_rate': eval_default.get('draw_rate', 0.0),
                'death_rate': eval_default['death_rate'],
                'flee_rate': eval_default['flee_rate'],
                'ponce_rate': eval_default['ponce_rate'],
                'avg_score': eval_default['avg_score'],
            }
            row = {
                'iteration': iteration,
                'winrate_vs_random': last_vs_random,
                'winrate_vs_default': last_vs_default,
                'chance_winrate': eval_random['chance_winrate'],
                'hache_well_used_rate': skill_rate,
                'hache_uses': skill.get('hache_uses', 0),
                'hache_well_used': skill.get('hache_well_used', 0),
                'avg_reward_per_player': rollout['avg_reward_per_player'],
                'policy_loss': update['policy_loss'],
                'value_loss': update['value_loss'],
                'entropy': update['entropy'],
                **last_behaviour,
            }
            history.append(row)
            if verbose:
                print(
                    f"[toy iter {iteration:03d}] "
                    f"vs_random={last_vs_random:.3f} vs_default={last_vs_default:.3f} "
                    f"(W{eval_default['winrate']:.2f}/L{eval_default.get('loss_rate', 0.0):.2f}/"
                    f"D{eval_default.get('draw_rate', 0.0):.2f}) "
                    f"hache_alloc={skill_rate:.3f} "
                    f"death={eval_default['death_rate']:.2f} flee={eval_default['flee_rate']:.2f} "
                    f"ponce={eval_default['ponce_rate']:.2f} score={eval_default['avg_score']:.2f} "
                    f"entropy={update['entropy']:.3f}",
                    flush=True,
                )

    optimal = probe_optimal_combat_decision(model, encoder, device=device)

    if run_dir:
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        torch.save(
            {'model_state_dict': {k: v.detach().cpu() for k, v in model.state_dict().items()},
             'hidden_dim': hidden_dim},
            run_path / 'toy_latest.pt',
        )
        (run_path / 'toy_metrics.json').write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8'
        )

    return ToyTrainResult(
        iterations=iterations,
        final_winrate_vs_random=last_vs_random,
        best_winrate_vs_random=best_vs_random,
        final_winrate_vs_default=last_vs_default,
        best_winrate_vs_default=best_vs_default,
        skill_rate=last_skill_rate,
        kinds_seen=last_kinds,
        optimal_line=optimal['optimal_line'],
        behaviour=last_behaviour,
        opponent=opponent,
        opponent_ratio=opponent_ratio,
        history=history,
    )


def format_toy_report(result: ToyTrainResult):
    regime = (
        "pure self-play" if result.opponent_ratio == 0
        else f"self-play + {result.opponent_ratio:.0%} vs-{result.opponent}"
    )
    b = result.behaviour
    lines = [
        "## Toy-mode RL diagnostic report",
        "",
        f"- Training regime: {regime}",
        f"- Iterations: {result.iterations}",
        f"- Winrate vs RandomPolicy: {result.final_winrate_vs_random:.3f} "
        f"(best {result.best_winrate_vs_random:.3f}, chance 0.50)",
        f"- Winrate vs DefaultDungeonPolicy (heuristic): {result.final_winrate_vs_default:.3f} "
        f"(best {result.best_winrate_vs_default:.3f}, chance 0.50)",
        # Descriptive only -- NOT a quality judgment. The agent decides where to
        # spend the one-shot Hache; this just observes how often it landed on a
        # monster the free tools could not already kill.
        f"- Hache de Glace allocation (observed; one-shot landed on a monster the "
        f"free tools can't kill): {result.skill_rate:.3f}",
        f"- Reproduces hand-derived optimal line on the probe: {result.optimal_line}",
    ]
    if b:
        if 'loss_rate' in b and 'draw_rate' in b:
            lines.append(
                f"- Outcome split vs the heuristic: agent wins {b['winrate']:.1%}, "
                f"heuristic wins {b['loss_rate']:.1%}, draws/double-death {b['draw_rate']:.1%}"
            )
        lines.append(
            f"- Agent behaviour vs the heuristic: death {b['death_rate']:.2f}, "
            f"flee {b['flee_rate']:.2f}, ponce {b['ponce_rate']:.2f}, "
            f"avg score {b['avg_score']:.2f}"
        )
    lines += [
        "",
        "Decision kinds encountered during rollouts (all must be network-encodable):",
    ]
    for name, count in sorted(result.kinds_seen.items()):
        managed = any(k.name == name for k in NORMAL_MANAGED_KINDS)
        structural = any(k.name == name for k in TOY_STRUCTURAL_KINDS)
        tag = "network" if managed else ("structural(identity)" if structural else "fallback")
        lines.append(f"  - {name}: {count}  [{tag}]")
    return "\n".join(lines)


def train_toy_imitation_then_rl(
    *,
    demo_games=800,
    bc_epochs=15,
    bc_lr=1e-3,
    hidden_dim=128,
    iterations=120,
    episodes_per_batch=256,
    eval_games=600,
    eval_every=10,
    lr=1e-4,
    entropy_coef=0.02,
    entropy_coef_final=None,
    opponent='default',
    opponent_ratio=1.0,
    correct_hache=False,
    reward_mode='shaped',
    snapshot_every=25,
    soften_head=None,
    freeze_binary=False,
    shuffle_objects=False,
    bc_anchor_weight=0.0,
    bc_anchor_weight_combat=None,
    deck='toy',
    seed=20260616,
    device='cpu',
    run_dir=None,
    verbose=True,
    num_workers=1,
):
    """Behaviour-clone the heuristic, then PPO fine-tune from those weights.
    Returns (rl_result, bc_metrics, eval_after_bc)."""
    torch.manual_seed(seed)
    model, encoder = build_toy_model(hidden_dim=hidden_dim, device=device)

    demos = collect_heuristic_demonstrations(
        encoder, num_games=demo_games, seed_start=seed, correct_hache=correct_hache,
        reward_mode=reward_mode, deck=deck)
    bc_metrics = behavior_clone(model, demos, epochs=bc_epochs, lr=bc_lr, device=device)
    eval_bank = _seed_bank(seed ^ 0x5151, eval_games)
    after_bc = {
        'vs_random': evaluate_toy(model, encoder, eval_bank, baseline='random', device=device, deck=deck,
                                  num_workers=num_workers, hidden_dim=hidden_dim)['winrate'],
        'vs_default': evaluate_toy(model, encoder, eval_bank, baseline='default', device=device, deck=deck,
                                   num_workers=num_workers, hidden_dim=hidden_dim)['winrate'],
    }
    if verbose:
        print(f"[BC] samples binary={bc_metrics['binary_samples']} combat={bc_metrics['combat_samples']} "
              f"acc={bc_metrics['accuracy']} | after-clone winrate "
              f"vs_random={after_bc['vs_random']:.3f} vs_default={after_bc['vs_default']:.3f}", flush=True)

    # Save the post-clone weights: this agent plays like the heuristic (~its
    # self-play ceiling), the reference point RL then tries to beat.
    if run_dir:
        _bcp = Path(run_dir)
        _bcp.mkdir(parents=True, exist_ok=True)
        torch.save(
            {'model_state_dict': {k: v.detach().cpu() for k, v in model.state_dict().items()},
             'hidden_dim': hidden_dim, 'vs_default': after_bc['vs_default']},
            _bcp / 'toy_postbc.pt',
        )

    # Optionally de-peak the cloned policy so PPO can explore off the BC anchor.
    if soften_head is not None:
        _soften_policy_heads(model, soften_head)
        if verbose:
            print(f"[BC] softened policy heads by factor {soften_head} (greedy action preserved)", flush=True)

    result = train_toy(
        iterations=iterations, episodes_per_batch=episodes_per_batch, eval_games=eval_games,
        eval_every=eval_every, hidden_dim=hidden_dim, lr=lr, entropy_coef=entropy_coef,
        entropy_coef_final=entropy_coef_final,
        opponent=opponent, opponent_ratio=opponent_ratio, reward_mode=reward_mode,
        snapshot_every=snapshot_every, freeze_binary=freeze_binary,
        shuffle_objects=shuffle_objects, deck=deck,
        anchor_demos=(demos if (bc_anchor_weight > 0 or (bc_anchor_weight_combat or 0) > 0) else None),
        bc_anchor_weight=bc_anchor_weight, bc_anchor_weight_combat=bc_anchor_weight_combat,
        seed=seed, device=device,
        run_dir=run_dir, verbose=verbose, init_state_dict={k: v.detach().cpu() for k, v in model.state_dict().items()},
        num_workers=num_workers,
    )
    return result, bc_metrics, after_bc


def run_toy_smoke():
    """Tiny end-to-end run used by tests: exercises every code path quickly."""
    result = train_toy(
        iterations=2,
        episodes_per_batch=24,
        eval_games=24,
        eval_every=1,
        hidden_dim=32,
        seed=777,
        verbose=False,
    )
    return result


def run_toy_imitation_smoke():
    """Tiny imitation+RL run used by tests."""
    result, bc, after_bc = train_toy_imitation_then_rl(
        demo_games=20, bc_epochs=2, hidden_dim=32, iterations=2,
        episodes_per_batch=24, eval_games=24, eval_every=1, seed=777, verbose=False,
    )
    return result, bc, after_bc


def main():
    parser = argparse.ArgumentParser(description="Toy-mode PPO diagnostic for simudonjon.")
    subparsers = parser.add_subparsers(dest='command', required=False)

    train_parser = subparsers.add_parser('train', help='Run the toy training loop and print a report.')
    train_parser.add_argument('--iterations', type=int, default=120)
    train_parser.add_argument('--episodes-per-batch', type=int, default=256)
    train_parser.add_argument('--eval-games', type=int, default=400)
    train_parser.add_argument('--eval-every', type=int, default=10)
    train_parser.add_argument('--hidden-dim', type=int, default=128)
    train_parser.add_argument('--lr', type=float, default=3e-4)
    train_parser.add_argument('--entropy-coef', type=float, default=0.01)
    train_parser.add_argument(
        '--entropy-coef-final', type=float, default=None,
        help='If set, linearly anneal the entropy bonus from --entropy-coef to this over training.')
    train_parser.add_argument(
        '--opponent', choices=('random', 'default', 'snapshot'), default='random',
        help="Opponent for the vs-opponent episodes: 'default' = heuristic, "
             "'snapshot' = frozen past-self (league self-play, refreshed every --snapshot-every).",
    )
    train_parser.add_argument('--snapshot-every', type=int, default=25,
                              help="Refresh the frozen self-play snapshot every N iters (opponent='snapshot').")
    train_parser.add_argument('--shuffle-objects', action='store_true',
                              help="Shuffle each player's inventory order per game (order-invariance).")
    train_parser.add_argument('--deck', choices=('toy', 'normal', 'full'), default='toy',
                              help="toy = reduced diagnostic deck/hands; normal = full dungeon, "
                                   "hands from the 14-object toy pool; full = full dungeon AND "
                                   "hands drawn from ALL game objects.")
    train_parser.add_argument(
        '--opponent-ratio', type=float, default=0.0,
        help='Fraction of rollout episodes played vs the fixed opponent (0 = pure self-play).',
    )
    train_parser.add_argument(
        '--reward-mode', choices=('shaped', 'margin'), default='shaped',
        help="'shaped' = absolute survive credit (default); 'margin' = competitive "
             "(my_score - opponent_score), un-gameable by fleeing.",
    )
    train_parser.add_argument('--seed', type=int, default=20260616)
    train_parser.add_argument('--run-dir', default='artifacts/rl_toy')
    train_parser.add_argument(
        '--num-workers', type=int, default=0,
        help="Parallel rollout/eval processes (0 = auto ~physical cores, 1 = serial).")

    subparsers.add_parser('smoke', help='Run a tiny toy training smoke and print a report.')

    imitate_parser = subparsers.add_parser(
        'imitate', help='Behaviour-clone the heuristic, then PPO fine-tune; print a report.')
    imitate_parser.add_argument('--demo-games', type=int, default=800)
    imitate_parser.add_argument('--bc-epochs', type=int, default=15)
    imitate_parser.add_argument('--bc-lr', type=float, default=1e-3)
    imitate_parser.add_argument('--iterations', type=int, default=120)
    imitate_parser.add_argument('--episodes-per-batch', type=int, default=256)
    imitate_parser.add_argument('--eval-games', type=int, default=600)
    imitate_parser.add_argument('--eval-every', type=int, default=10)
    imitate_parser.add_argument('--hidden-dim', type=int, default=128)
    imitate_parser.add_argument('--lr', type=float, default=1e-4)
    imitate_parser.add_argument('--entropy-coef', type=float, default=0.02)
    imitate_parser.add_argument(
        '--entropy-coef-final', type=float, default=None,
        help='If set, linearly anneal the entropy bonus from --entropy-coef to this over training.')
    imitate_parser.add_argument('--opponent', choices=('random', 'default', 'snapshot'), default='default')
    imitate_parser.add_argument('--opponent-ratio', type=float, default=1.0)
    imitate_parser.add_argument('--snapshot-every', type=int, default=25,
                                help="Refresh the frozen self-play snapshot every N iters (opponent='snapshot').")
    imitate_parser.add_argument(
        '--soften-head', type=float, default=None,
        help="Scale the cloned policy-head logits by this factor (<1) before RL, to "
             "de-peak the distribution so PPO can explore (greedy action preserved).")
    imitate_parser.add_argument(
        '--freeze-binary', action='store_true',
        help="Freeze the cloned flee/replay (binary) subnet; RL optimises ONLY the "
             "combat/Hache decisions (keeps the heuristic's good flee logic intact).")
    imitate_parser.add_argument(
        '--bc-anchor-weight', type=float, default=0.0,
        help="Leash strength on the BINARY (flee/replay) decisions -- the ones the "
             "heuristic does well, so anchor them hard.")
    imitate_parser.add_argument(
        '--bc-anchor-weight-combat', type=float, default=None,
        help="Leash strength on the OBJECT decisions (combat/repair/sacrifice) -- where "
             "the heuristic is weak, so anchor lightly. Defaults to --bc-anchor-weight "
             "(uniform leash) if unset; set lower for the decision-aware leash.")
    imitate_parser.add_argument(
        '--shuffle-objects', action='store_true',
        help="Shuffle each player's inventory order per game (order-invariance robustness).")
    imitate_parser.add_argument('--deck', choices=('toy', 'normal', 'full'), default='toy',
                                help="toy = reduced diagnostic deck/hands; normal = full dungeon, "
                                     "hands from the 14-object toy pool; full = full dungeon AND "
                                     "hands drawn from ALL game objects.")
    imitate_parser.add_argument(
        '--correct-hache', action='store_true',
        help="Clone a corrected teacher that saves the one-shot Hache for Dragons "
             "(the heuristic wastes it ~69%% of the time).")
    imitate_parser.add_argument(
        '--reward-mode', choices=('shaped', 'margin'), default='shaped',
        help="'shaped' = absolute survive credit (default); 'margin' = competitive "
             "(my_score - opponent_score), un-gameable by fleeing.",
    )
    imitate_parser.add_argument('--seed', type=int, default=20260616)
    imitate_parser.add_argument('--run-dir', default='artifacts/rl_toy')
    imitate_parser.add_argument(
        '--num-workers', type=int, default=0,
        help="Parallel rollout/eval processes (0 = auto ~physical cores, 1 = serial).")

    args = parser.parse_args()
    command = args.command or 'train'

    # Batch-1 NN inference is faster on a single torch thread; we parallelise
    # across PROCESSES instead (one game-chunk per core), so pin threads to 1.
    torch.set_num_threads(1)

    def _resolve_workers(requested):
        if requested and requested > 0:
            return requested
        return max(1, min(8, (os.cpu_count() or 2) // 2))  # ~physical cores

    if command == 'train':
        result = train_toy(
            iterations=args.iterations,
            episodes_per_batch=args.episodes_per_batch,
            eval_games=args.eval_games,
            eval_every=args.eval_every,
            hidden_dim=args.hidden_dim,
            lr=args.lr,
            entropy_coef=args.entropy_coef,
            entropy_coef_final=args.entropy_coef_final,
            opponent=args.opponent,
            opponent_ratio=args.opponent_ratio,
            reward_mode=args.reward_mode,
            snapshot_every=args.snapshot_every,
            shuffle_objects=args.shuffle_objects,
            deck=args.deck,
            seed=args.seed,
            run_dir=args.run_dir,
            num_workers=_resolve_workers(args.num_workers),
        )
        print(format_toy_report(result))
        return

    if command == 'smoke':
        result = run_toy_smoke()
        print(format_toy_report(result))
        return

    if command == 'imitate':
        result, bc, after_bc = train_toy_imitation_then_rl(
            demo_games=args.demo_games,
            bc_epochs=args.bc_epochs,
            bc_lr=args.bc_lr,
            iterations=args.iterations,
            episodes_per_batch=args.episodes_per_batch,
            eval_games=args.eval_games,
            eval_every=args.eval_every,
            hidden_dim=args.hidden_dim,
            lr=args.lr,
            entropy_coef=args.entropy_coef,
            entropy_coef_final=args.entropy_coef_final,
            opponent=args.opponent,
            opponent_ratio=args.opponent_ratio,
            correct_hache=args.correct_hache,
            reward_mode=args.reward_mode,
            snapshot_every=args.snapshot_every,
            soften_head=args.soften_head,
            freeze_binary=args.freeze_binary,
            shuffle_objects=args.shuffle_objects,
            bc_anchor_weight=args.bc_anchor_weight,
            bc_anchor_weight_combat=args.bc_anchor_weight_combat,
            deck=args.deck,
            seed=args.seed,
            run_dir=args.run_dir,
            num_workers=_resolve_workers(args.num_workers),
        )
        print(f"\n[imitation] clone accuracy={bc['accuracy']} | "
              f"after-clone vs_default={after_bc['vs_default']:.3f} vs_random={after_bc['vs_random']:.3f}\n")
        print(format_toy_report(result))
        return


if __name__ == '__main__':
    main()
