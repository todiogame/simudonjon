import csv
import json
import os
import unicodedata
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env.local"
ASSET_ROOT_ENV = "SIMUDONJON_ASSET_ROOT"
ITEM_MAPPING_CSV_ENV = "SIMUDONJON_ITEM_MAPPING_CSV"
MONSTER_MAPPING_CSV_ENV = "SIMUDONJON_MONSTER_MAPPING_CSV"
EVENT_MAPPING_CSV_ENV = "SIMUDONJON_EVENT_MAPPING_CSV"
CHARACTER_MAPPING_CSV_ENV = "SIMUDONJON_CHARACTER_MAPPING_CSV"
ASSET_OVERRIDES_ENV = "SIMUDONJON_ASSET_OVERRIDES"

CSV_ENV_BY_CATEGORY = {
    "characters": CHARACTER_MAPPING_CSV_ENV,
    "events": EVENT_MAPPING_CSV_ENV,
    "items": ITEM_MAPPING_CSV_ENV,
    "monsters": MONSTER_MAPPING_CSV_ENV,
}


def _load_env_file():
    if not ENV_FILE.exists():
        return
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def _repair_text(value):
    text = str(value or "").strip()
    if "Ã" not in text and "Â" not in text:
        return text
    try:
        return text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text


def _normalize(value):
    text = _repair_text(value).lower().replace("œ", "oe").replace("æ", "ae")
    chars = []
    for char in unicodedata.normalize("NFKD", text):
        if unicodedata.category(char) == "Mn":
            continue
        chars.append(char if char.isalnum() else " ")
    return " ".join("".join(chars).split())


def _mapping_keys(value):
    normalized = _normalize(value)
    if not normalized:
        return []
    variants = [normalized]
    words = normalized.split()
    if words and words[0] in {"l", "le", "la", "les"}:
        variants.append(" ".join(words[1:]))
    for variant in list(variants):
        singular_words = [word[:-1] if len(word) > 3 and word.endswith("s") else word for word in variant.split()]
        singular = " ".join(singular_words)
        if singular and singular != variant:
            variants.append(singular)
    keys = []
    for variant in variants:
        compact = variant.replace(" ", "")
        keys.append(variant)
        if compact != variant:
            keys.append(compact)
    return list(dict.fromkeys(keys))


def configured_asset_root():
    root = os.environ.get(ASSET_ROOT_ENV, "").strip()
    if not root:
        return None
    path = Path(root).expanduser()
    return path if path.exists() and path.is_dir() else None


def assets_enabled():
    return configured_asset_root() is not None


def _relative_asset_path(raw_path, category):
    text = _repair_text(raw_path).replace("\\", "/").strip()
    if not text:
        return None
    marker = f"/{category}/"
    lowered = text.lower()
    if marker in lowered:
        start = lowered.index(marker) + 1
        return text[start:]
    if lowered.startswith(f"{category}/"):
        return text
    return f"{category}/{Path(text).name}"


def _add_mapping(mapping, key, rel_path):
    for normalized in _mapping_keys(key):
        mapping.setdefault(normalized, rel_path)


@lru_cache(maxsize=None)
def _csv_mapping(category):
    csv_env = CSV_ENV_BY_CATEGORY.get(category)
    csv_path = os.environ.get(csv_env, "").strip() if csv_env else ""
    if not csv_path:
        return {}
    path = Path(csv_path).expanduser()
    if not path.exists():
        return {}

    mapping = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            title = row.get("Title") or row.get("title") or row.get("Nom") or row.get("Name")
            image = row.get("Image") or row.get("image")
            key = row.get("Key") or row.get("key") or row.get("Code") or row.get("id")
            rel_path = _relative_asset_path(image, category)
            if not rel_path:
                continue
            for candidate in (title, key):
                _add_mapping(mapping, candidate, rel_path)
            if category == "characters" and title:
                level = str(row.get("level") or row.get("Level") or "").strip()
                if level and level not in {"0", "1"}:
                    _add_mapping(mapping, f"{title} N{level}", rel_path)
    return mapping


@lru_cache(maxsize=1)
def _overrides():
    override_path = os.environ.get(ASSET_OVERRIDES_ENV, "").strip()
    if not override_path:
        return {}
    path = Path(override_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        category: {_normalize(name): rel_path for name, rel_path in aliases.items()}
        for category, aliases in data.items()
        if isinstance(aliases, dict)
    }


def _mapping_for(category):
    mapping = _csv_mapping(category).copy()
    mapping.update(_overrides().get(category, {}))
    return mapping


def asset_url(category, name):
    root = configured_asset_root()
    if root is None:
        return None
    mapping = _mapping_for(category)
    rel_path = next((mapping[key] for key in _mapping_keys(name) if key in mapping), None)
    if not rel_path:
        return None
    if "/" not in rel_path and "\\" not in rel_path:
        rel_path = f"{category}/{rel_path}"
    rel = Path(rel_path.replace("\\", "/"))
    full_path = root / rel
    if not full_path.exists() or not full_path.is_file():
        return None
    url_path = "/".join(quote(part) for part in rel.parts)
    return f"/assets/{url_path}"
