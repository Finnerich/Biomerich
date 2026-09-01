

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path


_MAX_LOG_BYTES = 750_000
_MAX_TIMELINE_ENTRIES = 300
_SECRET_KEY = re.compile(
    r"(?i)(cookie|token|password|webhook|private.?server|invite|authorization|"
    r"discord.?user.?id|roblox.?user.?id|hwid|machine.?id|secret)"
)
_DISCORD_WEBHOOK = re.compile(
    r"https?://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/[^\s\"']+",
    re.IGNORECASE,
)
_ROBLOX_COOKIE = re.compile(
    r"(?i)(?:_?\.ROBLOSECURITY\s*[=:]\s*)?(_\|WARNING:-DO-NOT-SHARE-THIS[^\s\"']*)"
)
_BEARER = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]{12,}")
_WINDOWS_USER = re.compile(r"(?i)\b([A-Z]:\\Users\\)[^\\\s\"']+")
_URL_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:token|key|code|secret|auth|ticket)=)[^&#\s\"']+"
)


def _redact_text(value: object, account_names=()) -> str:
    text = str(value or "").replace("\x00", "")
    text = _DISCORD_WEBHOOK.sub("[redacted webhook]", text)
    text = _ROBLOX_COOKIE.sub("[redacted Roblox login cookie]", text)
    text = _BEARER.sub(r"\1[redacted]", text)
    text = _WINDOWS_USER.sub(r"\1[Windows User]", text)
    text = _URL_QUERY_SECRET.sub(r"\1[redacted]", text)
    for index, name in enumerate(account_names, start=1):
        if name:
            text = re.sub(re.escape(str(name)), f"Account {index}", text, flags=re.I)
    return text


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _file_state(path: Path) -> dict:
    try:
        stat = path.stat()
        return {
            "exists": True,
            "sizeBytes": stat.st_size,
            "modifiedUnix": round(stat.st_mtime, 3),
        }
    except OSError:
        return {"exists": False}


def _safe_settings(settings: dict) -> dict:
    
    keys = (
        "macroMode", "biomeLogging", "fakePingGuard", "fakePingPrompt",
        "auraPushNotify", "auraMinimumRarity", "clippingEnabled", "clipHotkey",
        "clipBiomeDelay", "clipAuraDelay", "clipAuraMinimumRarity",
        "biomeHealthMonitorEnabled", "windowsNotificationsEnabled",
        "windowsNotifyBiomes", "windowsNotifyDisconnects", "windowsNotifyAuras",
        "windowsNotifyBiomeHealth", "windowsAuraMinimumRarity",
        "monitorDimEnabled", "antiAfkEnabled", "ramTrimEnabled",
        "throttleEnabled", "throttleMethod", "themeAnim", "navAnim",
    )
    result = {}
    for key in keys:
        if key not in settings:
            continue
        value = settings.get(key)
        if isinstance(value, (bool, int, float)) or value is None:
            result[key] = value
        elif isinstance(value, str) and len(value) <= 80 and not _SECRET_KEY.search(key):
            result[key] = value
    return result


def _account_summary(accounts: list) -> tuple[list[dict], list[str], dict]:
    names = [str(row.get("name") or "") for row in accounts if isinstance(row, dict)]
    id_aliases = {}
    rows = []
    for index, account in enumerate((row for row in accounts if isinstance(row, dict)), start=1):
        account_id = account.get("id")
        if account_id is not None:
            id_aliases[str(account_id)] = f"Account {index}"
        modules = account.get("modules") if isinstance(account.get("modules"), dict) else {}
        rows.append({
            "account": f"Account {index}",
            "enabled": bool(account.get("enabled", True)),
            "modules": {
                str(key): bool(value)
                for key, value in modules.items()
                if isinstance(value, (bool, int))
            },
            "hasWindowBinding": bool(account.get("windowTitle") or account.get("hwnd")),
        })
    return rows, names, id_aliases


def _safe_automation(automation: dict, id_aliases: dict) -> dict:
    
    result = {
        "mode": str(automation.get("mode") or "idle")[:30],
        "moduleFlags": {},
    }
    for key in ("strangeController", "biomeRandomizer", "merchantTeleporter"):
        result["moduleFlags"][key] = bool(automation.get(key, False))
    eden = automation.get("eden") if isinstance(automation.get("eden"), dict) else {}
    fishing = automation.get("fishing") if isinstance(automation.get("fishing"), dict) else {}
    result["eden"] = {
        "enabled": bool(eden.get("edenWatch", False)),
        "account": id_aliases.get(str(eden.get("account")), "Not selected"),
    }
    result["fishing"] = {
        "enabled": bool(fishing.get("enabled", False)),
        "moduleEnabled": bool(fishing.get("moduleEnabled", False)),
        "account": id_aliases.get(str(fishing.get("account")), "Not selected"),
        "scheduledAccounts": sum(
            1 for item in fishing.get("schedule", []) if isinstance(item, dict)
        ),
    }
    return result


def _safe_timeline(path: Path, account_names: list[str], id_aliases: dict) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        source = raw.get("entries", []) if isinstance(raw, dict) else []
    except (OSError, UnicodeError, json.JSONDecodeError):
        source = []
    rows = []
    for entry in source[-_MAX_TIMELINE_ENTRIES:]:
        if not isinstance(entry, dict):
            continue
        row = {
            "id": entry.get("id"),
            "ts": entry.get("ts"),
            "kind": _redact_text(entry.get("kind"), account_names)[:20],
            "category": _redact_text(entry.get("category"), account_names)[:30],
            "account": id_aliases.get(str(entry.get("accountId")), "Account"),
            "text": _redact_text(entry.get("text"), account_names)[:500],
        }
        if entry.get("biome"):
            row["biome"] = _redact_text(entry.get("biome"), account_names)[:80]
        decision = entry.get("decision")
        if isinstance(decision, dict):


            cleaned = _redact_text(json.dumps(decision, ensure_ascii=False), account_names)
            try:
                row["decision"] = json.loads(cleaned)
            except json.JSONDecodeError:
                pass
        rows.append(row)
    return {"version": 1, "entries": rows}


def _safe_log(path: Path, account_names: list[str]) -> bytes | None:
    try:
        with path.open("rb") as handle:
            size = path.stat().st_size
            if size > _MAX_LOG_BYTES:
                handle.seek(size - _MAX_LOG_BYTES)
            raw = handle.read(_MAX_LOG_BYTES)
    except OSError:
        return None
    text = raw.decode("utf-8", errors="replace")
    if path.stat().st_size > _MAX_LOG_BYTES:
        newline = text.find("\n")
        if newline >= 0:
            text = text[newline + 1:]
        text = "[Older log content omitted]\n" + text
    return _redact_text(text, account_names).encode("utf-8")


def _downloads_dir() -> Path | None:
    profile = os.getenv("USERPROFILE")
    if profile:
        candidate = Path(profile) / "Downloads"
        if candidate.is_dir():
            return candidate
    return None


def _reveal(path: Path) -> bool:
    if sys.platform != "win32":
        return False
    try:
        subprocess.Popen(["explorer.exe", "/select,", str(path)])
        return True
    except OSError:
        return False


def create(config_dir, config_data: dict, version: str, *, output_dir=None,
           reveal: bool = True, dev_build: bool = False) -> dict:
    
    started = time.time()
    config_dir = Path(config_dir).resolve()
    destination = Path(output_dir).resolve() if output_dir else (_downloads_dir() or config_dir / "Support Bundles")
    destination.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    target = destination / f"SolRich-Support-{stamp}.zip"
    suffix = 2
    while target.exists():
        target = destination / f"SolRich-Support-{stamp}-{suffix}.zip"
        suffix += 1

    data = config_data if isinstance(config_data, dict) else {}
    accounts = data.get("accounts") if isinstance(data.get("accounts"), list) else []
    account_rows, account_names, id_aliases = _account_summary(accounts)
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    automation = data.get("automation") if isinstance(data.get("automation"), dict) else {}

    diagnostics = {
        "createdUnix": round(started, 3),
        "solRichVersion": str(version),
        "build": "dev" if dev_build else "release",
        "platform": platform.system(),
        "platformRelease": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "frozenBuild": bool(getattr(sys, "frozen", False)),
        "configState": {
            "primary": _file_state(config_dir / "config.json"),
            "backup": _file_state(config_dir / "config.json.bak"),
            "corruptCopies": len(list(config_dir.glob("config.corrupt.*.json"))),
            "secureLoginStorePresent": (config_dir / "tokens.dat").is_file(),
        },
        "counts": {
            "accounts": len(account_rows),
            "webhooks": len(data.get("webhooks", [])) if isinstance(data.get("webhooks"), list) else 0,
        },
        "settings": _safe_settings(settings),
        "accounts": account_rows,
        "automation": _safe_automation(automation, id_aliases),
    }
    files = {
        "README.txt": (
            "SolRich Automatic Support Bundle\n\n"
            "This archive was created locally. It does not contain config.json, "
            "tokens.dat, Roblox login cookies, webhook URLs, private-server links, "
            "Discord/Roblox user IDs, or your Windows username.\n\n"
            "You can open this ZIP and inspect every file before sending it to support.\n"
        ).encode("utf-8"),
        "diagnostics.json": _json_bytes(diagnostics),
        "timeline.json": _json_bytes(
            _safe_timeline(config_dir / "account_timeline.json", account_names, id_aliases)
        ),
    }
    for filename in ("solrich.log", "solrich.log.1", "fishing_debug.txt"):
        safe = _safe_log(config_dir / filename, account_names)
        if safe is not None:
            files[f"logs/{filename}"] = safe

    fd, temporary_name = tempfile.mkstemp(prefix=".solrich-support-", suffix=".zip", dir=destination)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for filename, payload in files.items():
                archive.writestr(filename, payload)
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    opened = _reveal(target) if reveal else False
    return {
        "ok": True,
        "path": str(target),
        "name": target.name,
        "sizeBytes": target.stat().st_size,
        "files": sorted(files),
        "revealed": opened,
    }
