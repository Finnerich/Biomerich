import time
import threading
from urllib.parse import urlparse

import requests

from . import biomes, roblox_logs, webhooks


def _is_roblox_link(link: str) -> bool:
    try:
        url = link.strip()
        if "://" not in url:
            url = "https://" + url
        host = (urlparse(url).hostname or "").lower()
        return host == "roblox.com" or host.endswith(".roblox.com")
    except Exception:
        return False


class _AccountState:
    __slots__ = ("acc_id", "username", "reader", "current_biome",
                 "online", "last_line_ts")

    def __init__(self, acc_id, username):
        self.acc_id = acc_id
        self.username = username
        self.reader = None
        self.current_biome = None
        self.online = False
        self.last_line_ts = 0.0


class MacroEngine:
    def __init__(self, config):
        self.config = config
        self._running = False
        self._thread = None
        self._start_ts = None
        self._lock = threading.RLock()
        self._states = {}   # acc_id -> _AccountState

    # ----------------------------------------------------------- Status
    @property
    def running(self) -> bool:
        return self._running

    @property
    def uptime(self) -> int:
        if not self._running or self._start_ts is None:
            return 0
        return int(time.time() - self._start_ts)

    def account_states(self) -> list:
        with self._lock:
            return [
                {"id": s.acc_id, "currentBiome": s.current_biome, "online": s.online}
                for s in self._states.values()
            ]

    def validate(self) -> list:
        errors = []
        accounts = self.config.accounts
        webhook_list = self.config.webhooks

        if not accounts:
            errors.append("You must add at least one account.")

        if not webhook_list:
            errors.append("You must add at least one webhook.")
        else:
            for w in webhook_list:
                if not (w.get("url") or "").strip():
                    errors.append(f"Webhook „{w.get('name') or '?'}“ doesn't have a valid URL.")

        has_route = any(w.get("active", True) and w.get("routedAccounts") for w in webhook_list)
        if webhook_list and not has_route:
            errors.append("At least one webhook must be assigned to an account.")

        for a in accounts:
            link = (a.get("link") or "").strip()
            name = a.get("name") or "?"
            if not link:
                errors.append(f"Account „{name}“ doesn't have a Private-Server-Link (required).")
            elif not _is_roblox_link(link):
                errors.append(f"Private-Server-Link of „{name}“ must be a valid roblox.com link.")

        return errors

    # ----------------------------------------------------- Start / Stop
    def start(self) -> dict:
        with self._lock:
            if self._running:
                return {"ok": True, "errors": [], "running": True, "uptime": self.uptime}

            errors = self.validate()
            if errors:
                return {"ok": False, "errors": errors, "running": False}

            self._running = True
            self._start_ts = time.time()
            self._build_states()

            self._thread = threading.Thread(target=self._tracker_loop, daemon=True)
            self._thread.start()
            print("[Engine] Biomerich started.")

        webhooks.macro_started(self._all_active_urls(), self._tracked_account_names(), self._current_version())
        return {"ok": True, "errors": [], "running": True, "uptime": 0}

    def stop(self) -> dict:
        report = "00:00:00"
        biome_total = sum(self.config.biome_counts.values())
        with self._lock:
            if self._running:
                report = self._session_report()
                print(f"[Engine] Biomerich stopped. Session time: {report}")
            self._running = False
            self._start_ts = None
            self._thread = None
            self._states.clear()

        webhooks.macro_stopped(self._all_active_urls(), report, self._current_version())
        return {"ok": True, "running": False}

    def _session_report(self) -> str:
        secs = self.uptime
        return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"

    # --------------------------------------------------- State / Routing
    def _routed_account_ids(self):
        return {
            aid
            for w in self.config.webhooks if w.get("active", True)
            for aid in w.get("routedAccounts", [])
        }

    def _tracked_accounts(self):
        ids = self._routed_account_ids()
        return [a for a in self.config.accounts if a.get("id") in ids]

    def _tracked_account_names(self):
        return [a.get("name", "?") for a in self._tracked_accounts()]

    def _all_active_urls(self):
        seen, urls = set(), []
        for w in self.config.webhooks:
            url = (w.get("url") or "").strip()
            if w.get("active", True) and url and url not in seen:
                seen.add(url)
                urls.append(url)
        return urls
    
    def _current_version(self):
        if self.config.data.get("version"):
            return self.config.data["version"]
        return "?"

    def _urls_for_account(self, acc_id):
        seen, urls = set(), []
        for w in self.config.webhooks:
            url = (w.get("url") or "").strip()
            if w.get("active", True) and url and acc_id in w.get("routedAccounts", []):
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
        return urls

    def _account_by_id(self, acc_id):
        return next((a for a in self.config.accounts if a.get("id") == acc_id), None)

    def _build_states(self):
        self._states.clear()
        tracked = self._tracked_accounts()
        usernames = [a.get("name", "") for a in tracked]
        log_map = roblox_logs.match_logs_to_usernames(usernames)

        for acc in tracked:
            uname = (acc.get("name") or "").strip().lower()
            st = _AccountState(acc.get("id"), uname)
            log_file = log_map.get(uname)
            if log_file:
                st.reader = roblox_logs.LogReader(log_file)
                st.online = True
            self._states[acc.get("id")] = st

    # ----------------------------------------------------- tracking loop
    def _tracker_loop(self):
        rescan_counter = 0
        while self._running:
            rescan_counter += 1
            if rescan_counter >= 15:
                rescan_counter = 0
                self._rescan_missing_logs()

            with self._lock:
                states = list(self._states.values())

            for st in states:
                if not st.reader:
                    continue
                lines = st.reader.read_new_lines()
                if not lines:
                    continue
                st.last_line_ts = time.time()
                for line in lines:
                    self._process_line(st, line)
            time.sleep(1)

    def _rescan_missing_logs(self):
        missing = [s for s in self._states.values() if not s.reader]
        if not missing:
            return
        usernames = [s.username for s in missing]
        log_map = roblox_logs.match_logs_to_usernames(usernames)
        for st in missing:
            log_file = log_map.get(st.username)
            if log_file:
                st.reader = roblox_logs.LogReader(log_file)
                st.online = True
                print(f"[Engine] Log for '{st.username}' found: {log_file}")

    def _process_line(self, st, line):
        if roblox_logs.line_is_disconnect(line):
            if st.online:
                st.online = False
                acc = self._account_by_id(st.acc_id)
                webhooks.roblox_disconnected(self._urls_for_account(st.acc_id), acc, self._current_version())
                print(f"[Engine] Disconnect detected for '{st.username}'.")
            return

        biome_key = biomes.biome_from_rpc_line(line)
        if not biome_key:
            return
        if biome_key == st.current_biome:
            return

        old_biome = st.current_biome
        st.current_biome = biome_key
        st.online = True

        acc = self._account_by_id(st.acc_id)
        urls = self._urls_for_account(st.acc_id)

        report = "00:00:00"
        if self._running:
            report = self._session_report()

        if old_biome and old_biome != "normal":
            webhooks.biome_ended(urls, acc, old_biome, report, self._current_version())

        if biome_key == "normal":
            print(f"[Engine] '{st.username}' back in Normal. Sent biome_ended for '{old_biome}'.")
            return

        if biomes.is_unknown(biome_key):
            name = biomes.unknown_name(biome_key)
            self.config.increment_unknown(name)
            webhooks.biome_started(urls, acc, biome_key, report, self._current_version(), unknown=True)
            print(f"[Engine] '{st.username}' detected UNKNOWN biome: '{name}'.")
            return

        # Bekanntes Biome.
        self.config.increment_biome(biome_key)
        webhooks.biome_started(urls, acc, biome_key, report, self._current_version())

    # ----------------------------------------------------------- Avatar
    @staticmethod
    def get_roblox_avatar(username: str) -> str:
        username = (username or "").strip()
        if not username:
            return ""
        try:
            r = requests.post(
                "https://users.roblox.com/v1/usernames/users",
                json={"usernames": [username], "excludeBannedUsers": True},
                timeout=10,
            )
            data = r.json().get("data", [])
            if not data:
                return ""
            user_id = data[0]["id"]
            t = requests.get(
                "https://thumbnails.roblox.com/v1/users/avatar-headshot",
                params={"userIds": user_id, "size": "150x150",
                        "format": "Png", "isCircular": "false"},
                timeout=10,
            )
            tdata = t.json().get("data", [])
            if tdata and tdata[0].get("imageUrl"):
                return tdata[0]["imageUrl"]
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"[Avatar] Could not load avatar for '{username}': {e}")
        return ""
