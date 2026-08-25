import os
import time
import threading
from urllib.parse import urlparse

import requests

from . import activity_log, biomes, monitor_dim, roblox_logs, webhooks, win_windows, status_events
from .anti_afk import AntiAfk
from .automation import AutomationEngine
from .time_tracking import TimeTracker

def _is_roblox_link(link: str) -> bool:
    try:
        url = link.strip()
        if "://" not in url:
            url = "https://" + url
        host = (urlparse(url).hostname or "").lower()
        return host == "roblox.com" or host.endswith(".roblox.com")
    except Exception:
        return False

FAKE_PING_WINDOW = 12.0

class _AccountState:
    __slots__ = ("acc_id", "username", "reader", "current_biome", "biome_since",
                 "online", "last_line_ts", "disconnect_ts", "was_disconnected",
                 "blocked_biome", "blocked_ping_id")

    def __init__(self, acc_id, username):
        self.acc_id = acc_id
        self.username = username
        self.reader = None
        self.current_biome = None
        self.biome_since = None
        self.online = False
        self.last_line_ts = 0.0
        self.disconnect_ts = 0.0
        self.was_disconnected = False
        self.blocked_biome = None
        self.blocked_ping_id = None

class MacroEngine:
    def __init__(self, config):
        self.config = config
        self._running = False
        self._thread = None
        self._start_ts = None
        self._logging_active = False
        self._lock = threading.RLock()
        self._states = {}
        self.anti_afk = AntiAfk(config, lambda: self._running)
        self.automation = AutomationEngine(config, lambda: self._running, self.anti_afk)
        self.automation.engine = self
        self.time = TimeTracker(config)
        self._runtime_cache = []
        self._runtime_ts = 0.0
        self._pending_rare_pings = {}
        self._rare_ping_seq = 0
        self.rare_ping_notifier = None
        self.rare_ping_resolver = None

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
                {"id": s.acc_id, "currentBiome": s.current_biome,
                 "biomeSince": s.biome_since, "online": s.online}
                for s in self._states.values()
            ]

    def biome_for(self, acc_id):
        
        with self._lock:
            for s in self._states.values():
                if s.acc_id == acc_id:
                    return s.current_biome
        return None

    def account_runtime(self) -> list:
        now = time.time()
        if not self._running:
            self._runtime_cache = [
                {"id": a.get("id"), "online": False, "currentBiome": None,
                 "window": None, "hwndKnown": False}
                for a in self.config.accounts
            ]
            self._runtime_ts = now
            return self._runtime_cache
        if (now - self._runtime_ts) < 2.5 and self._runtime_cache:
            return self._runtime_cache

        try:
            resolved = win_windows.resolve_accounts(self.config.enabled_accounts())
        except Exception as e:
            print(f"[Engine] Window resolve failed: {e}")
            resolved = {}

        with self._lock:
            log_states = {s.acc_id: s for s in self._states.values()}

        out = []
        for a in self.config.accounts:
            aid = a.get("id")
            if not a.get("enabled", True):
                out.append({"id": aid, "online": False, "currentBiome": None,
                            "window": None, "hwndKnown": False})
                continue
            info = resolved.get(aid, {})
            st = log_states.get(aid)
            online = bool(info.get("online")) or bool(st and st.online)
            out.append({
                "id": aid,
                "online": online,
                "currentBiome": st.current_biome if st else None,
                "biomeSince": st.biome_since if st else None,
                "window": info.get("label"),
                "hwndKnown": info.get("hwnd") is not None,
            })
        self._runtime_cache = out
        self._runtime_ts = now
        return out

    def logging_enabled(self) -> bool:

        return True

    def logging_requirements_met(self) -> bool:
        accounts = self.config.enabled_accounts()
        webhook_list = self.config.webhooks
        if not accounts or not webhook_list:
            return False
        if not any(
            w.get("active", True) and (w.get("url") or "").strip()
            for w in webhook_list
        ):
            return False
        enabled_ids = {account.get("id") for account in accounts}
        return enabled_ids.issubset(self._routed_account_ids())

    def active_modules(self) -> list:
        auto = self.config.automation
        mode = auto.get("mode")
        mods = []
        if self.logging_enabled():
            mods.append("biomeLogging")
        if self.config.settings.get("ramTrimEnabled"):
            mods.append("ramTrim")
        if mode == "automation":
            if auto.get("strangeController"):
                mods.append("strangeController")
            if auto.get("biomeRandomizer"):
                mods.append("biomeRandomizer")
            fishing = auto.get("fishing") or {}
            if fishing.get("enabled") or fishing.get("moduleEnabled"):
                mods.append("fishing")
        elif mode == "eden":
            mods.append("eden")
            if auto.get("strangeController"):
                mods.append("strangeController")
            if auto.get("biomeRandomizer"):
                mods.append("biomeRandomizer")
        else:
            if self.config.settings.get("antiAfkEnabled"):
                mods.append("antiAfk")
        return mods

    def _validate_logging(self) -> list:
        errors = []
        accounts = self.config.enabled_accounts()
        webhook_list = self.config.webhooks

        if not accounts:
            errors.append("Biome Logging is on but you have no enabled account.")

        if not webhook_list:
            errors.append("Biome Logging is on but you haven't added a webhook.")
        else:
            for w in webhook_list:
                if not (w.get("url") or "").strip():
                    errors.append(f"Webhook '{w.get('name') or '?'}' has no valid URL.")

        routed_ids = self._routed_account_ids()
        missing_routes = [
            account.get("name") or "?"
            for account in accounts
            if account.get("id") not in routed_ids
        ]
        if webhook_list and missing_routes:
            names = ", ".join(f"'{name}'" for name in missing_routes)
            errors.append(
                "Biome Logging needs an active webhook route for every enabled "
                f"account. Missing: {names}. Open Webhooks and select each missing "
                "account under 'Route to accounts'."
            )

        for a in accounts:
            link = (a.get("link") or "").strip()
            name = a.get("name") or "?"
            if not link:
                errors.append(f"Account '{name}' is missing its Private Server link.")
            elif not _is_roblox_link(link):
                errors.append(f"The Private Server link for '{name}' isn't a valid roblox.com link.")

        return errors

    def validate(self) -> list:
        errors = []
        if not self.active_modules():
            errors.append("Turn on at least one module before you start.")
        if self.logging_enabled():
            errors.extend(self._validate_logging())
        enabled_accounts = self.config.enabled_accounts()
        if enabled_accounts:
            try:
                resolved = win_windows.resolve_accounts(enabled_accounts)
                if len(enabled_accounts) > 1:
                    missing = [
                        account.get("name") or "?"
                        for account in enabled_accounts
                        if (resolved.get(account.get("id")) or {}).get("hwnd") is None
                    ]
                    if missing:
                        names = ", ".join(f"'{name}'" for name in missing)
                        errors.append(
                            "Bind a Roblox window to every enabled account before starting "
                            f"Multi-Macro. Missing: {names}. Open the Macro tab, press Bind "
                            "Window for each account, then click its matching Roblox window."
                        )
                elif not any((info or {}).get("hwnd") is not None for info in resolved.values()):
                    errors.append(
                        "No Roblox window found. Launch your account first, or press "
                        "Bind Window in the Macro tab and click its Roblox window."
                    )
            except Exception:
                if len(enabled_accounts) > 1:
                    errors.append(
                        "Could not verify the Roblox window bindings. Open the Macro tab and "
                        "bind a window to every enabled account before starting Multi-Macro."
                    )
        auto = self.config.automation
        if auto.get("mode") == "automation":
            if (auto.get("strangeController") or auto.get("biomeRandomizer")
                    or auto.get("merchantTeleporter")) and not self.automation.pixels_ready():
                errors.append("Finish the Inventory calibration before starting. "
                              "Set all click points in the Calibration tab.")
            _fishing = auto.get("fishing") or {}
            if (_fishing.get("enabled") or _fishing.get("moduleEnabled")) and not self.automation.fishing.ready():
                errors.append("Finish the Fishing calibration before starting. "
                              "Set the 7 core click points in the Calibration tab.")
        if auto.get("mode") == "eden":
            eden = auto.get("eden") or {}
            effective_eden_account = (
                self.config.effective_eden_account_id()
                if hasattr(self.config, "effective_eden_account_id")
                else eden.get("account")
            )
            if effective_eden_account is None:
                errors.append("Eden mode is on but you haven't picked a main Eden account.")
            if self.automation._eden_click_point() is None:
                errors.append("Eden mode needs the Eden Click Point — set it under "
                              "Eden Calibrations in the Calibration tab.")
            if (auto.get("strangeController") or auto.get("biomeRandomizer")) \
                    and not self.automation.pixels_ready():
                errors.append("Strange Controller / Biome Randomizer are enabled but the "
                              "Inventory calibration is incomplete.")
        try:
            if self.automation.autopop.amount_region_required_missing():
                errors.append("Auto Pop still needs its Amount Scan Region. "
                              "Set it in the Auto Pop settings or under "
                              "Inventory Calibrations.")
        except Exception:
            pass
        return errors

    def start(self) -> dict:
        with self._lock:
            if self._running:
                return {"ok": True, "errors": [], "running": True, "uptime": self.uptime}

            errors = self.validate()
            if errors:
                return {"ok": False, "errors": errors, "running": False}

            self._running = True
            self._start_ts = time.time()
            self._logging_active = self.logging_enabled()
            self.config.reset_module_session_stats()

            if self._logging_active:
                self._build_states()

            self._sync_subsystems()
            self.time.start(self.config.automation.get("mode"))
            activity_log.reset()
            if self.config.settings.get("monitorDimEnabled"):
                try:
                    monitor_dim.start(self.config.settings.get("monitorDimLevel", 40))
                except Exception as e:
                    print(f"[MonitorDim] start failed: {e}")
            print("[Engine] SolRich started.")

        if self._logging_active:
            webhooks.macro_started(self._all_active_urls(), self._tracked_account_names(), self._current_version())
            self._bootstrap_current_biomes()



            with self._lock:
                if self._running and self._logging_active:
                    self._thread = threading.Thread(target=self._tracker_loop, daemon=True)
                    self._thread.start()
        return {"ok": True, "errors": [], "running": True, "uptime": 0}

    def stop(self) -> dict:
        report = "00:00:00"
        self.anti_afk.stop()
        self.automation.stop()
        self.time.stop()
        status_events.reset()
        monitor_dim.stop()
        with self._lock:
            was_running = self._running
            was_logging = self._logging_active
            if was_running:
                report = self._session_report()
                print(f"[Engine] SolRich stopped. Session time: {report}")
            self._running = False
            self._start_ts = None
            self._logging_active = False
            self._thread = None
            self._states.clear()
            pending_ids = list(self._pending_rare_pings)
            self._pending_rare_pings.clear()

        for pending_id in pending_ids:
            self._notify_rare_ping_resolved(pending_id)

        if was_running and was_logging:
            webhooks.macro_stopped(self._all_active_urls(), report, self._current_version())
        self._afk_reconcile()
        return {"ok": True, "running": False}

    def _session_report(self) -> str:
        secs = self.uptime
        return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"

    def _routed_account_ids(self):
        return {
            aid
            for w in self.config.webhooks
            if w.get("active", True) and (w.get("url") or "").strip()
            for aid in w.get("routedAccounts", [])
        }

    def _tracked_accounts(self):
        ids = self._routed_account_ids()
        return [a for a in self.config.enabled_accounts() if a.get("id") in ids]

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
        log_map = roblox_logs.match_logs_to_usernames(
            usernames, include_inactive=False
        )

        for acc in tracked:
            uname = (acc.get("name") or "").strip().lower()
            st = _AccountState(acc.get("id"), uname)
            log_file = log_map.get(uname)
            if log_file:
                st.reader = roblox_logs.LogReader(log_file)
                st.online = True
            self._states[acc.get("id")] = st

    def _bootstrap_current_biomes(self):
        
        with self._lock:
            states = list(self._states.values())
        for st in states:
            self._bootstrap_current_biome(st)

    def _bootstrap_current_biome(self, st, respect_fake_guard=False):
        if not st.reader:
            return
        biome_key = roblox_logs.latest_biome(st.reader.path)
        if not biome_key:
            return
        if st.blocked_biome:
            if biome_key == st.blocked_biome:
                return
            self._expire_blocked_ping(st)
        if biome_key == st.current_biome:
            return

        acc = self._account_by_id(st.acc_id)
        urls = self._urls_for_account(st.acc_id)
        if (
            respect_fake_guard
            and self._fake_ping_guard_on()
            and biomes.is_rare_ping(biome_key)
            and st.disconnect_ts
            and (time.time() - st.disconnect_ts) <= FAKE_PING_WINDOW
        ):
            self._block_rare_ping(st, acc, biome_key, urls)
            return

        st.current_biome = biome_key
        st.biome_since = time.time()
        st.online = True
        if biome_key == "normal":
            return

        report = self._session_report() if self._running else "00:00:00"
        if biomes.is_unknown(biome_key):
            self.config.increment_unknown(biomes.unknown_name(biome_key))
            webhooks.biome_started(
                urls, acc, biome_key, report, self._current_version(), unknown=True
            )
        else:
            self.config.increment_biome(biome_key, st.acc_id)
            webhooks.biome_started(
                urls,
                acc,
                biome_key,
                report,
                self._current_version(),
                ping_content=self.config.biome_ping_content(biome_key),
            )
        acc_name = (acc or {}).get("name") or st.username
        activity_log.push(
            f"{acc_name} started in {biomes.display_name(biome_key)}",
            account=acc_name,
            kind="biome",
            biome=biome_key,
        )
        print(
            f"[Engine] '{st.username}' was already in "
            f"'{biome_key}' at macro start; sent biome_started."
        )

    def _tracker_loop(self):
        rescan_counter = 0
        while self._running:


            try:
                rescan_counter += 1
                if rescan_counter >= 3:
                    rescan_counter = 0
                    self._rescan_logs()

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
                        try:
                            self._process_line(st, line)
                        except Exception as e:
                            print(f"[Engine] Failed to process log line for '{st.username}': {e}")
            except Exception as e:
                print(f"[Engine] Tracker loop error (recovering): {e}")
            time.sleep(1)

    def _rescan_logs(self):
        
        states = list(self._states.values())
        if not states:
            return
        usernames = [s.username for s in states]
        log_map = roblox_logs.match_logs_to_usernames(
            usernames, include_inactive=False
        )
        for st in states:
            log_file = log_map.get(st.username)
            if not log_file:
                continue
            old_path = st.reader.path if st.reader else None
            if old_path and os.path.normcase(old_path) == os.path.normcase(log_file):
                continue
            st.reader = roblox_logs.LogReader(log_file)
            st.online = True
            action = "switched" if old_path else "found"
            print(f"[Engine] Log for '{st.username}' {action}: {log_file}")
            self._bootstrap_current_biome(st, respect_fake_guard=True)

    def _fake_ping_guard_on(self) -> bool:
        return bool(self.config.settings.get("fakePingGuard", True))

    def _notify_rare_ping_resolved(self, pending_id):
        callback = self.rare_ping_resolver
        if callable(callback):
            try:
                callback(pending_id)
            except Exception as e:
                print(f"[Engine] Rare-ping resolve callback failed: {e}")

    def _expire_blocked_ping(self, st):
        pending_id = st.blocked_ping_id
        if pending_id:
            with self._lock:
                self._pending_rare_pings.pop(pending_id, None)
            self._notify_rare_ping_resolved(pending_id)
        st.blocked_biome = None
        st.blocked_ping_id = None

    def _block_rare_ping(self, st, acc, biome_key, urls):
        st.blocked_biome = biome_key
        webhooks.fake_rare_ping(urls, acc, self._current_version())
        if self.config.settings.get("fakePingPrompt", True):
            with self._lock:
                self._rare_ping_seq += 1
                pending_id = f"rare-{self._rare_ping_seq}-{time.time_ns()}"
                self._pending_rare_pings[pending_id] = {
                    "accountId": st.acc_id,
                    "biome": biome_key,
                }
            st.blocked_ping_id = pending_id
            callback = self.rare_ping_notifier
            if callable(callback):
                try:
                    callback({
                        "id": pending_id,
                        "account": (acc or {}).get("name") or st.username,
                    })
                except Exception as e:
                    print(f"[Engine] Rare-ping warning callback failed: {e}")
        print(
            f"[Engine] Suppressed fake '{biome_key}' ping for "
            f"'{st.username}' (just after disconnect)."
        )

    def confirm_blocked_rare_ping(self, pending_id):
        with self._lock:
            pending = self._pending_rare_pings.pop(str(pending_id), None)
            st = self._states.get(pending.get("accountId")) if pending else None
        if not pending or not st or st.blocked_ping_id != str(pending_id):
            return {"ok": False, "error": "expired"}

        biome_key = pending["biome"]
        acc = self._account_by_id(st.acc_id)
        webhooks.biome_started(
            self._urls_for_account(st.acc_id),
            acc,
            biome_key,
            self._session_report(),
            self._current_version(),
            ping_content="@everyone",
        )
        st.current_biome = biome_key
        st.biome_since = time.time()
        st.online = True
        st.was_disconnected = False
        st.disconnect_ts = 0.0
        st.blocked_biome = None
        st.blocked_ping_id = None
        self._notify_rare_ping_resolved(str(pending_id))
        print(f"[Engine] User manually approved blocked '{biome_key}' ping.")
        return {"ok": True}

    def dismiss_blocked_rare_ping(self, pending_id):
        with self._lock:
            pending = self._pending_rare_pings.pop(str(pending_id), None)
            st = self._states.get(pending.get("accountId")) if pending else None
        if st and st.blocked_ping_id == str(pending_id):
            st.blocked_ping_id = None
        self._notify_rare_ping_resolved(str(pending_id))
        return {"ok": bool(pending)}

    def _process_line(self, st, line):
        if roblox_logs.line_is_disconnect(line):
            if st.online:
                st.online = False
                st.disconnect_ts = time.time()
                st.was_disconnected = True
                acc = self._account_by_id(st.acc_id)
                webhooks.roblox_disconnected(self._urls_for_account(st.acc_id), acc, self._current_version())
                print(f"[Engine] Disconnect detected for '{st.username}'.")
            return

        biome_key = biomes.biome_from_rpc_line(line)
        if not biome_key:
            return

        if st.blocked_biome:
            if biome_key == st.blocked_biome:
                return
            self._expire_blocked_ping(st)

        acc = self._account_by_id(st.acc_id)
        urls = self._urls_for_account(st.acc_id)

        if (self._fake_ping_guard_on()
                and biomes.is_rare_ping(biome_key)
                and st.disconnect_ts
                and (time.time() - st.disconnect_ts) <= FAKE_PING_WINDOW):
            self._block_rare_ping(st, acc, biome_key, urls)
            return

        if st.was_disconnected:
            webhooks.roblox_reconnected(urls, acc, self._current_version())
            st.was_disconnected = False
            st.disconnect_ts = 0.0
            st.online = True
            print(f"[Engine] Reconnect detected for '{st.username}'.")

        if biome_key == st.current_biome:
            return

        old_biome = st.current_biome
        st.current_biome = biome_key
        st.biome_since = time.time()
        st.online = True

        if biome_key != "normal":
            acc_name = (acc or {}).get("name") or st.username
            activity_log.push(f"{acc_name} rolled {biomes.display_name(biome_key)}",
                              account=acc_name, kind="biome", biome=biome_key)

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
            try:
                self.automation.queue_autopop(st.acc_id, biome_key)
            except Exception as e:
                print(f"[Engine] Auto Pop queue failed: {e}")
            return

        self.config.increment_biome(biome_key, st.acc_id)
        webhooks.biome_started(urls, acc, biome_key, report, self._current_version(),
                               ping_content=self.config.biome_ping_content(biome_key))
        try:
            self.automation.queue_autopop(st.acc_id, biome_key)
        except Exception as e:
            print(f"[Engine] Auto Pop queue failed: {e}")

    def _sync_subsystems(self):
        self.automation.sync()
        self._afk_reconcile()

    def _afk_reconcile(self):
        
        auto_active = self._running and self.config.automation.get("mode") in ("automation", "eden")
        standalone = bool(self.config.settings.get("antiAfkStandalone", False))
        if self.anti_afk.enabled() and not auto_active and (self._running or standalone):
            self.anti_afk.start()
        else:
            self.anti_afk.stop()

    def refresh_anti_afk(self):
        
        self._afk_reconcile()

    def set_automation_mode(self, mode):
        allowed = ("automation", "eden")
        mode = mode if mode in allowed else "idle"
        self.config.set_automation("mode", mode)
        if self._running:
            self.time.note_mode_change(mode)
        self._sync_subsystems()
        return mode

    def current_module(self) -> dict:
        if not self._running:
            return {"key": "offline", "label": "Offline", "phase": ""}
        mode = self.config.automation.get("mode")
        if mode == "automation":
            act = self.automation.current_action
            acc = self.automation.current_account or ""
            if act == "autopop":
                return {"key": "autopop", "label": "Auto Pop",
                        "phase": self.automation.autopop.phase, "account": acc}
            if act == "fishing":
                return {"key": "fishing", "label": "Fishing",
                        "phase": self.automation.fishing.phase, "account": acc}
            if act == "strangeController":
                return {"key": "strangeController", "label": "Strange Controller", "phase": "", "account": acc}
            if act == "biomeRandomizer":
                return {"key": "biomeRandomizer", "label": "Biome Randomizer", "phase": "", "account": acc}
            if act == "merchantTeleporter":
                return {"key": "merchantTeleporter", "label": "Merchant Detection", "phase": "", "account": acc}
            if act == "antiAfk":
                return {"key": "antiAfk", "label": "Anti-AFK", "phase": "", "account": ""}
            return {"key": "waiting", "label": "Standby", "phase": "", "account": ""}
        if mode == "eden":
            act = self.automation.current_action
            acc = self.automation.current_account or ""
            labels = {
                "eden": "Eden", "strangeController": "Strange Controller",
                "biomeRandomizer": "Biome Randomizer", "merchantTeleporter": "Merchant Detection",
                "antiAfk": "Anti-AFK",
            }
            if act in labels:
                return {"key": "eden", "label": labels[act], "phase": "", "account": acc}
            return {"key": "eden", "label": "Eden", "phase": "", "account": ""}
        if self.config.settings.get("antiAfkEnabled"):
            return {"key": "antiAfk", "label": "Anti-AFK", "phase": ""}
        if self.logging_enabled():
            return {"key": "biomeLogging", "label": "Monitoring", "phase": ""}
        return {"key": "idle", "label": "Idle", "phase": ""}

    @staticmethod
    def get_roblox_profiles(usernames) -> dict:
        
        requested = [str(name or "").strip() for name in usernames]
        requested = list(dict.fromkeys(name for name in requested if name))
        if not requested:
            return {}
        try:
            r = requests.post(
                "https://users.roblox.com/v1/usernames/users",
                json={"usernames": requested, "excludeBannedUsers": True},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json().get("data", [])
            profiles = {}
            for entry in data:
                lookup_name = entry.get("requestedUsername") or entry.get("name") or ""
                if lookup_name:
                    profiles[lookup_name.casefold()] = {
                        "id": entry.get("id"),
                        "name": entry.get("name", ""),
                        "displayName": entry.get("displayName", ""),
                    }
            return profiles
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"[Profile] Could not resolve Roblox users: {e}")
            return {}

    @staticmethod
    def get_roblox_profile(username: str) -> dict:
        username = (username or "").strip()
        profiles = MacroEngine.get_roblox_profiles([username])
        profile = profiles.get(username.casefold())
        if not profile or not profile.get("id"):
            return {}
        profile = dict(profile)
        profile["avatar"] = ""
        try:
            user_id = profile["id"]
            t = requests.get(
                "https://thumbnails.roblox.com/v1/users/avatar-headshot",
                params={"userIds": user_id, "size": "150x150",
                        "format": "Png", "isCircular": "false"},
                timeout=10,
            )
            tdata = t.json().get("data", [])
            if tdata and tdata[0].get("imageUrl"):
                profile["avatar"] = tdata[0]["imageUrl"]
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"[Avatar] Could not load avatar for '{username}': {e}")
        return profile

    @staticmethod
    def get_roblox_avatar(username: str) -> str:
        return MacroEngine.get_roblox_profile(username).get("avatar", "")
