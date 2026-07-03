from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Tuple


class DecisionKind(Enum):
    SHOULD_REPLAY = auto()
    SHOULD_FLEE = auto()

    USE_OBJECT_IN_COMBAT = auto()
    CHOOSE_COMBAT_OBJECT = auto()
    USE_HERO_ABILITY = auto()
    USE_ACTIVE_OBJECT = auto()
    USE_EVENT_EFFECT = auto()

    SHOULD_FACE_SPECIAL_CARD = auto()
    SHOULD_KEEP_SPECIAL_MONSTER = auto()
    PAY_TRAQUENARD = auto()

    CHOOSE_OBJECT = auto()
    CHOOSE_OBJECTS = auto()
    CHOOSE_OBJECT_TO_SACRIFICE = auto()
    CHOOSE_OBJECT_TO_REPAIR = auto()

    CHOOSE_MONSTER = auto()
    CHOOSE_MONSTERS = auto()
    CHOOSE_CARD = auto()
    CHOOSE_CARDS = auto()
    CHOOSE_CARDS_SPLIT = auto()

    CHOOSE_PLAYER = auto()
    CHOOSE_POWER = auto()
    CHOOSE_TYPE = auto()
    CHOOSE_CATEGORY = auto()
    CHOOSE_DESTINATION = auto()
    CHOOSE_ORDER = auto()

    ORDER_OBJECTS = auto()
    ORDER_CARDS = auto()

    DRAFT_PICK = auto()


@dataclass(frozen=True)
class DecisionContext:
    kind: DecisionKind
    actor: Any
    game: Any
    phase: str
    subject: Any = None
    options: Tuple[Any, ...] = ()
    metadata: dict | None = None

    def meta(self, key: str, default: Any = None) -> Any:
        if self.metadata is None:
            return default
        return self.metadata.get(key, default)


class CombatObjectChoice(Enum):
    RESOLVE_NOW = auto()


def require_bool(value, decision_name):
    if type(value) is not bool:
        raise ValueError(f"Policy must return bool for {decision_name}, got {type(value).__name__}")
    return value


def require_option(value, options, *, allow_none=False, decision_name="decision"):
    if value is None and allow_none:
        return None
    if value not in options:
        raise ValueError(f"Policy returned invalid option for {decision_name}")
    return value


def require_combat_object_choice(value, options, *, decision_name="decision"):
    if value is CombatObjectChoice.RESOLVE_NOW:
        return value
    if value not in options:
        raise ValueError(f"Policy returned invalid combat object choice for {decision_name}")
    return value


def require_options(values, options, *, min_count=0, max_count=None, allow_empty=True, decision_name="decision"):
    values = tuple(values)
    if not allow_empty and not values:
        raise ValueError(f"Policy returned no option for {decision_name}")
    if len(values) < min_count:
        raise ValueError(f"Policy returned too few options for {decision_name}")
    if max_count is not None and len(values) > max_count:
        raise ValueError(f"Policy returned too many options for {decision_name}")
    if len(set(map(id, values))) != len(values):
        raise ValueError(f"Policy returned duplicate options for {decision_name}")
    for value in values:
        if value not in options:
            raise ValueError(f"Policy returned invalid option for {decision_name}")
    return values


def require_permutation(values, options, *, decision_name="decision"):
    values = tuple(values)
    options = tuple(options)
    if len(values) != len(options):
        raise ValueError(f"Policy returned wrong number of elements for {decision_name}")
    if set(map(id, values)) != set(map(id, options)):
        raise ValueError(f"Policy returned non-permutation for {decision_name}")
    return values
