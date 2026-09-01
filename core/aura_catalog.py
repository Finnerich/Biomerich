

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import unicodedata
from pathlib import Path

import requests


CATALOG_URL = (
    "https://raw.githubusercontent.com/Finnerich/Boterich-Images/"
    "main/aura_data/auras.json"
)
SCHEMA_VERSION = 1
MAX_CATALOG_BYTES = 2_000_000
REFRESH_INTERVAL = 15 * 60
DEFAULT_COLOR = 0xFFFFFF

_MINIMAL_FALLBACK = {
    "schemaVersion": 1,
    "auras": [
        {
            "id": "common",
            "displayName": "Common",
            "aliases": ["Common"],
            "rarity": 2,
            "category": "Basic",
            "color": "#FFFFFF",
            "conditions": [],
        },
        {
            "id": "glitch",
            "displayName": "Glitch",
            "aliases": ["Glitch"],
            "rarity": None,
            "category": "Challenged",
            "color": "#FFFFFF",
            "conditions": [
                {
                    "biome": "glitched",
                    "rarity": 12_210_110,
                    "label": "from GLITCHED",
                }
            ],
        },
    ],
}


def catalog_key(value) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    alphanumeric = "".join(char for char in normalized if char.isalnum())
    return alphanumeric or "".join(
        char for char in normalized if not char.isspace()
    )


def _positive_int(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError("rarity cannot be a boolean")
    number = int(value)
    if not 1 <= number <= 10**18:
        raise ValueError("rarity is outside the supported range")
    return number


def _color(value):
    if value in (None, ""):
        return DEFAULT_COLOR
    if isinstance(value, str):
        cleaned = value.strip().removeprefix("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", cleaned):
            raise ValueError("color must be #RRGGBB")
        return int(cleaned, 16)
    number = int(value)
    if not 0 <= number <= 0xFFFFFF:
        raise ValueError("color is outside the RGB range")
    return number


def validate_catalog(data) -> dict:
    
    if not isinstance(data, dict) or data.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("unsupported aura catalog schema")
    extra_top_level = set(data) - {"schemaVersion", "auras"}
    if extra_top_level:
        raise ValueError(
            f"unsupported aura catalog fields: {', '.join(sorted(extra_top_level))}"
        )
    raw_auras = data.get("auras")
    if not isinstance(raw_auras, list) or len(raw_auras) > 5000:
        raise ValueError("auras must be a list with at most 5000 entries")

    aliases = {}
    normalized = []
    for raw in raw_auras:
        if not isinstance(raw, dict):
            raise ValueError("each aura must be an object")
        extra_fields = set(raw) - {
            "id", "displayName", "aliases", "rarity", "category", "color",
            "conditions",
        }
        if extra_fields:
            raise ValueError(
                f"unsupported fields on aura '{raw.get('id', '?')}': "
                f"{', '.join(sorted(extra_fields))}"
            )
        aura_id = str(raw.get("id") or "").strip()
        display = str(raw.get("displayName") or "").strip()
        category = str(raw.get("category") or "").strip()
        if not aura_id or len(aura_id) > 100 or not display or len(display) > 100:
            raise ValueError("every aura needs a short id and displayName")
        if len(category) > 80:
            raise ValueError("aura category is too long")

        raw_aliases = raw.get("aliases") or []
        if not isinstance(raw_aliases, list) or len(raw_aliases) > 50:
            raise ValueError("aura aliases must be a short list")
        all_aliases = [aura_id, display, *raw_aliases]
        keys = []
        for alias in all_aliases:
            if not isinstance(alias, str) or len(alias) > 150:
                raise ValueError("invalid aura alias")
            key = catalog_key(alias)
            if key and key not in keys:
                keys.append(key)

        conditions = []
        raw_conditions = raw.get("conditions") or []
        if not isinstance(raw_conditions, list) or len(raw_conditions) > 30:
            raise ValueError("aura conditions must be a short list")
        for condition in raw_conditions:
            if not isinstance(condition, dict):
                raise ValueError("each aura condition must be an object")
            extra_condition_fields = set(condition) - {"biome", "rarity", "label"}
            if extra_condition_fields:
                raise ValueError("unsupported aura condition fields")
            biome = str(condition.get("biome") or "").strip().casefold().replace(" ", "_")
            label = str(condition.get("label") or "").strip()
            if not biome or len(biome) > 80 or len(label) > 100:
                raise ValueError("invalid aura condition")
            conditions.append({
                "biome": biome,
                "rarity": _positive_int(condition.get("rarity")),
                "label": label,
            })

        entry = {
            "id": aura_id,
            "displayName": display,
            "rarity": _positive_int(raw.get("rarity")),
            "category": category,
            "color": _color(raw.get("color")),
            "conditions": conditions,
            "aliases": keys,
        }
        index = len(normalized)
        for key in keys:
            previous = aliases.get(key)
            if previous is not None and previous != index:
                raise ValueError(f"duplicate aura alias: {key}")
            aliases[key] = index
        normalized.append(entry)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "auras": normalized,
        "aliasIndex": aliases,
    }


class AuraCatalog:
    def __init__(self, data=None, cache_path=None):
        self._lock = threading.RLock()
        self._refreshing = False
        self._last_attempt = 0.0
        self.cache_path = (
            Path(cache_path)
            if cache_path
            else (None if data is not None else self._default_cache_path())
        )
        self._catalog = validate_catalog(_MINIMAL_FALLBACK)
        if data is not None:
            self._catalog = validate_catalog(data)
        else:
            self._load_best_local()

    @staticmethod
    def _default_cache_path():
        try:
            from .config import get_config_dir

            return get_config_dir() / "aura_catalog.cache.json"
        except Exception:
            return None

    @staticmethod
    def _bundled_path():
        return Path(__file__).with_name("aura_catalog.json")

    @staticmethod
    def _read_file(path):
        if not path or not Path(path).is_file():
            return None
        path = Path(path)
        if path.stat().st_size > MAX_CATALOG_BYTES:
            raise ValueError("aura catalog is too large")
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_best_local(self):
        for path in (self._bundled_path(), self.cache_path):
            try:
                data = self._read_file(path)
                if data is not None:
                    self._catalog = validate_catalog(data)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                print(f"[Aura] Ignored invalid local catalog '{path}': {exc}")

    def resolve(self, raw_name, biome_key=None) -> dict:
        key = catalog_key(raw_name)
        with self._lock:
            index = self._catalog["aliasIndex"].get(key)
            if index is None:
                return {
                    "known": False,
                    "displayName": re.sub(
                        r"\s+", " ", str(raw_name or "").replace("_", " ")
                    ).strip(),
                    "rarity": None,
                    "category": "",
                    "color": DEFAULT_COLOR,
                    "conditionLabel": "",
                }
            entry = self._catalog["auras"][index]
            rarity = entry["rarity"]
            label = ""
            current_biome = str(biome_key or "").casefold().replace(" ", "_")
            for condition in entry["conditions"]:
                if condition["biome"] == current_biome:
                    if condition["rarity"] is not None:
                        rarity = condition["rarity"]
                    label = condition["label"]
                    break
            return {
                "known": True,
                "displayName": entry["displayName"],
                "rarity": rarity,
                "category": entry["category"],
                "color": entry["color"],
                "conditionLabel": label,
            }

    @staticmethod
    def _fetch_remote():
        response = requests.get(
            CATALOG_URL,
            timeout=(4, 8),
            headers={"User-Agent": "SolRich-AuraCatalog/1"},
        )
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_CATALOG_BYTES:
            raise ValueError("remote aura catalog is too large")
        payload = response.content
        if len(payload) > MAX_CATALOG_BYTES:
            raise ValueError("remote aura catalog is too large")
        return json.loads(payload.decode("utf-8"))

    def _write_cache(self, raw_data):
        if not self.cache_path:
            return
        path = Path(self.cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(raw_data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        fd, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def refresh(self):
        raw_data = self._fetch_remote()
        validated = validate_catalog(raw_data)
        with self._lock:
            self._catalog = validated
        self._write_cache(raw_data)
        return True

    def refresh_async(self, force=False):
        now = time.monotonic()
        with self._lock:
            if self._refreshing:
                return False
            if not force and now - self._last_attempt < REFRESH_INTERVAL:
                return False
            self._refreshing = True
            self._last_attempt = now

        def worker():
            try:
                self.refresh()
                print("[Aura] Aura catalog updated.")
            except Exception as exc:
                print(f"[Aura] Using cached aura catalog: {exc}")
            finally:
                with self._lock:
                    self._refreshing = False

        threading.Thread(target=worker, name="aura-catalog", daemon=True).start()
        return True
