import re
from datetime import datetime, timezone
import requests

ALL_KEYS = [
    "windy", "rainy", "snowy", "sandstorm", "hell",
    "starfall", "corruption", "null", "heaven",
    "graveyard", "singularity", "aurora", "blazing_sun",
    "glitched", "dreamspace", "cyberspace",
    "the_citadel_of_orders",
]

PING_BIOMES = ["glitched", "dreamspace", "cyberspace"]

RARE_PING_BIOMES = ["glitched", "dreamspace", "cyberspace", "singularity"]

def is_rare_ping(key) -> bool:
    return key in RARE_PING_BIOMES

DISPLAY_NAMES = {
    "windy": "Windy", "rainy": "Rainy", "snowy": "Snowy",
    "sandstorm": "Sand Storm", "hell": "Hell", "starfall": "Starfall",
    "corruption": "Corruption", "null": "Null", "heaven": "Heaven",
    "graveyard": "Graveyard", "singularity": "Singularity", "aurora": "Aurora",
    "blazing_sun": "BLAZING SUN",
    "glitched": "Glitched", "dreamspace": "Dreamspace", "cyberspace": "Cyberspace",
    "the_citadel_of_orders": "THE CITADEL OF ORDERS",
}

THUMBNAILS = {
    "windy": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/WINDY.png",
    "rainy": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/RAINY.png",
    "snowy": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/SNOWY.png",
    "sandstorm": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/SAND_STORM.png",
    "hell": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/HELL.png",
    "starfall": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/STARFALL.png",
    "corruption": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/CORRUPTION.png",
    "null": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/NULL.png",
    "heaven": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/HEAVEN.png",
    "graveyard": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/GRAVEYARD.png",
    "singularity": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/SINGULARITY.png",
    "aurora": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/AURORA.png",
    "glitched": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/GLITCHED.png",
    "dreamspace": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/DREAMSPACE.png",
    "cyberspace": "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/CYBERSPACE.png",
}

BIOME_COLORS = {
    "windy": 0xADD8E6,
    "rainy": 0x4682B4,
    "snowy": 0xFFFAFA,
    "sandstorm": 0xF4A460,
    "hell": 0xFF0000,
    "starfall": 0x191970,
    "corruption": 0x8B008B,
    "null": 0x000000,
    "heaven": 0xFFFFE0,
    "graveyard": 0x2F4F4F,
    "singularity": 0x4B0082,
    "aurora": 0x00FA9A,
    "blazing_sun": 0xFF8C00,
    "glitched": 0xFF1493,
    "dreamspace": 0xFF69B4,
    "cyberspace": 0x00FFFF,
    "the_citadel_of_orders": 0xFFD700,
}



BIOME_DURATIONS = {
    "windy": 120,
    "snowy": 120,
    "rainy": 120,
    "sandstorm": 650,
    "hell": 666,
    "starfall": 600,
    "heaven": 240,
    "corruption": 650,
    "null": 99,
    "glitched": 164,
    "dreamspace": 192,
    "cyberspace": 720,
    "singularity": 1200,
}

def duration_of(key):
    return BIOME_DURATIONS.get((key or "").lower())

RARITY = {
    "windy": 500,
    "snowy": 600,
    "rainy": 750,
    "sandstorm": 3_000,
    "hell": 6_666,
    "starfall": 7_500,
    "heaven": 8_333,
    "corruption": 9_000,
    "null": 10_100,
}

def rarity_of(key: str):
    return RARITY.get((key or "").lower())

def is_ping_biome(key: str) -> bool:
    return (key or "").lower() in PING_BIOMES

def display_name(key: str) -> str:
    if is_unknown(key):
        return unknown_name(key)
    return DISPLAY_NAMES.get((key or "").lower(), (key or "").title())

def thumbnail(key: str) -> str:
    return THUMBNAILS.get((key or "").lower(), "")

def color_of(key: str) -> int:
    return BIOME_COLORS.get((key or "").lower(), 0x7E8499)

def empty_counts() -> dict:
    return {k: 0 for k in ALL_KEYS}

ROOT_URL = "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/"

_HOVER_TO_KEY = {
    "normal": "normal",
    "windy": "windy",
    "rainy": "rainy",
    "snowy": "snowy",
    "sandstorm": "sandstorm",
    "sand storm": "sandstorm",
    "hell": "hell",
    "starfall": "starfall",
    "corruption": "corruption",
    "null": "null",
    "heaven": "heaven",
    "graveyard": "graveyard",
    "singularity": "singularity",
    "aurora": "aurora",
    "blazing sun": "blazing_sun",
    "glitched": "glitched",
    "glitch": "glitched",
    "dreamspace": "dreamspace",
    "dream space": "dreamspace",
    "cyberspace": "cyberspace",
    "cyber space": "cyberspace",
    "the citadel of orders": "the_citadel_of_orders",
    "citadel of orders": "the_citadel_of_orders",
}

_HOVER_BLACKLIST = {
    "sol's rng", "sols rng", "sol rng", "eon", "eon 1", "eon-1",
    "playing", "in game", "lobby", "the window", "by the window",
    "unknown", "loading", "menu",
}

UNKNOWN_PREFIX = "unknown:"

def is_unknown(token: str) -> bool:
    return (token or "").startswith(UNKNOWN_PREFIX)

def unknown_name(token: str) -> str:
    return token[len(UNKNOWN_PREFIX):] if is_unknown(token) else token

def _plausible_biome_name(text: str) -> bool:
    t = (text or "").strip()
    if not (2 <= len(t) <= 30):
        return False
    if t.lower() in _HOVER_BLACKLIST:
        return False
    return all(c.isalnum() or c in " '-" for c in t)

_HOVER_RE = re.compile(
    r'"largeImage"\s*:\s*\{[^}]*"hoverText"\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)
_HOVER_RE_LOOSE = re.compile(r'"hoverText"\s*:\s*"([^"]+)"', re.IGNORECASE)

def biome_from_rpc_line(line: str):
    if not line or "[BloxstrapRPC]" not in line:
        return None
    m = _HOVER_RE.search(line) or _HOVER_RE_LOOSE.search(line)
    if not m:
        return None
    return normalize_hover(m.group(1))

def normalize_hover(hover_text: str):
    if not hover_text:
        return None
    norm = hover_text.strip().lower()
    if norm in _HOVER_TO_KEY:
        return _HOVER_TO_KEY[norm]
    compact = norm.replace(" ", "")
    for k, key in _HOVER_TO_KEY.items():
        if k.replace(" ", "") == compact:
            return key
    if _plausible_biome_name(hover_text):
        return UNKNOWN_PREFIX + hover_text.strip()
    return None

def detect_from_line(line: str):
    return biome_from_rpc_line(line)
