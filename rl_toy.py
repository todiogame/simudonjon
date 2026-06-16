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
    - ``Marteau de Guerre``   : type-tagged executor (Golem / Squelette)
    - ``Torche Bleue``        : power-tagged executor (power <= 2)
    - ``Couronne en Mousse``  : damage reducer (-2), combo piece #1
    - ``Couronne en Mousse``  : damage reducer (-2), combo piece #2
* Fixed dungeon order, plain monsters only (no events, no special effects,
  no X-cards) so the only decisions raised are the encodable binary / 1-of-N
  kinds. The lone source of residual randomness is the seedable flee die roll.
* The planted 2-object combo: stacking *both* Couronnes on a Dragon (power 9)
  turns an otherwise-lethal 9 damage into 5, which is the only way to survive it
  at the tuned HP. We know the combo because we built it, so we can measure
  whether the agent discovers it.

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

Diagnostic findings (what the toy taught us)
--------------------------------------------
1. The PPO machinery *learns*. Across every configuration the agent drives the
   planted combo trigger-rate from ~0.33 (random) to ~1.0 and reproduces the
   hand-derived optimal combat line on the controlled probe. The encoder /
   network / PPO update are sound -- the full-game failures are not in here.

2. *Pure self-play on this shared-queue duel is degenerate, and the win-rate is
   highly sensitive to the reward.* Because both seats draw from one shared
   dungeon queue, "draw aggressively" is safe against a mirror (the opponent
   drains the queue / dies first) yet lethal against Random -- so self-play
   over-fits to self-play dynamics. Which degenerate policy emerges depends on
   the reward:
   - Pile-rewarding terminal rewards (placement rank, or score-if-survive)
     converge to drawing into a lethal monster: death-rate ~0.86, win-rate vs
     Random collapses to ~0.12.
   - A pure winner reward (+1 winner / -1 else) instead settles into "flee
     immediately": safe, ~0.57 vs Random, combo still mastered.

3. *The two attractors are flee-immediately (~0.57) and draw-into-death (~0.12),
   and the agent oscillates between them* rather than settling on the
   survive-and-score optimum (clear safe monsters, combo the Dragon, then stop
   before the lethal second Dragon). The intended optimum needs a precise "stop
   here" decision that the current reward/exploration does not reliably find.
   Mixing Random opponents in (``--versus-random-ratio``) shifts the balance --
   the best observed win-rate (~0.65) came from a placement reward with a Random
   mix -- but does not by itself stabilise the optimum.

The point of the toy is exactly this: it isolated a *training-regime* problem
(self-play curriculum + terminal reward on a shared-queue duel) from the
*machinery* (which provably learns the combo and the optimal combat line), with
every decision inspectable. The next lever to turn is the reward / curriculum,
not the network. Set ``--versus-random-ratio 0`` to reproduce the pure
self-play collapse; raise it to study the opponent-diversity effect.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import torch

from ai_decisions import DecisionContext, DecisionKind
from ai_policy import RandomPolicy
from monstres import CarteMonstre
from simu import ordonnanceur

from rl_toy_env import (  # torch-free toy environment
    TOY_ALLOWED_KINDS,
    TOY_HERO_PV,
    TOY_MANAGED_KINDS,
    TOY_PLAYER_NAMES,
    ToyDonjon,
    ToyStructuralPolicy,
    build_toy_match,
    is_dragon_combat_context,
    is_reducer,
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


# Terminal reward for a player that is not counted at the end (died, or fled
# while the opponent ponced). Must be below the lowest survivor score (0) so
# that surviving with an empty pile still beats dying.
DEATH_REWARD = -1.0


# --- Guardrail policy --------------------------------------------------------

class ToyControlPolicy(HybridNeuralPolicy):
    """HybridNeuralPolicy specialised for the toy: records every decision kind,
    asserts it is in the allowed set, and tracks the planted combo."""

    def __init__(self, model, encoder, **kwargs):
        kwargs.setdefault('managed_kinds', TOY_MANAGED_KINDS)
        kwargs['fallback'] = ToyStructuralPolicy()
        super().__init__(model, encoder, **kwargs)
        self._kinds_seen = Counter()
        self._combo = Counter()

    def decide(self, context):
        kind = context.kind
        self._kinds_seen[kind.name] += 1
        if kind not in TOY_ALLOWED_KINDS:
            raise AssertionError(
                f"toy: unexpected decision kind {kind.name} (phase={context.phase!r}); "
                f"the fixed object/dungeon set must only raise {sorted(k.name for k in TOY_ALLOWED_KINDS)}"
            )

        dragon_combat = is_dragon_combat_context(context)
        combat_step = context.meta('combat_step', 0) if dragon_combat else 0
        if dragon_combat and combat_step == 0:
            self._combo['dragon_combats'] += 1

        decision = super().decide(context)

        if dragon_combat and is_reducer(decision):
            self._combo['reducer_uses_on_dragon'] += 1
            # A reducer chosen after at least one combat object already applied
            # this combat completes the planted 2-object combo.
            if combat_step >= 1:
                self._combo['combo_fired'] += 1
        return decision

    def clear_toy_stats(self):
        self._kinds_seen.clear()
        self._combo.clear()

    def export_kinds_seen(self):
        return dict(self._kinds_seen)

    def export_combo_stats(self):
        return dict(self._combo)


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

def collect_toy_rollouts(model, encoder, *, episodes, seed_start, versus_random_ratio=0.0, device='cpu'):
    """Rollouts for one PPO batch.

    ``versus_random_ratio`` is the fraction of episodes played against a
    RandomPolicy opponent (the agent occupies one rotated seat and only its
    steps are recorded). The default 0.0 is pure self-play, as the brief
    specifies; a non-zero ratio mirrors the self/random curriculum the real
    harness uses and is available for experiments, but with the game-aligned
    reward below it is not needed to beat Random.
    """
    policy = _make_toy_policy(model, encoder, sample=True, record=True, device=device)
    baseline = RandomPolicy()
    steps = []
    reward_sum = 0.0
    recorded_players = 0
    versus_random_period = (
        max(1, round(1.0 / versus_random_ratio)) if versus_random_ratio > 0 else 0
    )
    for offset in range(episodes):
        seed = seed_start + offset
        joueurs, objets = build_toy_match(seed)
        policy.clear_records()
        is_versus_random = versus_random_period and (offset % versus_random_period == 0)
        if is_versus_random:
            agent_seat = offset % len(joueurs)
            assignments = {i: (policy if i == agent_seat else baseline) for i in range(len(joueurs))}
            recorded = [joueurs[agent_seat]]
        else:
            assignments = {i: policy for i in range(len(joueurs))}
            recorded = list(joueurs)
        routed = routed_toy_policy(assignments, joueurs)
        ordonnanceur(joueurs, ToyDonjon(), objets, False, policy=routed)
        # Game-aligned terminal reward (no shaping): your final score if you
        # survive to be counted (`compte_au_score`), a fixed penalty otherwise
        # (death, or exclusion for fleeing while the opponent ponced). This is
        # the game's own objective. It rewards drawing extra *safe* monsters
        # (more pile while surviving) yet strictly punishes dying -- avoiding
        # both degenerate self-play equilibria the simpler rewards produce:
        # placement-rank rewards "die with a bigger pile" (draw-into-death),
        # and pure winner +1/-1 never rewards a bigger pile (flee-immediately).
        for joueur in recorded:
            reward = float(joueur.score_final) if joueur.compte_au_score else DEATH_REWARD
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
        'combo_stats': policy.export_combo_stats(),
    }


def evaluate_toy_vs_random(model, encoder, seed_bank, *, device='cpu'):
    """Greedy agent vs RandomPolicy, agent seat rotated across games. Also
    reports the agent's behaviour (death / flee / ponce / score) so the win-rate
    can be interpreted, not just read."""
    agent = _make_toy_policy(model, encoder, sample=False, record=False, device=device)
    baseline = RandomPolicy()
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
        'combo_stats': agent.export_combo_stats(),
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
    """Controlled single-decision probe (criterion #2).

    Facing a Dragon (9 power / 9 damage) at HP where tanking is lethal, the
    greedy agent should choose to use a Couronne (reduce) rather than resolve the
    monster as-is -- and again for the second reducer. We construct the exact
    state and read the argmax action.
    """
    from joueurs import Joueur

    policy = _make_toy_policy(model, encoder, sample=False, record=False, device=device)

    def choose(step, hp, reduced_damage):
        actor = Joueur(TOY_PLAYER_NAMES[0], make_toy_hero(), make_toy_objects())
        actor.pv_total = hp
        couronnes = [o for o in actor.objets if is_reducer(o)]
        dragon = CarteMonstre("Dragon", 9, ["Dragon"])
        dragon.dommages = reduced_damage
        dragon.dommages_reference = 9
        # After `step` reducers used, that many Couronnes are no longer candidates.
        options = tuple(couronnes[step:])
        game = _toy_game_namespace(actor, remaining_indices=[2, 3, 4])
        context = DecisionContext(
            kind=DecisionKind.CHOOSE_COMBAT_OBJECT,
            actor=actor,
            game=game,
            phase='choose_combat_object',
            subject=dragon,
            options=options,
            metadata={'allow_resolve_now': True, 'combat_step': step, 'log_details': []},
        )
        return policy.decide(context)

    first = choose(step=0, hp=TOY_HERO_PV, reduced_damage=9)
    second = choose(step=1, hp=TOY_HERO_PV, reduced_damage=7)
    return {
        'first_reducer_used': is_reducer(first),
        'second_reducer_used': is_reducer(second),
        'optimal_line': is_reducer(first) and is_reducer(second),
    }


# --- Training loop -----------------------------------------------------------

@dataclass
class ToyTrainResult:
    iterations: int
    final_winrate_vs_random: float
    best_winrate_vs_random: float
    combo_rate: float
    kinds_seen: dict
    optimal_line: bool
    behaviour: dict
    versus_random_ratio: float
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
    versus_random_ratio=0.0,
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
    best_winrate = 0.0
    last_winrate = 0.0
    last_combo_rate = 0.0
    last_kinds = {}
    last_behaviour = {}

    for iteration in range(1, iterations + 1):
        rollout_seed = seed + iteration * episodes_per_batch
        rollout = collect_toy_rollouts(
            model, encoder, episodes=episodes_per_batch, seed_start=rollout_seed,
            versus_random_ratio=versus_random_ratio, device=device,
        )
        update = ppo_update(model, optimizer, rollout['steps'], ppo_config, device=device)

        combo = rollout['combo_stats']
        combo_rate = combo.get('combo_fired', 0) / max(1, combo.get('dragon_combats', 0))
        last_combo_rate = combo_rate
        last_kinds = rollout['kinds_seen']

        if iteration % eval_every == 0 or iteration == iterations:
            evaluation = evaluate_toy_vs_random(model, encoder, eval_bank, device=device)
            last_winrate = evaluation['winrate']
            best_winrate = max(best_winrate, last_winrate)
            last_behaviour = {
                'death_rate': evaluation['death_rate'],
                'flee_rate': evaluation['flee_rate'],
                'ponce_rate': evaluation['ponce_rate'],
                'avg_score': evaluation['avg_score'],
            }
            row = {
                'iteration': iteration,
                'winrate_vs_random': last_winrate,
                'chance_winrate': evaluation['chance_winrate'],
                'avg_rank': evaluation['avg_rank'],
                'combo_rate': combo_rate,
                'combo_fired': combo.get('combo_fired', 0),
                'dragon_combats': combo.get('dragon_combats', 0),
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
                    f"winrate_vs_random={last_winrate:.3f} (chance {evaluation['chance_winrate']:.2f}) "
                    f"combo_rate={combo_rate:.3f} "
                    f"death={evaluation['death_rate']:.2f} flee={evaluation['flee_rate']:.2f} "
                    f"ponce={evaluation['ponce_rate']:.2f} score={evaluation['avg_score']:.2f} "
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
        final_winrate_vs_random=last_winrate,
        best_winrate_vs_random=best_winrate,
        combo_rate=last_combo_rate,
        kinds_seen=last_kinds,
        optimal_line=optimal['optimal_line'],
        behaviour=last_behaviour,
        versus_random_ratio=versus_random_ratio,
        history=history,
    )


def format_toy_report(result: ToyTrainResult):
    regime = (
        "pure self-play" if result.versus_random_ratio == 0
        else f"self-play + {result.versus_random_ratio:.0%} vs-random"
    )
    b = result.behaviour
    lines = [
        "## Toy-mode RL diagnostic report",
        "",
        f"- Training regime: {regime}",
        f"- Iterations: {result.iterations}",
        f"- Winrate vs RandomPolicy: {result.final_winrate_vs_random:.3f} "
        f"(best {result.best_winrate_vs_random:.3f}, chance 0.50)",
        f"- Combo trigger rate (both reducers on a Dragon): {result.combo_rate:.3f}",
        f"- Reproduces hand-derived optimal line on the probe: {result.optimal_line}",
    ]
    if b:
        lines.append(
            f"- Agent behaviour vs random: death {b['death_rate']:.2f}, "
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
        '--versus-random-ratio', type=float, default=0.0,
        help='Fraction of rollout episodes played vs RandomPolicy (0 = pure self-play, the brief default).',
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
            versus_random_ratio=args.versus_random_ratio,
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
