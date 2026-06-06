import os
import re
import glob

_TUTORIAL_RE = re.compile(
    r'Players\.([^.\'"\s]+)\.PlayerGui:WaitForChild\(\s*["\']TutorialCursor["\']',
    re.IGNORECASE,
)
_PLAYERS_RE = re.compile(r'Players\.([A-Za-z0-9_]{3,20})\.', re.IGNORECASE)

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

def match_logs_to_usernames(usernames, limit=12):
    wanted = {u.strip().lower() for u in usernames if u and u.strip()}
    result = {}
    if not wanted:
        return result
    for log_file in list_logs(limit=limit):
        owner = username_of_log(log_file)
        if owner and owner in wanted and owner not in result:
            result[owner] = log_file
            if len(result) == len(wanted):
                break
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
