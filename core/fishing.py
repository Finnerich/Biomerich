import time
import threading
import os

from . import win_input, win_pixel, fishing_presets, ocr, status_events, webhooks
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
SHOP_MAX_ATTEMPTS = 3
OCR_TEXT_THRESHOLD = 0.6

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
        self._primed_acc = None
        self._rot_idx = 0
        self._rot_started = None

    def _fish(self):
        auto = self.config.data.setdefault("automation", {})
        return auto.setdefault("fishing", {})

    def enabled(self):
        return (self._module_active
                or bool(self._fish().get("enabled", False))
                or self.cycle_enabled())

    def _pixels(self):
        return self._fish().get("pixels", {}) or {}

    def _point(self, slot):
        pos = self._pixels().get(slot)
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            return (int(pos[0]), int(pos[1]))
        return None

    def _regions(self):
        return self._fish().get("regions", {}) or {}

    def _region(self, name):
        r = self._regions().get(name)
        if isinstance(r, (list, tuple)) and len(r) == 4:
            return tuple(int(v) for v in r)
        return None

    def _ocr_failsafe(self, name):
        v = self.config.automation.get("ocrFailsafe", {})
        if isinstance(v, dict):
            return bool(v.get(name, False))
        return False

    def _current_acc_id(self):
        
        if self._active_account_id is not None:
            return self._active_account_id
        return self._fish().get("account")

    def _acc_cfg(self):
        
        acc_id = self._current_acc_id()
        if acc_id is None:
            return {}
        entry = (self._fish().get("accounts") or {}).get(str(acc_id))
        return entry if isinstance(entry, dict) else {}

    def schedule(self):
        
        raw = self._fish().get("schedule")
        if not isinstance(raw, list):
            return []
        enabled_ids = {a.get("id") for a in self.config.accounts
                       if a.get("enabled", True)}
        out = []
        for e in raw:
            if not isinstance(e, dict):
                continue
            aid = e.get("accId")
            if aid is None or aid not in enabled_ids:
                continue
            try:
                mins = max(1, int(e.get("minutes", 30)))
            except (TypeError, ValueError):
                mins = 30
            out.append({"accId": aid, "minutes": mins})
        return out

    def rotation_account(self):
        
        sched = self.schedule()
        if not sched:
            self._rot_started = None
            self._active_account_id = None
            return None
        now = time.monotonic()
        if self._rot_started is None or self._rot_idx >= len(sched):
            self._rot_idx = 0
            self._rot_started = now
        entry = sched[self._rot_idx]
        if now - self._rot_started >= entry["minutes"] * 60:
            self._rot_idx = (self._rot_idx + 1) % len(sched)
            self._rot_started = now
            entry = sched[self._rot_idx]
        return entry["accId"]

    def rotation_status(self):
        
        sched = self.schedule()
        if not sched or self._rot_started is None or self._rot_idx >= len(sched):
            return {"accId": None, "remaining": 0, "index": -1, "total": len(sched)}
        entry = sched[self._rot_idx]
        remaining = int(entry["minutes"] * 60 - (time.monotonic() - self._rot_started))
        return {"accId": entry["accId"], "remaining": max(0, remaining),
                "index": self._rot_idx, "total": len(sched)}

    def _acc_int(self, key, default):
        try:
            return int(self._acc_cfg().get(key, default))
        except (TypeError, ValueError):
            return int(default)

    def _int(self, key, default):
        
        try:
            return int(self._fish().get(key, default))
        except (TypeError, ValueError):
            return int(default)

    def _slow_reset(self):
        
        return bool(self.config.settings.get("slowReset", False))

    def ready(self):
        required = ("cast_point", "bite_indicator", "bar_sample", "zone_left",
                    "zone_right", "reel_click", "claim_button")
        return all(self._point(s) is not None for s in required)

    def reset(self):
        with self._lock:
            self.catch_count = 0
            self.sell_count = 0
            self.total_caught = 0
            self.phase = "idle"
            self._session_start = time.time()
            self._primed_acc = None
            self._active_account_id = None
            self._rot_idx = 0
            self._rot_started = None

    def status(self):
        return {
            "caught": self.total_caught,
            "sinceSell": self.catch_count,
            "sells": self.sell_count,
        }

    def _cycle(self):
        auto = self.config.data.setdefault("automation", {})
        cyc = auto.setdefault("cycle", {})
        cyc.setdefault("steps", [])
        cyc.setdefault("enabled", False)
        lim = cyc.setdefault("limbo", {})
        if not isinstance(lim.get("accounts"), dict):
            lim["accounts"] = {}
        return cyc

    def cycle_enabled(self):
        return False

    def cycle_steps(self):
        
        raw = self._cycle().get("steps")
        if not isinstance(raw, list):
            return []
        enabled_ids = {a.get("id") for a in self.config.accounts if a.get("enabled", True)}
        out = []
        for s in raw:
            if not isinstance(s, dict):
                continue
            aid = s.get("accId")
            if aid is None or aid not in enabled_ids:
                continue
            t = s.get("type") or "fishing"
            entry = {"type": t, "accId": aid}
            if t == "fishing":
                try:
                    entry["minutes"] = max(1, int(s.get("minutes", 30)))
                except (TypeError, ValueError):
                    entry["minutes"] = 30
            elif t == "limboEden":
                entry["afk"] = bool(s.get("afk", False))
                try:
                    entry["minutes"] = max(1, int(s.get("minutes", 30)))
                except (TypeError, ValueError):
                    entry["minutes"] = 30
            out.append(entry)
        return out

    @staticmethod
    def _step_minutes(step):
        
        t = step.get("type")
        if t == "fishing":
            return step.get("minutes", 30)
        if t == "limboEden" and not step.get("afk"):
            return step.get("minutes", 30)
        return None

    def limbo_settings(self, acc_id):
        
        accs = (self._cycle().get("limbo") or {}).get("accounts") or {}
        entry = accs.get(str(acc_id))
        out = {"path": "vip", "edenWatch": False, "edenInterval": 120}
        if isinstance(entry, dict):
            if entry.get("path"):
                out["path"] = str(entry["path"])
            out["edenWatch"] = bool(entry.get("edenWatch", False))
            try:
                out["edenInterval"] = max(30, min(3600, int(entry.get("edenInterval", 120))))
            except (TypeError, ValueError):
                pass
        return out

    def current_step(self):
        
        steps = self.cycle_steps()
        if not steps:
            self._rot_started = None
            self._active_account_id = None
            return None
        now = time.monotonic()
        if self._rot_started is None or self._rot_idx >= len(steps):
            self._rot_idx = 0
            self._rot_started = now
        step = steps[self._rot_idx]
        mins = self._step_minutes(step)
        if mins is not None and now - self._rot_started >= mins * 60:
            self._rot_idx = (self._rot_idx + 1) % len(steps)
            self._rot_started = now
            step = steps[self._rot_idx]
            mins = self._step_minutes(step)
        remaining = int(mins * 60 - (now - self._rot_started)) if mins is not None else 0
        return {**step, "remaining": max(0, remaining),
                "index": self._rot_idx, "total": len(steps)}

    def advance_step(self):
        
        steps = self.cycle_steps()
        if not steps:
            return
        self._rot_idx = (self._rot_idx + 1) % len(steps)
        self._rot_started = time.monotonic()

    def cycle_status(self):
        
        steps = self.cycle_steps()
        if not steps or self._rot_started is None or self._rot_idx >= len(steps):
            return {"type": None, "accId": None, "remaining": 0, "index": -1,
                    "total": len(steps), "enabled": self.cycle_enabled()}
        step = steps[self._rot_idx]
        mins = self._step_minutes(step)
        remaining = int(mins * 60 - (time.monotonic() - self._rot_started)) if mins is not None else 0
        return {"type": step.get("type"), "accId": step.get("accId"),
                "remaining": max(0, remaining), "index": self._rot_idx,
                "total": len(steps), "enabled": self.cycle_enabled()}

    def run_path(self, steps, ev):
        
        try:
            for step in steps:
                if ev.is_set():
                    return False
                self._run_step(step, ev)
            return True
        finally:
            self._release_all()

    def _webhook_enabled(self):
        return bool(self._fish().get("webhookEnabled", False))

    def _webhook_urls(self):
        seen, urls = set(), []
        for w in (self.config.webhooks or []):
            url = (w.get("url") or "").strip()
            if w.get("active", True) and url and url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def _version(self):
        try:
            return self.config.data.get("version") or "?"
        except Exception:
            return "?"

    def _session_time(self):
        secs = max(0, int(time.time() - self._session_start))
        return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"

    def _fire_fish_webhook(self, is_catch, total_caught, since_sell):
        if not self._webhook_enabled():
            return
        urls = self._webhook_urls()
        if not urls:
            return
        try:
            if is_catch:
                webhooks.fish_caught(
                    urls, self._active_account, total_caught,
                    since_sell, self._session_time(), self._version(),
                )
            else:
                webhooks.fish_failed(
                    urls, self._active_account, total_caught,
                    self._session_time(), self._version(),
                )
        except Exception as e:
            print(f"[Fishing] Webhook send failed: {e}")

    def _failsafe_notify_on(self):
        try:
            notif = self.config.automation.get("notifications", {}) or {}
            return bool(notif.get("failsafes", False))
        except Exception:
            return False

    def _fire_failsafe_webhook(self, label, success, detail=""):
        if not self._failsafe_notify_on():
            return
        urls = self._webhook_urls()
        if not urls:
            return
        try:
            webhooks.failsafe_result(
                urls, label, self._active_account, success,
                self._session_time(), self._version(), detail=detail,
            )
        except Exception as e:
            print(f"[Fishing] Failsafe webhook failed: {e}")

    def _fire_sell_route_webhook(self, route_name, shop=True):
        if not self._webhook_enabled():
            return
        urls = self._webhook_urls()
        if not urls:
            return
        try:
            total = int(self.config.time_tracking().get("fishCaught", 0))
        except Exception:
            total = self.total_caught
        try:
            webhooks.sell_route(
                urls, self._active_account, route_name, total,
                self._session_time(), self._version(), shop=shop,
            )
        except Exception as e:
            print(f"[Fishing] Sell route webhook failed: {e}")

    def _detect_catch_result(self):
        if not self._ocr_failsafe("fishingFailed"):
            return True
        if not ocr.available():
            print("[Fishing] Fishing Failed failsafe ON but Tesseract not available — counting as catch.")
            return True
        region = self._region("fishing_failed")
        if region is None:
            print("[Fishing] Fishing Failed failsafe ON but no 'Fishing Failed' region calibrated — counting as catch.")
            return True
        status_events.push_event("Scanning catch result…", kind="info", ttl=1.5)
        x, y, w, h = region
        reads = ocr.read_region_variants(x, y, w, h)
        print(f"[Fishing][OCR] fishing_failed region=({x},{y},{w}x{h}) | reads: {reads!r}")

        meaningful = [r for r in reads if len(ocr.normalize(r)) >= 3]
        if not meaningful:
            print("[Fishing][OCR] No readable text in region — NOT counting catch.")
            status_events.push_event("No catch detected", kind="warn", ttl=2.0)
            return False
        failed_score = 0.0
        caught_score = 0.0
        for txt in reads:
            failed_score = max(failed_score, ocr.similarity(txt, FAILED_TEXT))
            caught_score = max(caught_score, ocr.similarity(txt, CAUGHT_TEXT))
        if failed_score >= OCR_TEXT_THRESHOLD and failed_score >= caught_score:
            print(f"[Fishing][OCR] 'Fishing Failed' detected (failed={failed_score:.2f}, caught={caught_score:.2f}) — NOT counting catch.")
            status_events.push_event("Fishing Failed", kind="bad", ttl=4.0)
            return False
        if caught_score >= OCR_TEXT_THRESHOLD:
            print(f"[Fishing][OCR] 'Fish Caught' detected (caught={caught_score:.2f}, failed={failed_score:.2f}) — counting catch.")
            status_events.push_event("Fish Caught", kind="good", ttl=4.0)
            return True

        print(f"[Fishing][OCR] No clear match (failed={failed_score:.2f}, caught={caught_score:.2f}) — NOT counting catch.")
        status_events.push_event("Catch unclear — not counting", kind="warn", ttl=2.0)
        return False

    def _shop_name_ok(self):
        if not ocr.available():
            return True
        region = self._region("shop_name")
        if region is None:
            print("[Fishing] Sell Fish Shop failsafe ON but no 'Shop Name' region calibrated — assuming shop OK.")
            return True
        status_events.push_event("Checking shop name…", kind="info", ttl=1.5)
        x, y, w, h = region
        reads = ocr.read_region_variants(x, y, w, h)
        score = 0.0
        for txt in reads:
            score = max(score, ocr.similarity(txt, SHOP_NAME_TARGET))
        print(f"[Fishing][OCR] shop_name region=({x},{y},{w}x{h}) | reads: {reads!r} | '{SHOP_NAME_TARGET}' score={score:.2f}")
        ok = score >= OCR_TEXT_THRESHOLD
        if ok:
            status_events.push_event("Captain Flarg found", kind="good", ttl=1.8)
        return ok

    def do_cycle(self, ev, focus_fn=None, account=None):
        self._active_account = account
        self._active_account_id = (account or {}).get("id") if isinstance(account, dict) else None
        if not win_input.IS_WINDOWS or not self.ready():
            ev.wait(1.0)
            return False

        if focus_fn is not None:
            focus_fn()
        else:
            focus_roblox()

        if self._acc_cfg().get("primeRoute", False):
            acc_id = self._current_acc_id()
            if acc_id is not None and self._primed_acc != acc_id:
                name = self._acc_cfg().get("route", "")
                steps = fishing_presets.get_route(name)
                if steps:
                    print(f"[Fishing] Priming route '{name}' — walking without opening the shop.")
                    status_events.push_event("Walking the route (no shop)…", kind="info", ttl=2.0)
                    status_events.set_detail("Walking the sell route — no shop")
                    self.phase = "selling"
                    self._run_route_steps(steps, ev, max(1, self._acc_int("sellCycle", 1)), skip_shop=True)
                    if ev.is_set() or not self.enabled():
                        self.phase = "idle"
                        return False
                else:
                    print(f"[Fishing] Route prime skipped: route '{name}' not found.")
                self._primed_acc = acc_id

        self.phase = "casting"
        status_events.set_detail("Casting the line")

        claim = self._point("claim_button")
        if claim is not None:
            win_input.click_at(claim[0], claim[1])
            if ev.wait(0.3):
                self.phase = "idle"
                return False

        cast = self._point("cast_point")
        win_input.click_at(cast[0], cast[1])
        if ev.wait(0.35):
            self.phase = "idle"
            return False

        self.phase = "waiting"
        bite = self._wait_for_bite(ev)
        if bite != "bite":
            if bite == "timeout" and self._ocr_failsafe("noBite"):
                print(f"[Fishing] No bite for {NO_BITE_TIMEOUT:.0f}s — running sell route WITHOUT opening the shop.")
                status_events.push_event("No bite — running sell route (no shop)", kind="warn", ttl=None)
                status_events.set_detail("Running sell route — no shop")
                self._fire_failsafe_webhook("No Bite Failsafe", False,
                                            detail=f"No bite for {NO_BITE_TIMEOUT:.0f}s — selling without shop")
                self.phase = "selling"
                name = self._acc_cfg().get("route", "")
                steps = fishing_presets.get_route(name)
                if steps:
                    cycles = max(1, self._acc_int("sellCycle", 1))
                    self._fire_sell_route_webhook(name, shop=False)
                    self._run_route_steps(steps, ev, cycles, skip_shop=True)
                else:
                    print(f"[Fishing] No-bite failsafe: route '{name}' not found — skipping.")
            elif bite == "timeout":
                print(f"[Fishing] No bite for {BITE_TIMEOUT:.0f}s — recasting.")
                status_events.push_event("No bite — recasting", kind="warn", ttl=2.0)
            self.phase = "idle"
            return False

        status_events.push_event("Bite! Reeling in", kind="good", ttl=1.5)
        self.phase = "reeling"
        status_events.set_detail("Reeling it in")
        self._reel(ev)

        if ev.is_set():
            self.phase = "idle"
            return False

        claim = self._point("claim_button")
        time.sleep(0.3)

        is_catch = self._detect_catch_result()

        win_input.click_at(claim[0], claim[1])
        time.sleep(0.3)

        if is_catch:
            with self._lock:
                self.catch_count += 1
                self.total_caught += 1
                since = self.catch_count

            try:
                lifetime = self.config.add_fish_caught(1)
            except Exception:
                lifetime = None
            self._fire_fish_webhook(True, lifetime if lifetime is not None else self.total_caught, since)
        else:
            with self._lock:
                since = self.catch_count
            try:
                lifetime = int(self.config.time_tracking().get("fishCaught", 0))
            except Exception:
                lifetime = self.total_caught
            self._fire_fish_webhook(False, lifetime, since)

        if is_catch and self._acc_cfg().get("autoSell", False):
            sell_after = max(1, self._acc_int("sellAfter", 20))
            if since >= sell_after:
                self.phase = "selling"
                if self._run_sell_route(ev):
                    with self._lock:
                        self.catch_count = 0
                        self.sell_count += 1
        self.phase = "idle"
        return True

    def _wait_for_bite(self, ev):
        indicator = self._point("bite_indicator")
        status_events.clear_event()
        status_events.set_detail("Waiting for a bite")
        timeout = NO_BITE_TIMEOUT if self._ocr_failsafe("noBite") else BITE_TIMEOUT
        baseline = win_pixel.get_pixel(indicator[0], indicator[1])
        already_white = win_pixel.color_match(baseline, WHITE, BITE_TOLERANCE)
        print(f"[Fishing] Waiting for bite — indicator@{indicator} rgb={baseline} "
              f"matchesWhite={already_white} (tol={BITE_TOLERANCE})")
        if already_white:
            print("[Fishing] WARNING: the Fish Indicator Pixel is ALREADY white before any "
                  "bite — this causes instant false bites (cast → reel 0s → repeat). Re-set "
                  "'Fish Indicator Pixel' in Calibration onto the spot that ONLY turns white "
                  "when a fish bites.")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if ev.is_set() or not self.enabled():
                return "stopped"
            rgb = win_pixel.get_pixel(indicator[0], indicator[1])
            if win_pixel.color_match(rgb, WHITE, BITE_TOLERANCE):
                print(f"[Fishing] Bite detected — indicator rgb={rgb}")
                return "bite"
            time.sleep(0.05)
        return "timeout"

    def _reel(self, ev):
        sample = self._point("bar_sample")
        left = self._point("zone_left")
        right = self._point("zone_right")
        reel_click = self._point("reel_click")

        x1 = min(left[0], right[0])
        x2 = max(left[0], right[0])
        width = max(1, x2 - x1 + 1)
        y = sample[1]
        top = max(0, y - STRIP_BAND // 2)

        win_input.move_to(reel_click[0], reel_click[1])
        time.sleep(0.06)

        pixels = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                px = win_pixel.get_pixel(sample[0] + dx, sample[1] + dy)
                if px:
                    pixels.append(px)

        if pixels:
            avg_r = sum(p[0] for p in pixels) // len(pixels)
            avg_g = sum(p[1] for p in pixels) // len(pixels)
            avg_b = sum(p[2] for p in pixels) // len(pixels)
            bar_color = (avg_r, avg_g, avg_b)
        else:
            bar_color = WHITE

        zone_color = bar_color


        current_tolerance = self._int("reelTolerance", REEL_TOLERANCE)
        warm_tolerance = self._int("reelWarmTolerance", REEL_WARM_TOL)





        r0, g0, b0 = bar_color
        if r0 >= g0 and r0 >= b0 and r0 - min(g0, b0) > 40:
            tol_rgb = (current_tolerance, warm_tolerance, warm_tolerance)
        else:
            tol_rgb = (current_tolerance, current_tolerance, current_tolerance)

        deadline = time.time() + REEL_DURATION
        while time.time() < deadline:
            if ev.is_set() or not self.enabled():
                return

            found = win_pixel.color_in_region_pc(x1, top, width, STRIP_BAND,
                                                 bar_color, tol_rgb)
            if not found:
                win_input.click_here(0.0)

            time.sleep(REEL_POLL)


    def run_sell(self, ev, focus_fn=None, account=None):
        
        self._active_account = account
        self._active_account_id = (account or {}).get("id") if isinstance(account, dict) else None
        if not win_input.IS_WINDOWS or not self.ready():
            return False
        if focus_fn is not None:
            focus_fn()
        else:
            focus_roblox()
        self.phase = "selling"
        ok = self._run_sell_route(ev)
        if ok:
            with self._lock:
                self.catch_count = 0
                self.sell_count += 1
        self.phase = "idle"
        return ok

    def _run_sell_route(self, ev):
        name = self._acc_cfg().get("route", "")
        steps = fishing_presets.get_route(name)
        if not steps:
            print(f"[Fishing] Sell skipped: route '{name}' not found.")
            return False
        cycles = max(1, self._acc_int("sellCycle", 1))

        failsafe = self._ocr_failsafe("sellFishShop")
        self._fire_sell_route_webhook(name, shop=True)
        if not failsafe:
            print(f"[Fishing] Running sell route '{name}' (sell cycle x{cycles}).")
            return self._run_route_steps(steps, ev, cycles, skip_shop=False)

        for attempt in range(1, SHOP_MAX_ATTEMPTS + 1):
            if ev.is_set() or not self.enabled():
                self._release_all()
                return False
            print(f"[Fishing] Running sell route '{name}' (attempt {attempt}/{SHOP_MAX_ATTEMPTS}, sell cycle x{cycles}).")
            status_events.set_detail(f"Selling — shop attempt {attempt}/{SHOP_MAX_ATTEMPTS}")
            result = self._run_route_steps(steps, ev, cycles, skip_shop=False, verify_shop=True)
            if result == "shop_missing":
                print(f"[Fishing] Captain Flarg not found on attempt {attempt} — retrying route.")
                status_events.push_event(
                    f"Sell Fish Shop failsafe failed — shop route try {attempt}/{SHOP_MAX_ATTEMPTS}",
                    kind="warn", ttl=2.5)
                self._release_all()
                continue
            self._fire_failsafe_webhook("Sell Fish Shop Failsafe", True,
                                        detail="Captain Flarg verified")
            return bool(result)

        print(f"[Fishing] Captain Flarg not found after {SHOP_MAX_ATTEMPTS} attempts — running route with shop skipped.")
        status_events.push_event(
            "Sell Fish Shop failsafe gave up — running route, shop skipped",
            kind="bad", ttl=3.0)
        self._fire_failsafe_webhook("Sell Fish Shop Failsafe", False,
                                    detail=f"Captain Flarg not found after {SHOP_MAX_ATTEMPTS} tries")
        return self._run_route_steps(steps, ev, cycles, skip_shop=True)

    def _run_route_steps(self, steps, ev, cycles, skip_shop=False, verify_shop=False):
        for step in steps:
            if ev.is_set() or not self.enabled():
                self._release_all()
                return False

            if isinstance(step, dict) and step.get("shop_name_check"):
                if verify_shop:
                    ev.wait(SHOP_WAIT)
                    if not self._shop_name_ok():
                        return "shop_missing"
                continue

            if skip_shop and isinstance(step, dict) and step.get("shop_step"):
                continue

            if isinstance(step, dict) and step.get("sell_cycle"):
                if skip_shop:
                    continue
                for _ in range(cycles):
                    for unit_step in fishing_presets.SELL_CYCLE_UNIT:
                        if ev.is_set() or not self.enabled():
                            self._release_all()
                            return False
                        self._run_step(unit_step, ev)
                continue
            self._run_step(step, ev)
        self._release_all()
        print("[Fishing] Sell route done.")
        return True

    def _release_all(self):
        for key in ("w", "a", "s", "d", "space"):
            win_input.key_up(key)

    def _run_step(self, step, ev):
        if not isinstance(step, dict):
            return
        if "wait" in step:
            delay = float(step["wait"])
            extra = step.get("slow_extra")
            if extra and self._slow_reset():
                delay += float(extra)
            ev.wait(delay)
            return
        if "tap" in step:
            t = step.get("time")
            if t is not None:
                win_input.hold_key(step["tap"], float(t))
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
            pos = step["click"]
            win_input.click_at(int(pos[0]), int(pos[1]))
            time.sleep(0.12)
            return
        if "click_slot" in step:
            pos = self._point(step["click_slot"])
            if pos:
                win_input.click_at(pos[0], pos[1])
                time.sleep(0.12)
            return
        if "move" in step:
            pos = step["move"]
            win_input.move_to(int(pos[0]), int(pos[1]))
            return
        if "scroll" in step:
            win_input.scroll(int(step["scroll"]))
            return
        if "look" in step:
            d = step["look"]
            win_input.look(int(d[0]), int(d[1]))
            return
        if "type" in step:
            win_input.type_text(str(step["type"]))
            return

    def capture(self, slot, timeout=30.0):
        if not win_input.IS_WINDOWS:
            return {"ok": False, "error": "not_windows"}
        if slot not in fishing_presets.slot_keys():
            return {"ok": False, "error": "bad_slot"}
        pos = win_input.capture_next_click(timeout=timeout)
        if not pos:
            return {"ok": False, "error": "timeout"}
        self.config.set_fishing_pixel(slot, [pos[0], pos[1]])
        print(f"[Fishing] Captured '{slot}' -> {pos[0]}, {pos[1]}")
        return {"ok": True, "slot": slot, "x": pos[0], "y": pos[1]}
