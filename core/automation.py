import re
import time
import threading

from . import win_input, presets, win_windows, ocr, status_events, merchants_data, webhooks, screenshot, win_pixel
from . import detection
from . import merchant_logic
from . import calibration
from .autopop import AutoPopEngine
from .merchant import MerchantController




from .eden import EdenController

limbo_paths = None

class LimboController:
    def __init__(self, engine): pass
    def reset(self): pass
    def pause(self, acc_id): pass
    def run_afk(self, acc_id, ev): pass
    def run_cycle(self, acc_id, ev): pass


STRANGE_INTERVAL = 21 * 60
BIOME_INTERVAL   = 36 * 60
MERCHANT_INTERVAL = 30 * 60

ITEM_TASKS = ("strangeController", "biomeRandomizer")
WINDOW_REFRESH = 5.0

ITEM_OCR_ATTEMPTS  = 3
OCR_MATCH_THRESHOLD = 0.62

DEFAULT_TERMS = {
    "strangeController": "Strange Controller",
    "biomeRandomizer":   "Biome Randomizer",
    "merchantTeleporter":   "Merchant Teleporter",
}
DEFAULT_INTERVALS = {
    "strangeController": STRANGE_INTERVAL,
    "biomeRandomizer":   BIOME_INTERVAL,
    "merchantTeleporter":   MERCHANT_INTERVAL,
}

try:
    from .fishing import FishingEngine
    _FISHING_AVAILABLE = True
except ImportError:
    _FISHING_AVAILABLE = False
    class FishingEngine:
        def __init__(self, config): pass
        def enabled(self): return False
        def ready(self): return False
        def reset(self): pass
        def do_cycle(self, ev, focus_fn=None, account=None): pass
        def run_sell(self, ev, focus_fn=None, account=None): return False
        def cycle_enabled(self): return False
        phase = "idle"
        _module_active = False

class AutomationEngine:
    def __init__(self, config, is_tracking, anti_afk=None):
        self.config      = config
        self._is_tracking = is_tracking
        self._anti_afk   = anti_afk
        self._throttler  = None
        self._stop       = threading.Event()
        self._thread     = None


        self._action_lock = threading.RLock()
        if self._anti_afk is not None:
            self._anti_afk.set_action_lock(self._action_lock)
        self._active_action_account = None
        self._active_action_hwnd = None
        self._next_run   = {}
        self._windows    = {}
        self._win_ts     = 0.0
        self._last_window_state = {}
        self.fishing     = FishingEngine(config)
        self._fishing_warned = False
        self._manual_sell_pending = False
        self.autopop     = AutoPopEngine(config)
        self.limbo       = LimboController(self)
        self.eden        = EdenController(self)
        self.merchant    = MerchantController(self)
        self._prev_limbo_acc = None
        self._prev_eden_acc  = None
        self.engine      = None
        self.current_action  = "idle"
        self.current_account = ""
        self._session_start = time.time()

    def set_throttler(self, throttler):
        self._throttler = throttler

    def _auto(self):
        return self.config.data.setdefault("automation", {})

    def mode(self):
        return self._auto().get("mode", "idle")

    def _accounts(self):
        return self.config.accounts

    def _account_name(self, acc_id):
        acc = next((a for a in self._accounts() if a.get("id") == acc_id), None)
        return acc.get("name", "?") if acc else "?"

    def _account_obj(self, acc_id):
        return next((a for a in self._accounts() if a.get("id") == acc_id), None)

    def biome_for(self, acc_id):
        
        eng = self.engine
        if eng is None:
            return None
        try:
            return eng.biome_for(acc_id)
        except Exception:
            return None

    def _account_window_rect(self, acc_id):
        
        hwnd = self._windows.get(acc_id)
        if not hwnd:
            return None
        try:
            return win_windows.window_rect(hwnd)
        except Exception:
            return None

    def _eden_click_point(self):
        
        calib = (self._auto().get("calib", {}) or {}).get("eden", {}) or {}
        pt = (calib.get("pixels", {}) or {}).get("eden_click")
        if isinstance(pt, (list, tuple)) and len(pt) == 2:
            return (int(pt[0]), int(pt[1]))
        return None


    def _notif(self):
        return (self._auto().get("notifications", {}) or {})

    def _notif_on(self, key):
        return bool(self._notif().get(key, False))

    def _notif_urls(self):
        seen, urls = set(), []
        for w in (self.config.webhooks or []):
            url = (w.get("url") or "").strip()
            if w.get("active", True) and url and url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def _notif_version(self):
        try:
            return self.config.data.get("version") or "?"
        except Exception:
            return "?"

    def _notif_session_time(self):
        secs = max(0, int(time.time() - getattr(self, "_session_start", time.time())))
        return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"

    def _notify_module(self, task, acc_id, success, detail=""):
        flag = {
            "strangeController": "strangeController",
            "biomeRandomizer": "biomeRandomizer",
            "merchantTeleporter": "merchantTeleporter",
        }.get(task)
        if not flag or not self._notif_on(flag):
            return
        urls = self._notif_urls()
        if not urls:
            return
        try:
            webhooks.module_used(
                urls, task, self._account_obj(acc_id), success,
                self._notif_session_time(), self._notif_version(), detail=detail,
            )
        except Exception as e:
            print(f"[Automation] Module webhook failed: {e}")

    def _notify_merchant(self, acc_id, merchant_name, mid="", image_bytes=None):
        urls = self._notif_urls()
        if not urls:
            return
        try:
            webhooks.merchant_detected(
                urls, self._account_obj(acc_id), merchant_name, mid,
                self._notif_session_time(), self._notif_version(),
                image_bytes=image_bytes,
            )
        except Exception as e:
            print(f"[Automation] Merchant webhook failed: {e}")

    def _notify_autobuy(self, acc_id, mid, item, purchased, wanted, wanted_left):
        if not self._notif_on("merchantAutoBuy"):
            return
        urls = self._notif_urls()
        if not urls:
            return
        try:
            webhooks.merchant_autobuy(
                urls, self._account_obj(acc_id),
                merchants_data.detect_merchant_name(mid), mid,
                item, purchased, wanted, wanted_left,
                self._notif_session_time(), self._notif_version(),
            )
        except Exception as e:
            print(f"[Automation] Auto Buy webhook failed: {e}")

    def _notify_failsafe(self, label, acc_id, success, detail=""):
        if not self._notif_on("failsafes"):
            return
        urls = self._notif_urls()
        if not urls:
            return
        try:
            webhooks.failsafe_result(
                urls, label, self._account_obj(acc_id) if acc_id else None,
                success, self._notif_session_time(), self._notif_version(), detail=detail,
            )
        except Exception as e:
            print(f"[Automation] Failsafe webhook failed: {e}")

    def accounts_for(self, task):
        return [
            a.get("id")
            for a in self.config.enabled_accounts()
            if (a.get("modules") or {}).get(task)
        ]

    def _fishing_account(self):
        chosen = self._auto().get("fishing", {}).get("account")
        if chosen is not None and any(a.get("id") == chosen for a in self.config.enabled_accounts()):
            return chosen
        return None

    def _fishing_module_account(self):
        
        ids = self.accounts_for("fishing")
        return ids[0] if ids else None

    def _anti_afk_enabled(self):
        return bool(self.config.settings.get("antiAfkEnabled", False))

    def _anti_afk_interval(self):
        try:
            return max(30, int(self.config.settings.get("antiAfkInterval", 300)))
        except (TypeError, ValueError):
            return 300

    def _interval(self, task):
        intervals = self._auto().get("intervals", {})
        return int(intervals.get(task, DEFAULT_INTERVALS.get(task, 1800)))

    def _search_term(self, task):
        terms = self._auto().get("searchTerms", {})
        return str(terms.get(task) or DEFAULT_TERMS.get(task, task))

    def _amount(self):
        return str(self._auto().get("amount", "1") or "1")

    def _pixels(self):
        return self._auto().get("pixels", {}) or {}

    def pixels_ready(self):
        px = self._pixels()
        return all(
            isinstance(px.get(k), (list, tuple)) and len(px.get(k)) == 2
            for k in presets.slot_keys()
        )

    def _ocr_enabled(self, task):
        v = self._auto().get("ocrFailsafe", {})
        if isinstance(v, dict):
            return bool(v.get(task, False))
        return False

    def _item_region(self):
        r = self._auto().get("firstItemRegion")
        if isinstance(r, (list, tuple)) and len(r) == 4:
            return tuple(int(v) for v in r)
        return None

    def _verify_item(self, search_term, task):
        if not (self._ocr_enabled(task) and ocr.available()):
            return None
        region = self._item_region()
        if region is None:
            print(f"[OCR] task={task} | No item region calibrated — skipping OCR check.")
            return None
        x, y, w, h = region

        dbg_path = ocr.save_debug_image(x, y, w, h)
        if dbg_path:
            print(f"[OCR] Debug image saved → {dbg_path}")

        candidates = ocr.read_region_variants(x, y, w, h)
        print(f"[OCR] region=({x},{y},{w}x{h}) | all reads: {candidates!r}")

        best_text, best_score = "", 0.0
        for txt in candidates:
            score = ocr.similarity(txt, search_term)
            if score > best_score:
                best_text, best_score = txt, score

        ok = best_score >= OCR_MATCH_THRESHOLD
        status = "MATCH" if ok else "MISMATCH"
        print(f"[OCR] task={task} | searching='{search_term}' | best='{best_text}' | score={best_score:.2f} | result={status}")
        return bool(ok)

    def _refresh_windows(self, force=False):
        now = time.time()
        if not force and (now - self._win_ts) < WINDOW_REFRESH:
            return
        self._win_ts = now
        try:
            resolved = win_windows.resolve_accounts(self.config.enabled_accounts())
            new_windows = {aid: info.get("hwnd") for aid, info in resolved.items()}

            for aid, hwnd in new_windows.items():
                prev = self._last_window_state.get(aid, "__unset__")
                if prev != hwnd:
                    name = self._account_name(aid)
                    if hwnd:
                        via = resolved[aid].get("via") or "?"
                        print(f"[Windows] '{name}' → bound to PID {resolved[aid].get('pid')} "
                              f"hwnd {hwnd} (via {via})")
                    elif prev != "__unset__":
                        print(f"[Windows] '{name}' → window lost")
            self._last_window_state = new_windows
            self._windows = new_windows
        except Exception as e:
            print(f"[Automation] Window resolve failed: {e}")

    def _focus_account(self, acc_id):
        name = self._account_name(acc_id)
        self._active_action_account = None
        self._active_action_hwnd = None
        hwnd = self._windows.get(acc_id)
        print(f"[Focus] Account '{name}' (id={acc_id}) → target hwnd {hwnd}")
        if not hwnd:
            self._refresh_windows(force=True)
            hwnd = self._windows.get(acc_id)
        if not hwnd:
            print(f"[Focus] '{name}' → no window bound, skipping.")
            return False

        for attempt in range(2):
            win_windows.focus_hwnd(hwnd)
            time.sleep(0.30)
            fg = win_windows.foreground_hwnd()
            if fg == int(hwnd):
                rect = win_windows.window_rect(hwnd)
                print(f"[Focus] '{name}' VERIFIED foreground {fg} (wanted {hwnd}) | rect {rect}")
                time.sleep(0.20)
                if self._throttler is not None:
                    pid = win_windows.foreground_pid()
                    if self._throttler.warm_up_process(pid, 3.0):
                        print(f"[Focus] '{name}' throttle warm-up complete (3.0s).")


                fg_after_warmup = win_windows.foreground_hwnd()
                if fg_after_warmup == int(hwnd):
                    self._active_action_account = acc_id
                    self._active_action_hwnd = int(hwnd)
                    return True
                print(f"[Focus] '{name}' lost foreground during warm-up "
                      f"({fg_after_warmup} != {hwnd}); retrying")
            print(f"[Focus] '{name}' attempt {attempt+1} FAILED — foreground {fg} != wanted {hwnd}, retrying")
            self._refresh_windows(force=True)
            hwnd = self._windows.get(acc_id) or hwnd

        print(f"[Focus] '{name}' → could NOT bring window to foreground, skipping (no wrong-account run).")
        return False

    def _ensure_action_focus(self):
        
        target = getattr(self, "_active_action_hwnd", None)
        account = getattr(self, "_active_action_account", None)
        if not target or account is None:
            raise RuntimeError("no verified action window")
        if win_windows.foreground_hwnd() == int(target):
            return True

        print(f"[FocusGuard] Foreground changed during action; restoring "
              f"'{self._account_name(account)}' before input.")
        return self._focus_account(account)

    def _begin_input_transaction(self):
        
        held = False
        if self._throttler is not None:
            held = bool(self._throttler.begin_input_hold())
        try:

            win_input.release_mouse_buttons(settle=0.05)
            return held
        except Exception:
            if held and self._throttler is not None:
                self._throttler.end_input_hold()
            raise

    def _end_input_transaction(self, held):
        
        target = getattr(self, "_active_action_hwnd", None)
        try:


            win_input.release_mouse_buttons(settle=0.05)
            if target and win_windows.foreground_hwnd() == int(target):



                time.sleep(0.80)
        finally:
            if held and self._throttler is not None:
                self._throttler.end_input_hold()
            self._active_action_account = None
            self._active_action_hwnd = None

    def _replace_active_text(self, text):
        
        if not self._ensure_action_focus():
            raise RuntimeError("focus lost before text input")
        win_input.select_all_and_clear()
        time.sleep(0.20)
        if not self._ensure_action_focus():
            raise RuntimeError("focus lost while preparing text input")
        win_input.type_text(str(text))

    def start(self):
        if not win_input.IS_WINDOWS:
            return
        self.stop()
        ev = threading.Event()
        self._stop = ev
        now = time.time()
        self._session_start = now

        self._next_run = {}
        for task in ITEM_TASKS:
            for acc_id in self.accounts_for(task):
                self._next_run[(acc_id, task)] = now

        for acc_id in self.accounts_for("merchantTeleporter"):
            self._next_run[(acc_id, "merchantTeleporter")] = now
        if self._anti_afk_enabled():
            self._next_run[("__afk__", "antiAfk")] = now

        self._fishing_warned = False
        self.current_action  = "idle"
        self.current_account = ""
        self.fishing.reset()
        self.autopop.reset()
        self.limbo.reset()
        self.eden.reset()
        self._prev_limbo_acc = None
        self._prev_eden_acc = None
        self._win_ts = 0.0
        self._refresh_windows(force=True)
        self._thread = threading.Thread(target=self._loop, args=(ev,), daemon=True)
        self._thread.start()
        print("[Automation] Started.")

    def stop(self):
        if self._thread:
            print("[Automation] Stopped.")
        self._stop.set()
        self._thread     = None
        self._next_run   = {}
        self.current_action  = "idle"
        self.current_account = ""
        self.fishing.phase   = "idle"

    def queue_autopop(self, acc_id, biome_key):
        
        if self.mode() != "automation":
            return False
        try:
            return self.autopop.enqueue(acc_id, biome_key)
        except Exception as e:
            print(f"[AutoPop] enqueue failed: {e}")
            return False

    def queue_manual_sell(self):
        
        if not (self._is_tracking() and self.mode() == "automation"):
            return {"ok": False, "error": "not_running"}
        if self._fishing_module_account() is not None:
            if not self.fishing.ready():
                return {"ok": False, "error": "not_calibrated"}
            self._manual_sell_pending = True
            return {"ok": True}
        if not self.fishing.cycle_enabled():
            return {"ok": False, "error": "fishing_off"}
        if not self.fishing.ready():
            return {"ok": False, "error": "not_calibrated"}
        step = self.fishing.current_step()
        if not step or step.get("type") != "fishing":
            return {"ok": False, "error": "no_account"}
        self._manual_sell_pending = True
        return {"ok": True}

    def sync(self):
        if self._is_tracking() and self.mode() in ("automation", "eden"):
            self.start()
        else:
            self.stop()

    def _loop(self, ev):
        
        import traceback
        while not ev.is_set():
            try:
                self._loop_inner(ev)
                return
            except Exception:
                print(f"[Automation] Loop crashed — recovering in 5s:\n{traceback.format_exc()}")
                self.current_action = "idle"
                self.current_account = ""
                ev.wait(5)

    def _loop_inner(self, ev):
        while not ev.is_set():
            if not (self._is_tracking() and self.mode() in ("automation", "eden")):
                break

            self._refresh_windows()
            now = time.time()


            eden_mode = self.mode() == "eden"
            if not eden_mode and self._prev_eden_acc is not None:
                try:
                    self.eden.pause(self._prev_eden_acc)
                except Exception as e:
                    print(f"[Eden] pause failed: {e}")
                self._prev_eden_acc = None

            step = self.fishing.current_step() if (not eden_mode and self.fishing.cycle_enabled()) else None
            limbo_active = bool(step and step.get("type") == "limboEden" and not step.get("afk"))
            limbo_owns_pop = limbo_active and bool(
                (self.config.automation.get("autopop") or {}).get("leaveLimboOnRareBiome"))
            cur_limbo_acc = step.get("accId") if limbo_active else None
            if self._prev_limbo_acc is not None and self._prev_limbo_acc != cur_limbo_acc:
                try:
                    self.limbo.pause(self._prev_limbo_acc)
                except Exception as e:
                    print(f"[Limbo] pause failed: {e}")
            self._prev_limbo_acc = cur_limbo_acc

            if not limbo_owns_pop:
                while self.autopop.has_pending() and not ev.is_set():
                    job = self.autopop.pop_job()
                    if not job:
                        break
                    acc_id, biome_key = job
                    self.current_action  = "autopop"
                    self.current_account = self._account_name(acc_id)
                    self._run_autopop(acc_id, biome_key, ev)
                    self.current_action  = "idle"
                    self.current_account = ""
            if ev.is_set():
                break

            afk_key = ("__afk__", "antiAfk")
            if not limbo_active and self._anti_afk_enabled() and now >= self._next_run.get(afk_key, now + 1):
                self.current_action  = "antiAfk"
                self.current_account = ""
                self._run_anti_afk()
                self.current_action = "idle"
                self._next_run[afk_key] = time.time() + self._anti_afk_interval()

            if not limbo_active:
                for task in ITEM_TASKS:
                    if ev.is_set():
                        break
                    for acc_id in self.accounts_for(task):
                        if ev.is_set():
                            break
                        key = (acc_id, task)
                        if key not in self._next_run:
                            self._next_run[key] = now
                        if now < self._next_run[key]:
                            continue
                        self.current_action  = task
                        self.current_account = self._account_name(acc_id)
                        self._run_item_task(task, acc_id, ev)
                        self.current_action  = "idle"
                        self.current_account = ""
                        self._next_run[key]  = time.time() + self._interval(task)

            if ev.is_set():
                break

            if not eden_mode and not limbo_active:
                did_chat = False
                if not did_chat:
                    for acc_id in self.accounts_for("merchantTeleporter"):
                        if ev.is_set():
                            break
                        key = (acc_id, "merchantTeleporter")
                        if key not in self._next_run:
                            self._next_run[key] = now
                        if now < self._next_run[key]:
                            continue
                        self.current_action  = "merchantTeleporter"
                        self.current_account = self._account_name(acc_id)
                        self._run_item_task("merchantTeleporter", acc_id, ev)
                        self.current_action  = "idle"
                        self.current_account = ""
                        self._next_run[key]  = time.time() + self._interval("merchantTeleporter")

            if ev.is_set():
                break

            if eden_mode:
                main_acc = self.config.effective_eden_account_id()
                runnable_ids = {a.get("id") for a in self.config.enabled_accounts()}
                runnable = main_acc is not None and main_acc in runnable_ids
                if ev.is_set():
                    break
                if runnable:
                    if self._prev_eden_acc is not None and self._prev_eden_acc != main_acc:
                        try:
                            self.eden.pause(self._prev_eden_acc)
                        except Exception as e:
                            print(f"[Eden] pause failed: {e}")
                    self._prev_eden_acc = main_acc
                    self.current_action  = "eden"
                    self.current_account = self._account_name(main_acc)
                    self.eden.run_spam(main_acc, ev)
                    self.current_action  = "idle"
                    self.current_account = ""
                else:
                    if self._prev_eden_acc is not None:
                        try:
                            self.eden.pause(self._prev_eden_acc)
                        except Exception as e:
                            print(f"[Eden] pause failed: {e}")
                        self._prev_eden_acc = None
                    if not self._fishing_warned:
                        print("[Eden] No runnable Eden account available.")
                        self._fishing_warned = True
                    ev.wait(1.0)
                continue


            if ev.is_set():
                break


            if not eden_mode and not limbo_active:
                facc = self._fishing_module_account()
                if facc is not None and self.fishing.ready():
                    self._fishing_warned = False
                    manual = self._manual_sell_pending
                    self._manual_sell_pending = False
                    self.current_action  = "fishing"
                    self.current_account = self._account_name(facc)
                    with self._action_lock:
                        self.fishing._module_active = True
                        try:
                            if manual:
                                self.fishing.run_sell(ev, focus_fn=lambda: self._focus_account(facc), account=self._account_obj(facc))
                            else:
                                self.fishing.do_cycle(ev, focus_fn=lambda: self._focus_account(facc), account=self._account_obj(facc))
                        finally:
                            self.fishing._module_active = False
                    self.current_action  = "idle"
                    self.current_account = ""
                    continue
                elif facc is not None and not self._fishing_warned:



                    msg = "Fishing is on but its click points are not set. Open Calibration and set the 7 fishing points."
                    print(f"[Automation] {msg}")
                    status_events.push_event(msg, kind="warn", ttl=None)
                    status_events.set_detail("Fishing needs calibration")
                    self._fishing_warned = True

            self.current_action  = "idle"
            self.current_account = ""
            ev.wait(1.0)

    def _run_anti_afk(self):
        with self._action_lock:
            try:
                if self._anti_afk:
                    self._anti_afk.fire_now()
                    print("[Automation] Ran task 'antiAfk'.")
                return True
            except Exception as e:
                print(f"[Automation] Task 'antiAfk' failed: {e}")
                return False

    def _run_item_task(self, task, acc_id, ev):
        if not self.pixels_ready():
            print(f"[Automation] Skipped '{task}': click points not set.")
            return False
        self._refresh_windows(force=True)
        with self._action_lock:
            input_held = False
            try:
                input_held = self._begin_input_transaction()
                if not self._focus_account(acc_id):
                    print(f"[Automation] Skipped '{task}' on '{self._account_name(acc_id)}': "
                          f"no verified Roblox window (not running on wrong account).")
                    return False
                used_at = self._use_inventory_item(self._search_term(task), task, ev)
                used = bool(used_at)
                if used:
                    print(f"[Automation] Ran '{task}' on '{self._account_name(acc_id)}'.")
                else:
                    print(f"[Automation] Skipped '{task}' on '{self._account_name(acc_id)}' "
                          f"(item not confirmed after {ITEM_OCR_ATTEMPTS} tries).")

                if task in ("strangeController", "biomeRandomizer"):
                    if used:
                        try:
                            self.config.increment_module_use(task, acc_id, used_at=used_at)
                        except Exception as e:
                            print(f"[Automation] module count failed: {e}")
                    self._notify_module(task, acc_id, used,
                                        detail="" if used else "Item not confirmed")
                if used and task == "merchantTeleporter":
                    self.merchant._merchant_detect(ev, acc_id=acc_id)
                elif not used and task == "merchantTeleporter":
                    self._notify_failsafe("Merchant Detection Item Failsafe", acc_id,
                                          False, detail="Item not confirmed")
                return used
            except Exception as e:
                print(f"[Automation] Task '{task}' failed: {e}")
                return False
            finally:
                self._end_input_transaction(input_held)

    def _click_slot(self, slot, settle, ev, *, commit_on_click=False):
        pos = self._pixels().get(slot)
        if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
            raise RuntimeError(f"click point '{slot}' is not set")
        x, y = int(pos[0]), int(pos[1])

        if not self._ensure_action_focus():
            raise RuntimeError(f"focus lost before moving to click point '{slot}'")
        try:
            win_input.move_to(x + 60, y + 60, duration=0.05)
            time.sleep(0.04)
            win_input.move_to(x, y, duration=0.08)
            time.sleep(0.05)
        except Exception:
            pass
        if not self._ensure_action_focus():
            raise RuntimeError(f"focus lost before click point '{slot}'")


        win_input.move_to(x, y, duration=0.01, steps=1)
        if win_windows.foreground_hwnd() != int(self._active_action_hwnd):
            raise RuntimeError(f"focus changed immediately before click point '{slot}'")


        clicked_at = time.time()
        if win_input.click_here(settle=0.06) is False:
            raise RuntimeError(f"Windows rejected click point '{slot}'")
        if ev.is_set():
            if commit_on_click:
                return clicked_at
            raise RuntimeError("stopped")
        time.sleep(settle)
        return clicked_at

    def _enter_search(self, search_term, ev):
        self._click_slot("search_bar", 0.55, ev)
        self._replace_active_text(search_term)
        time.sleep(0.90)

        pos = self._pixels().get("search_bar")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            try:
                win_input.move_to(int(pos[0]), int(pos[1]))
            except Exception:
                pass
        time.sleep(0.18)

    def _use_inventory_item(self, search_term, task, ev):
        self._click_slot("inventory_button", 1.10, ev)
        self._click_slot("item_tab", 0.80, ev)

        task_label = DEFAULT_TERMS.get(task, task)
        ocr_on = self._ocr_enabled(task) and ocr.available() and self._item_region() is not None

        confirmed = True
        for attempt in range(1, ITEM_OCR_ATTEMPTS + 1):
            if ev.is_set():
                raise RuntimeError("stopped")
            self._enter_search(search_term, ev)
            if ocr_on:
                status_events.push_event(f"{task_label}: checking item…", kind="info", ttl=1.5)
            result = self._verify_item(search_term, task)
            if result is None:
                confirmed = True
                break
            if result:
                confirmed = True
                status_events.push_event(f"{task_label}: item confirmed", kind="good", ttl=1.8)
                break
            confirmed = False
            if attempt < ITEM_OCR_ATTEMPTS:
                print(f"[Automation] Item mismatch (try {attempt}/{ITEM_OCR_ATTEMPTS}), retrying.")
                status_events.push_event(
                    f"{task_label} failsafe: wrong item — retry {attempt}/{ITEM_OCR_ATTEMPTS}",
                    kind="warn", ttl=2.2)
                time.sleep(0.35)

        if not confirmed:
            status_events.push_event(
                f"{task_label} failsafe failed — skipping use", kind="bad", ttl=2.5)
            self._notify_failsafe(f"{task_label} Item Failsafe", None, False,
                                  detail="Wrong item after retries")
            self._click_slot("inventory_button", 0.55, ev)
            return False

        self._click_slot("first_item_slot", 0.55, ev)
        self._click_slot("amount_box", 0.55, ev)
        self._replace_active_text(self._amount())
        time.sleep(0.45)



        used_at = self._click_slot("use_button", 0.85, ev, commit_on_click=True)
        if not ev.is_set():
            try:
                self._click_slot("inventory_button", 0.55, ev)
            except Exception as e:
                print(f"[Automation] Item was used, but Inventory cleanup failed: {e}")
        return used_at

    def _use_simple_item(self, search_term, amount, ev):
        
        if not self.pixels_ready():
            print("[Limbo] Item use skipped: inventory click points not set.")
            return False
        self._click_slot("inventory_button", 1.10, ev)
        self._click_slot("item_tab", 0.80, ev)
        self._enter_search(search_term, ev)
        self._click_slot("first_item_slot", 0.55, ev)
        self._click_slot("amount_box", 0.55, ev)
        self._replace_active_text(str(amount))
        time.sleep(0.45)
        self._click_slot("use_button", 0.85, ev)
        self._click_slot("inventory_button", 0.55, ev)
        return True

    def _autopop_notif_account(self, acc_id):
        return self._account_obj(acc_id)

    def _autopop_notify_used(self, acc_id, biome_key, used_items):
        if not self.autopop.notify_use():
            return
        urls = self._notif_urls()
        if not urls:
            return
        try:
            webhooks.autopop_used(
                urls, self._autopop_notif_account(acc_id), biome_key, used_items,
                self._notif_session_time(), self._notif_version(),
            )
        except Exception as e:
            print(f"[AutoPop] Used webhook failed: {e}")

    def _autopop_notify_failsafe(self, acc_id, biome_key, missing_items):
        if not self.autopop.notify_fail():
            return
        urls = self._notif_urls()
        if not urls:
            return
        try:
            webhooks.autopop_failsafe(
                urls, self._autopop_notif_account(acc_id), biome_key, missing_items,
                self._notif_session_time(), self._notif_version(),
            )
        except Exception as e:
            print(f"[AutoPop] Failsafe webhook failed: {e}")

    @staticmethod
    def _parse_amount_text(text):
        
        import re as _re
        if not text:
            return None
        m = _re.findall(r"\d+", str(text).replace("O", "0").replace("o", "0"))
        if not m:
            return None
        try:
            return int(m[0])
        except ValueError:
            return None

    def _scan_available_amount(self):
        
        region = self.autopop.amount_region()
        if region is None or not ocr.available():
            return None
        x, y, w, h = region
        reads = ocr.read_region_variants(x, y, w, h)
        for txt in reads:
            n = self._parse_amount_text(txt)
            if n is not None and n >= 0:
                print(f"[AutoPop] Amount region read '{txt}' → {n}")
                return n
        print(f"[AutoPop] Amount region unreadable (reads={reads!r}).")
        return None

    def _verify_autopop_item(self, item_name):
        
        if not (self.autopop.ocr_enabled() and ocr.available()):
            return None
        region = self._item_region()
        if region is None:
            return None
        x, y, w, h = region
        ok, text, score = ocr.region_matches(x, y, w, h, item_name, OCR_MATCH_THRESHOLD)
        status = "MATCH" if ok else "MISMATCH"
        print(f"[AutoPop] OCR item='{item_name}' best='{text}' score={score:.2f} → {status}")
        return bool(ok)

    def _use_autopop_item(self, item_name, want_amount, ev, use_all=False):
        
        self._enter_search(item_name, ev)

        verified = self._verify_autopop_item(item_name)
        if verified is False:
            status_events.push_event(f"Auto Pop: '{item_name}' not found", kind="bad", ttl=2.5)
            return (False, 0, "not_found")

        use_amount = 999999 if use_all else max(1, int(want_amount))
        available = self._scan_available_amount()
        if available is not None:
            if available <= 0:
                status_events.push_event(f"Auto Pop: 0× '{item_name}'", kind="warn", ttl=2.2)
                return (False, 0, "empty")
            if available < use_amount:
                print(f"[AutoPop] Want {use_amount}× '{item_name}', only {available} available — using {available}.")
                use_amount = available

        self._click_slot("first_item_slot", 0.55, ev)
        self._click_slot("amount_box", 0.55, ev)
        self._replace_active_text(str(use_amount))
        time.sleep(0.45)
        self._click_slot("use_button", 0.85, ev)
        return (True, use_amount, "")

    def _run_autopop(self, acc_id, biome_key, ev):
        if not self.pixels_ready():
            print("[AutoPop] Skipped: inventory click points not set.")
            return False
        if self.autopop.amount_region() is None:
            print("[AutoPop] Skipped: Amount Scan Region not calibrated (required).")
            status_events.push_event("Auto Pop: set the Amount Scan Region", kind="warn", ttl=3.0)
            return False
        items = self.autopop.items_for(acc_id, biome_key)
        if not items:
            return False

        self._refresh_windows(force=True)
        with self._action_lock:
            input_held = False
            try:
                input_held = self._begin_input_transaction()
                if not self._focus_account(acc_id):
                    print(f"[AutoPop] Skipped on '{self._account_name(acc_id)}': "
                          f"no verified Roblox window.")
                    return False

                self.autopop.phase = "popping"
                self.autopop.current_biome = biome_key
                from . import biomes as _b
                bname = _b.display_name(biome_key)
                status_events.push_event(f"Auto Pop · {bname}", kind="info", ttl=2.0)
                print(f"[AutoPop] Running on '{self._account_name(acc_id)}' for '{biome_key}' "
                      f"({len(items)} item(s)).")

                self._click_slot("inventory_button", 1.10, ev)
                self._click_slot("item_tab", 0.80, ev)

                used_items = []
                missing_items = []
                for it in items:
                    if ev.is_set():
                        break
                    name = it.get("name", "")
                    amount = it.get("amount", 1)
                    if not name:
                        continue
                    used, used_amt, reason = self._use_autopop_item(
                        name, amount, ev, use_all=bool(it.get("all")))
                    if used:
                        used_items.append((name, used_amt))
                        self.autopop.pops += 1
                        print(f"[AutoPop] Used {used_amt}× '{name}'.")
                    else:
                        if reason in ("not_found", "empty"):
                            missing_items.append(name)
                        print(f"[AutoPop] Did not use '{name}' ({reason}).")
                    time.sleep(0.3)

                self._click_slot("inventory_button", 0.55, ev)
                self.autopop.phase = "idle"

                if used_items:
                    self._autopop_notify_used(acc_id, biome_key, used_items)
                    status_events.push_event(
                        f"Auto Pop done · {len(used_items)} item(s)", kind="good", ttl=2.2)
                if missing_items:
                    self._autopop_notify_failsafe(acc_id, biome_key, missing_items)
                return True
            except Exception as e:
                self.autopop.phase = "idle"
                print(f"[AutoPop] Run failed: {e}")
                return False
            finally:
                self._end_input_transaction(input_held)


    @staticmethod
    def _is_pt(v):
        return calibration.is_point(v)

    @staticmethod
    def _is_rg(v):
        return calibration.is_region(v)





    @staticmethod
    def _norm_name(s):
        return detection.norm_name(s)

    def _capture_click(self, timeout=30.0):
        if not win_input.IS_WINDOWS:
            return None
        return win_input.capture_next_click(timeout=timeout)

    def capture(self, slot, timeout=30.0):
        if not win_input.IS_WINDOWS:
            return {"ok": False, "error": "not_windows"}
        if slot not in presets.slot_keys():
            return {"ok": False, "error": "bad_slot"}
        if self._is_tracking():
            return {"ok": False, "error": "tracking_active"}
        pos = win_input.capture_next_click(timeout=timeout)
        if not pos:
            return {"ok": False, "error": "timeout"}
        self.config.set_pixel(slot, [pos[0], pos[1]])
        print(f"[Automation] Captured '{slot}' → {pos[0]}, {pos[1]}")
        return {"ok": True, "slot": slot, "x": pos[0], "y": pos[1]}
