from __future__ import annotations

import argparse
import __main__
import csv
import json
import multiprocessing as mp
import os
import random
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torch.distributions import Bernoulli, Categorical

from ai_decisions import CombatObjectChoice, DecisionKind
from ai_policy import default_dungeon_policy, random_dungeon_policy
from heros import persos_disponibles
from joueurs import Joueur
from monstres import DonjonDeck
from objets import ITEM_GAMEPLAY_TAGS, objets_disponibles
from simu import ordonnanceur


PLAYER_NAMES = ("Sagarex", "Francis", "Mastho", "Mr.Adam")
INITIAL_MANAGED_KINDS = (
    DecisionKind.SHOULD_FLEE,
    DecisionKind.USE_OBJECT_IN_COMBAT,
    DecisionKind.USE_ACTIVE_OBJECT,
    DecisionKind.USE_HERO_ABILITY,
    DecisionKind.CHOOSE_OBJECT,
    DecisionKind.CHOOSE_OBJECTS,
    DecisionKind.CHOOSE_COMBAT_OBJECT,
    DecisionKind.CHOOSE_OBJECT_TO_SACRIFICE,
    DecisionKind.CHOOSE_OBJECT_TO_REPAIR,
    DecisionKind.ORDER_OBJECTS,
)
DECISION_EXPANSION_ORDER = ()
BINARY_KINDS = (
    DecisionKind.SHOULD_FLEE,
    DecisionKind.USE_OBJECT_IN_COMBAT,
    DecisionKind.USE_ACTIVE_OBJECT,
    DecisionKind.USE_HERO_ABILITY,
)
SINGLE_OBJECT_KINDS = (
    DecisionKind.CHOOSE_COMBAT_OBJECT,
    DecisionKind.CHOOSE_OBJECT,
    DecisionKind.CHOOSE_OBJECT_TO_SACRIFICE,
    DecisionKind.CHOOSE_OBJECT_TO_REPAIR,
)
MULTI_OBJECT_KINDS = (DecisionKind.CHOOSE_OBJECTS,)
ORDER_OBJECT_KINDS = (DecisionKind.ORDER_OBJECTS,)
KIND_VOCAB = INITIAL_MANAGED_KINDS + DECISION_EXPANSION_ORDER
PHASE_VOCAB = (
    'flee',
    'object_combat',
    'choose_combat_object',
    'traquenard',
    'kraken_face_or_bottom',
    'guardian_angel_face_or_discard',
    'fortune_wheel',
    'ninja_flee_bonus',
    'princess_draw',
    'tricheur_debut_tour',
    'chevalier_dragon',
    'docteur_de_peste',
    'inventeur_genial',
    'flutiste',
    'avatar',
    'berserker_survive',
    'prophete',
    'shaman_reroll',
    'lapin_skip_turn',
    'repair_object',
    'shop_discard',
    'kraken_confidence_object',
    'guardian_angel_confidence_object',
    'break_object_limon',
    'object_sacrifice',
    'object_sacrifice_limon',
    'draw_two_keep_one',
    'couteau_suisse_repair',
    'inventeur_discards',
    'gants_de_gaia_discards',
    'inventory',
)
PHASE_INDEX = {phase: index for index, phase in enumerate(PHASE_VOCAB)}
KIND_INDEX = {kind: index for index, kind in enumerate(KIND_VOCAB)}
OBJECT_TYPE_NAMES = tuple(sorted({type(objet).__name__ for objet in objets_disponibles}))
OBJECT_TYPE_INDEX = {name: index + 1 for index, name in enumerate(OBJECT_TYPE_NAMES)}

SELF_PLAY = 'self_play'
VERSUS_DEFAULT = 'versus_default'
VERSUS_RANDOM = 'versus_random'
CURRICULUM_LABELS = (SELF_PLAY, VERSUS_DEFAULT, VERSUS_RANDOM)

RANDOM_GATE_MARGIN = 0.10
DEFAULT_GATE_MARGIN = 0.05
DEFAULT_GATE_CONSECUTIVE = 2

EVAL_RANDOM_BASE_SEED = 2026061501
EVAL_DEFAULT_BASE_SEED = 2026061502

REWARD_SCHEDULES = {
    3: (1.0, 0.0, -1.0),
    4: (1.0, 0.3, -0.3, -1.0),
}
CHECKPOINT_NAME = 'progressive_latest.pt'
BEST_CHECKPOINT_NAME = 'progressive_best.pt'
SUCCESS_CHECKPOINT_NAME = 'progressive_success.pt'


@dataclass
class PPOConfig:
    clip_eps: float = 0.2
    entropy_coef: float = 0.01
    value_coef: float = 0.5
    lr: float = 3e-4
    ppo_epochs: int = 4
    minibatch_size: int = 4096


@dataclass
class CurriculumMix:
    self_play: float
    versus_default: float
    versus_random: float

    def normalized_counts(self, total_episodes: int) -> dict[str, int]:
        weights = {
            SELF_PLAY: self.self_play,
            VERSUS_DEFAULT: self.versus_default,
            VERSUS_RANDOM: self.versus_random,
        }
        total_weight = sum(weights.values())
        if total_weight <= 0:
            raise ValueError("Curriculum weights must sum to a positive value")

        exact = {label: (weight / total_weight) * total_episodes for label, weight in weights.items()}
        counts = {label: int(value) for label, value in exact.items()}
        assigned = sum(counts.values())
        remainders = sorted(
            CURRICULUM_LABELS,
            key=lambda label: (exact[label] - counts[label], exact[label]),
            reverse=True,
        )
        while assigned < total_episodes:
            label = remainders[assigned % len(remainders)]
            counts[label] += 1
            assigned += 1
        return counts


@dataclass
class RewardConfig:
    enabled: bool = False
    placement_mode: str = 'ranked'
    score_coef: float = 0.02
    monster_coef: float = 0.01
    death_penalty: float = 0.20
    bad_flee_penalty: float = 0.10


@dataclass
class StageConfig:
    name: str
    max_iterations: int
    hidden_dim: int
    managed_kinds: tuple[str, ...]
    ppo: PPOConfig
    reward: RewardConfig
    restart_from_scratch: bool = False


@dataclass
class TrainResult:
    success: bool
    run_dir: str
    latest_checkpoint: str
    best_checkpoint: str
    total_iterations: int
    history: list[dict]
    random_gate_iteration: int | None
    default_gate_iteration: int | None


class ObservationEncoder:
    derived_candidate_size = 16

    def __init__(self, max_objects=8, max_candidates=8):
        self.max_objects = max_objects
        self.max_candidates = max_candidates
        self.kind_size = len(KIND_VOCAB)
        self.phase_size = len(PHASE_VOCAB) + 1  # last slot = unknown
        self.item_tag_size = len(ITEM_GAMEPLAY_TAGS)
        self.binary_size = 39 + self.item_tag_size + self.kind_size + self.phase_size
        self.combat_global_size = 33 + self.kind_size + self.phase_size
        self.candidate_size = 12 + self.item_tag_size + self.derived_candidate_size
        self.object_type_vocab_size = len(OBJECT_TYPE_INDEX) + 1

    def observation_spec(self):
        return {
            'binary_size': self.binary_size,
            'combat_global_size': self.combat_global_size,
            'candidate_size': self.candidate_size,
            'max_candidates': self.max_candidates,
            'object_type_vocab_size': self.object_type_vocab_size,
        }

    def encode(self, context):
        if context.kind in SINGLE_OBJECT_KINDS:
            return self._encode_object_choice(context)
        if context.kind in MULTI_OBJECT_KINDS:
            return self._encode_object_choice(context, mode='multi_object')
        if context.kind in ORDER_OBJECT_KINDS:
            return self._encode_object_choice(context, mode='order_objects')
        return self._encode_binary(context)

    def _encode_binary(self, context):
        actor = context.actor
        game = context.game
        subject = context.subject
        candidate = self._binary_candidate(context)

        remaining_cards, players_alive, players_in_dungeon, player_count, game_turn = self._game_stats(game)
        subject_types = tuple(getattr(subject, 'types', ()) or ())
        candidate_types = tuple(getattr(candidate, 'types_tags', ()) or ())
        candidate_powers = tuple(getattr(candidate, 'puissance_tags', ()) or ())
        gameplay_tags = set(getattr(candidate, 'gameplay_tags', ()) or ())
        tag_features = [float(tag in gameplay_tags) for tag in ITEM_GAMEPLAY_TAGS]
        subject_power = getattr(subject, 'puissance_initiale', getattr(subject, 'puissance', 0))
        subject_damage = getattr(subject, 'dommages', getattr(subject, 'puissance', 0))
        score_now = _score_now(actor)
        intact_objects = [objet for objet in actor.objets if objet.intact]

        kind_features = [0.0] * self.kind_size
        kind_slot = KIND_INDEX.get(context.kind)
        if kind_slot is not None:
            kind_features[kind_slot] = 1.0

        phase_features = [0.0] * self.phase_size
        phase_slot = PHASE_INDEX.get(context.phase, self.phase_size - 1)
        phase_features[phase_slot] = 1.0

        features = kind_features + phase_features + [
            actor.pv_total / 20.0,
            actor.pv_base / 20.0,
            actor.medailles / 4.0,
            score_now / 20.0,
            len(actor.pile_monstres_vaincus) / 20.0,
            len(actor.objets) / float(self.max_objects),
            len(intact_objects) / float(self.max_objects),
            sum(1 for objet in actor.objets if not objet.intact) / float(self.max_objects),
            sum(1 for objet in intact_objects if getattr(objet, 'actif', False)) / float(self.max_objects),
            float(actor.vivant),
            float(actor.dans_le_dj),
            float(actor.fuite_reussie),
            players_alive / 4.0,
            players_in_dungeon / 4.0,
            player_count / 4.0,
            (player_count - players_alive) / 4.0,
            game_turn / 50.0,
            remaining_cards / 60.0,
            len(context.options) / float(self.max_candidates),
            float(candidate is not None),
            float(context.meta('allow_none', False)),
            float(getattr(subject, 'event', False)),
            float(getattr(subject, 'is_X', False)),
            subject_power / 12.0,
            subject_damage / 12.0,
            float(subject_damage >= actor.pv_total),
            len(subject_types) / 4.0,
            float(getattr(subject, 'effet', None) is not None),
            float(candidate is not None and getattr(candidate, 'actif', False)),
            float(candidate is not None and getattr(candidate, 'intact', False)),
            getattr(candidate, 'pv_bonus', 0) / 10.0,
            getattr(candidate, 'modificateur_de', 0) / 6.0,
            float(any(card_type in candidate_types for card_type in subject_types)),
            float(subject_power in candidate_powers),
            len(candidate_types) / 4.0,
            len(candidate_powers) / 4.0,
            float(any(10 in objet.puissance_tags for objet in intact_objects)),
            float(any(8 in objet.puissance_tags for objet in intact_objects)),
            float(any("Attrape" in getattr(objet, 'nom', '') and objet.intact for objet in actor.objets)),
            *tag_features,
        ]
        return {
            'mode': 'binary',
            'obs': np.asarray(features, dtype=np.float32),
        }

    def _binary_candidate(self, context):
        if context.kind == DecisionKind.USE_HERO_ABILITY:
            return (
                context.meta('hero')
                or context.meta('source')
                or (context.subject if context.subject is not None and not hasattr(context.subject, 'dommages') else None)
                or getattr(context.actor, 'perso_obj', None)
            )
        return context.meta('objet') or context.meta('source') or (context.options[0] if context.options else None)

    def _encode_object_choice(self, context, mode=None):
        actor = context.actor
        game = context.game
        subject = context.subject
        options = tuple(context.options[:self.max_candidates])
        option_count = len(options)
        remaining_cards, players_alive, players_in_dungeon, player_count, game_turn = self._game_stats(game)
        subject_types = tuple(getattr(subject, 'types', ()) or ())
        subject_power = getattr(subject, 'puissance_initiale', getattr(subject, 'puissance', 0))
        subject_damage = getattr(subject, 'dommages', getattr(subject, 'puissance', 0))
        score_now = _score_now(actor)
        intact_objects = [objet for objet in actor.objets if objet.intact]

        kind_features = [0.0] * self.kind_size
        kind_slot = KIND_INDEX.get(context.kind)
        if kind_slot is not None:
            kind_features[kind_slot] = 1.0

        phase_features = [0.0] * self.phase_size
        phase_slot = PHASE_INDEX.get(context.phase, self.phase_size - 1)
        phase_features[phase_slot] = 1.0

        global_features = kind_features + phase_features + [
            actor.pv_total / 20.0,
            actor.pv_base / 20.0,
            actor.medailles / 4.0,
            score_now / 20.0,
            len(actor.pile_monstres_vaincus) / 20.0,
            len(actor.objets) / float(self.max_objects),
            len(intact_objects) / float(self.max_objects),
            sum(1 for objet in actor.objets if not objet.intact) / float(self.max_objects),
            float(actor.vivant),
            float(actor.dans_le_dj),
            float(actor.fuite_reussie),
            players_alive / 4.0,
            players_in_dungeon / 4.0,
            player_count / 4.0,
            (player_count - players_alive) / 4.0,
            game_turn / 50.0,
            remaining_cards / 60.0,
            len(options) / float(self.max_candidates),
            float(context.meta('allow_resolve_now', True)),
            float(getattr(game, 'traquenard_actif', False) if game is not None else False),
            float(getattr(game, 'traquenard_paye', False) if game is not None else False),
            float(getattr(game, 'execute_next_monster', False) if game is not None else False),
            float(getattr(subject, 'event', False)),
            float(getattr(subject, 'is_X', False)),
            subject_power / 12.0,
            subject_damage / 12.0,
            float(subject_damage >= actor.pv_total),
            len(subject_types) / 4.0,
            float(getattr(subject, 'effet', None) is not None),
            min(1.0, context.meta('combat_step', 0) / 6.0),
            float(any(10 in objet.puissance_tags for objet in intact_objects)),
            float(any(8 in objet.puissance_tags for objet in intact_objects)),
            float(any("Attrape" in getattr(objet, 'nom', '') and objet.intact for objet in actor.objets)),
        ]

        candidate_obs = np.zeros((self.max_candidates, self.candidate_size), dtype=np.float32)
        candidate_ids = np.zeros(self.max_candidates, dtype=np.int64)
        has_null_action = self._has_null_action(context)
        mask_size = self.max_candidates + 1 if context.kind in SINGLE_OBJECT_KINDS else self.max_candidates
        action_mask = np.zeros(mask_size, dtype=np.float32)

        for index, objet in enumerate(options):
            candidate_obs[index] = self._encode_candidate(
                objet,
                subject_types,
                subject_power,
                subject_damage,
                actor,
            )
            candidate_ids[index] = OBJECT_TYPE_INDEX.get(type(objet).__name__, 0)
            action_mask[index] = 1.0
        if context.kind in SINGLE_OBJECT_KINDS and has_null_action:
            action_mask[self.max_candidates] = 1.0

        if mode is None:
            mode = 'combat_object' if context.kind == DecisionKind.CHOOSE_COMBAT_OBJECT else 'single_object'
        result = {
            'mode': mode,
            'global_obs': np.asarray(global_features, dtype=np.float32),
            'candidate_obs': candidate_obs,
            'candidate_ids': candidate_ids,
            'action_mask': action_mask,
            'option_count': option_count,
            'full_option_count': len(context.options),
        }
        if mode == 'multi_object':
            min_count, max_count = self._multi_count_bounds(context, option_count)
            result.update({'min_count': min_count, 'max_count': max_count})
        return result

    @staticmethod
    def _has_null_action(context):
        if context.kind == DecisionKind.CHOOSE_COMBAT_OBJECT:
            return context.meta('allow_resolve_now', True)
        if context.kind == DecisionKind.CHOOSE_OBJECT_TO_SACRIFICE and context.phase == 'break_object_limon':
            return True
        if context.kind == DecisionKind.CHOOSE_OBJECT and context.phase == 'coursier_volant_discard':
            return True
        return context.meta('allow_none', False)

    @staticmethod
    def _multi_count_bounds(context, option_count):
        target_count = context.meta('count')
        default_min = target_count if target_count is not None else 0
        default_max = target_count if target_count is not None else option_count
        if context.phase == 'inventeur_discards':
            default_min = default_max = 2
        min_count = int(context.meta('min_count', default_min))
        max_count = int(context.meta('max_count', default_max))
        min_count = max(0, min(min_count, option_count))
        max_count = max(min_count, min(max_count, option_count))
        return min_count, max_count

    def _game_stats(self, game):
        remaining_cards = 0
        players_alive = 1
        players_in_dungeon = 1
        player_count = 1
        game_turn = 0
        if game is not None:
            ordre = getattr(game.donjon, 'ordre', None)
            if ordre is not None:
                remaining_cards = max(0, len(ordre) - game.donjon.index)
            players_alive = sum(1 for joueur in game.joueurs if joueur.vivant)
            players_in_dungeon = sum(1 for joueur in game.joueurs if joueur.dans_le_dj)
            player_count = len(game.joueurs)
            game_turn = game.tour
        return remaining_cards, players_alive, players_in_dungeon, player_count, game_turn

    def _encode_candidate(self, objet, subject_types, subject_power, subject_damage, actor):
        types_tags = tuple(getattr(objet, 'types_tags', ()) or ())
        puissance_tags = tuple(getattr(objet, 'puissance_tags', ()) or ())
        type_match = any(card_type in types_tags for card_type in subject_types)
        power_match = subject_power in puissance_tags
        covers_lethal = (type_match or power_match) and subject_damage >= actor.pv_total
        gameplay_tags = set(getattr(objet, 'gameplay_tags', ()))
        has = gameplay_tags.__contains__
        tag_features = [float(tag in gameplay_tags) for tag in ITEM_GAMEPLAY_TAGS]
        actor_hp = float(actor.pv_total)
        actor_base_hp = float(max(1, getattr(actor, 'pv_base', actor.pv_total)))
        hp_bonus = float(getattr(objet, 'pv_bonus', 0))
        lethal = subject_damage >= actor.pv_total
        low_hp = actor_hp <= max(3.0, actor_base_hp * 0.5)
        survival_tags = {
            "EXECUTE",
            "ABSORB",
            "REDUCE_DAMAGE",
            "DISCARD_MONSTER",
            "PUT_BACK_MONSTER",
            "REROLL",
            "DICE_6_WIN",
            "SURVIVE",
            "SET_HP",
        }
        healing = has("HEAL_NOW") or has("HEAL_CONDITIONAL") or has("SET_HP")
        monster_control = has("EXECUTE") or has("DISCARD_MONSTER") or has("PUT_BACK_MONSTER") or has("STEAL_MONSTER")
        condition_count = sum(1 for tag in ("TYPE_CONDITION", "POWER_CONDITION", "HP_CONDITION") if has(tag))
        condition_hits = (
            int(has("TYPE_CONDITION") and type_match)
            + int(has("POWER_CONDITION") and power_match)
            + int(has("HP_CONDITION") and low_hp)
        )
        derived_features = [
            float(lethal),
            float(lethal and bool(gameplay_tags.intersection(survival_tags))),
            float(lethal and monster_control),
            float(lethal and healing),
            float(healing and actor_hp < actor_base_hp),
            float(has("RAW_HP") and hp_bonus > 0),
            max(-1.0, min(1.0, (actor_hp + max(0.0, hp_bonus) - subject_damage) / 20.0)),
            float(has("LOSE_HP") and actor_hp <= 2.0),
            float(has("ESCAPE_BONUS") and (low_hp or lethal)),
            float(has("ESCAPE_PENALTY") and (low_hp or lethal)),
            float(has("VP_BONUS") and not lethal),
            float(has("VP_PENALTY")),
            float(condition_count == 0 or condition_hits > 0),
            condition_hits / 3.0,
            float(has("PICK_NEW_ITEM") and len(actor.objets) <= self.max_objects),
            float(has("BREAK_SELF") or has("EN_MOUSSE")),
        ]
        return (
            float(getattr(objet, 'intact', False)),
            float(getattr(objet, 'actif', False)),
            getattr(objet, 'pv_bonus', 0) / 10.0,
            getattr(objet, 'modificateur_de', 0) / 6.0,
            len(types_tags) / 4.0,
            len(puissance_tags) / 4.0,
            float(8 in puissance_tags),
            float(10 in puissance_tags),
            (getattr(objet, 'couleur', 0) or 0) / 5.0,
            float(type_match),
            float(power_match),
            float(covers_lethal),
            *tag_features,
            *derived_features,
        )


class PolicyValueNet(nn.Module):
    def __init__(self, encoder, hidden_dim=128, object_embed_dim=16):
        super().__init__()
        self.binary_trunk = nn.Sequential(
            nn.Linear(encoder.binary_size, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        self.binary_policy_head = nn.Linear(hidden_dim, 2)
        self.binary_value_head = nn.Linear(hidden_dim, 1)

        self.object_embedding = nn.Embedding(encoder.object_type_vocab_size, object_embed_dim)
        self.combat_global_encoder = nn.Sequential(
            nn.Linear(encoder.combat_global_size, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        self.combat_candidate_encoder = nn.Sequential(
            nn.Linear(encoder.candidate_size + object_embed_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        self.combat_policy_head = nn.Linear(hidden_dim * 2, 1)
        self.multi_policy_head = nn.Linear(hidden_dim * 2, 1)
        self.order_policy_head = nn.Linear(hidden_dim * 2, 1)
        self.combat_resolve_head = nn.Linear(hidden_dim * 3, 1)
        self.combat_value_head = nn.Linear(hidden_dim, 1)

    @staticmethod
    def _masked_candidate_summary(candidate_hidden, candidate_mask):
        valid_candidates = (candidate_mask > 0.5).unsqueeze(-1)
        candidate_count = valid_candidates.sum(dim=1).clamp(min=1)
        masked_candidates = candidate_hidden * valid_candidates
        pooled_mean = masked_candidates.sum(dim=1) / candidate_count

        max_input = candidate_hidden.masked_fill(~valid_candidates, -1e9)
        pooled_max = max_input.max(dim=1).values
        has_candidates = (candidate_count.squeeze(-1) > 0).unsqueeze(-1)
        pooled_max = torch.where(has_candidates, pooled_max, torch.zeros_like(pooled_max))
        return pooled_mean, pooled_max

    def forward_binary(self, obs):
        hidden = self.binary_trunk(obs)
        return self.binary_policy_head(hidden), self.binary_value_head(hidden).squeeze(-1)

    def _candidate_parts(self, global_obs, candidate_obs, candidate_ids):
        global_hidden = self.combat_global_encoder(global_obs)
        candidate_emb = self.object_embedding(candidate_ids)
        candidate_hidden = self.combat_candidate_encoder(torch.cat((candidate_obs, candidate_emb), dim=-1))
        return global_hidden, candidate_hidden

    @staticmethod
    def _candidate_logits(global_hidden, candidate_hidden, head):
        global_expanded = global_hidden.unsqueeze(1).expand(-1, candidate_hidden.shape[1], -1)
        return head(torch.cat((global_expanded, candidate_hidden), dim=-1)).squeeze(-1)

    def forward_combat(self, global_obs, candidate_obs, candidate_ids, action_mask):
        global_hidden, candidate_hidden = self._candidate_parts(global_obs, candidate_obs, candidate_ids)
        candidate_logits = self._candidate_logits(global_hidden, candidate_hidden, self.combat_policy_head)
        candidate_mask = action_mask[:, :-1]
        pooled_mean, pooled_max = self._masked_candidate_summary(candidate_hidden, candidate_mask)
        resolve_logits = self.combat_resolve_head(torch.cat((global_hidden, pooled_mean, pooled_max), dim=-1))
        logits = torch.cat((candidate_logits, resolve_logits), dim=1)
        valid_mask = action_mask > 0.5
        logits = logits.masked_fill(~valid_mask, -1e9)
        return logits, self.combat_value_head(global_hidden).squeeze(-1)

    def forward_single_object(self, global_obs, candidate_obs, candidate_ids, action_mask):
        return self.forward_combat(global_obs, candidate_obs, candidate_ids, action_mask)

    def forward_multi_object(self, global_obs, candidate_obs, candidate_ids, action_mask):
        global_hidden, candidate_hidden = self._candidate_parts(global_obs, candidate_obs, candidate_ids)
        logits = self._candidate_logits(global_hidden, candidate_hidden, self.multi_policy_head)
        logits = logits.masked_fill(action_mask <= 0.5, 0.0)
        return logits, self.combat_value_head(global_hidden).squeeze(-1)

    def forward_order_objects(self, global_obs, candidate_obs, candidate_ids, action_mask):
        global_hidden, candidate_hidden = self._candidate_parts(global_obs, candidate_obs, candidate_ids)
        logits = self._candidate_logits(global_hidden, candidate_hidden, self.order_policy_head)
        logits = logits.masked_fill(action_mask <= 0.5, -1e9)
        return logits, self.combat_value_head(global_hidden).squeeze(-1)


class HybridNeuralPolicy:
    def __init__(
        self,
        model,
        encoder,
        *,
        managed_kinds,
        fallback=None,
        sample=True,
        record=True,
        device='cpu',
    ):
        self.model = model
        self.encoder = encoder
        self.managed_kinds = frozenset(managed_kinds)
        self.fallback = fallback or default_dungeon_policy()
        self.sample = sample
        self.record = record
        self.device = device
        self._records = {}
        self._action_counts = defaultdict(lambda: defaultdict(int))

    def decide(self, context):
        if context.actor is None or context.kind not in self.managed_kinds:
            return self.fallback.decide(context)

        encoded = self.encoder.encode(context)
        if encoded['mode'] == 'binary':
            action_value, action_record, value, log_prob = self._decide_binary(encoded)
        elif encoded['mode'] in ('combat_object', 'single_object'):
            action_value, action_record, value, log_prob = self._decide_single_object(context, encoded)
        elif encoded['mode'] == 'multi_object':
            action_value, action_record, value, log_prob = self._decide_multi_object(context, encoded)
        elif encoded['mode'] == 'order_objects':
            action_value, action_record, value, log_prob = self._decide_order_objects(context, encoded)
        else:
            raise ValueError(f"Unknown encoded action mode: {encoded['mode']}")

        counts = self._action_counts[context.kind.name]
        if encoded['mode'] == 'combat_object':
            counts['object' if action_value is not CombatObjectChoice.RESOLVE_NOW else 'resolve_now'] += 1
        elif encoded['mode'] == 'single_object':
            counts['object' if action_value is not None else 'none'] += 1
        elif encoded['mode'] == 'multi_object':
            counts[f'count_{len(action_value)}'] += 1
        elif encoded['mode'] == 'order_objects':
            counts['ordered'] += 1
        else:
            counts['true' if action_value else 'false'] += 1

        if self.record:
            record = {
                'mode': encoded['mode'],
                'action': action_record,
                'logprob': float(log_prob),
                'value': float(value),
                'kind': context.kind.name,
                'phase': context.phase,
            }
            if encoded['mode'] in ('combat_object', 'single_object', 'multi_object', 'order_objects'):
                record.update({
                    'global_obs': encoded['global_obs'],
                    'candidate_obs': encoded['candidate_obs'],
                    'candidate_ids': encoded['candidate_ids'],
                    'action_mask': encoded['action_mask'],
                })
                if encoded['mode'] == 'multi_object':
                    record['multi_action'] = action_record
                elif encoded['mode'] == 'order_objects':
                    record['action_sequence'] = action_record
            else:
                record['obs'] = encoded['obs']
            self._records.setdefault(id(context.actor), []).append(record)
        return action_value

    def _candidate_tensors(self, encoded):
        return (
            torch.from_numpy(encoded['global_obs']).unsqueeze(0).to(self.device),
            torch.from_numpy(encoded['candidate_obs']).unsqueeze(0).to(self.device),
            torch.from_numpy(encoded['candidate_ids']).unsqueeze(0).to(self.device),
            torch.from_numpy(encoded['action_mask']).unsqueeze(0).to(self.device),
        )

    def _decide_binary(self, encoded):
        with torch.no_grad():
            obs_tensor = torch.from_numpy(encoded['obs']).unsqueeze(0).to(self.device)
            logits, value = self.model.forward_binary(obs_tensor)
            dist = Categorical(logits=logits.squeeze(0))
            action_index = dist.sample() if self.sample else torch.argmax(logits.squeeze(0), dim=-1)
            log_prob = dist.log_prob(action_index)
        action_idx = int(action_index.item())
        return bool(action_idx), action_idx, float(value.item()), float(log_prob.item())

    def _decide_single_object(self, context, encoded):
        with torch.no_grad():
            tensors = self._candidate_tensors(encoded)
            if encoded['mode'] == 'combat_object':
                logits, value = self.model.forward_combat(*tensors)
            else:
                logits, value = self.model.forward_single_object(*tensors)
            dist = Categorical(logits=logits.squeeze(0))
            action_index = dist.sample() if self.sample else torch.argmax(logits.squeeze(0), dim=-1)
            log_prob = dist.log_prob(action_index)
        action_idx = int(action_index.item())
        if action_idx < encoded['option_count']:
            return context.options[action_idx], action_idx, float(value.item()), float(log_prob.item())
        if encoded['mode'] == 'combat_object':
            return CombatObjectChoice.RESOLVE_NOW, action_idx, float(value.item()), float(log_prob.item())
        return None, action_idx, float(value.item()), float(log_prob.item())

    def _decide_multi_object(self, context, encoded):
        with torch.no_grad():
            logits, value = self.model.forward_multi_object(*self._candidate_tensors(encoded))
            logits = logits.squeeze(0)
            action_mask = torch.from_numpy(encoded['action_mask']).to(self.device) > 0.5
            probs = torch.sigmoid(logits)
            if self.sample:
                selected = Bernoulli(probs=probs).sample().bool() & action_mask
            else:
                selected = (probs >= 0.5) & action_mask
            selected = self._enforce_multi_bounds(selected, logits, action_mask, encoded['min_count'], encoded['max_count'])
            targets = selected.float()
            log_probs = -F.binary_cross_entropy_with_logits(logits, targets, reduction='none')
            log_prob = (log_probs * action_mask.float()).sum()
        selection = selected.detach().cpu().numpy().astype(np.float32)
        values = tuple(context.options[index] for index in range(encoded['option_count']) if selection[index] > 0.5)
        return values, selection, float(value.item()), float(log_prob.item())

    @staticmethod
    def _enforce_multi_bounds(selected, logits, action_mask, min_count, max_count):
        selected = selected.clone()
        current_count = int(selected.sum().item())
        if current_count > max_count:
            chosen = torch.where(selected)[0]
            keep = chosen[torch.topk(logits[chosen], k=max_count).indices] if max_count else torch.empty(0, dtype=torch.long, device=logits.device)
            selected[:] = False
            selected[keep] = True
        current_count = int(selected.sum().item())
        if current_count < min_count:
            candidates = action_mask & ~selected
            needed = min_count - current_count
            if needed > 0 and candidates.any():
                candidate_indexes = torch.where(candidates)[0]
                add = candidate_indexes[torch.topk(logits[candidate_indexes], k=min(needed, len(candidate_indexes))).indices]
                selected[add] = True
        return selected

    def _decide_order_objects(self, context, encoded):
        with torch.no_grad():
            logits, value = self.model.forward_order_objects(*self._candidate_tensors(encoded))
            logits = logits.squeeze(0)
            remaining = torch.from_numpy(encoded['action_mask']).to(self.device) > 0.5
            chosen_indexes = []
            log_probs = []
            while remaining.any():
                masked_logits = logits.masked_fill(~remaining, -1e9)
                dist = Categorical(logits=masked_logits)
                action_index = dist.sample() if self.sample else torch.argmax(masked_logits, dim=-1)
                log_probs.append(dist.log_prob(action_index))
                idx = int(action_index.item())
                chosen_indexes.append(idx)
                remaining[idx] = False
            log_prob = torch.stack(log_probs).sum() if log_probs else torch.tensor(0.0, device=self.device)
        ordered = [context.options[index] for index in chosen_indexes]
        ordered.extend(context.options[index] for index in range(encoded['option_count'], len(context.options)))
        sequence = np.full(self.encoder.max_candidates, -1, dtype=np.int64)
        sequence[:len(chosen_indexes)] = np.asarray(chosen_indexes, dtype=np.int64)
        return tuple(ordered), sequence, float(value.item()), float(log_prob.item())

    def clear_records(self):
        self._records.clear()

    def clear_action_counts(self):
        self._action_counts.clear()

    def take_records(self, actor):
        return self._records.pop(id(actor), [])

    def export_action_counts(self):
        return {
            kind: dict(counts)
            for kind, counts in self._action_counts.items()
        }


def _score_now(player):
    if hasattr(player, '_score_rapide'):
        return player._score_rapide()
    return len(player.pile_monstres_vaincus)


def _build_match(seed):
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)
    torch.manual_seed(seed)

    objets_simu = list(objets_disponibles)
    for objet in objets_simu:
        objet.repare()

    nb_joueurs = random.choice([3, 4])
    persos = random.sample(persos_disponibles, nb_joueurs)
    joueurs = []
    for index, nom in enumerate(PLAYER_NAMES[:nb_joueurs]):
        objets_joueur = random.sample(objets_simu, 6)
        for objet in objets_joueur:
            objets_simu.remove(objet)
        joueurs.append(Joueur(nom, persos[index], objets_joueur))
    return joueurs, objets_simu


def _ranking(players):
    return sorted(
        players,
        key=lambda joueur: (
            float(getattr(joueur, 'compte_au_score', False)),
            joueur.score_final,
            float(joueur.vivant),
            float(joueur.dans_le_dj),
            joueur.pv_total,
        ),
        reverse=True,
    )


def _placement_rewards(players):
    ranked = _ranking(players)
    schedule = REWARD_SCHEDULES[len(ranked)]
    return {id(player): schedule[index] for index, player in enumerate(ranked)}


def _training_base_rewards(players, reward_config):
    if reward_config.placement_mode == 'ranked':
        return _placement_rewards(players)
    if reward_config.placement_mode == 'winner_take_all':
        ranked = _ranking(players)
        winner = ranked[0]
        return {id(player): (1.0 if player is winner else 0.0) for player in ranked}
    raise ValueError(f"Unknown reward placement_mode: {reward_config.placement_mode}")


def _player_rank(players, target):
    for index, player in enumerate(_ranking(players), start=1):
        if player is target:
            return index
    return len(players)


def _dense_bonus(player, reward_config, rank):
    if not reward_config.enabled:
        return 0.0

    bonus = (
        reward_config.score_coef * float(player.score_final)
        + reward_config.monster_coef * float(len(player.pile_monstres_vaincus))
    )
    if not player.vivant:
        bonus -= reward_config.death_penalty
    player_count = len(player.partie_joueurs or [player])
    if player.fuite_reussie and rank > max(1, player_count // 2):
        bonus -= reward_config.bad_flee_penalty
    return bonus


def _player_reward(player, reward_config, base_rewards):
    rank = _player_rank(player.partie_joueurs or [player], player)
    return base_rewards[id(player)] + _dense_bonus(player, reward_config, rank)


def _cpu_state_dict(model):
    return {key: value.detach().cpu() for key, value in model.state_dict().items()}


def _cpu_optimizer_state_dict(optimizer):
    state_dict = optimizer.state_dict()
    cpu_state = {}
    for key, value in state_dict['state'].items():
        cpu_state[key] = {
            inner_key: (inner_value.detach().cpu() if torch.is_tensor(inner_value) else inner_value)
            for inner_key, inner_value in value.items()
        }
    return {
        'state': cpu_state,
        'param_groups': state_dict['param_groups'],
    }


def _load_compatible_state_dict(model, state_dict):
    current_state = model.state_dict()
    compatible = {}
    for key, value in state_dict.items():
        if key not in current_state:
            continue
        current_value = current_state[key]
        if current_value.shape == value.shape:
            compatible[key] = value
        elif key == 'combat_candidate_encoder.0.weight' and value.ndim == 2 and current_value.ndim == 2:
            merged = current_value.clone()
            embed_cols = model.object_embedding.embedding_dim
            old_feature_cols = value.shape[1] - embed_cols
            current_feature_cols = current_value.shape[1] - embed_cols
            if (
                value.shape[0] == current_value.shape[0]
                and old_feature_cols > 0
                and current_feature_cols >= old_feature_cols
            ):
                legacy_feature_cols = 14 + len(ITEM_GAMEPLAY_TAGS)
                current_base_cols = 12
                current_tag_end = current_base_cols + len(ITEM_GAMEPLAY_TAGS)
                if old_feature_cols == legacy_feature_cols and current_feature_cols >= current_tag_end:
                    # Legacy combat candidates had: base13, tags, heuristic_worthit.
                    # Current managed-object candidates removed priorite/worthit:
                    # base12, tags, derived_features.
                    merged[:, :current_feature_cols] = 0.0
                    merged[:, :4] = value[:, :4]
                    merged[:, 4:current_base_cols] = value[:, 5:13]
                    merged[:, current_base_cols:current_tag_end] = value[:, 13:13 + len(ITEM_GAMEPLAY_TAGS)]
                else:
                    merged[:, :current_feature_cols] = 0.0
                    merged[:, :old_feature_cols] = value[:, :old_feature_cols]
                merged[:, -embed_cols:] = value[:, -embed_cols:]
                compatible[key] = merged
        elif value.ndim == current_value.ndim == 2 and value.shape[0] == current_value.shape[0]:
            merged = current_value.clone()
            cols = min(value.shape[1], current_value.shape[1])
            merged[:, :cols] = value[:, :cols]
            compatible[key] = merged
        elif value.ndim == current_value.ndim == 1:
            merged = current_value.clone()
            rows = min(value.shape[0], current_value.shape[0])
            merged[:rows] = value[:rows]
            compatible[key] = merged
    current_state.update(compatible)
    model.load_state_dict(current_state)


def _build_model(hidden_dim, *, device):
    encoder = ObservationEncoder()
    model = PolicyValueNet(encoder, hidden_dim=hidden_dim).to(device)
    model.eval()
    return model, encoder


def _make_model_and_policy(state_dict, managed_kinds, *, sample, record, device='cpu'):
    encoder = ObservationEncoder()
    hidden_dim = int(state_dict['binary_trunk.0.bias'].shape[0])
    model = PolicyValueNet(encoder, hidden_dim=hidden_dim).to(device)
    try:
        model.load_state_dict(state_dict)
    except RuntimeError:
        _load_compatible_state_dict(model, state_dict)
    model.eval()
    policy = HybridNeuralPolicy(
        model,
        encoder,
        managed_kinds=managed_kinds,
        sample=sample,
        record=record,
        device=device,
    )
    return model, policy


def _seed_bank(base_seed, count):
    rng = random.Random(base_seed)
    return [rng.randrange(1, 2**31 - 1) for _ in range(count)]


def build_eval_banks(random_games=1000, default_games=2000):
    return {
        'random': _seed_bank(EVAL_RANDOM_BASE_SEED, random_games),
        'default': _seed_bank(EVAL_DEFAULT_BASE_SEED, default_games),
    }


def _episode_specs(total_episodes, curriculum, *, seed_start):
    counts = curriculum.normalized_counts(total_episodes)
    labels = (
        [SELF_PLAY] * counts[SELF_PLAY]
        + [VERSUS_DEFAULT] * counts[VERSUS_DEFAULT]
        + [VERSUS_RANDOM] * counts[VERSUS_RANDOM]
    )
    rng = random.Random(seed_start ^ 0x5F3759DF)
    rng.shuffle(labels)
    return [(seed_start + offset, labels[offset], offset) for offset in range(total_episodes)]


def _split_episode_specs(specs, num_workers, state_dict, managed_kinds, reward_config):
    worker_count = max(1, min(num_workers, len(specs)))
    tasks = [[] for _ in range(worker_count)]
    for index, spec in enumerate(specs):
        tasks[index % worker_count].append(spec)
    return [
        (chunk, state_dict, tuple(kind.name for kind in managed_kinds), reward_config)
        for chunk in tasks
        if chunk
    ]


def _split_eval_specs(seeds, baseline_name, num_workers, state_dict, managed_kinds):
    worker_count = max(1, min(num_workers, len(seeds)))
    tasks = [[] for _ in range(worker_count)]
    for index, seed in enumerate(seeds):
        tasks[index % worker_count].append((seed, index))
    return [
        (chunk, baseline_name, state_dict, tuple(kind.name for kind in managed_kinds))
        for chunk in tasks
        if chunk
    ]


def _baseline_policy(name):
    if name == 'default':
        return default_dungeon_policy()
    if name == 'random':
        return random_dungeon_policy()
    raise ValueError(f"Unknown baseline: {name}")


def _merge_action_counts(results):
    merged = defaultdict(lambda: defaultdict(int))
    for result in results:
        for kind, counts in result.items():
            for label, count in counts.items():
                merged[kind][label] += count
    return {kind: dict(counts) for kind, counts in merged.items()}


def _collect_rollout_worker(args):
    episode_specs, state_dict, managed_kind_names, reward_config = args
    managed_kinds = tuple(DecisionKind[name] for name in managed_kind_names)
    _, policy = _make_model_and_policy(state_dict, managed_kinds, sample=True, record=True)

    steps = []
    total_reward = 0.0
    total_decisions = 0
    policy.clear_action_counts()
    for seed, scenario, ordinal in episode_specs:
        joueurs, objets_simu = _build_match(seed)
        seat_index = seed % len(joueurs)
        if scenario == SELF_PLAY:
            policies = [policy] * len(joueurs)
        else:
            baseline = _baseline_policy('default' if scenario == VERSUS_DEFAULT else 'random')
            policies = [baseline] * len(joueurs)
            policies[seat_index] = policy

        policy.clear_records()
        ordonnanceur(joueurs, DonjonDeck(), objets_simu, False, policy=policies)
        rewards = _training_base_rewards(joueurs, reward_config)
        for joueur in joueurs:
            player_reward = _player_reward(joueur, reward_config, rewards)
            player_steps = policy.take_records(joueur)
            total_reward += player_reward
            total_decisions += len(player_steps)
            for step in player_steps:
                step['reward'] = player_reward
                step['scenario'] = scenario
                step['episode_seed'] = seed
                step['episode_ordinal'] = ordinal
                steps.append(step)
    return {
        'steps': steps,
        'episodes': len(episode_specs),
        'reward_sum': total_reward,
        'decisions': total_decisions,
        'action_counts': policy.export_action_counts(),
    }


def _evaluate_worker(args):
    seed_specs, baseline_name, state_dict, managed_kind_names = args
    managed_kinds = tuple(DecisionKind[name] for name in managed_kind_names)
    _, agent_policy = _make_model_and_policy(state_dict, managed_kinds, sample=False, record=False)
    baseline = _baseline_policy(baseline_name)
    agent_policy.clear_action_counts()

    wins = 0
    reward_sum = 0.0
    rank_sum = 0.0
    chance_sum = 0.0
    chance_rank_sum = 0.0
    for seed, eval_index in seed_specs:
        joueurs, objets_simu = _build_match(seed)
        seat_index = eval_index % len(joueurs)
        policies = [baseline] * len(joueurs)
        policies[seat_index] = agent_policy
        winner, joueurs_finaux = ordonnanceur(joueurs, DonjonDeck(), objets_simu, False, policy=policies)
        target = joueurs_finaux[seat_index]
        wins += int(target is winner)
        reward_sum += _placement_rewards(joueurs_finaux)[id(target)]
        rank_sum += _player_rank(joueurs_finaux, target)
        chance_sum += 1.0 / len(joueurs_finaux)
        chance_rank_sum += (len(joueurs_finaux) + 1.0) / 2.0
    return {
        'games': len(seed_specs),
        'wins': wins,
        'reward_sum': reward_sum,
        'rank_sum': rank_sum,
        'chance_sum': chance_sum,
        'chance_rank_sum': chance_rank_sum,
        'action_counts': agent_policy.export_action_counts(),
    }


def _run_parallel(worker, tasks, num_workers):
    if num_workers <= 1 or len(tasks) == 1:
        return [worker(task) for task in tasks]
    ctx = mp.get_context('spawn')
    with ctx.Pool(processes=num_workers) as pool:
        return pool.map(worker, tasks)


def collect_rollouts(
    model,
    managed_kinds,
    reward_config,
    curriculum,
    total_episodes,
    seed_start,
    *,
    num_workers=1,
):
    state_dict = _cpu_state_dict(model)
    specs = _episode_specs(total_episodes, curriculum, seed_start=seed_start)
    tasks = _split_episode_specs(specs, num_workers, state_dict, managed_kinds, reward_config)
    results = _run_parallel(_collect_rollout_worker, tasks, num_workers)

    steps = []
    episodes = 0
    reward_sum = 0.0
    decisions = 0
    for result in results:
        steps.extend(result['steps'])
        episodes += result['episodes']
        reward_sum += result['reward_sum']
        decisions += result['decisions']
    return {
        'steps': steps,
        'episodes': episodes,
        'avg_reward_per_player': reward_sum / max(1, episodes * 4),
        'decisions': decisions,
        'action_counts': _merge_action_counts(result['action_counts'] for result in results),
    }


def evaluate_against_baseline(
    model,
    managed_kinds,
    baseline_name,
    seed_bank,
    *,
    num_workers=1,
):
    state_dict = _cpu_state_dict(model)
    tasks = _split_eval_specs(seed_bank, baseline_name, num_workers, state_dict, managed_kinds)
    results = _run_parallel(_evaluate_worker, tasks, num_workers)

    games = 0
    wins = 0
    reward_sum = 0.0
    rank_sum = 0.0
    chance_sum = 0.0
    chance_rank_sum = 0.0
    for result in results:
        games += result['games']
        wins += result['wins']
        reward_sum += result['reward_sum']
        rank_sum += result['rank_sum']
        chance_sum += result['chance_sum']
        chance_rank_sum += result['chance_rank_sum']
    return {
        'games': games,
        'winrate': wins / max(1, games),
        'avg_reward': reward_sum / max(1, games),
        'avg_rank': rank_sum / max(1, games),
        'chance_winrate': chance_sum / max(1, games),
        'chance_avg_rank': chance_rank_sum / max(1, games),
        'action_counts': _merge_action_counts(result['action_counts'] for result in results),
    }


def _report_worker(args):
    seed_specs, policy_name, checkpoint_state_dict, managed_kind_names, policy_label = args
    if policy_name == 'PPO':
        managed_kinds = tuple(DecisionKind[name] for name in managed_kind_names)
        _, target_policy = _make_model_and_policy(
            checkpoint_state_dict,
            managed_kinds,
            sample=False,
            record=False,
        )
    elif policy_name == 'DefaultDungeonPolicy':
        target_policy = default_dungeon_policy()
    elif policy_name == 'RandomPolicy':
        target_policy = random_dungeon_policy()
    else:
        raise ValueError(f"Unknown report policy: {policy_name}")

    baseline = default_dungeon_policy()
    stats = {
        'episodes': 0,
        'wins': 0,
        'deaths': 0,
        'flees': 0,
        'clears': 0,
        'score_sum': 0.0,
        'policy_label': policy_label,
    }
    for seed, eval_index in seed_specs:
        joueurs, objets_simu = _build_match(seed)
        seat_index = eval_index % len(joueurs)
        policies = [baseline] * len(joueurs)
        policies[seat_index] = target_policy
        winner, joueurs_finaux = ordonnanceur(joueurs, DonjonDeck(), objets_simu, False, policy=policies)
        target = joueurs_finaux[seat_index]
        stats['episodes'] += 1
        stats['wins'] += int(target is winner)
        stats['deaths'] += int(not target.vivant)
        stats['flees'] += int(target.fuite_reussie)
        stats['clears'] += int(target.dans_le_dj)
        stats['score_sum'] += float(target.score_final)
    return stats


def _merge_report_stats(results):
    merged = {
        'episodes': 0,
        'wins': 0,
        'deaths': 0,
        'flees': 0,
        'clears': 0,
        'score_sum': 0.0,
        'policy_label': None,
    }
    for result in results:
        for key in merged:
            if key == 'policy_label':
                merged[key] = result[key]
                continue
            merged[key] += result[key]
    return merged


def _parse_managed_kind_names(value):
    if value is None:
        return None
    names = tuple(part.strip() for part in value.split(',') if part.strip())
    for name in names:
        if name not in DecisionKind.__members__:
            raise ValueError(f"Unknown DecisionKind for --ppo-managed-kinds: {name}")
    return names


def report_policy_stats(*, checkpoint_path=None, episodes=1000, num_workers=8, ppo_managed_kinds=None):
    _assert_multiprocessing_launch_safe(num_workers)
    seeds = _seed_bank(EVAL_DEFAULT_BASE_SEED, episodes)
    worker_count = max(1, min(num_workers, len(seeds)))
    seed_chunks = [[] for _ in range(worker_count)]
    for index, seed in enumerate(seeds):
        seed_chunks[index % worker_count].append((seed, index))

    policies = [('DefaultDungeonPolicy', 'DefaultDungeonPolicy'), ('RandomPolicy', 'RandomPolicy')]
    checkpoint_state_dict = None
    managed_kind_names = ()
    if checkpoint_path:
        checkpoint = _load_checkpoint(checkpoint_path)
        stage_index = checkpoint['stage_index']
        managed_kind_names = ppo_managed_kinds or progressive_stages()[stage_index].managed_kinds
        checkpoint_state_dict = checkpoint['model_state_dict']
        if ppo_managed_kinds:
            managed_label = '+'.join(managed_kind_names)
            policies.append(('PPO', f'PPO[{managed_label}]'))
        else:
            policies.append(('PPO', 'PPO'))

    rows = []
    for policy_name, policy_label in policies:
        tasks = [
            (chunk, policy_name, checkpoint_state_dict, managed_kind_names, policy_label)
            for chunk in seed_chunks
            if chunk
        ]
        stats = _merge_report_stats(_run_parallel(_report_worker, tasks, num_workers))
        total = max(1, stats['episodes'])
        rows.append({
            'Policy': stats['policy_label'] or policy_label,
            'Episodes': stats['episodes'],
            'Winrate': stats['wins'] / total,
            'Death%': stats['deaths'] / total,
            'Flee%': stats['flees'] / total,
            'Clear%': stats['clears'] / total,
            'AvgScore': stats['score_sum'] / total,
        })
    return rows


def format_policy_report(rows):
    lines = [
        "| Policy | Episodes | Winrate | Death% | Flee% | Clear% | AvgScore |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['Policy']} | {row['Episodes']} | "
            f"{row['Winrate']:.3f} | {100.0 * row['Death%']:.1f}% | "
            f"{100.0 * row['Flee%']:.1f}% | {100.0 * row['Clear%']:.1f}% | "
            f"{row['AvgScore']:.2f} |"
        )
    return "\n".join(lines)


def _order_logprobs_and_entropy(logits, action_mask, sequences):
    logprobs = []
    entropies = []
    for row_index in range(logits.shape[0]):
        remaining = action_mask[row_index] > 0.5
        row_logprob = logits[row_index].new_tensor(0.0)
        row_entropy = logits[row_index].new_tensor(0.0)
        for action_index in sequences[row_index]:
            if action_index.item() < 0:
                break
            masked_logits = logits[row_index].masked_fill(~remaining, -1e9)
            dist = Categorical(logits=masked_logits)
            row_logprob = row_logprob + dist.log_prob(action_index)
            row_entropy = row_entropy + dist.entropy()
            remaining[action_index] = False
        logprobs.append(row_logprob)
        entropies.append(row_entropy)
    return torch.stack(logprobs), torch.stack(entropies).mean()


def ppo_update(model, optimizer, steps, config, *, device='cpu'):
    if not steps:
        return {
            'policy_loss': 0.0,
            'value_loss': 0.0,
            'entropy': 0.0,
        }

    old_logprobs = torch.tensor([step['logprob'] for step in steps], dtype=torch.float32, device=device)
    returns = torch.tensor([step['reward'] for step in steps], dtype=torch.float32, device=device)
    old_values = torch.tensor([step['value'] for step in steps], dtype=torch.float32, device=device)
    advantages = returns - old_values
    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

    grouped_indexes = defaultdict(list)
    for index, step in enumerate(steps):
        grouped_indexes[step['mode']].append(index)
    policy_losses = []
    value_losses = []
    entropies = []

    model.train()
    for _ in range(config.ppo_epochs):
        for mode, indexes in grouped_indexes.items():
            batch_order = np.asarray(indexes, dtype=np.int64)
            np.random.shuffle(batch_order)
            for start in range(0, len(batch_order), config.minibatch_size):
                batch_indexes = batch_order[start:start + config.minibatch_size]
                batch_old_logprobs = old_logprobs[batch_indexes]
                batch_returns = returns[batch_indexes]
                batch_advantages = advantages[batch_indexes]

                if mode in ('combat_object', 'single_object'):
                    batch_action_tensor = torch.tensor([steps[i]['action'] for i in batch_indexes], dtype=torch.long, device=device)
                    global_obs = torch.from_numpy(np.stack([steps[i]['global_obs'] for i in batch_indexes])).to(device)
                    candidate_obs = torch.from_numpy(np.stack([steps[i]['candidate_obs'] for i in batch_indexes])).to(device)
                    candidate_ids = torch.from_numpy(np.stack([steps[i]['candidate_ids'] for i in batch_indexes])).to(device)
                    action_mask = torch.from_numpy(np.stack([steps[i]['action_mask'] for i in batch_indexes])).to(device)
                    if mode == 'combat_object':
                        logits, values = model.forward_combat(global_obs, candidate_obs, candidate_ids, action_mask)
                    else:
                        logits, values = model.forward_single_object(global_obs, candidate_obs, candidate_ids, action_mask)
                    dist = Categorical(logits=logits)
                    new_logprobs = dist.log_prob(batch_action_tensor)
                    entropy = dist.entropy().mean()
                elif mode == 'multi_object':
                    global_obs = torch.from_numpy(np.stack([steps[i]['global_obs'] for i in batch_indexes])).to(device)
                    candidate_obs = torch.from_numpy(np.stack([steps[i]['candidate_obs'] for i in batch_indexes])).to(device)
                    candidate_ids = torch.from_numpy(np.stack([steps[i]['candidate_ids'] for i in batch_indexes])).to(device)
                    action_mask = torch.from_numpy(np.stack([steps[i]['action_mask'] for i in batch_indexes])).to(device)
                    targets = torch.from_numpy(np.stack([steps[i]['multi_action'] for i in batch_indexes])).to(device)
                    logits, values = model.forward_multi_object(global_obs, candidate_obs, candidate_ids, action_mask)
                    log_probs = -F.binary_cross_entropy_with_logits(logits, targets, reduction='none')
                    new_logprobs = (log_probs * action_mask).sum(dim=1)
                    entropy = (Bernoulli(logits=logits).entropy() * action_mask).sum(dim=1).mean()
                elif mode == 'order_objects':
                    global_obs = torch.from_numpy(np.stack([steps[i]['global_obs'] for i in batch_indexes])).to(device)
                    candidate_obs = torch.from_numpy(np.stack([steps[i]['candidate_obs'] for i in batch_indexes])).to(device)
                    candidate_ids = torch.from_numpy(np.stack([steps[i]['candidate_ids'] for i in batch_indexes])).to(device)
                    action_mask = torch.from_numpy(np.stack([steps[i]['action_mask'] for i in batch_indexes])).to(device)
                    sequences = torch.from_numpy(np.stack([steps[i]['action_sequence'] for i in batch_indexes])).long().to(device)
                    logits, values = model.forward_order_objects(global_obs, candidate_obs, candidate_ids, action_mask)
                    new_logprobs, entropy = _order_logprobs_and_entropy(logits, action_mask, sequences)
                else:
                    batch_action_tensor = torch.tensor([steps[i]['action'] for i in batch_indexes], dtype=torch.long, device=device)
                    obs = torch.from_numpy(np.stack([steps[i]['obs'] for i in batch_indexes])).to(device)
                    logits, values = model.forward_binary(obs)
                    dist = Categorical(logits=logits)
                    new_logprobs = dist.log_prob(batch_action_tensor)
                    entropy = dist.entropy().mean()

                ratio = torch.exp(new_logprobs - batch_old_logprobs)
                unclipped = ratio * batch_advantages
                clipped = torch.clamp(ratio, 1.0 - config.clip_eps, 1.0 + config.clip_eps) * batch_advantages

                policy_loss = -torch.min(unclipped, clipped).mean()
                value_loss = F.mse_loss(values, batch_returns)
                loss = policy_loss + (config.value_coef * value_loss) - (config.entropy_coef * entropy)

                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()

                policy_losses.append(float(policy_loss.item()))
                value_losses.append(float(value_loss.item()))
                entropies.append(float(entropy.item()))

    model.eval()
    return {
        'policy_loss': sum(policy_losses) / max(1, len(policy_losses)),
        'value_loss': sum(value_losses) / max(1, len(value_losses)),
        'entropy': sum(entropies) / max(1, len(entropies)),
    }


def initial_curriculum():
    return CurriculumMix(self_play=0.50, versus_default=0.30, versus_random=0.20)


def post_random_curriculum():
    return CurriculumMix(self_play=0.20, versus_default=0.60, versus_random=0.20)


def progressive_stages():
    flee_and_combat = (
        DecisionKind.SHOULD_FLEE.name,
        DecisionKind.CHOOSE_COMBAT_OBJECT.name,
        DecisionKind.USE_OBJECT_IN_COMBAT.name,
    )
    plus_single_objects = flee_and_combat + (
        DecisionKind.CHOOSE_OBJECT.name,
        DecisionKind.CHOOSE_OBJECT_TO_SACRIFICE.name,
        DecisionKind.CHOOSE_OBJECT_TO_REPAIR.name,
        DecisionKind.USE_ACTIVE_OBJECT.name,
    )
    plus_multi_objects = plus_single_objects + (DecisionKind.CHOOSE_OBJECTS.name,)
    all_object_hero = tuple(kind.name for kind in INITIAL_MANAGED_KINDS)

    return [
        StageConfig(
            name='flee_combat_objects',
            max_iterations=20,
            hidden_dim=128,
            managed_kinds=flee_and_combat,
            ppo=PPOConfig(lr=3e-4, entropy_coef=0.01, minibatch_size=4096),
            reward=RewardConfig(enabled=False),
            restart_from_scratch=True,
        ),
        StageConfig(
            name='single_object_cluster',
            max_iterations=20,
            hidden_dim=256,
            managed_kinds=plus_single_objects,
            ppo=PPOConfig(lr=1e-4, entropy_coef=0.02, minibatch_size=4096),
            reward=RewardConfig(enabled=False),
            restart_from_scratch=True,
        ),
        StageConfig(
            name='multi_object_cluster',
            max_iterations=20,
            hidden_dim=256,
            managed_kinds=plus_multi_objects,
            ppo=PPOConfig(lr=1e-4, entropy_coef=0.02, minibatch_size=4096),
            reward=RewardConfig(enabled=True),
        ),
        StageConfig(
            name='order_objects',
            max_iterations=20,
            hidden_dim=256,
            managed_kinds=all_object_hero,
            ppo=PPOConfig(lr=1e-4, entropy_coef=0.02, minibatch_size=4096),
            reward=RewardConfig(enabled=True),
        ),
        StageConfig(
            name='all_object_hero',
            max_iterations=20,
            hidden_dim=256,
            managed_kinds=all_object_hero,
            ppo=PPOConfig(lr=1e-4, entropy_coef=0.02, minibatch_size=4096),
            reward=RewardConfig(enabled=True),
        ),
    ]


def _meets_random_gate(metrics):
    return (
        metrics['winrate'] >= metrics['chance_winrate'] + RANDOM_GATE_MARGIN
        and metrics['avg_rank'] < metrics['chance_avg_rank']
    )


def _meets_default_gate(metrics):
    return (
        metrics['winrate'] >= metrics['chance_winrate'] + DEFAULT_GATE_MARGIN
        and metrics['avg_rank'] < metrics['chance_avg_rank']
    )


def _action_frequency_summary(action_counts):
    summary = {}
    for kind, counts in sorted(action_counts.items()):
        total = sum(counts.values())
        kind_summary = {'total': total}
        for label, count in sorted(counts.items()):
            kind_summary[label] = count
            kind_summary[f'{label}_rate'] = (count / total) if total else 0.0
        summary[kind] = kind_summary
    return summary


def _serialize_for_json(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _serialize_for_json(subvalue) for key, subvalue in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_for_json(item) for item in value]
    return value


def _append_metrics_csv(csv_path, row):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(row.keys())
    exists = csv_path.exists()
    with csv_path.open('a', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _append_metrics_jsonl(jsonl_path, payload):
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(_serialize_for_json(payload), ensure_ascii=False) + "\n")


def _checkpoint_payload(
    *,
    model,
    optimizer,
    history,
    stage_index,
    stage_iteration,
    total_iteration,
    random_gate_iteration,
    default_gate_iteration,
    default_gate_streak,
    run_config,
):
    return {
        'model_state_dict': _cpu_state_dict(model),
        'optimizer_state_dict': _cpu_optimizer_state_dict(optimizer),
        'history': history,
        'stage_index': stage_index,
        'stage_iteration': stage_iteration,
        'total_iteration': total_iteration,
        'random_gate_iteration': random_gate_iteration,
        'default_gate_iteration': default_gate_iteration,
        'default_gate_streak': default_gate_streak,
        'run_config': _serialize_for_json(run_config),
        'observation_spec': ObservationEncoder().observation_spec(),
    }


def _save_checkpoint(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + '.tmp')
    torch.save(payload, temp_path)
    os.replace(temp_path, path)


def _load_checkpoint(path):
    return torch.load(path, map_location='cpu')


def benchmark_rollout_workers(
    *,
    episodes=128,
    worker_options=(4, 8),
    hidden_dim=128,
    managed_kinds=INITIAL_MANAGED_KINDS,
    reward_config=None,
    curriculum=None,
):
    _assert_multiprocessing_launch_safe(max(worker_options))
    reward_config = reward_config or RewardConfig(enabled=False)
    curriculum = curriculum or initial_curriculum()
    results = []
    for workers in worker_options:
        model, _ = _build_model(hidden_dim, device='cpu')
        start = time.perf_counter()
        rollout = collect_rollouts(
            model,
            managed_kinds,
            reward_config,
            curriculum,
            episodes,
            seed_start=777000,
            num_workers=workers,
        )
        elapsed = time.perf_counter() - start
        results.append({
            'workers': workers,
            'episodes': episodes,
            'decisions': rollout['decisions'],
            'seconds': elapsed,
            'episodes_per_second': episodes / elapsed if elapsed else 0.0,
        })
    return results


def train_progressive(
    *,
    run_dir='artifacts/rl',
    seed=12345,
    num_workers=8,
    episodes_per_batch=2048,
    eval_every=5,
    random_eval_games=1000,
    default_eval_games=2000,
    device=None,
    resume_path=None,
    warmstart_path=None,
    stages=None,
    curriculum_override=None,
):
    _assert_multiprocessing_launch_safe(num_workers)
    device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)
    checkpoints_dir = run_path / 'checkpoints'
    metrics_csv = run_path / 'metrics.csv'
    metrics_jsonl = run_path / 'metrics.jsonl'
    eval_banks = build_eval_banks(random_games=random_eval_games, default_games=default_eval_games)
    stages = stages or progressive_stages()

    history = []
    total_iteration = 0
    stage_index_start = 0
    stage_iteration_start = 0
    random_gate_iteration = None
    default_gate_iteration = None
    default_gate_streak = 0
    model = None
    optimizer = None
    warmstart_state_dict = None

    if resume_path:
        checkpoint = _load_checkpoint(resume_path)
        stage_index_start = checkpoint['stage_index']
        stage_iteration_start = checkpoint['stage_iteration']
        total_iteration = checkpoint['total_iteration']
        random_gate_iteration = checkpoint['random_gate_iteration']
        default_gate_iteration = checkpoint['default_gate_iteration']
        default_gate_streak = checkpoint['default_gate_streak']
        history = checkpoint['history']
        current_stage = stages[stage_index_start]
        model, _ = _build_model(current_stage.hidden_dim, device=device)
        model.load_state_dict(checkpoint['model_state_dict'])
        optimizer = torch.optim.Adam(model.parameters(), lr=current_stage.ppo.lr)
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        model.to(device)
        model.eval()
    elif warmstart_path:
        warmstart_state_dict = _load_checkpoint(warmstart_path)['model_state_dict']

    run_config = {
        'run_dir': str(run_path),
        'seed': seed,
        'num_workers': num_workers,
        'episodes_per_batch': episodes_per_batch,
        'eval_every': eval_every,
        'random_eval_games': random_eval_games,
        'default_eval_games': default_eval_games,
        'device': device,
        'warmstart_path': str(warmstart_path) if warmstart_path else None,
        'curriculum_override': asdict(curriculum_override) if curriculum_override is not None else None,
        'stages': [asdict(stage) for stage in stages],
    }

    best_score = float('-inf')

    for stage_index, stage in enumerate(stages):
        if stage_index < stage_index_start:
            continue
        if random_gate_iteration is not None and stage.restart_from_scratch and stage.name == 'loop1_restart_binary':
            continue

        managed_kinds = tuple(DecisionKind[name] for name in stage.managed_kinds)
        should_restart = (
            model is None
            or optimizer is None
            or (stage_index > stage_index_start and stage.restart_from_scratch)
        )
        if should_restart:
            model, _ = _build_model(stage.hidden_dim, device=device)
            if warmstart_state_dict is not None:
                _load_compatible_state_dict(model, warmstart_state_dict)
                model.to(device)
                warmstart_state_dict = None
            optimizer = torch.optim.Adam(model.parameters(), lr=stage.ppo.lr)
            stage_iteration_start = 0
        else:
            for param_group in optimizer.param_groups:
                param_group['lr'] = stage.ppo.lr

        stage_iteration = stage_iteration_start if stage_index == stage_index_start else 0
        while stage_iteration < stage.max_iterations:
            total_iteration += 1
            stage_iteration += 1
            curriculum = (
                curriculum_override
                if curriculum_override is not None
                else post_random_curriculum() if random_gate_iteration is not None else initial_curriculum()
            )
            rollout_seed = seed + ((total_iteration - 1) * episodes_per_batch)
            rollouts = collect_rollouts(
                model,
                managed_kinds,
                stage.reward,
                curriculum,
                episodes_per_batch,
                rollout_seed,
                num_workers=num_workers,
            )
            update_stats = ppo_update(model, optimizer, rollouts['steps'], stage.ppo, device=device)

            if total_iteration % eval_every == 0 or stage_iteration == stage.max_iterations:
                random_eval = evaluate_against_baseline(
                    model,
                    managed_kinds,
                    'random',
                    eval_banks['random'],
                    num_workers=num_workers,
                )
                default_eval = evaluate_against_baseline(
                    model,
                    managed_kinds,
                    'default',
                    eval_banks['default'],
                    num_workers=num_workers,
                )

                if random_gate_iteration is None and _meets_random_gate(random_eval):
                    random_gate_iteration = total_iteration

                if random_gate_iteration is not None and _meets_default_gate(default_eval):
                    default_gate_streak += 1
                    if default_gate_streak >= DEFAULT_GATE_CONSECUTIVE:
                        default_gate_iteration = total_iteration
                else:
                    default_gate_streak = 0

                eval_metrics = {
                    'iteration': total_iteration,
                    'stage_name': stage.name,
                    'stage_iteration': stage_iteration,
                    'managed_kinds': list(stage.managed_kinds),
                    'episodes': rollouts['episodes'],
                    'decisions': rollouts['decisions'],
                    'policy_loss': update_stats['policy_loss'],
                    'value_loss': update_stats['value_loss'],
                    'entropy': update_stats['entropy'],
                    'curriculum': _serialize_for_json(asdict(curriculum)),
                    'reward_shaping': stage.reward.enabled,
                    'random_winrate': random_eval['winrate'],
                    'random_chance': random_eval['chance_winrate'],
                    'random_avg_rank': random_eval['avg_rank'],
                    'random_chance_rank': random_eval['chance_avg_rank'],
                    'random_avg_reward': random_eval['avg_reward'],
                    'default_winrate': default_eval['winrate'],
                    'default_chance': default_eval['chance_winrate'],
                    'default_avg_rank': default_eval['avg_rank'],
                    'default_chance_rank': default_eval['chance_avg_rank'],
                    'default_avg_reward': default_eval['avg_reward'],
                    'random_gate_hit': random_gate_iteration is not None,
                    'default_gate_streak': default_gate_streak,
                    'rollout_action_frequencies': _action_frequency_summary(rollouts['action_counts']),
                    'random_eval_action_frequencies': _action_frequency_summary(random_eval['action_counts']),
                    'default_eval_action_frequencies': _action_frequency_summary(default_eval['action_counts']),
                }
                history.append(eval_metrics)

                flat_row = {
                    'iteration': total_iteration,
                    'stage_name': stage.name,
                    'stage_iteration': stage_iteration,
                    'episodes': rollouts['episodes'],
                    'decisions': rollouts['decisions'],
                    'policy_loss': update_stats['policy_loss'],
                    'value_loss': update_stats['value_loss'],
                    'entropy': update_stats['entropy'],
                    'reward_shaping': stage.reward.enabled,
                    'random_winrate': random_eval['winrate'],
                    'random_chance': random_eval['chance_winrate'],
                    'random_avg_rank': random_eval['avg_rank'],
                    'default_winrate': default_eval['winrate'],
                    'default_chance': default_eval['chance_winrate'],
                    'default_avg_rank': default_eval['avg_rank'],
                    'default_gate_streak': default_gate_streak,
                }
                _append_metrics_csv(metrics_csv, flat_row)
                _append_metrics_jsonl(metrics_jsonl, eval_metrics)

                payload = _checkpoint_payload(
                    model=model,
                    optimizer=optimizer,
                    history=history,
                    stage_index=stage_index,
                    stage_iteration=stage_iteration,
                    total_iteration=total_iteration,
                    random_gate_iteration=random_gate_iteration,
                    default_gate_iteration=default_gate_iteration,
                    default_gate_streak=default_gate_streak,
                    run_config=run_config,
                )
                latest_checkpoint = checkpoints_dir / CHECKPOINT_NAME
                _save_checkpoint(latest_checkpoint, payload)

                score = (
                    (default_eval['winrate'] - default_eval['chance_winrate'])
                    + 0.5 * (random_eval['winrate'] - random_eval['chance_winrate'])
                    - 0.05 * max(0.0, default_eval['avg_rank'] - default_eval['chance_avg_rank'])
                )
                if score > best_score:
                    best_score = score
                    _save_checkpoint(checkpoints_dir / BEST_CHECKPOINT_NAME, payload)
                if default_gate_iteration is not None:
                    _save_checkpoint(checkpoints_dir / SUCCESS_CHECKPOINT_NAME, payload)

                print(
                    f"[iter {total_iteration:03d}] stage={stage.name} "
                    f"episodes={rollouts['episodes']} decisions={rollouts['decisions']} "
                    f"policy_loss={update_stats['policy_loss']:.4f} "
                    f"value_loss={update_stats['value_loss']:.4f} "
                    f"entropy={update_stats['entropy']:.4f} "
                    f"random={random_eval['winrate']:.3f}/{random_eval['chance_winrate']:.3f} "
                    f"default={default_eval['winrate']:.3f}/{default_eval['chance_winrate']:.3f} "
                    f"default_streak={default_gate_streak}"
                )

                if default_gate_iteration is not None:
                    return TrainResult(
                        success=True,
                        run_dir=str(run_path),
                        latest_checkpoint=str(checkpoints_dir / CHECKPOINT_NAME),
                        best_checkpoint=str(checkpoints_dir / BEST_CHECKPOINT_NAME),
                        total_iterations=total_iteration,
                        history=history,
                        random_gate_iteration=random_gate_iteration,
                        default_gate_iteration=default_gate_iteration,
                    )

        stage_iteration_start = 0

    return TrainResult(
        success=False,
        run_dir=str(run_path),
        latest_checkpoint=str(checkpoints_dir / CHECKPOINT_NAME),
        best_checkpoint=str(checkpoints_dir / BEST_CHECKPOINT_NAME),
        total_iterations=total_iteration,
        history=history,
        random_gate_iteration=random_gate_iteration,
        default_gate_iteration=default_gate_iteration,
    )


def load_checkpoint_for_eval(checkpoint_path, *, device='cpu'):
    checkpoint = _load_checkpoint(checkpoint_path)
    stage_index = checkpoint['stage_index']
    managed_kind_names = None
    if checkpoint.get('history'):
        managed_kind_names = checkpoint['history'][-1].get('managed_kinds')
    if managed_kind_names is None:
        managed_kind_names = progressive_stages()[stage_index].managed_kinds
    managed_kinds = tuple(DecisionKind[name] for name in managed_kind_names)
    model, _ = _make_model_and_policy(checkpoint['model_state_dict'], managed_kinds, sample=False, record=False, device=device)
    return checkpoint, model, managed_kinds


def _assert_multiprocessing_launch_safe(num_workers):
    if num_workers <= 1:
        return
    main_file = getattr(__main__, '__file__', None)
    main_text = str(main_file) if main_file is not None else ''
    if not main_text or '<stdin>' in main_text:
        raise RuntimeError(
            "Multiprocessing training on Windows must be launched from a real .py file. "
            "Do not use `python -` or stdin redirection when num_workers > 1."
        )


def _parse_curriculum_mix(value):
    if value is None:
        return None
    parts = [float(part.strip()) for part in value.split(',') if part.strip()]
    if len(parts) != 3:
        raise ValueError("--curriculum must have three comma-separated weights: self,default,random")
    return CurriculumMix(self_play=parts[0], versus_default=parts[1], versus_random=parts[2])


def _customize_stages(
    stages,
    *,
    stage_limit=None,
    max_stage_iterations=None,
    managed_kind_names=None,
    reward_shaping=None,
    winner_take_all=None,
    lr=None,
    entropy_coef=None,
):
    customized = []
    for stage in stages[:stage_limit] if stage_limit else stages:
        ppo = PPOConfig(**asdict(stage.ppo))
        reward = RewardConfig(**asdict(stage.reward))
        if lr is not None:
            ppo.lr = lr
        if entropy_coef is not None:
            ppo.entropy_coef = entropy_coef
        if reward_shaping is not None:
            reward.enabled = reward_shaping
        if winner_take_all is not None:
            reward.placement_mode = 'winner_take_all' if winner_take_all else 'ranked'
        customized.append(StageConfig(
            name=stage.name,
            max_iterations=max_stage_iterations if max_stage_iterations is not None else stage.max_iterations,
            hidden_dim=stage.hidden_dim,
            managed_kinds=managed_kind_names if managed_kind_names is not None else stage.managed_kinds,
            ppo=ppo,
            reward=reward,
            restart_from_scratch=stage.restart_from_scratch,
        ))
    return customized


def benchmark_worker_choices():
    results = benchmark_rollout_workers()
    for result in results:
        print(
            f"workers={result['workers']} episodes={result['episodes']} "
            f"seconds={result['seconds']:.2f} eps={result['episodes_per_second']:.2f}"
        )
    return results


def run_smoke_training():
    smoke_stage = StageConfig(
        name='smoke',
        max_iterations=1,
        hidden_dim=64,
        managed_kinds=tuple(kind.name for kind in INITIAL_MANAGED_KINDS),
        ppo=PPOConfig(ppo_epochs=1, minibatch_size=64),
        reward=RewardConfig(enabled=False),
        restart_from_scratch=True,
    )
    with TemporaryDirectory() as temp_dir:
        result = train_progressive(
            run_dir=temp_dir,
            seed=4444,
            num_workers=1,
            episodes_per_batch=16,
            eval_every=1,
            random_eval_games=16,
            default_eval_games=16,
            device='cpu',
            stages=[smoke_stage],
        )
        return result.history[-1]


def smoke_checkpoint_reproducibility():
    smoke_stage = StageConfig(
        name='smoke',
        max_iterations=1,
        hidden_dim=64,
        managed_kinds=tuple(kind.name for kind in INITIAL_MANAGED_KINDS),
        ppo=PPOConfig(ppo_epochs=1, minibatch_size=64),
        reward=RewardConfig(enabled=False),
        restart_from_scratch=True,
    )
    with TemporaryDirectory() as temp_dir:
        result = train_progressive(
            run_dir=temp_dir,
            seed=5555,
            num_workers=1,
            episodes_per_batch=16,
            eval_every=1,
            random_eval_games=16,
            default_eval_games=16,
            device='cpu',
            stages=[smoke_stage],
        )
        checkpoint, model, managed_kinds = load_checkpoint_for_eval(result.latest_checkpoint, device='cpu')
        eval_banks = build_eval_banks(random_games=16, default_games=16)
        random_eval = evaluate_against_baseline(model, managed_kinds, 'random', eval_banks['random'], num_workers=1)
        default_eval = evaluate_against_baseline(model, managed_kinds, 'default', eval_banks['default'], num_workers=1)
        last_metrics = checkpoint['history'][-1]
        assert abs(random_eval['winrate'] - last_metrics['random_winrate']) < 1e-9
        assert abs(random_eval['avg_rank'] - last_metrics['random_avg_rank']) < 1e-9
        assert abs(default_eval['winrate'] - last_metrics['default_winrate']) < 1e-9
        assert abs(default_eval['avg_rank'] - last_metrics['default_avg_rank']) < 1e-9
        return {
            'random_winrate': random_eval['winrate'],
            'default_winrate': default_eval['winrate'],
            'checkpoint': result.latest_checkpoint,
        }


def print_environment():
    print(f"python={sys.version.split()[0]}")
    print(f"torch={torch.__version__}")
    print(f"cuda_available={torch.cuda.is_available()}")
    print(f"cuda_device_count={torch.cuda.device_count()}")
    if torch.cuda.is_available():
        print(f"cuda_name={torch.cuda.get_device_name(0)}")
    print(f"cpu_count={mp.cpu_count()}")


def main():
    parser = argparse.ArgumentParser(description="Progressive PPO training for simudonjon.")
    subparsers = parser.add_subparsers(dest='command', required=False)

    train_parser = subparsers.add_parser('train', help='Run the full progressive training loop.')
    train_parser.add_argument('--run-dir', default='artifacts/rl')
    train_parser.add_argument('--seed', type=int, default=12345)
    train_parser.add_argument('--num-workers', type=int, default=8)
    train_parser.add_argument('--episodes-per-batch', type=int, default=2048)
    train_parser.add_argument('--eval-every', type=int, default=5)
    train_parser.add_argument('--random-eval-games', type=int, default=1000)
    train_parser.add_argument('--default-eval-games', type=int, default=2000)
    train_parser.add_argument('--device', default=None)
    train_parser.add_argument('--resume', default=None)
    train_parser.add_argument('--warmstart', default=None)
    train_parser.add_argument('--stage-limit', type=int, default=None)
    train_parser.add_argument('--max-stage-iterations', type=int, default=None)
    train_parser.add_argument(
        '--curriculum',
        default=None,
        help='Override rollout mix as self,default,random weights.',
    )
    train_parser.add_argument(
        '--reward-shaping',
        action='store_true',
        help='Enable dense score/monster/death shaping for all selected stages.',
    )
    train_parser.add_argument(
        '--winner-take-all',
        action='store_true',
        help='Train with 1.0 reward for the winner and 0.0 for all other players.',
    )
    train_parser.add_argument('--lr', type=float, default=None)
    train_parser.add_argument('--entropy-coef', type=float, default=None)
    train_parser.add_argument(
        '--managed-kinds',
        default=None,
        help='Comma-separated DecisionKind names controlled by PPO during training.',
    )

    benchmark_parser = subparsers.add_parser('benchmark', help='Benchmark rollout throughput.')
    benchmark_parser.add_argument('--episodes', type=int, default=128)

    report_parser = subparsers.add_parser('report', help='Print policy comparison stats.')
    report_parser.add_argument('--checkpoint', default=None)
    report_parser.add_argument('--episodes', type=int, default=1000)
    report_parser.add_argument('--num-workers', type=int, default=8)
    report_parser.add_argument(
        '--ppo-managed-kinds',
        default=None,
        help='Comma-separated DecisionKind names controlled by PPO during report evaluation.',
    )

    subparsers.add_parser('smoke', help='Run a small RL smoke training loop.')
    subparsers.add_parser('smoke-checkpoint', help='Run checkpoint roundtrip reproducibility smoke.')
    subparsers.add_parser('env', help='Print torch/CUDA environment information.')

    args = parser.parse_args()
    command = args.command or 'train'

    if command == 'train':
        stages = _customize_stages(
            progressive_stages(),
            stage_limit=args.stage_limit,
            max_stage_iterations=args.max_stage_iterations,
            managed_kind_names=_parse_managed_kind_names(args.managed_kinds),
            reward_shaping=True if args.reward_shaping else None,
            winner_take_all=True if args.winner_take_all else None,
            lr=args.lr,
            entropy_coef=args.entropy_coef,
        )
        result = train_progressive(
            run_dir=args.run_dir,
            seed=args.seed,
            num_workers=args.num_workers,
            episodes_per_batch=args.episodes_per_batch,
            eval_every=args.eval_every,
            random_eval_games=args.random_eval_games,
            default_eval_games=args.default_eval_games,
            device=args.device,
            resume_path=args.resume,
            warmstart_path=args.warmstart,
            stages=stages,
            curriculum_override=_parse_curriculum_mix(args.curriculum),
        )
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return

    if command == 'benchmark':
        results = benchmark_rollout_workers(episodes=args.episodes, worker_options=(4, 8))
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    if command == 'report':
        rows = report_policy_stats(
            checkpoint_path=args.checkpoint,
            episodes=args.episodes,
            num_workers=args.num_workers,
            ppo_managed_kinds=_parse_managed_kind_names(args.ppo_managed_kinds),
        )
        print(format_policy_report(rows))
        return

    if command == 'smoke':
        print(json.dumps(run_smoke_training(), ensure_ascii=False, indent=2))
        return

    if command == 'smoke-checkpoint':
        print(json.dumps(smoke_checkpoint_reproducibility(), ensure_ascii=False, indent=2))
        return

    if command == 'env':
        print_environment()
        return


if __name__ == '__main__':
    main()
