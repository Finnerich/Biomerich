import glob
import os
import re
import shutil
import time

_TUTORIAL_RE = re.compile(
    r'Players\.([^.\'"\s]+)\.PlayerGui:WaitForChild\(\s*["\']TutorialCursor["\']',
    re.IGNORECASE,
)
_PLAYERS_RE = re.compile(r"Players\.([A-Za-z0-9_]{3,20})\.PlayerGui", re.IGNORECASE)

_DISCONNECT_MARKERS = (
    "[FLog::Network] Client:Disconnect",
    "Disconnect from",
    "disconnected",
    "DISCONNECTING",
    "handleLeaveUniverse",
    "Connection lost",
    "[FLog::SingleSurfaceApp] handleLeaveUniverse",
)


def roblox_log_dir():
    local = os.getenv("LOCALAPPDATA")
    if not local:
        return None
    path = os.path.join(local, "Roblox", "logs")
    return path if os.path.isdir(path) else None


def _count_log_items(path):
    count = 0
    try:
        for _root, dirs, files in os.walk(path, followlinks=False):
            count += len(dirs) + len(files)
    except OSError:
        pass
    return count


def _remaining_log_items(path):
    items = []

    def _scan(directory):
        try:
            entries = list(os.scandir(directory))
        except OSError:
            relative = os.path.relpath(directory, path)
            items.append("logs" if relative == "." else relative)
            return
        for entry in entries:
            relative = os.path.relpath(entry.path, path)
            items.append(relative)
            try:
                is_directory = (
                    entry.is_dir(follow_symlinks=False) and not entry.is_symlink()
                )
            except OSError:
                is_directory = False
            if is_directory:
                _scan(entry.path)

    _scan(path)
    return items


def clear_all(retries=4, retry_delay=0.25):
    local = os.getenv("LOCALAPPDATA")
    if not local:
        return {
            "ok": False,
            "error": "localappdata_unavailable",
            "deletedItems": 0,
            "remainingItems": 0,
            "failedFiles": [],
        }

    log_dir = os.path.abspath(os.path.join(local, "Roblox", "logs"))
    expected_parent = os.path.abspath(os.path.join(local, "Roblox"))
    if os.path.dirname(log_dir).casefold() != expected_parent.casefold():
        return {
            "ok": False,
            "error": "invalid_log_path",
            "deletedItems": 0,
            "remainingItems": 0,
            "failedFiles": [],
        }

    if not os.path.exists(log_dir):
        return {
            "ok": False,
            "error": None,
            "deletedItems": 0,
            "remainingItems": 0,
            "failedFiles": [],
        }
    if not os.path.isdir(log_dir):
        return {
            "ok": False,
            "error": "invalid_log_path",
            "deletedItems": 0,
            "remainingItems": 1,
            "failedFiles": ["logs"],
        }
    if (
        os.path.dirname(os.path.realpath(log_dir)).casefold()
        != os.path.realpath(expected_parent).casefold()
    ):
        return {
            "ok": False,
            "error": "invalid_log_path",
            "deletedItems": 0,
            "remainingItems": 1,
            "failedFiles": ["logs"],
        }

    initial_count = _count_log_items(log_dir)
    attempts = max(1, int(retries))
    for attempt in range(attempts):
        try:
            entries = list(os.scandir(log_dir))
        except OSError:
            entries = []

        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                    shutil.rmtree(entry.path)
                else:
                    os.unlink(entry.path)
            except OSError:
                pass

        remaining = _remaining_log_items(log_dir)
        if not remaining:
            return {
                "ok": True,
                "error": None,
                "deletedItems": initial_count,
                "remainingItems": 0,
                "failedFiles": [],
            }
        if attempt + 1 < attempts:
            time.sleep(max(0.0, float(retry_delay)))

    remaining = _remaining_log_items(log_dir)
    remaining_count = len(remaining)
    return {
        "ok": False,
        "error": "deleted_failed",
        "deletedItems": max(0, initial_count - remaining_count),
        "remainingItems": remaining_count,
        "failed_Files": remaining[:12],
    }


def list_logs(limit=12):
    log_dir = roblox_log_dir()
    if not log_dir:
        return []
    files = glob.glob(os.path.join(log_dir, "*.log"))
    files.sort(key=lambda f: _safe_mtime(f), reverse=True)
    return files[:limit]


def _safe_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def username_of_log(log_file):
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = _TUTORIAL_RE.search(line)
                if m:
                    return m.group(1).strip().lower()
    except OSError:
        return ""
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(200_000)
        m = _PLAYERS_RE.search(head)
        if m:
            return m.group(1).strip().lower()
    except OSError:
        pass
    return ""


def is_log_active(log_file):

    try:
        size = os.path.getsize(log_file)
        read_tail = min(size, 8000)
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(max(0, size - read_tail))
            tail = f.read()
        for marker in _DISCONNECT_MARKERS:
            if marker.lower() in tail.lower():
                return False
        return True
    except OSError:
        return True


def match_logs_to_usernames(usernames, limit=30, include_inactive=True):
    
    wanted = {u.strip().lower() for u in usernames if u and u.strip()}
    result = {}
    if not wanted:
        return result

    candidates = list_logs(limit=limit)
    for log_file in candidates:
        owner = username_of_log(log_file)
        if (
            owner
            and owner in wanted
            and owner not in result
            and is_log_active(log_file)
        ):
            result[owner] = log_file

    if include_inactive:
        for log_file in candidates:
            if len(result) == len(wanted):
                break
            owner = username_of_log(log_file)
            if owner and owner in wanted and owner not in result:
                result[owner] = log_file
    return result


def line_is_disconnect(line):
    if not line:
        return False
    low = line.lower()
    for marker in _DISCONNECT_MARKERS:
        if marker.lower() in low:
            return True
    return False


class LogReader:
    def __init__(self, path):
        self.path = path
        self.position = 0
        try:
            self.position = os.path.getsize(path)
        except OSError:
            self.position = 0

    def read_new_lines(self):
        if not self.path or not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(self.position)
                lines = f.readlines()
                self.position = f.tell()
                return lines
        except OSError:
            return []


def latest_biome(log_file, max_bytes=512_000):
    
    if not log_file:
        return None
    try:
        size = os.path.getsize(log_file)
        with open(log_file, "rb") as f:
            f.seek(max(0, size - max(1, int(max_bytes))))
            text = f.read().decode("utf-8", errors="ignore")
    except OSError:
        return None

    from . import biomes

    latest = None
    for line in text.splitlines():
        detected = biomes.biome_from_rpc_line(line)
        if detected:
            latest = detected
    return latest


def latest_aura_state(log_file, max_bytes=512_000):
    
    if not log_file:
        return False, None
    try:
        size = os.path.getsize(log_file)
        with open(log_file, "rb") as f:
            f.seek(max(0, size - max(1, int(max_bytes))))
            text = f.read().decode("utf-8", errors="ignore")
    except OSError:
        return False, None

    from .aura import aura_state_from_rpc_line

    for line in reversed(text.splitlines()):
        is_update, aura_name = aura_state_from_rpc_line(line)
        if is_update:
            return True, aura_name
    return False, None
