import copy
import json
import random
import threading
import time
import traceback
import uuid
from pathlib import Path

import numpy as np

from draft import _charger_priors, score_pick
from heros import _classes_persos, persos_disponibles
from ia_strategies import list_strategy_names
from joueurs import Joueur
from monstres import DonjonDeck
from objets import COULEUR_NOMS, _cle_nom, objets_disponibles
from party import (
    MAX_MANCHES_PAR_SOIREE,
    MANCHES_MAX,
    MANCHES_MIN,
    NB_OBJETS_PAR_JOUEUR,
    SEUIL_PV_ESSAI_FUITE as PARTY_SEUIL_PV_ESSAI_FUITE,
    TAILLE_MAIN_DRAFT,
    score_pick_soiree,
)
from simu import ordonnanceur
from ui_assets import asset_url


BOT_NAMES = ["Bot 1", "Bot 2", "Bot 3"]
DEFAULT_PLAYER_COUNT = 4
RANDOM_SEUIL_PV_ESSAI_FUITE = 6
TEACHER_STRATEGY_NAME = "teacher_best"
HEURISTIC_STRATEGY_NAME = "baseline"
ISMCTS_PROF_STRATEGY_NAME = "ismcts_prof"
ISMCTS_PROF_FAST_STRATEGY_NAME = "ismcts_prof_fast"
ISMCTS_PROF_ITERS = {
    ISMCTS_PROF_STRATEGY_NAME: 200,
    ISMCTS_PROF_FAST_STRATEGY_NAME: 50,
}
BOT_STRATEGY_LABELS = {
    TEACHER_STRATEGY_NAME: "Teacher",
    HEURISTIC_STRATEGY_NAME: "Heuristic",
    ISMCTS_PROF_STRATEGY_NAME: "ISMCTS Prof",
    ISMCTS_PROF_FAST_STRATEGY_NAME: "ISMCTS Prof Fast",
}
BOT_CONTROL_LABELS = {
    TEACHER_STRATEGY_NAME: "teacher ai",
    HEURISTIC_STRATEGY_NAME: "heuristic ai",
    ISMCTS_PROF_STRATEGY_NAME: "ismcts prof",
    ISMCTS_PROF_FAST_STRATEGY_NAME: "ismcts prof",
}
ITEM_COLOR_HEX = {
    1: "#c84b4b",
    2: "#3f9464",
    3: "#3f6fb5",
    4: "#7a5cb8",
    5: "#d2a728",
}
_ITEM_VISUALS = None


def _item_visuals():
    global _ITEM_VISUALS
    if _ITEM_VISUALS is None:
        path = Path(__file__).resolve().parent / "item_visuals.json"
        with path.open("r", encoding="utf-8") as f:
            _ITEM_VISUALS = {_cle_nom(name): data for name, data in json.load(f).items()}
    return _ITEM_VISUALS


def _item_visual(obj):
    return _item_visuals().get(_cle_nom(getattr(obj, "nom", "")), {})


def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def serialize_card(card):
    if card is None:
        return None
    return {
        "title": getattr(card, "titre", None),
        "description": (getattr(card, "description", "") or "")
        .replace("<b>", "")
        .replace("</b>", ""),
        "effect": getattr(card, "effet", None),
        "event": bool(getattr(card, "event", False)),
        "power": getattr(card, "puissance", None),
        "damage": getattr(card, "dommages", None),
        "types": list(getattr(card, "types", []) or []),
        "image": asset_url("events" if getattr(card, "event", False) else "monsters", getattr(card, "titre", "")),
    }


def serialize_object(obj):
    visual = _item_visual(obj)
    color_code = getattr(obj, "couleur", None) or visual.get("color_code")
    try:
        color_code = int(color_code) if color_code is not None else None
    except (TypeError, ValueError):
        color_code = None
    return {
        "itemId": str(id(obj)),
        "name": getattr(obj, "nom", str(obj)),
        "pv": getattr(obj, "pv_bonus", 0),
        "flee": getattr(obj, "modificateur_de", 0),
        "active": bool(getattr(obj, "actif", False)),
        "intact": bool(getattr(obj, "intact", True)),
        "priority": round(float(getattr(obj, "priorite", 0)), 2),
        "effect": (getattr(obj, "effet", "") or ""),
        "description": (visual.get("description", "") or ""),
        "colorCode": color_code,
        "colorName": COULEUR_NOMS.get(color_code, ""),
        "color": ITEM_COLOR_HEX.get(color_code, "#cfd8d2"),
        "types": list(getattr(obj, "types_tags", []) or []),
        "powers": list(getattr(obj, "puissance_tags", []) or []),
        "image": asset_url("items", getattr(obj, "nom", "")),
    }


def serialize_hero(hero):
    if hero is None:
        return None
    return {
        "heroId": str(id(hero)),
        "name": getattr(hero, "nom", str(hero)),
        "pv": getattr(hero, "pv_bonus", 0),
        "flee": getattr(hero, "modificateur_de", 0),
        "effect": (getattr(hero, "effet", "") or ""),
        "level": getattr(hero, "level", None),
        "image": asset_url("characters", getattr(hero, "nom", "")),
    }


def _strategy_name(strategy):
    return getattr(strategy, "name", strategy or "")


def serialize_player(player):
    control = getattr(player, "control", "ai")
    return {
        "name": player.nom,
        "control": control,
        "strategy": "" if control == "human" else _strategy_name(getattr(player, "strategy", "")),
        "hero": serialize_hero(getattr(player, "perso_obj", None)),
        "pv": player.pv_total,
        "medals": getattr(player, "medailles", 0),
        "score": getattr(player, "score_final", 0),
        "currentScore": player._score_rapide() if hasattr(player, "_score_rapide") else 0,
        "alive": bool(player.vivant),
        "inDungeon": bool(player.dans_le_dj),
        "fled": bool(player.fuite_reussie),
        "turn": getattr(player, "tour", 0),
        "items": [serialize_object(o) for o in getattr(player, "objets", [])],
        "monsters": [serialize_card(m) for m in getattr(player, "pile_monstres_vaincus", [])],
    }


def fresh_item_pool():
    pool = copy.deepcopy(objets_disponibles)
    for obj in pool:
        obj.repare()
    return pool


def fresh_hero_pool():
    heroes = copy.deepcopy(persos_disponibles)
    for hero in heroes:
        hero.capacite_utilisee = False
    return heroes


class GameSession:
    def __init__(self, config):
        self.id = uuid.uuid4().hex
        self.config = dict(config)
        self.mode = self.config.get("mode", "random")
        self.bot_delay_ms = int(self.config.get("botDelayMs", 800))
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.events = []
        self.next_event_id = 1
        self.pending_decision = None
        self._decision_answer = None
        self.status = "created"
        self.phase = "setup"
        self.round_label = ""
        self.players = []
        self.current_card = None
        self.dungeon_state = {
            "remainingCount": 0,
            "remainingSummary": [],
            "discardCount": 0,
            "discard": [],
            "discardOrder": "top-first",
        }
        self.draft_state = None
        self.result = None
        self.error = None
        self.thread = None
        self.cancelled = False

    def start(self):
        self.status = "running"
        self.thread = threading.Thread(target=self._run_guarded, daemon=True)
        self.thread.start()

    def _run_guarded(self):
        try:
            run_game(self)
        except Exception as exc:
            with self.lock:
                self.status = "error"
                self.error = f"{type(exc).__name__}: {exc}"
                self.pending_decision = None
                self.condition.notify_all()
            self.emit({
                "kind": "error",
                "text": self.error,
                "payload": {"traceback": traceback.format_exc()},
                "basic": True,
            })

    def emit(self, event):
        with self.lock:
            payload = _json_safe(event.get("payload", {}))
            kind = event.get("kind", "log")
            if kind == "card_drawn":
                self.current_card = payload.get("card")
            if kind == "current_card":
                self.current_card = payload.get("card")
                self.condition.notify_all()
                return
            if kind == "dungeon_state":
                self.dungeon_state = payload
                self.condition.notify_all()
                return
            row = {
                "id": self.next_event_id,
                "kind": kind,
                "text": str(event.get("text", "")),
                "payload": payload,
                "basic": bool(event.get("basic", False)),
                "ts": time.time(),
            }
            self.next_event_id += 1
            self.events.append(row)
            if len(self.events) > 2000:
                self.events = self.events[-2000:]
            self.condition.notify_all()

    def set_phase(self, phase, round_label=""):
        with self.lock:
            self.phase = phase
            self.round_label = round_label
            self.condition.notify_all()

    def set_players(self, players):
        with self.lock:
            self.players = list(players)
            self.condition.notify_all()

    def set_draft_state(self, state):
        with self.lock:
            self.draft_state = _json_safe(state) if state else None
            self.condition.notify_all()

    def wait_for_decision(self, player, kind, prompt, options, default_id, context):
        with self.condition:
            decision_id = uuid.uuid4().hex
            self._decision_answer = None
            self.pending_decision = {
                "id": decision_id,
                "player": player.nom,
                "kind": kind,
                "prompt": prompt,
                "options": options,
                "defaultId": default_id,
                "context": _json_safe(context),
            }
            self.emit({
                "kind": "decision_needed",
                "text": f"{player.nom} must decide: {prompt}",
                "payload": self.pending_decision,
                "basic": True,
            })
            while (
                not self.cancelled
                and self.status == "running"
                and self._decision_answer is None
            ):
                self.condition.wait()
            answer = self._decision_answer or default_id
            selected = next((o for o in options if o["id"] == answer), None)
            self.emit({
                "kind": "human_decision",
                "text": f"{player.nom}: {selected['label'] if selected else answer}",
                "payload": {"kind": kind, "option": selected or {"id": answer}},
                "basic": True,
            })
            self.pending_decision = None
            self._decision_answer = None
            self.condition.notify_all()
            return answer

    def submit_decision(self, decision_id, option_id):
        with self.condition:
            if not self.pending_decision:
                raise ValueError("No decision is pending.")
            if self.pending_decision["id"] != decision_id:
                raise ValueError("This decision is no longer pending.")
            legal = {o["id"] for o in self.pending_decision["options"]}
            if option_id not in legal:
                raise ValueError("Illegal option.")
            self._decision_answer = option_id
            self.condition.notify_all()

    def snapshot(self):
        with self.lock:
            return {
                "id": self.id,
                "mode": self.mode,
                "status": self.status,
                "phase": self.phase,
                "round": self.round_label,
                "players": [serialize_player(p) for p in self.players],
                "currentCard": self.current_card,
                "dungeon": self.dungeon_state,
                "draft": self.draft_state,
                "pendingDecision": self.pending_decision,
                "result": self.result,
                "error": self.error,
                "lastEventId": self.next_event_id - 1,
            }

    def events_after(self, after=0, level="full"):
        with self.lock:
            rows = [e for e in self.events if e["id"] > after]
            if level == "basic":
                rows = [e for e in rows if e["basic"]]
            return rows

    def finish(self, result):
        with self.lock:
            self.result = _json_safe(result)
            self.status = "finished"
            self.phase = "finished"
            self.pending_decision = None
            self.condition.notify_all()

    def cancel(self):
        with self.condition:
            self.cancelled = True
            self.status = "cancelled"
            self.pending_decision = None
            self.condition.notify_all()


class BlockingDecisionProvider:
    def __init__(self, session):
        self.session = session

    def choose(self, joueur, kind, prompt, options, default_id, context=None):
        if getattr(joueur, "control", "ai") == "human":
            return self.session.wait_for_decision(
                joueur, kind, prompt, options, default_id, context or {}
            )
        self._bot_delay(joueur, kind, prompt)
        selected = next((o for o in options if o["id"] == default_id), None)
        label = selected["label"] if selected else default_id
        self.session.emit({
            "kind": "bot_decision",
            "text": f"{joueur.nom}: {label}",
            "payload": {"kind": kind, "prompt": prompt, "option": selected},
            "basic": True,
        })
        return default_id

    def record(self, joueur, kind, prompt, result, label=None, context=None):
        self._bot_delay(joueur, kind, prompt)
        if label is None:
            label = "yes" if result else "no"
        self.session.emit({
            "kind": "bot_decision",
            "text": f"{joueur.nom}: {label}",
            "payload": {
                "kind": kind,
                "prompt": prompt,
                "result": _json_safe(result),
                "context": _json_safe(context or {}),
            },
            "basic": True,
        })

    def _bot_delay(self, joueur, kind, prompt):
        delay = max(0, self.session.bot_delay_ms) / 1000.0
        if delay <= 0:
            return
        self.session.emit({
            "kind": "bot_thinking",
            "text": f"{joueur.nom} is deciding...",
            "payload": {"kind": kind, "prompt": prompt},
            "basic": True,
        })
        time.sleep(delay)


def build_names(player_name, count):
    names = [player_name or "Human"]
    names.extend(BOT_NAMES[: max(0, count - 1)])
    return names


def normalize_bot_strategies(config, count):
    requested = config.get("botStrategies") or []
    strategies = []
    for bot_idx in range(max(0, count - 1)):
        strategy = requested[bot_idx] if bot_idx < len(requested) else TEACHER_STRATEGY_NAME
        if strategy not in BOT_STRATEGY_LABELS:
            strategy = TEACHER_STRATEGY_NAME
        strategies.append(strategy)
    return strategies


def make_players(names, heroes, builds, provider, medals=None, bot_strategies=None):
    players = []
    medals = medals or [0] * len(names)
    bot_strategies = bot_strategies or [TEACHER_STRATEGY_NAME] * max(0, len(names) - 1)
    for idx, name in enumerate(names):
        if idx == 0:
            control = "human"
            strategy = None
        else:
            strategy = bot_strategies[idx - 1] if idx - 1 < len(bot_strategies) else TEACHER_STRATEGY_NAME
            control = BOT_CONTROL_LABELS.get(strategy, "ai")
        player = Joueur(
            name,
            heroes[idx],
            list(builds[idx]),
            medailles=medals[idx],
            strategy=strategy,
            control=control,
            decision_provider=provider,
        )
        players.append(player)
    return players


class UiLiveISMCTSPolicy:
    def __init__(self, session, seat, seed, n_iters):
        import fast_search

        self.session = session
        self.seat = seat
        self.n_iters = n_iters
        self._live = fast_search._LivePolicy(seat, seed, n_iters)

    def on_turn_start(self, game, index):
        self._live.on_turn_start(game, index)

    def decide(self, context):
        import real_search as rs

        searchable = (
            self._live.searcher is not None
            and context.actor is self._live.searcher
            and context.kind.name in rs.TREE_KINDS
            and rs.legal_keys(context)
        )
        if searchable:
            self.session.emit({
                "kind": "bot_thinking",
                "text": f"{context.actor.nom}: ISMCTS search ({self.n_iters} iterations).",
                "payload": {
                    "player": context.actor.nom,
                    "decision": context.kind.name,
                    "iterations": self.n_iters,
                },
                "basic": True,
            })
            start = time.perf_counter()
            action = self._live.decide(context)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            label = getattr(action, "nom", None) or getattr(action, "titre", None) or str(action)
            self.session.emit({
                "kind": "bot_decision",
                "text": f"{context.actor.nom}: {label}",
                "payload": {
                    "kind": context.kind.name,
                    "option": label,
                    "elapsedMs": elapsed_ms,
                    "iterations": self.n_iters,
                },
                "basic": True,
            })
            return action
        return self._live.decide(context)


def build_dungeon_policy(session, players, bot_strategies):
    if not any(strategy in ISMCTS_PROF_ITERS for strategy in bot_strategies):
        return None, None

    from ai_policy import default_dungeon_policy

    base_seed = session.config.get("seed")
    if base_seed in (None, ""):
        base_seed = random.randrange(1, 2**31)
    else:
        base_seed = int(base_seed)

    policies = [default_dungeon_policy() for _ in players]
    live_policies = []
    for bot_offset, strategy in enumerate(bot_strategies, start=1):
        if strategy not in ISMCTS_PROF_ITERS or bot_offset >= len(players):
            continue
        n_iters = ISMCTS_PROF_ITERS[strategy]
        if strategy == ISMCTS_PROF_STRATEGY_NAME:
            try:
                n_iters = max(1, int(session.config.get("ismctsIterations") or n_iters))
            except (TypeError, ValueError):
                pass
        live = UiLiveISMCTSPolicy(
            session,
            seat=bot_offset,
            seed=base_seed + bot_offset * 1009,
            n_iters=n_iters,
        )
        policies[bot_offset] = live
        live_policies.append(live)

    def on_turn_start(game, index):
        for live in live_policies:
            live.on_turn_start(game, index)

    return policies, on_turn_start


def choose_draft_pick(session, draft_player, hand, default_pick, round_no, pick_no,
                      picked=None, your_picked=None):
    session.set_draft_state({
        "round": round_no,
        "pick": pick_no,
        "player": draft_player.nom,
        "hand": [serialize_object(o) for o in hand],
        "picked": [serialize_object(o) for o in (picked or [])],
        "yourPicked": [serialize_object(o) for o in (your_picked or [])],
    })
    return draft_player.demander_choix(
        "draft_pick",
        f"Pick item {pick_no}/6.",
        hand,
        default=default_pick,
        context={"round": round_no, "pick": pick_no},
    )


def run_draft_phase(session, provider, names, heroes, medals=None, party_mode=False,
                    bot_strategies=None):
    session.set_phase("draft", session.round_label)
    pool = fresh_item_pool()
    hands = []
    hand_size = TAILLE_MAIN_DRAFT
    for _ in names:
        hand = random.sample(pool, min(hand_size, len(pool)))
        for obj in hand:
            pool.remove(obj)
        hands.append(hand)

    builds = [[] for _ in names]
    draft_players = make_players(
        names,
        heroes,
        [[] for _ in names],
        provider,
        medals=medals,
        bot_strategies=bot_strategies,
    )
    priors = _charger_priors()
    total_medals = sum(medals or [0])
    round_no = 1
    while any(len(build) < NB_OBJETS_PAR_JOUEUR for build in builds) and any(hands):
        next_hands = [[] for _ in names]
        for idx, hand in enumerate(hands):
            if len(builds[idx]) < NB_OBJETS_PAR_JOUEUR and hand:
                if party_mode:
                    adverse = total_medals - (medals or [0] * len(names))[idx]
                    default_pick = max(
                        hand,
                        key=lambda obj: score_pick_soiree(
                            obj, heroes[idx], priors, (medals or [0] * len(names))[idx], adverse
                        ),
                    )
                else:
                    default_pick = max(hand, key=lambda obj: score_pick(obj, heroes[idx], priors))
                pick = choose_draft_pick(
                    session,
                    draft_players[idx],
                    hand,
                    default_pick,
                    round_no,
                    len(builds[idx]) + 1,
                    picked=builds[idx],
                    your_picked=builds[0],
                )
                builds[idx].append(pick)
                hand.remove(pick)
                session.emit({
                    "kind": "draft_pick",
                    "text": f"{names[idx]} picked {pick.nom}.",
                    "payload": {"player": names[idx], "item": serialize_object(pick)},
                    "basic": True,
                })
            next_hands[(idx + 1) % len(names)] = hand
        hands = next_hands
        round_no += 1
    trash = [obj for hand in hands for obj in hand]
    session.set_draft_state(None)
    return builds, pool + trash


def run_dungeon(session, provider, players, remaining_items, threshold, bot_strategies=None):
    session.set_phase("dungeon", session.round_label)
    session.set_players(players)
    policy, on_turn_start = build_dungeon_policy(session, players, bot_strategies or [])
    winner, final_players = ordonnanceur(
        players,
        DonjonDeck(),
        threshold,
        remaining_items,
        log=False,
        event_sink=session.emit,
        decision_provider=provider,
        bot_delay_ms=session.bot_delay_ms,
        policy=policy,
        on_turn_start=on_turn_start,
    )
    session.set_players(final_players)
    return winner, final_players


def run_random(session, provider, names, bot_strategies):
    heroes = random.sample(fresh_hero_pool(), len(names))
    pool = fresh_item_pool()
    builds = []
    for _ in names:
        build = random.sample(pool, NB_OBJETS_PAR_JOUEUR)
        for obj in build:
            pool.remove(obj)
        builds.append(build)
    players = make_players(names, heroes, builds, provider, bot_strategies=bot_strategies)
    session.emit({"kind": "setup", "text": "Random game started.", "basic": True})
    winner, final_players = run_dungeon(
        session, provider, players, pool, RANDOM_SEUIL_PV_ESSAI_FUITE, bot_strategies
    )
    return {
        "winner": winner.nom if winner else None,
        "players": [serialize_player(p) for p in final_players],
    }


def run_draft(session, provider, names, bot_strategies):
    heroes = random.sample(fresh_hero_pool(), len(names))
    builds, remaining = run_draft_phase(
        session, provider, names, heroes, bot_strategies=bot_strategies
    )
    players = make_players(names, heroes, builds, provider, bot_strategies=bot_strategies)
    winner, final_players = run_dungeon(
        session, provider, players, remaining, RANDOM_SEUIL_PV_ESSAI_FUITE, bot_strategies
    )
    return {
        "winner": winner.nom if winner else None,
        "players": [serialize_player(p) for p in final_players],
    }


def run_party(session, provider, names, bot_strategies):
    count = len(names)
    class_pool = list(_classes_persos)
    random.shuffle(class_pool)
    player_classes = [class_pool.pop() for _ in range(count)]
    levels = [1] * count
    medals = [0] * count
    planned_rounds = int(
        session.config.get("partyRounds")
        or random.randint(MANCHES_MIN, MANCHES_MAX)
    )
    round_no = 0
    winner_idx = None

    while True:
        round_no += 1
        if round_no > MAX_MANCHES_PAR_SOIREE:
            top = max(medals)
            winner_idx = random.choice([i for i, m in enumerate(medals) if m == top])
            break

        session.round_label = f"Round {round_no}/{planned_rounds}"
        heroes = [cls(levels[i]) for i, cls in enumerate(player_classes)]
        session.emit({
            "kind": "party_round",
            "text": f"Party round {round_no} started.",
            "payload": {"medals": medals, "levels": levels},
            "basic": True,
        })
        builds, remaining = run_draft_phase(
            session,
            provider,
            names,
            heroes,
            medals=medals,
            party_mode=True,
            bot_strategies=bot_strategies,
        )
        players = make_players(
            names, heroes, builds, provider, medals=medals, bot_strategies=bot_strategies
        )
        winner, final_players = run_dungeon(
            session, provider, players, remaining, PARTY_SEUIL_PV_ESSAI_FUITE, bot_strategies
        )

        for idx, player in enumerate(final_players):
            medals[idx] = player.medailles
            if player is winner:
                gain = 1
                for obj in player.objets:
                    if obj.intact and getattr(obj, "medailles_victoire", 0) > gain:
                        gain = obj.medailles_victoire
                medals[idx] += gain
                session.emit({
                    "kind": "party_medal",
                    "text": f"{player.nom} wins the round and gains {gain} medal(s).",
                    "payload": {"player": player.nom, "medals": medals[idx]},
                    "basic": True,
                })
            if player.vivant:
                levels[idx] = 2
            else:
                new_class = random.choice(class_pool)
                class_pool.remove(new_class)
                class_pool.append(player_classes[idx])
                player_classes[idx] = new_class
                levels[idx] = 1

        if round_no >= planned_rounds:
            top = max(medals)
            leaders = [i for i, m in enumerate(medals) if m == top]
            if len(leaders) == 1:
                winner_idx = leaders[0]
                break
            session.emit({
                "kind": "party_tiebreak",
                "text": "Party is tied; playing a tiebreak round.",
                "payload": {"leaders": [names[i] for i in leaders], "medals": medals},
                "basic": True,
            })

    return {
        "winner": names[winner_idx] if winner_idx is not None else None,
        "medals": dict(zip(names, medals)),
        "rounds": round_no,
    }


def run_game(session):
    seed = session.config.get("seed")
    if seed not in (None, ""):
        seed = int(seed)
        random.seed(seed)
        np.random.seed(seed & 0xFFFFFFFF)
    count = int(session.config.get("playerCount") or DEFAULT_PLAYER_COUNT)
    count = max(3, min(4, count))
    names = build_names(session.config.get("playerName") or "Human", count)
    bot_strategies = normalize_bot_strategies(session.config, count)
    provider = BlockingDecisionProvider(session)

    session.emit({
        "kind": "setup",
        "text": f"Starting {session.mode} mode with {count} players.",
        "payload": {
            "mode": session.mode,
            "players": names,
            "botStrategies": dict(zip(names[1:], bot_strategies)),
            "strategies": list_strategy_names(),
        },
        "basic": True,
    })

    if session.mode == "draft":
        result = run_draft(session, provider, names, bot_strategies)
    elif session.mode == "party":
        result = run_party(session, provider, names, bot_strategies)
    else:
        result = run_random(session, provider, names, bot_strategies)
    session.finish(result)
    session.emit({
        "kind": "finished",
        "text": f"Game finished. Winner: {result.get('winner') or 'none'}.",
        "payload": result,
        "basic": True,
    })
