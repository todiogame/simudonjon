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
* 4 fixed objects per player, identical every game:
    - ``Marteau de Guerre`` : type-tagged executor (Golem / Squelette), free, reusable
    - ``Torche Bleue``      : power-tagged executor (power <= 2), free, reusable
    - ``Hache de Glace``    : active ONE-SHOT executor of any monster (incl. Dragon),
                              consumed on use -- the scarce, decisive tool
    - ``Armure en cuir``    : pure passive +5 PV (start HP = 7 hero + 5 = 12)
* Fixed dungeon: the full set of "standard" monsters (Gobelin..Dragon, the base
  DonjonDeck composition), in ascending power -- no rats, no special-rule /
  effect / X cards -- so the only decisions raised stay the encodable binary /
  1-of-N kinds. The lone source of residual randomness is the seedable flee roll.
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
Terminal, game-aligned, no shaping and no raw score: +1 win the game / 0 survive
but lose / -1 die. Using the score directly is fatal on a hard dungeon (a huge
score upside against a tiny death penalty makes drawing-into-death EV-positive);
rewarding the *outcome* instead -- with death strictly worse than a survived loss
-- removes that trap while leaving honest fleeing neutral.

Diagnostic findings (what the toy taught us)
--------------------------------------------
1. The PPO machinery *learns* and is not the bottleneck. The agent reproduces the
   hand-derived optimal combat line on the controlled probe, and on an easy,
   fully-clearable dungeon pure self-play converges to a strong policy that beats
   Random markedly (~0.9). The encoder / network / PPO update are sound.

2. *Pure self-play on this shared-queue duel falls into degenerate equilibria,
   and which one depends on the dungeon's difficulty.* Both seats draw from one
   shared queue, so the self-play dynamics differ from facing a fixed opponent
   and the agent does not find the intended "clear the cheap monsters, spend the
   one-shot Hache on a monster the free tools can't kill, then flee before the
   late high-power monsters" line. Observed attractors:
   - Easy/clearable dungeon: converges to clearing everything -> beats Random.
   - Hard dungeon (the full standard monster set): oscillates between fleeing
     immediately (score ~0) and drawing everything and dying (score high, but
     death-rate 1.0) -> loses to Random.
   The lever is the training regime (reward / opponent mix via ``--opponent``
   and ``--opponent-ratio``, e.g. train against the heuristic DefaultDungeonPolicy),
   not the network.

(This is an iterated design -- objects, dungeon and skill metric have changed as
we probe the difficulty. Re-run ``python rl_toy.py train`` to refresh the numbers
for the current setup.)

The point of the toy is exactly this: it isolates training-regime and
game-difficulty questions from the *machinery* (which provably learns), with
every decision inspectable.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import torch

from ai_decisions import DecisionContext, DecisionKind
from ai_policy import RandomPolicy, default_dungeon_policy
from monstres import CarteMonstre
from simu import ordonnanceur

from rl_toy_env import (  # torch-free toy environment
    TOY_ALLOWED_KINDS,
    TOY_MANAGED_KINDS,
    TOY_PLAYER_NAMES,
    TOY_START_PV,
    ToyDonjon,
    ToyStructuralPolicy,
    build_toy_match,
    is_hache,
    is_hache_worthy,
    make_toy_hero,
    make_toy_objects,
    routed_toy_policy,
)
from rl_train import (
    HybridNeuralPolicy,
    ObservationEncoder,
    PolicyValueNet,
    PPOConfig,
    _player_rank,
    _seed_bank,
    ppo_update,
)


# Three-tier terminal reward (the game objective, no raw score, no shaping):
#   +1 win the game / 0 survive but lose / -1 die.
# Death is strictly worse than a survived loss, so it kills the draw-into-death
# line; surviving-but-losing isn't punished, so honest fleeing stays neutral.
WIN_REWARD = 1.0
SURVIVE_REWARD = 0.0   # alive at the end but not the winner (fled or out-scored)
DEATH_REWARD = -1.0


# --- Guardrail policy --------------------------------------------------------

class ToyControlPolicy(HybridNeuralPolicy):
    """HybridNeuralPolicy specialised for the toy: records every decision kind,
    asserts it is in the allowed set, and tracks the key strategic skill --
    spending the one-shot Hache de Glace on a monster the free tools cannot kill
    rather than wasting it on a free kill."""

    def __init__(self, model, encoder, **kwargs):
        kwargs.setdefault('managed_kinds', TOY_MANAGED_KINDS)
        kwargs['fallback'] = ToyStructuralPolicy()
        super().__init__(model, encoder, **kwargs)
        self._kinds_seen = Counter()
        self._skill = Counter()

    def decide(self, context):
        kind = context.kind
        self._kinds_seen[kind.name] += 1
        if kind not in TOY_ALLOWED_KINDS:
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


# --- Model / policy construction ---------------------------------------------

def build_toy_model(*, hidden_dim=128, device='cpu'):
    encoder = ObservationEncoder()
    model = PolicyValueNet(encoder, hidden_dim=hidden_dim).to(device)
    model.eval()
    return model, encoder


def _make_toy_policy(model, encoder, *, sample, record, device='cpu'):
    return ToyControlPolicy(
        model, encoder, sample=sample, record=record, device=device
    )


# --- Rollouts / evaluation (single process: deterministic and simple) --------

def _opponent_policy(kind):
    """Fixed opponent for non-self-play episodes. The opponent may be the
    heuristic DefaultDungeonPolicy -- only the *agent* seat must avoid the
    heuristic (guardrail), the opponent is free to use it."""
    if kind == 'random':
        return RandomPolicy()
    if kind == 'default':
        return default_dungeon_policy()
    raise ValueError(f"Unknown toy opponent: {kind}")


def collect_toy_rollouts(model, encoder, *, episodes, seed_start,
                         opponent_ratio=0.0, opponent='random', device='cpu'):
    """Rollouts for one PPO batch.

    ``opponent_ratio`` is the fraction of episodes the agent plays against a
    fixed ``opponent`` ('random' or 'default'); the rest are self-play. On each
    such episode the agent occupies one rotated seat and only its steps are
    recorded. Pure self-play (ratio 0.0) over-fits to facing a clone on the
    shared dungeon queue; training against a fixed competent opponent (the
    heuristic 'default') mirrors what the real harness does.
    """
    policy = _make_toy_policy(model, encoder, sample=True, record=True, device=device)
    baseline = _opponent_policy(opponent)
    steps = []
    reward_sum = 0.0
    recorded_players = 0
    opponent_period = (
        max(1, round(1.0 / opponent_ratio)) if opponent_ratio > 0 else 0
    )
    for offset in range(episodes):
        seed = seed_start + offset
        joueurs, objets = build_toy_match(seed)
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
        winner, _ = ordonnanceur(joueurs, ToyDonjon(), objets, False, policy=routed)
        # Terminal reward = the game objective: +1 win / 0 survive-but-lose / -1 die.
        # No raw score, so the score reward's fatal asymmetry (huge score upside vs
        # tiny death penalty -> drawing-into-death is EV-positive) disappears. Death
        # is strictly worse than a survived loss, so the draw-into-death line is
        # punished; an honest "fled and lost" stays neutral (0). Against a fixed
        # competent opponent, +1 means outscoring it while surviving.
        for joueur in recorded:
            if joueur is winner:
                reward = WIN_REWARD
            elif joueur.vivant:
                reward = SURVIVE_REWARD
            else:
                reward = DEATH_REWARD
            reward_sum += reward
            recorded_players += 1
            for step in policy.take_records(joueur):
                step['reward'] = reward
                steps.append(step)
    return {
        'steps': steps,
        'episodes': episodes,
        'avg_reward_per_player': reward_sum / max(1, recorded_players),
        'kinds_seen': policy.export_kinds_seen(),
        'skill_stats': policy.export_skill_stats(),
    }


def evaluate_toy(model, encoder, seed_bank, *, baseline='random', device='cpu'):
    """Greedy agent vs a fixed baseline ('random' or 'default'), agent seat
    rotated across games. Also reports the agent's behaviour (death / flee /
    ponce / score) so the win-rate can be interpreted, not just read."""
    agent = _make_toy_policy(model, encoder, sample=False, record=False, device=device)
    baseline = _opponent_policy(baseline)
    wins = rank_sum = deaths = flees = ponces = 0
    score_sum = 0.0
    for eval_index, seed in enumerate(seed_bank):
        joueurs, objets = build_toy_match(seed)
        seat = eval_index % len(joueurs)
        assignments = {i: (agent if i == seat else baseline) for i in range(len(joueurs))}
        routed = routed_toy_policy(assignments, joueurs)
        winner, joueurs_finaux = ordonnanceur(joueurs, ToyDonjon(), objets, False, policy=routed)
        target = joueurs_finaux[seat]
        wins += int(target is winner)
        rank_sum += _player_rank(joueurs_finaux, target)
        deaths += int(not target.vivant)
        flees += int(target.fuite_reussie)
        ponces += int(target.dans_le_dj)
        score_sum += float(target.score_final)
    games = max(1, len(seed_bank))
    return {
        'games': games,
        'winrate': wins / games,
        'avg_rank': rank_sum / games,
        'chance_winrate': 1.0 / len(TOY_PLAYER_NAMES),
        'death_rate': deaths / games,
        'flee_rate': flees / games,
        'ponce_rate': ponces / games,
        'avg_score': score_sum / games,
        'kinds_seen': agent.export_kinds_seen(),
        'skill_stats': agent.export_skill_stats(),
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
    opponent='random',
    opponent_ratio=0.0,
    seed=20260616,
    device='cpu',
    run_dir=None,
    verbose=True,
):
    torch.manual_seed(seed)
    model, encoder = build_toy_model(hidden_dim=hidden_dim, device=device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    ppo_config = PPOConfig(lr=lr, entropy_coef=entropy_coef, minibatch_size=2048)
    eval_bank = _seed_bank(seed ^ 0x5151, eval_games)

    history = []
    best_vs_random = best_vs_default = 0.0
    last_vs_random = last_vs_default = 0.0
    last_skill_rate = 0.0
    last_kinds = {}
    last_behaviour = {}

    for iteration in range(1, iterations + 1):
        rollout_seed = seed + iteration * episodes_per_batch
        rollout = collect_toy_rollouts(
            model, encoder, episodes=episodes_per_batch, seed_start=rollout_seed,
            opponent=opponent, opponent_ratio=opponent_ratio, device=device,
        )
        update = ppo_update(model, optimizer, rollout['steps'], ppo_config, device=device)

        skill = rollout['skill_stats']
        skill_rate = skill.get('hache_well_used', 0) / max(1, skill.get('hache_uses', 0))
        last_skill_rate = skill_rate
        last_kinds = rollout['kinds_seen']

        if iteration % eval_every == 0 or iteration == iterations:
            eval_random = evaluate_toy(model, encoder, eval_bank, baseline='random', device=device)
            eval_default = evaluate_toy(model, encoder, eval_bank, baseline='default', device=device)
            last_vs_random = eval_random['winrate']
            last_vs_default = eval_default['winrate']
            best_vs_random = max(best_vs_random, last_vs_random)
            best_vs_default = max(best_vs_default, last_vs_default)
            last_behaviour = {
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
                    f"(chance {eval_random['chance_winrate']:.2f}) "
                    f"hache_well_used={skill_rate:.3f} "
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
        f"- Hache de Glace spent wisely (on a monster the free tools can't kill): {result.skill_rate:.3f}",
        f"- Reproduces hand-derived optimal line on the probe: {result.optimal_line}",
    ]
    if b:
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
        managed = any(k.name == name for k in TOY_MANAGED_KINDS)
        tag = "network" if managed else "structural(identity)"
        lines.append(f"  - {name}: {count}  [{tag}]")
    return "\n".join(lines)


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
        '--opponent', choices=('random', 'default'), default='random',
        help="Fixed opponent for the non-self-play episodes ('default' = heuristic DefaultDungeonPolicy).",
    )
    train_parser.add_argument(
        '--opponent-ratio', type=float, default=0.0,
        help='Fraction of rollout episodes played vs the fixed opponent (0 = pure self-play).',
    )
    train_parser.add_argument('--seed', type=int, default=20260616)
    train_parser.add_argument('--run-dir', default='artifacts/rl_toy')

    subparsers.add_parser('smoke', help='Run a tiny toy training smoke and print a report.')

    args = parser.parse_args()
    command = args.command or 'train'

    if command == 'train':
        result = train_toy(
            iterations=args.iterations,
            episodes_per_batch=args.episodes_per_batch,
            eval_games=args.eval_games,
            eval_every=args.eval_every,
            hidden_dim=args.hidden_dim,
            lr=args.lr,
            entropy_coef=args.entropy_coef,
            opponent=args.opponent,
            opponent_ratio=args.opponent_ratio,
            seed=args.seed,
            run_dir=args.run_dir,
        )
        print(format_toy_report(result))
        return

    if command == 'smoke':
        result = run_toy_smoke()
        print(format_toy_report(result))
        return


if __name__ == '__main__':
    main()
