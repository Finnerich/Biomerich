import os
import threading
import time

from . import decision_trace, win_input, win_pixel, fishing_presets, ocr, status_events, webhooks
from .anti_afk import focus_roblox

WHITE = (255, 255, 255)
REEL_POLL = 0.015
STRIP_BAND = 16
BITE_TOLERANCE = 12
REEL_TOLERANCE = 35
REEL_WARM_TOL = 65
REEL_DURATION = 9.0
BITE_TIMEOUT = 60.0
NO_BITE_TIMEOUT = 45.0
OVERLAY_MAX_R = 80
OVERLAY_MIN_B = 140
CENTER_DEAD_ZONE = 20

FAILED_TEXT = "Fishing Failed"
CAUGHT_TEXT = "Fish Caught"
SHOP_NAME_TARGET = "Captain Flarg"
SHOP_WAIT = 0.6
OCR_TEXT_THRESHOLD = 0.6


def _median_color(pixel_samples, fallback=WHITE):
    
    if not pixel_samples:
        return fallback

    middle_index = len(pixel_samples) // 2
    return tuple(
        sorted(pixel[channel] for pixel in pixel_samples)[middle_index]
        for channel in range(3)
    )


class FishingEngine:
    

    def __init__(self, config):
        self.config = config
        self._lock = threading.Lock()
        self.catch_count = 0
        self.sell_count = 0
        self.total_caught = 0
        self.phase = "idle"
        self._session_start = time.time()
        self._active_account = None
        self._active_account_id = None
        self._module_active = False
        self._primed_account_ids = set()
        self._rotation_index = 0
        self._rotation_started_at = None
        self._decision_last = {}





    def _fishing_config(self):
        automation_config = self.config.data.setdefault("automation", {})
        return automation_config.setdefault("fishing", {})

    def enabled(self):
        return (
            self._module_active
            or bool(self._fishing_config().get("enabled", False))
            or self.cycle_enabled()
        )

    def _configured_pixels(self):
        return self._fishing_config().get("pixels", {}) or {}

    def _point(self, slot):
        position = self._configured_pixels().get(slot)
        if isinstance(position, (list, tuple)) and len(position) == 2:
            return int(position[0]), int(position[1])
        return None

    def _configured_regions(self):
        return self._fishing_config().get("regions", {}) or {}

    def _region(self, name):
        region = self._configured_regions().get(name)
        if isinstance(region, (list, tuple)) and len(region) == 4:
            return tuple(int(value) for value in region)
        return None

    def _ocr_failsafe_enabled(self, name):
        failsafe_config = self.config.automation.get("ocrFailsafe", {})
        if isinstance(failsafe_config, dict):
            return bool(failsafe_config.get(name, False))
        return False

    def _current_account_id(self):
        
        if self._active_account_id is not None:
            return self._active_account_id
        return self._fishing_config().get("account")

    def _active_account_config(self):
        
        account_id = self._current_account_id()
        if account_id is None:
            return {}

        account_config = (self._fishing_config().get("accounts") or {}).get(
            str(account_id)
        )
        return account_config if isinstance(account_config, dict) else {}

    def _account_int(self, key, default):
        try:
            return int(self._active_account_config().get(key, default))
        except (TypeError, ValueError):
            return int(default)

    def _acc_int(self, key, default):
        
        return self._account_int(key, default)

    def _fishing_int(self, key, default):
        try:
            return int(self._fishing_config().get(key, default))
        except (TypeError, ValueError):
            return int(default)

    def _slow_reset_enabled(self):
        
        return bool(self.config.settings.get("slowReset", False))





    def schedule(self):
        
        raw_schedule = self._fishing_config().get("schedule")
        if not isinstance(raw_schedule, list):
            return []

        enabled_account_ids = {
            account.get("id")
            for account in self.config.accounts
            if account.get("enabled", True)
        }
        schedule_entries = []

        for raw_entry in raw_schedule:
            if not isinstance(raw_entry, dict):
                continue

            account_id = raw_entry.get("accId")
            if account_id is None or account_id not in enabled_account_ids:
                continue

            try:
                duration_minutes = max(1, int(raw_entry.get("minutes", 30)))
            except (TypeError, ValueError):
                duration_minutes = 30

            schedule_entries.append({"accId": account_id, "minutes": duration_minutes})

        return schedule_entries

    def rotation_account(self):
        
        schedule = self.schedule()
        if not schedule:
            self._rotation_started_at = None
            self._active_account_id = None
            return None

        now = time.monotonic()
        if self._rotation_started_at is None or self._rotation_index >= len(schedule):
            self._rotation_index = 0
            self._rotation_started_at = now

        active_entry = schedule[self._rotation_index]
        if now - self._rotation_started_at >= active_entry["minutes"] * 60:
            self._rotation_index = (self._rotation_index + 1) % len(schedule)
            self._rotation_started_at = now
            active_entry = schedule[self._rotation_index]

        return active_entry["accId"]

    def rotation_status(self):
        
        schedule = self.schedule()
        if (
            not schedule
            or self._rotation_started_at is None
            or self._rotation_index >= len(schedule)
        ):
            return {
                "accId": None,
                "remaining": 0,
                "index": -1,
                "total": len(schedule),
            }

        active_entry = schedule[self._rotation_index]
        elapsed_seconds = time.monotonic() - self._rotation_started_at
        remaining_seconds = int(active_entry["minutes"] * 60 - elapsed_seconds)

        return {
            "accId": active_entry["accId"],
            "remaining": max(0, remaining_seconds),
            "index": self._rotation_index,
            "total": len(schedule),
        }

    def ready(self):
        return not self._missing_required_slots()

    def _missing_required_slots(self):
        required_slots = (
            "cast_point",
            "bite_indicator",
            "bar_sample",
            "zone_left",
            "zone_right",
            "reel_click",
            "claim_button",
        )
        return [slot for slot in required_slots if self._point(slot) is None]

    def _decision_account(self):
        active_account = getattr(self, "_active_account", None)
        account = active_account if isinstance(active_account, dict) else {}
        account_id = getattr(self, "_active_account_id", None)
        if account_id is None:
            account_id = account.get("id")
        return account.get("name") or "Fishing account", account_id

    def _fishing_next_step(self, label="Open Fishing Settings"):
        _name, account_id = self._decision_account()
        result = {"label": label, "tab": "modules", "drawer": "fishing"}
        if account_id is not None:
            result["accountId"] = account_id
        return result

    def _push_fishing_decision(self, text, kind, decision, *, dedupe_key=None,
                               cooldown=20.0):
        
        if dedupe_key:
            now = time.monotonic()
            recent = getattr(self, "_decision_last", None)
            if not isinstance(recent, dict):
                recent = {}
                self._decision_last = recent
            if now - float(recent.get(dedupe_key, 0.0)) < cooldown:
                return False
            recent[dedupe_key] = now
        account_name, account_id = self._decision_account()
        status_events.push_event(
            text, kind=kind, ttl=5.0, account=account_name,
            account_id=account_id, category="fishing", decision=decision,
        )
        return True

    def reset(self):
        with self._lock:
            self.catch_count = 0
            self.sell_count = 0
            self.total_caught = 0
            self.phase = "idle"
            self._session_start = time.time()
            self._primed_account_ids = set()
            self._active_account_id = None
            self._rotation_index = 0
            self._rotation_started_at = None
            self._decision_last = {}

    def status(self):
        return {
            "caught": self.total_caught,
            "sinceSell": self.catch_count,
            "sells": self.sell_count,
        }

    def _cycle_config(self):
        automation_config = self.config.data.setdefault("automation", {})
        cycle_config = automation_config.setdefault("cycle", {})
        cycle_config.setdefault("steps", [])
        cycle_config.setdefault("enabled", False)

        limbo_config = cycle_config.setdefault("limbo", {})
        if not isinstance(limbo_config.get("accounts"), dict):
            limbo_config["accounts"] = {}

        return cycle_config

    def cycle_enabled(self):
        return False

    def cycle_steps(self):
        
        raw_steps = self._cycle_config().get("steps")
        if not isinstance(raw_steps, list):
            return []

        enabled_account_ids = {
            account.get("id")
            for account in self.config.accounts
            if account.get("enabled", True)
        }
        cycle_steps = []

        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                continue

            account_id = raw_step.get("accId")
            if account_id is None or account_id not in enabled_account_ids:
                continue

            step_type = raw_step.get("type") or "fishing"
            sanitized_step = {"type": step_type, "accId": account_id}

            if step_type == "fishing":
                try:
                    sanitized_step["minutes"] = max(1, int(raw_step.get("minutes", 30)))
                except (TypeError, ValueError):
                    sanitized_step["minutes"] = 30
            elif step_type == "limboEden":
                sanitized_step["afk"] = bool(raw_step.get("afk", False))
                try:
                    sanitized_step["minutes"] = max(1, int(raw_step.get("minutes", 30)))
                except (TypeError, ValueError):
                    sanitized_step["minutes"] = 30

            cycle_steps.append(sanitized_step)

        return cycle_steps

    @staticmethod
    def _step_minutes(step):
        
        step_type = step.get("type")
        if step_type == "fishing":
            return step.get("minutes", 30)
        if step_type == "limboEden" and not step.get("afk"):
            return step.get("minutes", 30)
        return None

    def limbo_settings(self, account_id):
        
        account_configs = (self._cycle_config().get("limbo") or {}).get(
            "accounts"
        ) or {}
        account_config = account_configs.get(str(account_id))
        settings = {"path": "vip", "edenWatch": False, "edenInterval": 120}

        if isinstance(account_config, dict):
            if account_config.get("path"):
                settings["path"] = str(account_config["path"])
            settings["edenWatch"] = bool(account_config.get("edenWatch", False))
            try:
                settings["edenInterval"] = max(
                    30,
                    min(3600, int(account_config.get("edenInterval", 120))),
                )
            except (TypeError, ValueError):
                pass

        return settings

    def current_step(self):
        
        steps = self.cycle_steps()
        if not steps:
            self._rotation_started_at = None
            self._active_account_id = None
            return None
        now = time.monotonic()
        if self._rotation_started_at is None or self._rotation_index >= len(steps):
            self._rotation_index = 0
            self._rotation_started_at = now

        current_step = steps[self._rotation_index]
        duration_minutes = self._step_minutes(current_step)

        if (
            duration_minutes is not None
            and now - self._rotation_started_at >= duration_minutes * 60
        ):
            self._rotation_index = (self._rotation_index + 1) % len(steps)
            self._rotation_started_at = now
            current_step = steps[self._rotation_index]
            duration_minutes = self._step_minutes(current_step)

        if duration_minutes is None:
            remaining_seconds = 0
        else:
            elapsed_seconds = now - self._rotation_started_at
            remaining_seconds = int(duration_minutes * 60 - elapsed_seconds)

        return {
            **current_step,
            "remaining": max(0, remaining_seconds),
            "index": self._rotation_index,
            "total": len(steps),
        }

    def advance_step(self):
        
        steps = self.cycle_steps()
        if not steps:
            return
        self._rotation_index = (self._rotation_index + 1) % len(steps)
        self._rotation_started_at = time.monotonic()

    def cycle_status(self):
        
        steps = self.cycle_steps()
        if (
            not steps
            or self._rotation_started_at is None
            or self._rotation_index >= len(steps)
        ):
            return {
                "type": None,
                "accId": None,
                "remaining": 0,
                "index": -1,
                "total": len(steps),
                "enabled": self.cycle_enabled(),
            }

        current_step = steps[self._rotation_index]
        duration_minutes = self._step_minutes(current_step)
        if duration_minutes is None:
            remaining_seconds = 0
        else:
            elapsed_seconds = time.monotonic() - self._rotation_started_at
            remaining_seconds = int(duration_minutes * 60 - elapsed_seconds)

        return {
            "type": current_step.get("type"),
            "accId": current_step.get("accId"),
            "remaining": max(0, remaining_seconds),
            "index": self._rotation_index,
            "total": len(steps),
            "enabled": self.cycle_enabled(),
        }

    def run_path(self, steps, stop_event):
        
        try:
            for step in steps:
                if stop_event.is_set():
                    return False
                self._run_step(step, stop_event)
            return True
        finally:
            self._release_all()





    def _fishing_webhooks_enabled(self):
        return bool(self._fishing_config().get("webhookEnabled", False))

    def _active_webhook_urls(self):
        seen_urls = set()
        active_urls = []

        for webhook in self.config.webhooks or []:
            url = (webhook.get("url") or "").strip()
            if webhook.get("active", True) and url and url not in seen_urls:
                seen_urls.add(url)
                active_urls.append(url)

        return active_urls

    def _app_version(self):
        try:
            return self.config.data.get("version") or "?"
        except Exception:
            return "?"

    def _session_duration(self):
        elapsed_seconds = max(0, int(time.time() - self._session_start))
        hours = elapsed_seconds // 3600
        minutes = (elapsed_seconds % 3600) // 60
        seconds = elapsed_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _send_catch_webhook(self, catch_succeeded, total_caught, caught_since_sell):
        if not self._fishing_webhooks_enabled():
            return

        webhook_urls = self._active_webhook_urls()
        if not webhook_urls:
            return

        try:
            if catch_succeeded:
                webhooks.fish_caught(
                    webhook_urls,
                    self._active_account,
                    total_caught,
                    caught_since_sell,
                    self._session_duration(),
                    self._app_version(),
                )
            else:
                webhooks.fish_failed(
                    webhook_urls,
                    self._active_account,
                    total_caught,
                    self._session_duration(),
                    self._app_version(),
                )
        except Exception as error:
            print(f"[Fishing] Webhook send failed: {error}")

    def _failsafe_notifications_enabled(self):
        try:
            notification_config = self.config.automation.get("notifications", {}) or {}
            return bool(notification_config.get("failsafes", False))
        except Exception:
            return False

    def _send_failsafe_webhook(self, label, success, detail=""):
        if not self._failsafe_notifications_enabled():
            return

        webhook_urls = self._active_webhook_urls()
        if not webhook_urls:
            return

        try:
            webhooks.failsafe_result(
                webhook_urls,
                label,
                self._active_account,
                success,
                self._session_duration(),
                self._app_version(),
                detail=detail,
            )
        except Exception as error:
            print(f"[Fishing] Failsafe webhook failed: {error}")

    def _send_sell_route_webhook(self, route_name, shop=True):
        if not self._fishing_webhooks_enabled():
            return

        webhook_urls = self._active_webhook_urls()
        if not webhook_urls:
            return

        try:
            lifetime_catch_count = int(self.config.time_tracking().get("fishCaught", 0))
        except Exception:
            lifetime_catch_count = self.total_caught

        try:
            webhooks.sell_route(
                webhook_urls,
                self._active_account,
                route_name,
                lifetime_catch_count,
                self._session_duration(),
                self._app_version(),
                shop=shop,
            )
        except Exception as error:
            print(f"[Fishing] Sell route webhook failed: {error}")





    def _detect_catch_result(self):
        if not self._ocr_failsafe_enabled("fishingFailed"):
            return True
        if not ocr.available():
            print(
                "[Fishing] Fishing Failed failsafe ON but Tesseract not "
                "available — counting as catch."
            )
            return True
        region = self._region("fishing_failed")
        if region is None:
            print(
                "[Fishing] Fishing Failed failsafe ON but no 'Fishing Failed' "
                "region calibrated — counting as catch."
            )
            return True
        status_events.push_event("Scanning catch result…", kind="info", ttl=1.5)
        region_x, region_y, region_width, region_height = region
        text_variants = ocr.read_region_variants(
            region_x, region_y, region_width, region_height
        )
        print(
            "[Fishing][OCR] fishing_failed "
            f"region=({region_x},{region_y},{region_width}x{region_height}) | "
            f"reads: {text_variants!r}"
        )

        readable_variants = [
            text for text in text_variants if len(ocr.normalize(text)) >= 3
        ]
        if not readable_variants:
            print("[Fishing][OCR] No readable text in region — NOT counting catch.")
            self._push_fishing_decision(
                "No catch detected",
                "warn",
                decision_trace.make(
                    "skipped", "catch_ocr_unreadable", "Fishing",
                    "The catch was not counted because OCR could not read enough text from the Fishing Result region.",
                    checks=[
                        decision_trace.check("Fishing Failed failsafe is enabled", True),
                        decision_trace.check("Tesseract is available", True),
                        decision_trace.check("Fishing Result region is calibrated", True),
                        decision_trace.check("Readable result text was found", False),
                    ],
                    facts=[decision_trace.fact("OCR reads", "No readable text")],
                    next_step={"label": "Open Fishing Calibration", "tab": "calibration"},
                ),
                dedupe_key="catch_ocr_unreadable",
            )
            return False
        failed_score = 0.0
        caught_score = 0.0
        for text in text_variants:
            failed_score = max(failed_score, ocr.similarity(text, FAILED_TEXT))
            caught_score = max(caught_score, ocr.similarity(text, CAUGHT_TEXT))
        if failed_score >= OCR_TEXT_THRESHOLD and failed_score >= caught_score:
            print(
                "[Fishing][OCR] 'Fishing Failed' detected "
                f"(failed={failed_score:.2f}, caught={caught_score:.2f}) — "
                "NOT counting catch."
            )
            self._push_fishing_decision(
                "Fishing Failed",
                "bad",
                decision_trace.make(
                    "skipped", "fishing_failed_detected", "Fishing",
                    "The catch was not counted because OCR detected Fishing Failed.",
                    checks=[
                        decision_trace.check("Fishing result was readable", True),
                        decision_trace.check("Fish Caught was detected", False),
                        decision_trace.check("Catch counter was increased", False),
                    ],
                    facts=[
                        decision_trace.fact("Fishing Failed score", f"{failed_score:.0%}"),
                        decision_trace.fact("Fish Caught score", f"{caught_score:.0%}"),
                    ],
                    next_step=self._fishing_next_step(),
                ),
            )
            return False
        if caught_score >= OCR_TEXT_THRESHOLD:
            print(
                "[Fishing][OCR] 'Fish Caught' detected "
                f"(caught={caught_score:.2f}, failed={failed_score:.2f}) — "
                "counting catch."
            )
            self._push_fishing_decision(
                "Fish Caught",
                "good",
                decision_trace.make(
                    "acted", "fish_caught_detected", "Fishing",
                    "OCR detected Fish Caught, so SolRich accepted the catch and continued the fishing cycle.",
                    checks=[
                        decision_trace.check("Fishing result was readable", True),
                        decision_trace.check("Fish Caught was detected", True),
                        decision_trace.check("Catch can be counted", True),
                    ],
                    facts=[
                        decision_trace.fact("Fish Caught score", f"{caught_score:.0%}"),
                        decision_trace.fact("Fishing Failed score", f"{failed_score:.0%}"),
                    ],
                ),
            )
            return True

        print(
            "[Fishing][OCR] No clear match "
            f"(failed={failed_score:.2f}, caught={caught_score:.2f}) — "
            "NOT counting catch."
        )
        self._push_fishing_decision(
            "Catch unclear — not counting",
            "warn",
            decision_trace.make(
                "skipped", "catch_ocr_unclear", "Fishing",
                "The catch was not counted because neither Fishing Failed nor Fish Caught reached the required OCR confidence.",
                checks=[
                    decision_trace.check("Fishing result was readable", True),
                    decision_trace.check("A result reached the OCR threshold", False),
                    decision_trace.check("Catch counter was increased", False),
                ],
                facts=[
                    decision_trace.fact("Required confidence", f"{OCR_TEXT_THRESHOLD:.0%}"),
                    decision_trace.fact("Fishing Failed score", f"{failed_score:.0%}"),
                    decision_trace.fact("Fish Caught score", f"{caught_score:.0%}"),
                ],
                next_step={"label": "Open Fishing Calibration", "tab": "calibration"},
            ),
            dedupe_key="catch_ocr_unclear",
        )
        return False

    def _shop_name_ok(self):
        if not ocr.available():
            return True

        region = self._region("shop_name")
        if region is None:
            print(
                "[Fishing] Sell Fish Shop failsafe ON but no 'Shop Name' "
                "region calibrated — assuming shop OK."
            )
            return True

        status_events.push_event("Checking shop name…", kind="info", ttl=1.5)
        region_x, region_y, region_width, region_height = region
        text_variants = ocr.read_region_variants(
            region_x, region_y, region_width, region_height
        )
        best_match_score = 0.0
        for text in text_variants:
            best_match_score = max(
                best_match_score, ocr.similarity(text, SHOP_NAME_TARGET)
            )

        print(
            "[Fishing][OCR] shop_name "
            f"region=({region_x},{region_y},{region_width}x{region_height}) | "
            f"reads: {text_variants!r} | '{SHOP_NAME_TARGET}' "
            f"score={best_match_score:.2f}"
        )
        shop_name_found = best_match_score >= OCR_TEXT_THRESHOLD
        if shop_name_found:
            status_events.push_event("Captain Flarg found", kind="good", ttl=1.8)
        return shop_name_found





    def do_cycle(self, stop_event, focus_fn=None, account=None):
        self._active_account = account
        self._active_account_id = (
            (account or {}).get("id") if isinstance(account, dict) else None
        )
        missing_slots = self._missing_required_slots()
        if not win_input.IS_WINDOWS or missing_slots:
            summary = (
                "Fishing did not start because this platform cannot control the Roblox window."
                if not win_input.IS_WINDOWS
                else "Fishing did not start because required calibration points are missing."
            )
            self._push_fishing_decision(
                "Fishing did not start",
                "warn",
                decision_trace.make(
                    "blocked", "fishing_calibration_incomplete" if missing_slots else "unsupported_platform",
                    "Fishing", summary,
                    checks=[
                        decision_trace.check("Windows input control is available", win_input.IS_WINDOWS),
                        decision_trace.check("Required fishing calibration is complete", not missing_slots),
                    ],
                    facts=[
                        decision_trace.fact("Missing calibration", ", ".join(missing_slots) if missing_slots else "None"),
                    ],
                    next_step={"label": "Open Fishing Calibration", "tab": "calibration"},
                ),
                dedupe_key="fishing_not_ready", cooldown=60.0,
            )
            stop_event.wait(1.0)
            return False

        if focus_fn is not None:
            focus_fn()
        else:
            focus_roblox()

        account_config = self._active_account_config()
        prime_route = bool(account_config.get("primeRoute", False))
        sell_on_start = bool(account_config.get("sellOnStart", False))
        account_id = self._current_account_id()
        if (
            account_id is not None
            and account_id not in self._primed_account_ids
            and (prime_route or sell_on_start)
        ):
            route_name = account_config.get("route", "")
            if sell_on_start:
                print(
                    f"[Fishing] Startup sale: running complete route "
                    f"'{route_name}' before the first cast."
                )
                status_events.push_event(
                    "Clearing fish inventory before fishing…",
                    kind="info",
                    ttl=2.5,
                )
                status_events.set_detail("Selling existing fish before first cast")
                self.phase = "selling"
                sell_succeeded = self._run_sell_route(stop_event)
                if sell_succeeded:
                    with self._lock:
                        self.catch_count = 0
                        self.sell_count += 1
                if stop_event.is_set() or not self.enabled():
                    self.phase = "idle"
                    return False
            else:
                route_steps = fishing_presets.get_route(route_name)
                if route_steps:
                    print(
                        f"[Fishing] Priming route '{route_name}' — walking "
                        "without opening the shop."
                    )
                    status_events.push_event(
                        "Walking the route (no shop)…", kind="info", ttl=2.0
                    )
                    status_events.set_detail("Walking the sell route — no shop")
                    self.phase = "selling"
                    self._run_route_steps(
                        route_steps,
                        stop_event,
                        max(1, self._account_int("sellCycle", 1)),
                        skip_shop=True,
                    )
                    if stop_event.is_set() or not self.enabled():
                        self.phase = "idle"
                        return False
                else:
                    print(
                        f"[Fishing] Route prime skipped: route '{route_name}' "
                        "not found."
                    )
            self._primed_account_ids.add(account_id)

        self.phase = "casting"
        status_events.set_detail("Casting the line")

        claim_button = self._point("claim_button")
        if claim_button is not None:
            win_input.click_at(claim_button[0], claim_button[1])
            if stop_event.wait(0.3):
                self.phase = "idle"
                return False

        cast_point = self._point("cast_point")
        win_input.click_at(cast_point[0], cast_point[1])
        if stop_event.wait(0.35):
            self.phase = "idle"
            return False

        self.phase = "waiting"
        bite_result = self._wait_for_bite(stop_event)
        if bite_result != "bite":
            if bite_result == "timeout" and self._ocr_failsafe_enabled("noBite"):
                print(
                    f"[Fishing] No bite for {NO_BITE_TIMEOUT:.0f}s — "
                    "running sell route WITHOUT opening the shop."
                )
                status_events.set_detail("Running sell route — no shop")
                self._send_failsafe_webhook(
                    "No Bite Failsafe",
                    False,
                    detail=(
                        f"No bite for {NO_BITE_TIMEOUT:.0f}s — selling without shop"
                    ),
                )
                self.phase = "selling"
                route_name = account_config.get("route", "")
                route_steps = fishing_presets.get_route(route_name)
                if route_steps:
                    sell_cycles = max(1, self._account_int("sellCycle", 1))
                    self._push_fishing_decision(
                        "No bite — running sell route (no shop)",
                        "warn",
                        decision_trace.make(
                            "acted", "no_bite_failsafe_started_route", "Fishing",
                            "No bite was detected before the timeout, so the No Bite failsafe started the configured route without opening the shop.",
                            checks=[
                                decision_trace.check("No Bite failsafe is enabled", True),
                                decision_trace.check("Bite arrived before timeout", False),
                                decision_trace.check("Configured sell route was found", True),
                                decision_trace.check("Shop steps will be skipped", True),
                            ],
                            facts=[
                                decision_trace.fact("Timeout", f"{NO_BITE_TIMEOUT:.0f} seconds"),
                                decision_trace.fact("Route", route_name),
                                decision_trace.fact("Route cycles", sell_cycles),
                            ],
                            next_step=self._fishing_next_step(),
                        ),
                    )
                    self._send_sell_route_webhook(route_name, shop=False)
                    self._run_route_steps(
                        route_steps,
                        stop_event,
                        sell_cycles,
                        skip_shop=True,
                    )
                else:
                    print(
                        f"[Fishing] No-bite failsafe: route '{route_name}' "
                        "not found — skipping."
                    )
                    self._push_fishing_decision(
                        "Sell route did not run · route not found",
                        "bad",
                        decision_trace.make(
                            "failed", "sell_route_not_found", "Fishing",
                            "The No Bite failsafe wanted to run a route, but the configured sell route could not be found.",
                            checks=[
                                decision_trace.check("No Bite failsafe is enabled", True),
                                decision_trace.check("No bite timeout was reached", True),
                                decision_trace.check("Configured sell route was found", False),
                                decision_trace.check("Sell route was started", False),
                            ],
                            facts=[decision_trace.fact("Configured route", route_name or "Not selected")],
                            next_step=self._fishing_next_step(),
                        ),
                    )
            elif bite_result == "timeout":
                print(f"[Fishing] No bite for {BITE_TIMEOUT:.0f}s — recasting.")
                self._push_fishing_decision(
                    "No bite — recasting",
                    "warn",
                    decision_trace.make(
                        "acted", "bite_timeout_recast", "Fishing",
                        "No bite was detected before the timeout, so SolRich ended this attempt and will cast again.",
                        checks=[
                            decision_trace.check("Bite arrived before timeout", False),
                            decision_trace.check("No Bite sell-route failsafe is enabled", False),
                            decision_trace.check("Fishing cycle will retry", True),
                        ],
                        facts=[decision_trace.fact("Timeout", f"{BITE_TIMEOUT:.0f} seconds")],
                        next_step=self._fishing_next_step(),
                    ),
                    dedupe_key="bite_timeout_recast", cooldown=60.0,
                )
            self.phase = "idle"
            return False

        status_events.push_event("Bite! Reeling in", kind="good", ttl=1.5)
        self.phase = "reeling"
        status_events.set_detail("Reeling it in")
        self._reel(stop_event)

        if stop_event.is_set():
            self.phase = "idle"
            return False

        claim_button = self._point("claim_button")
        time.sleep(0.3)

        catch_succeeded = self._detect_catch_result()

        win_input.click_at(claim_button[0], claim_button[1])
        time.sleep(0.3)

        if catch_succeeded:
            with self._lock:
                self.catch_count += 1
                self.total_caught += 1
                caught_since_sell = self.catch_count

            try:
                lifetime_catch_count = self.config.add_fish_caught(1)
            except Exception:
                lifetime_catch_count = None

            self._send_catch_webhook(
                True,
                (
                    lifetime_catch_count
                    if lifetime_catch_count is not None
                    else self.total_caught
                ),
                caught_since_sell,
            )
        else:
            with self._lock:
                caught_since_sell = self.catch_count
            try:
                lifetime_catch_count = int(
                    self.config.time_tracking().get("fishCaught", 0)
                )
            except Exception:
                lifetime_catch_count = self.total_caught
            self._send_catch_webhook(False, lifetime_catch_count, caught_since_sell)

        if catch_succeeded and account_config.get("autoSell", False):
            sell_after = max(1, self._account_int("sellAfter", 20))
            if caught_since_sell >= sell_after:
                self.phase = "selling"
                if self._run_sell_route(stop_event):
                    with self._lock:
                        self.catch_count = 0
                        self.sell_count += 1
        self.phase = "idle"
        return True





    def _wait_for_bite(self, stop_event):
        bite_indicator = self._point("bite_indicator")
        status_events.clear_event()
        status_events.set_detail("Waiting for a bite")
        timeout = (
            NO_BITE_TIMEOUT if self._ocr_failsafe_enabled("noBite") else BITE_TIMEOUT
        )
        baseline_color = win_pixel.get_pixel(bite_indicator[0], bite_indicator[1])
        indicator_already_white = win_pixel.color_match(
            baseline_color, WHITE, BITE_TOLERANCE
        )
        print(
            f"[Fishing] Waiting for bite — indicator@{bite_indicator} "
            f"rgb={baseline_color} matchesWhite={indicator_already_white} "
            f"(tol={BITE_TOLERANCE})"
        )
        if indicator_already_white:
            print(
                "[Fishing] WARNING: the Fish Indicator Pixel is ALREADY white "
                "before any bite — this causes instant false bites "
                "(cast → reel 0s → repeat). Re-set 'Fish Indicator Pixel' in "
                "Calibration onto the spot that ONLY turns white when a fish "
                "bites."
            )

        deadline = time.time() + timeout
        while time.time() < deadline:
            if stop_event.is_set() or not self.enabled():
                return "stopped"
            current_color = win_pixel.get_pixel(bite_indicator[0], bite_indicator[1])
            if win_pixel.color_match(current_color, WHITE, BITE_TOLERANCE):
                print(f"[Fishing] Bite detected — indicator rgb={current_color}")
                return "bite"
            time.sleep(0.05)
        return "timeout"

    def _reel(self, stop_event):
        bar_sample_point = self._point("bar_sample")
        zone_left_point = self._point("zone_left")
        zone_right_point = self._point("zone_right")
        reel_click_point = self._point("reel_click")

        scan_left_x = min(zone_left_point[0], zone_right_point[0])
        scan_right_x = max(zone_left_point[0], zone_right_point[0])
        scan_width = max(1, scan_right_x - scan_left_x + 1)
        scan_y = bar_sample_point[1]
        scan_top_y = max(0, scan_y - STRIP_BAND // 2)






        initial_color_samples = []
        for x_offset in (-1, 0, 1):
            for y_offset in (-1, 0, 1):
                pixel_color = win_pixel.get_pixel(
                    bar_sample_point[0] + x_offset,
                    bar_sample_point[1] + y_offset,
                )
                if pixel_color:
                    initial_color_samples.append(pixel_color)

        target_color = _median_color(initial_color_samples)
        print(
            "[Fishing] Initial overlapped target colour="
            f"{target_color} at {bar_sample_point}"
        )

        win_input.move_to(
            reel_click_point[0],
            reel_click_point[1],
            duration=0.05,
            steps=6,
        )
        time.sleep(0.02)


        base_tolerance = self._fishing_int("reelTolerance", REEL_TOLERANCE)
        warm_tolerance = self._fishing_int("reelWarmTolerance", REEL_WARM_TOL)





        target_red, target_green, target_blue = target_color
        red_is_dominant = (
            target_red >= target_green
            and target_red >= target_blue
            and target_red - min(target_green, target_blue) > 40
        )
        if red_is_dominant:
            channel_tolerances = (
                base_tolerance,
                warm_tolerance,
                warm_tolerance,
            )
        else:
            channel_tolerances = (
                base_tolerance,
                base_tolerance,
                base_tolerance,
            )

        deadline = time.time() + REEL_DURATION
        while time.time() < deadline:
            if stop_event.is_set() or not self.enabled():
                return

            target_found = win_pixel.color_block_in_region_pc(
                scan_left_x,
                scan_top_y,
                scan_width,
                STRIP_BAND,
                target_color,
                channel_tolerances,
                min_columns=2,
                min_rows=3,
            )
            if not target_found:
                win_input.click_here(0.0)

            time.sleep(REEL_POLL)






    def run_sell(self, stop_event, focus_fn=None, account=None):
        
        self._active_account = account
        self._active_account_id = (
            (account or {}).get("id") if isinstance(account, dict) else None
        )
        missing_slots = self._missing_required_slots()
        if not win_input.IS_WINDOWS or missing_slots:
            self._push_fishing_decision(
                "Sell route did not run",
                "bad",
                decision_trace.make(
                    "blocked", "sell_route_fishing_not_ready", "Fishing",
                    "The sell route did not run because Fishing is not fully calibrated or Windows input control is unavailable.",
                    checks=[
                        decision_trace.check("Windows input control is available", win_input.IS_WINDOWS),
                        decision_trace.check("Required fishing calibration is complete", not missing_slots),
                        decision_trace.check("Sell route was started", False),
                    ],
                    facts=[decision_trace.fact("Missing calibration", ", ".join(missing_slots) if missing_slots else "None")],
                    next_step={"label": "Open Fishing Calibration", "tab": "calibration"},
                ),
                dedupe_key="manual_sell_not_ready", cooldown=30.0,
            )
            return False

        if focus_fn is not None:
            focus_fn()
        else:
            focus_roblox()

        self.phase = "selling"
        sell_succeeded = self._run_sell_route(stop_event)
        if sell_succeeded:
            with self._lock:
                self.catch_count = 0
                self.sell_count += 1
        self.phase = "idle"
        return sell_succeeded

    def _run_sell_route(self, stop_event):
        route_name = self._active_account_config().get("route", "")
        route_steps = fishing_presets.get_route(route_name)
        if not route_steps:
            print(f"[Fishing] Sell skipped: route '{route_name}' not found.")
            self._push_fishing_decision(
                "Sell route did not run · route not found",
                "bad",
                decision_trace.make(
                    "failed", "sell_route_not_found", "Fishing",
                    "The sell route did not run because the selected route could not be found.",
                    checks=[
                        decision_trace.check("A sell route is selected", bool(route_name)),
                        decision_trace.check("Selected route exists", False),
                        decision_trace.check("Sell route was started", False),
                    ],
                    facts=[decision_trace.fact("Selected route", route_name or "Not selected")],
                    next_step=self._fishing_next_step(),
                ),
            )
            return False

        sell_cycles = max(1, self._account_int("sellCycle", 1))
        verify_shop = self._ocr_failsafe_enabled("sellFishShop")
        self._send_sell_route_webhook(route_name, shop=True)

        if not verify_shop:
            print(
                f"[Fishing] Running sell route '{route_name}' "
                f"(sell cycle x{sell_cycles})."
            )
            route_result = self._run_route_steps(
                route_steps, stop_event, sell_cycles, skip_shop=False
            )
            if route_result:
                self._push_fishing_decision(
                    f"Sell route completed · {route_name}",
                    "good",
                    decision_trace.make(
                        "acted", "sell_route_completed", "Fishing",
                        "The configured sell route finished successfully. Shop verification was disabled.",
                        checks=[
                            decision_trace.check("Selected route exists", True),
                            decision_trace.check("Sell Fish Shop verification is enabled", False),
                            decision_trace.check("Route finished", True),
                        ],
                        facts=[
                            decision_trace.fact("Route", route_name),
                            decision_trace.fact("Sell cycles", sell_cycles),
                        ],
                        next_step=self._fishing_next_step(),
                    ),
                )
            else:
                self._push_fishing_decision(
                    f"Sell route stopped · {route_name}",
                    "warn",
                    decision_trace.make(
                        "cancelled", "sell_route_stopped", "Fishing",
                        "The sell route started but did not finish because Fishing stopped or was disabled.",
                        checks=[
                            decision_trace.check("Selected route exists", True),
                            decision_trace.check("Route finished", False),
                        ],
                        facts=[decision_trace.fact("Route", route_name)],
                        next_step=self._fishing_next_step(),
                    ),
                )
            return bool(route_result)

        attempt = 0
        while not stop_event.is_set() and self.enabled():
            attempt += 1
            if stop_event.is_set() or not self.enabled():
                self._release_all()
                return False

            print(
                f"[Fishing] Running sell route '{route_name}' "
                f"(shop attempt {attempt}, "
                f"sell cycle x{sell_cycles})."
            )
            status_events.set_detail(
                f"Selling — shop attempt {attempt} — retrying until verified"
            )
            route_result = self._run_route_steps(
                route_steps,
                stop_event,
                sell_cycles,
                skip_shop=False,
                verify_shop=True,
            )
            if route_result == "shop_missing":
                print(
                    "[Fishing] Captain Flarg not found on attempt "
                    f"{attempt} — retrying route."
                )
                self._push_fishing_decision(
                    "Sell Fish Shop not found — retrying route "
                    f"(try {attempt})",
                    "warn",
                    decision_trace.make(
                        "waiting", "sell_shop_not_verified_retrying", "Fishing",
                        "The route ran, but Captain Flarg was not detected. SolRich will retry instead of claiming that the fish were sold.",
                        checks=[
                            decision_trace.check("Sell route was started", True),
                            decision_trace.check("Captain Flarg was verified", False),
                            decision_trace.check("Sale was counted", False),
                            decision_trace.check("Another route attempt will run", True),
                        ],
                        facts=[
                            decision_trace.fact("Route", route_name),
                            decision_trace.fact("Failed attempt", attempt),
                        ],
                        next_step=self._fishing_next_step(),
                    ),
                )
                self._release_all()
                continue

            if route_result != "shop_verified":

                self._release_all()
                self._push_fishing_decision(
                    f"Sell route stopped · {route_name}",
                    "warn",
                    decision_trace.make(
                        "cancelled", "sell_route_stopped_before_verification", "Fishing",
                        "The sell route did not complete because it stopped before Captain Flarg could be verified.",
                        checks=[
                            decision_trace.check("Sell route was started", True),
                            decision_trace.check("Captain Flarg was verified", False),
                            decision_trace.check("Sale was counted", False),
                        ],
                        facts=[
                            decision_trace.fact("Route", route_name),
                            decision_trace.fact("Last attempt", attempt),
                        ],
                        next_step=self._fishing_next_step(),
                    ),
                )
                return False

            self._send_failsafe_webhook(
                "Sell Fish Shop Failsafe",
                True,
                detail="Captain Flarg verified",
            )
            self._push_fishing_decision(
                f"Sell route completed · {route_name}",
                "good",
                decision_trace.make(
                    "acted", "sell_route_shop_verified", "Fishing",
                    "The sell route finished and Captain Flarg was verified before SolRich counted the sale.",
                    checks=[
                        decision_trace.check("Sell route was started", True),
                        decision_trace.check("Captain Flarg was verified", True),
                        decision_trace.check("Sale can be counted", True),
                    ],
                    facts=[
                        decision_trace.fact("Route", route_name),
                        decision_trace.fact("Successful attempt", attempt),
                        decision_trace.fact("Sell cycles", sell_cycles),
                    ],
                    next_step=self._fishing_next_step(),
                ),
            )
            return True

        self._release_all()
        self._push_fishing_decision(
            f"Sell route stopped · {route_name}",
            "warn",
            decision_trace.make(
                "cancelled", "sell_route_disabled_or_stopped", "Fishing",
                "The sell route did not run again because the macro stopped or Fishing was disabled.",
                checks=[
                    decision_trace.check("Sell Fish Shop was verified", False),
                    decision_trace.check("Fishing remained enabled", self.enabled()),
                    decision_trace.check("Stop was requested", stop_event.is_set(), detail="A requested stop safely cancels the route."),
                ],
                facts=[
                    decision_trace.fact("Route", route_name),
                    decision_trace.fact("Attempts", attempt),
                ],
                next_step=self._fishing_next_step(),
            ),
        )
        return False

    def _run_route_steps(
        self,
        route_steps,
        stop_event,
        sell_cycles,
        skip_shop=False,
        verify_shop=False,
    ):
        shop_verified = False
        for route_step in route_steps:
            if stop_event.is_set() or not self.enabled():
                self._release_all()
                return False

            if isinstance(route_step, dict) and route_step.get("shop_name_check"):
                if verify_shop:
                    if stop_event.wait(SHOP_WAIT):
                        self._release_all()
                        return False
                    if not self._shop_name_ok():
                        return "shop_missing"
                    shop_verified = True
                continue

            if (
                skip_shop
                and isinstance(route_step, dict)
                and route_step.get("shop_step")
            ):
                continue

            if isinstance(route_step, dict) and route_step.get("sell_cycle"):
                if skip_shop:
                    continue

                for _ in range(sell_cycles):
                    for unit_step in fishing_presets.SELL_CYCLE_UNIT:
                        if stop_event.is_set() or not self.enabled():
                            self._release_all()
                            return False
                        self._run_step(unit_step, stop_event)
                continue

            self._run_step(route_step, stop_event)
        self._release_all()
        print("[Fishing] Sell route done.")
        if verify_shop:
            if not shop_verified:
                print(
                    "[Fishing] Sell route has no shop_name_check step — "
                    "refusing to report a verified sale."
                )
                return False
            return "shop_verified"
        return True

    def _release_all(self):
        for key in ("w", "a", "s", "d", "space"):
            win_input.key_up(key)

    def _run_step(self, step, stop_event):
        if not isinstance(step, dict):
            return

        if "wait" in step:
            delay = float(step["wait"])
            slow_machine_extra = step.get("slow_extra")
            if slow_machine_extra and self._slow_reset_enabled():
                delay += float(slow_machine_extra)
            stop_event.wait(delay)
            return

        if "tap" in step:
            hold_time = step.get("time")
            if hold_time is not None:
                win_input.hold_key(step["tap"], float(hold_time))
                time.sleep(0.04)
            else:
                win_input.press_key(step["tap"], 0.08)
            return

        if "hold" in step:
            win_input.hold_key(step["hold"], float(step.get("time", 0.5)))
            time.sleep(0.08)
            return

        if "down" in step:
            win_input.key_down(step["down"])
            return

        if "up" in step:
            win_input.key_up(step["up"])
            return

        if "click" in step:
            position = step["click"]
            win_input.click_at(int(position[0]), int(position[1]))
            time.sleep(0.12)
            return

        if "click_slot" in step:
            position = self._point(step["click_slot"])
            if position:
                win_input.click_at(position[0], position[1])
                time.sleep(0.12)
            return

        if "move" in step:
            position = step["move"]
            win_input.move_to(int(position[0]), int(position[1]))
            return

        if "scroll" in step:
            win_input.scroll(int(step["scroll"]))
            return

        if "look" in step:
            look_delta = step["look"]
            win_input.look(int(look_delta[0]), int(look_delta[1]))
            return

        if "type" in step:
            win_input.type_text(str(step["type"]))
            return

    def capture(self, slot, timeout=30.0):
        if not win_input.IS_WINDOWS:
            return {"ok": False, "error": "not_windows"}
        if slot not in fishing_presets.slot_keys():
            return {"ok": False, "error": "bad_slot"}
        position = win_input.capture_next_click(timeout=timeout)
        if not position:
            return {"ok": False, "error": "timeout"}

        self.config.set_fishing_pixel(slot, [position[0], position[1]])
        print(f"[Fishing] Captured '{slot}' -> {position[0]}, {position[1]}")
        return {
            "ok": True,
            "slot": slot,
            "x": position[0],
            "y": position[1],
        }
