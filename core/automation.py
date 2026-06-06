import time
import threading

from . import win_input, presets
from .anti_afk import focus_roblox

STRANGE_INTERVAL = 21 * 60
BIOME_INTERVAL = 36 * 60

TASK_ORDER = ("antiAfk", "strangeController", "biomeRandomizer")
ITEM_TASKS = ("strangeController", "biomeRandomizer")

DEFAULT_TERMS = {
    "strangeController": "Strange Controller",
    "biomeRandomizer": "Biome Randomizer",
}
DEFAULT_INTERVALS = {
    "strangeController": STRANGE_INTERVAL,
    "biomeRandomizer": BIOME_INTERVAL,
}

class AutomationEngine:
    def __init__(self, config, is_tracking, anti_afk=None):
        self.config = config
        self._is_tracking = is_tracking
        self._anti_afk = anti_afk
        self._stop = threading.Event()
        self._thread = None
        self._action_lock = threading.Lock()
        self._next_run = {}

    def _auto(self):
        return self.config.data.setdefault("automation", {})

    def mode(self):
        return self._auto().get("mode", "idle")

    def _task_enabled(self, task):
        if task == "antiAfk":

            return bool(self.config.settings.get("antiAfkEnabled", False))
        return bool(self._auto().get(task, False))

    def _interval(self, task):
        if task == "antiAfk":
            try:
                return max(30, int(self.config.settings.get("antiAfkInterval", 300)))
            except (TypeError, ValueError):
                return 300
        intervals = self._auto().get("intervals", {})
        return int(intervals.get(task, DEFAULT_INTERVALS[task]))

    def _search_term(self, task):
        terms = self._auto().get("searchTerms", {})
        return str(terms.get(task) or DEFAULT_TERMS[task])

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

    def start(self):
        if not win_input.IS_WINDOWS:
            return

        self.stop()
        ev = threading.Event()
        self._stop = ev
        now = time.time()

        self._next_run = {t: now for t in TASK_ORDER}
        self._thread = threading.Thread(target=self._loop, args=(ev,), daemon=True)
        self._thread.start()
        print("[Automation] Started.")

    def stop(self):
        if self._thread:
            print("[Automation] Stopped.")
        self._stop.set()
        self._thread = None
        self._next_run = {}

    def sync(self):
        if self._is_tracking() and self.mode() == "automation":
            self.start()
        else:
            self.stop()

    def _loop(self, ev):
        while not ev.is_set():
            if not (self._is_tracking() and self.mode() == "automation"):
                break

            now = time.time()
            for task in TASK_ORDER:
                if ev.is_set():
                    break
                if not self._task_enabled(task):
                    continue
                if now >= self._next_run.get(task, now):
                    self._run_task(task, ev)

                    self._next_run[task] = time.time() + self._interval(task)

            ev.wait(1.0)

    def _run_task(self, task, ev):

        if task == "antiAfk":
            with self._action_lock:
                try:
                    if self._anti_afk:
                        self._anti_afk.fire_now()
                        print("[Automation] Ran task 'antiAfk'.")
                    return True
                except Exception as e:
                    print(f"[Automation] Task 'antiAfk' failed: {e}")
                    return False

        if not self.pixels_ready():
            print(f"[Automation] Skipped '{task}': click points not set.")
            return False
        with self._action_lock:
            try:

                focus_roblox()
                self._use_inventory_item(self._search_term(task), ev)
                print(f"[Automation] Ran task '{task}'.")
                return True
            except Exception as e:
                print(f"[Automation] Task '{task}' failed: {e}")
                return False

    def _use_inventory_item(self, search_term, ev):
        px = self._pixels()

        def click(slot, settle):
            pos = px.get(slot)
            if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
                raise RuntimeError(f"click point '{slot}' is not set")
            win_input.click_at(int(pos[0]), int(pos[1]))
            if ev.is_set():
                raise RuntimeError("stopped")
            time.sleep(settle)

        click("inventory_button", 1.10)
        click("item_tab", 0.80)
        click("search_bar", 0.55)
        win_input.select_all_and_clear()
        time.sleep(0.25)
        win_input.type_text(search_term)
        time.sleep(0.90)

        click("first_item_slot", 0.55)

        click("amount_box", 0.55)
        win_input.select_all_and_clear()
        time.sleep(0.20)
        win_input.type_text(self._amount())
        time.sleep(0.45)

        click("use_button", 0.85)
        click("inventory_button", 0.55)

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
        print(f"[Automation] Captured '{slot}' -> {pos[0]}, {pos[1]}")
        return {"ok": True, "slot": slot, "x": pos[0], "y": pos[1]}
