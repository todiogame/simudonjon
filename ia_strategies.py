"""Strategy configuration for SimuDonjon bots.

This module deliberately contains no game-rule code.  It only stores knobs used
by Joueur/Objet decision points.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import os
from typing import Any, Dict, Optional, Union


LEAGUE_DIR = "league_results"
LEAGUE_BEST_FILE = os.path.join(LEAGUE_DIR, "league_best_strategy.json")
DEFAULT_STRATEGY_NAME = os.environ.get("SIMUDONJON_STRATEGY", "league_best")


@dataclass(frozen=True)
class StrategyConfig:
    name: str = "baseline"

    # Flee policy. "legacy" means use Joueur.politique_fuite exactly as before.
    flee_policy: str = "legacy"  # legacy | ev | seuils | never | oracle_next | ev_hunter | ev_score | ev_lock | ev_exact
    use_exact_next: bool = False
    oracle_flee_on_lethal: bool = False
    oracle_flee_min_escape: float = 0.01
    oracle_flee_min_score_lead: int = 0
    oracle_flee_danger_ratio: float = 0.75
    oracle_flee_danger_escape: float = 0.65
    oracle_hunt_min_score: int = 3
    oracle_hunt_min_escape: float = 0.45
    score_lock_min_score: int = 5
    score_lock_lead: int = 2
    score_lock_min_escape: float = 0.35
    score_lock_only_last: bool = False
    flee_rival_block_lead: int = -999

    # EV flee constants. Baseline values mirror joueurs.py's historical globals.
    valeur_medaille_pts: float = 6.0
    valeur_survie_pts: float = 1.0
    bonus_ponceur_pts: float = 1.5
    fuite_ev_horizon: int = 10
    efficacite_option: float = 0.8
    taux_gain_par_pioche: float = 0.7
    prudence_pv_par_medaille: float = 2.0
    prudence_risque_par_medaille: float = 0.05

    # Voluntary draw-again policy.
    replay_policy: str = "baseline"  # baseline | oracle_safe | greedy_safe | oracle_predatory | oracle_score
    replay_safe_damage: int = 2
    replay_safe_margin: int = 3
    replay_greedy_margin: int = 1
    replay_option_buffer: int = 4
    replay_flee_setup: bool = False
    replay_hunt_setup: bool = False
    replay_use_options_for_score: bool = False
    replay_take_safe_when_ahead: bool = False
    replay_take_margin_when_ahead: bool = False
    replay_predatory_pass: bool = False
    replay_allow_estimated_x: bool = False
    replay_target_lead: int = 1
    replay_score_margin: int = 4
    score_target_policy: str = "alive"  # alive | dungeon_only | contextual
    score_estimate_policy: str = "rapid"  # rapid | static
    event_policy: str = "strict"  # strict | loose | greedy | resource
    replay_allow_executable: bool = True
    replay_allow_events: bool = True

    # Combat item usage/order policies.
    item_order_policy: str = "priority"  # priority | dynamic
    item_use_policy: str = "baseline"  # baseline | aggressive | combat_value | score_value | lethal_only | conserve
    item_aggressive_min_damage: int = 3
    item_aggressive_damage_ratio: float = 0.45
    item_conserve_min_pv: int = 5
    traquenard_strategy: str = "net_gain"

    # Non-combat item choices.
    sacrifice_policy: str = "baseline"  # baseline | future_value
    draw_item_policy: str = "priority"  # priority | strategic
    repair_policy: str = "pv"  # pv | strategic
    copy_policy: str = "priority"  # priority | strategic
    fortune_wheel_max_pv: int = 6
    resource_drag_max_pv: int = 10
    resource_drag_min_intacts: int = 5

    # League metadata.
    parent: str = ""
    generation: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


BUILTIN_STRATEGIES: Dict[str, StrategyConfig] = {
    "baseline": StrategyConfig(name="baseline"),
    "teacher_best": StrategyConfig(
        name="teacher_best",
        flee_policy="ev_lock",
        use_exact_next=False,
        score_lock_min_score=10,
        score_lock_lead=4,
        score_lock_min_escape=0.65,
        score_lock_only_last=True,
        valeur_survie_pts=0.25,
        bonus_ponceur_pts=4.0,
        fuite_ev_horizon=8,
        efficacite_option=1.2,
        taux_gain_par_pioche=0.3,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_take_margin_when_ahead=True,
        replay_target_lead=12,
        replay_score_margin=12,
        replay_safe_damage=2,
        score_target_policy="contextual",
        event_policy="resource",
        traquenard_strategy="net_gain_prudent",
        item_order_policy="dynamic",
        item_use_policy="score_value",
        item_aggressive_min_damage=3,
        item_aggressive_damage_ratio=0.40,
        sacrifice_policy="future_value",
        draw_item_policy="strategic",
        repair_policy="strategic",
        copy_policy="strategic",
        notes="UI enemy profile based on the strongest teacher/league configuration, with full combat-item choice.",
    ),
    "ev_baseline": StrategyConfig(name="ev_baseline"),
    "seuils": StrategyConfig(name="seuils", flee_policy="seuils"),
    "oracle_next": StrategyConfig(
        name="oracle_next",
        flee_policy="oracle_next",
        use_exact_next=True,
        oracle_flee_on_lethal=True,
        replay_policy="oracle_safe",
        replay_safe_damage=2,
        replay_safe_margin=3,
        item_order_policy="dynamic",
        item_use_policy="baseline",
        sacrifice_policy="future_value",
        draw_item_policy="strategic",
        repair_policy="strategic",
        copy_policy="strategic",
        notes="Uses exact next-card information for choices; rules unchanged.",
    ),
    "oracle_aggressive": StrategyConfig(
        name="oracle_aggressive",
        flee_policy="oracle_next",
        use_exact_next=True,
        oracle_flee_on_lethal=True,
        oracle_flee_danger_ratio=0.65,
        oracle_flee_danger_escape=0.50,
        replay_policy="oracle_safe",
        replay_safe_damage=3,
        replay_safe_margin=2,
        item_order_policy="dynamic",
        item_use_policy="aggressive",
        item_aggressive_min_damage=3,
        item_aggressive_damage_ratio=0.40,
        sacrifice_policy="future_value",
        draw_item_policy="strategic",
        repair_policy="strategic",
        copy_policy="strategic",
        notes="More willing to spend legal items and take safe known cards.",
    ),
    "oracle_greedy": StrategyConfig(
        name="oracle_greedy",
        flee_policy="oracle_next",
        use_exact_next=True,
        oracle_flee_on_lethal=True,
        oracle_flee_danger_ratio=1.10,
        oracle_flee_danger_escape=0.95,
        replay_policy="greedy_safe",
        replay_safe_damage=0,
        replay_safe_margin=1,
        replay_option_buffer=6,
        replay_flee_setup=True,
        replay_allow_executable=True,
        replay_allow_events=True,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        repair_policy="pv",
        copy_policy="priority",
        notes="Draws known survivable cards, but avoids non-baseline item changes.",
    ),
    "never_flee": StrategyConfig(
        name="never_flee",
        flee_policy="never",
        replay_policy="baseline",
        notes="Scores aggressively by disabling voluntary flee except hard engine cases.",
    ),
    "ev_value_items": StrategyConfig(
        name="ev_value_items",
        flee_policy="legacy",
        replay_policy="baseline",
        item_order_policy="priority",
        item_use_policy="combat_value",
        item_aggressive_min_damage=3,
        item_aggressive_damage_ratio=0.35,
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Baseline flee/replay with narrower extra combat item spending.",
    ),
    "ev_long_safe": StrategyConfig(
        name="ev_long_safe",
        flee_policy="ev",
        fuite_ev_horizon=16,
        bonus_ponceur_pts=2.5,
        valeur_survie_pts=2.5,
        efficacite_option=1.2,
        sacrifice_policy="future_value",
        draw_item_policy="strategic",
        notes="Longer EV horizon plus strategic non-combat item choices.",
    ),
    "ev_long_only": StrategyConfig(
        name="ev_long_only",
        flee_policy="ev",
        fuite_ev_horizon=16,
        bonus_ponceur_pts=2.5,
        valeur_survie_pts=2.5,
        efficacite_option=1.2,
        notes="Longer/prudent EV constants only.",
    ),
    "ev_low_survive": StrategyConfig(
        name="ev_low_survive",
        flee_policy="ev",
        fuite_ev_horizon=16,
        bonus_ponceur_pts=3.5,
        valeur_survie_pts=0.5,
        efficacite_option=1.0,
        notes="More score-seeking EV constants.",
    ),
    "oracle_predatory": StrategyConfig(
        name="oracle_predatory",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_predatory",
        replay_safe_damage=0,
        replay_safe_margin=1,
        replay_option_buffer=3,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Uses exact top card to draw survivable cards and pass opponent-lethal cards.",
    ),
    "oracle_hunter": StrategyConfig(
        name="oracle_hunter",
        flee_policy="oracle_next",
        use_exact_next=True,
        oracle_flee_on_lethal=True,
        oracle_hunt_min_score=3,
        oracle_hunt_min_escape=0.45,
        replay_policy="oracle_predatory",
        replay_hunt_setup=True,
        replay_safe_damage=0,
        replay_safe_margin=1,
        replay_option_buffer=3,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Uses known top monsters to flee and pass lethal cards to the next opponent.",
    ),
    "ev_hunter_flee": StrategyConfig(
        name="ev_hunter_flee",
        flee_policy="ev_hunter",
        use_exact_next=True,
        oracle_flee_on_lethal=False,
        oracle_hunt_min_score=5,
        oracle_hunt_min_escape=0.55,
        replay_policy="baseline",
        item_order_policy="priority",
        item_use_policy="baseline",
        notes="Baseline replay with only an added exact-card hunter flee option.",
    ),
    "ev_long_hunter": StrategyConfig(
        name="ev_long_hunter",
        flee_policy="ev_hunter",
        use_exact_next=True,
        oracle_flee_on_lethal=False,
        oracle_hunt_min_score=5,
        oracle_hunt_min_escape=0.55,
        fuite_ev_horizon=16,
        bonus_ponceur_pts=2.5,
        valeur_survie_pts=2.5,
        efficacite_option=1.2,
        replay_policy="baseline",
        item_order_policy="priority",
        item_use_policy="baseline",
        notes="Long EV constants plus a conservative hunter flee option.",
    ),
    "ev_long_value_items": StrategyConfig(
        name="ev_long_value_items",
        flee_policy="ev",
        fuite_ev_horizon=16,
        bonus_ponceur_pts=2.5,
        valeur_survie_pts=2.5,
        efficacite_option=1.2,
        replay_policy="baseline",
        item_order_policy="priority",
        item_use_policy="combat_value",
        item_aggressive_min_damage=3,
        item_aggressive_damage_ratio=0.35,
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Neutral long EV constants plus narrow combat-value item spending.",
    ),
    "oracle_score": StrategyConfig(
        name="oracle_score",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_target_lead=1,
        replay_score_margin=4,
        replay_safe_damage=2,
        replay_safe_margin=4,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Score-aware exact top-card replay with event filtering.",
    ),
    "oracle_score_items": StrategyConfig(
        name="oracle_score_items",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_target_lead=1,
        replay_score_margin=4,
        replay_safe_damage=2,
        replay_safe_margin=4,
        item_order_policy="priority",
        item_use_policy="combat_value",
        item_aggressive_min_damage=4,
        item_aggressive_damage_ratio=0.45,
        sacrifice_policy="future_value",
        draw_item_policy="strategic",
        notes="Score-aware exact replay plus conservative choice improvements.",
    ),
    "oracle_score_flee": StrategyConfig(
        name="oracle_score_flee",
        flee_policy="ev_score",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_target_lead=1,
        replay_score_margin=6,
        replay_safe_damage=1,
        replay_safe_margin=4,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Score-aware exact replay plus top-card-aware flee suppression.",
    ),
    "oracle_score_itemscore": StrategyConfig(
        name="oracle_score_itemscore",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_target_lead=1,
        replay_score_margin=6,
        replay_safe_damage=1,
        replay_safe_margin=4,
        item_order_policy="priority",
        item_use_policy="score_value",
        item_aggressive_min_damage=3,
        item_aggressive_damage_ratio=0.40,
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Score-aware replay plus score-aware legal item spending.",
    ),
    "oracle_score_lock": StrategyConfig(
        name="oracle_score_lock",
        flee_policy="ev_score",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_target_lead=1,
        replay_score_margin=6,
        replay_safe_damage=1,
        replay_safe_margin=4,
        score_lock_min_score=5,
        score_lock_lead=2,
        score_lock_min_escape=0.35,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Score-aware exact replay plus exact-card score-lock flee attempts.",
    ),
    "oracle_score_events": StrategyConfig(
        name="oracle_score_events",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_target_lead=1,
        replay_score_margin=6,
        replay_safe_damage=1,
        event_policy="loose",
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Tuned score-aware replay with looser useful-event filtering.",
    ),
    "oracle_score_events_greedy": StrategyConfig(
        name="oracle_score_events_greedy",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_target_lead=1,
        replay_score_margin=6,
        replay_safe_damage=1,
        event_policy="greedy",
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Score-aware replay with broader exact-event exploitation.",
    ),
    "oracle_score_events_flee": StrategyConfig(
        name="oracle_score_events_flee",
        flee_policy="ev_score",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_target_lead=2,
        replay_score_margin=7,
        replay_safe_damage=1,
        event_policy="loose",
        score_lock_min_score=99,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Best loose event replay plus flee suppression for known valuable cards.",
    ),
    "oracle_score_events_options": StrategyConfig(
        name="oracle_score_events_options",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_target_lead=3,
        replay_score_margin=9,
        replay_safe_damage=1,
        replay_use_options_for_score=True,
        replay_option_buffer=6,
        event_policy="loose",
        traquenard_strategy="net_gain_prudent",
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Loose-event score policy that counts remaining combat options when behind.",
    ),
    "oracle_score_events_best": StrategyConfig(
        name="oracle_score_events_best",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_target_lead=3,
        replay_score_margin=9,
        replay_safe_damage=1,
        event_policy="loose",
        traquenard_strategy="net_gain_prudent",
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Best confirmed score-aware loose-event replay neighborhood.",
    ),
    "oracle_score_events_context": StrategyConfig(
        name="oracle_score_events_context",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_target_lead=2,
        replay_score_margin=7,
        replay_safe_damage=1,
        score_target_policy="dungeon_only",
        event_policy="loose",
        traquenard_strategy="net_gain_prudent",
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Score-aware replay that ignores fuyards while racing to clear.",
    ),
    "oracle_score_events_safe": StrategyConfig(
        name="oracle_score_events_safe",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_target_lead=3,
        replay_score_margin=9,
        replay_safe_damage=1,
        score_target_policy="dungeon_only",
        event_policy="loose",
        traquenard_strategy="net_gain_prudent",
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Score-aware replay that also takes safe known cards while ahead.",
    ),
    "oracle_score_events_predatory": StrategyConfig(
        name="oracle_score_events_predatory",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_predatory_pass=True,
        replay_target_lead=12,
        replay_score_margin=12,
        replay_safe_damage=2,
        score_target_policy="dungeon_only",
        event_policy="loose",
        traquenard_strategy="net_gain_prudent",
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Safe score-chasing replay that passes opponent-lethal cards when ahead.",
    ),
    "oracle_score_events_safe_wheel": StrategyConfig(
        name="oracle_score_events_safe_wheel",
        flee_policy="ev",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_target_lead=12,
        replay_score_margin=12,
        replay_safe_damage=2,
        score_target_policy="dungeon_only",
        event_policy="loose",
        traquenard_strategy="net_gain_prudent",
        fortune_wheel_max_pv=9,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Safe score-chasing replay with a higher Fortune Wheel survival threshold.",
    ),
    "oracle_score_events_safe_lock": StrategyConfig(
        name="oracle_score_events_safe_lock",
        flee_policy="ev_lock",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_target_lead=12,
        replay_score_margin=12,
        replay_safe_damage=2,
        score_target_policy="contextual",
        event_policy="loose",
        traquenard_strategy="net_gain_prudent",
        fuite_ev_horizon=8,
        bonus_ponceur_pts=4.0,
        valeur_survie_pts=0.25,
        efficacite_option=1.2,
        taux_gain_par_pioche=0.3,
        score_lock_min_score=7,
        score_lock_lead=3,
        score_lock_min_escape=0.45,
        score_lock_only_last=True,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Safe score-chasing replay plus narrow last-runner score-lock flee.",
    ),
    "oracle_score_events_margin": StrategyConfig(
        name="oracle_score_events_margin",
        flee_policy="ev_lock",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_take_margin_when_ahead=True,
        replay_target_lead=12,
        replay_score_margin=12,
        replay_safe_damage=2,
        score_target_policy="contextual",
        event_policy="loose",
        traquenard_strategy="net_gain_prudent",
        fuite_ev_horizon=8,
        bonus_ponceur_pts=4.0,
        valeur_survie_pts=0.25,
        efficacite_option=1.2,
        taux_gain_par_pioche=0.3,
        score_lock_min_score=10,
        score_lock_lead=4,
        score_lock_min_escape=0.65,
        score_lock_only_last=True,
        flee_rival_block_lead=-999,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Safe score-chasing replay that takes high-buffer cards while ahead.",
    ),
    "oracle_score_events_pressure": StrategyConfig(
        name="oracle_score_events_pressure",
        flee_policy="ev_lock",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_take_margin_when_ahead=True,
        replay_target_lead=12,
        replay_score_margin=12,
        replay_safe_damage=2,
        score_target_policy="contextual",
        event_policy="loose",
        traquenard_strategy="net_gain_prudent",
        fuite_ev_horizon=8,
        bonus_ponceur_pts=4.0,
        valeur_survie_pts=0.25,
        efficacite_option=1.2,
        taux_gain_par_pioche=0.3,
        score_lock_min_score=10,
        score_lock_lead=4,
        score_lock_min_escape=0.65,
        score_lock_only_last=True,
        flee_rival_block_lead=4,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Margin replay plus a flee veto while live rivals can still clear.",
    ),
    "oracle_score_events_conserve": StrategyConfig(
        name="oracle_score_events_conserve",
        flee_policy="ev_lock",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_take_margin_when_ahead=True,
        replay_target_lead=12,
        replay_score_margin=12,
        replay_safe_damage=2,
        score_target_policy="contextual",
        event_policy="loose",
        traquenard_strategy="net_gain_prudent",
        fuite_ev_horizon=8,
        bonus_ponceur_pts=4.0,
        valeur_survie_pts=0.25,
        efficacite_option=1.2,
        taux_gain_par_pioche=0.3,
        score_lock_min_score=10,
        score_lock_lead=4,
        score_lock_min_escape=0.65,
        score_lock_only_last=True,
        item_order_policy="priority",
        item_use_policy="conserve",
        item_conserve_min_pv=5,
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Margin replay with conservative one-shot active item spending.",
    ),
    "oracle_score_events_resource": StrategyConfig(
        name="oracle_score_events_resource",
        flee_policy="ev_lock",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_take_margin_when_ahead=True,
        replay_target_lead=12,
        replay_score_margin=12,
        replay_safe_damage=2,
        score_target_policy="contextual",
        event_policy="resource",
        traquenard_strategy="net_gain_prudent",
        fuite_ev_horizon=8,
        bonus_ponceur_pts=4.0,
        valeur_survie_pts=0.25,
        efficacite_option=1.2,
        taux_gain_par_pioche=0.3,
        score_lock_min_score=10,
        score_lock_lead=4,
        score_lock_min_escape=0.65,
        score_lock_only_last=True,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Margin replay with events that convert Dragons into survival resources.",
    ),
    "oracle_score_events_exact_flee": StrategyConfig(
        name="oracle_score_events_exact_flee",
        flee_policy="ev_exact",
        use_exact_next=True,
        oracle_flee_min_escape=0.45,
        oracle_flee_danger_ratio=0.65,
        oracle_flee_min_score_lead=0,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_take_margin_when_ahead=True,
        replay_target_lead=12,
        replay_score_margin=12,
        replay_safe_damage=2,
        score_target_policy="contextual",
        event_policy="resource",
        traquenard_strategy="net_gain_prudent",
        fuite_ev_horizon=8,
        bonus_ponceur_pts=4.0,
        valeur_survie_pts=0.25,
        efficacite_option=1.2,
        taux_gain_par_pioche=0.3,
        score_lock_min_score=10,
        score_lock_lead=4,
        score_lock_min_escape=0.65,
        score_lock_only_last=True,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Resource replay plus exact top-card flee override when already ahead.",
    ),
    "oracle_score_events_static": StrategyConfig(
        name="oracle_score_events_static",
        flee_policy="ev_lock",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_take_margin_when_ahead=True,
        replay_target_lead=12,
        replay_score_margin=12,
        replay_safe_damage=2,
        score_target_policy="contextual",
        score_estimate_policy="static",
        event_policy="resource",
        traquenard_strategy="net_gain_prudent",
        fuite_ev_horizon=8,
        bonus_ponceur_pts=4.0,
        valeur_survie_pts=0.25,
        efficacite_option=1.2,
        taux_gain_par_pioche=0.3,
        score_lock_min_score=10,
        score_lock_lead=4,
        score_lock_min_escape=0.65,
        score_lock_only_last=True,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Resource replay with deterministic final-score item estimates.",
    ),
    "oracle_score_events_x": StrategyConfig(
        name="oracle_score_events_x",
        flee_policy="ev_lock",
        use_exact_next=True,
        replay_policy="oracle_score",
        replay_allow_events=False,
        replay_take_safe_when_ahead=True,
        replay_take_margin_when_ahead=True,
        replay_allow_estimated_x=True,
        replay_target_lead=12,
        replay_score_margin=14,
        replay_safe_damage=2,
        score_target_policy="contextual",
        event_policy="resource",
        traquenard_strategy="net_gain_prudent",
        fuite_ev_horizon=8,
        bonus_ponceur_pts=4.0,
        valeur_survie_pts=0.25,
        efficacite_option=1.2,
        taux_gain_par_pioche=0.3,
        score_lock_min_score=10,
        score_lock_lead=4,
        score_lock_min_escape=0.65,
        score_lock_only_last=True,
        item_order_policy="priority",
        item_use_policy="baseline",
        sacrifice_policy="baseline",
        draw_item_policy="priority",
        notes="Resource replay that estimates known X-power monsters.",
    ),
}


_league_best_cache: Optional[StrategyConfig] = None
_league_best_mtime: Optional[float] = None


def strategy_from_dict(data: Dict[str, Any]) -> StrategyConfig:
    fields = set(StrategyConfig.__dataclass_fields__)
    clean = {k: v for k, v in data.items() if k in fields}
    return StrategyConfig(**clean)


def legal_info_strategy(config: StrategyConfig, name: Optional[str] = None) -> StrategyConfig:
    """Return the same strategy, constrained to legally known next-card info only."""
    cfg = replace(config, use_exact_next=False)
    if name is not None:
        cfg = replace(cfg, name=name)
    return cfg


def save_strategy(config: StrategyConfig, path: str = LEAGUE_BEST_FILE) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)


def load_strategy_file(path: str) -> StrategyConfig:
    with open(path, "r", encoding="utf-8") as f:
        return strategy_from_dict(json.load(f))


def _load_league_best() -> StrategyConfig:
    global _league_best_cache, _league_best_mtime
    if not os.path.exists(LEAGUE_BEST_FILE):
        return BUILTIN_STRATEGIES["baseline"]
    mtime = os.path.getmtime(LEAGUE_BEST_FILE)
    if _league_best_cache is None or _league_best_mtime != mtime:
        cfg = load_strategy_file(LEAGUE_BEST_FILE)
        if cfg.name != "league_best":
            cfg = StrategyConfig(**{**cfg.to_dict(), "name": "league_best"})
        _league_best_cache = cfg
        _league_best_mtime = mtime
    return _league_best_cache


def get_strategy(config_or_name: Optional[Union[str, StrategyConfig, Dict[str, Any]]] = None) -> StrategyConfig:
    if isinstance(config_or_name, StrategyConfig):
        return config_or_name
    if isinstance(config_or_name, dict):
        return strategy_from_dict(config_or_name)

    name = config_or_name or DEFAULT_STRATEGY_NAME
    if name == "league_best":
        return _load_league_best()
    if name in BUILTIN_STRATEGIES:
        return BUILTIN_STRATEGIES[name]
    if os.path.exists(name):
        return load_strategy_file(name)
    return BUILTIN_STRATEGIES["baseline"]


def list_strategy_names() -> list[str]:
    names = sorted(BUILTIN_STRATEGIES)
    if os.path.exists(LEAGUE_BEST_FILE):
        names.append("league_best")
    return names
