

import time

from . import win_input

EDEN_BURST = 3.0


class EdenController:
    def __init__(self, auto):
        self.auto = auto
        self._clock = {}
        self._persist = {}

    def reset(self):
        self._clock.clear()
        self._persist.clear()

    def _start_clock(self, acc_id):
        now = time.monotonic()
        self._clock[acc_id] = now
        self._persist[acc_id] = now

    def _flush_clock(self, acc_id, keep=False):
        last = self._clock.get(acc_id)
        if last is None:
            return
        delta = time.monotonic() - last
        if delta > 0:
            try:
                self.auto.config.add_eden_time(acc_id, delta)
            except Exception as e:
                print(f"[Eden] eden time accrue failed: {e}")
        if keep:
            self._clock[acc_id] = time.monotonic()
        else:
            self._clock.pop(acc_id, None)
            self._persist.pop(acc_id, None)

    def pause(self, acc_id):
        
        self._flush_clock(acc_id)

    def _accrue(self, acc_id):
        if self._clock.get(acc_id) is None:
            self._start_clock(acc_id)
        elif time.monotonic() - self._persist.get(acc_id, 0.0) >= 60:
            self._flush_clock(acc_id, keep=True)
            self._persist[acc_id] = time.monotonic()

    def run_spam(self, acc_id, ev):
        
        a = self.auto
        self._accrue(acc_id)
        pt = a._eden_click_point()
        with a._action_lock:
            if not a._focus_account(acc_id):
                ev.wait(1.0)
                return
            cx = cy = None
            if pt:
                cx, cy = int(pt[0]), int(pt[1])
            deadline = time.monotonic() + EDEN_BURST
            while not ev.is_set() and time.monotonic() < deadline:
                win_input.press_key("e", 0.02)
                if cx is not None:
                    win_input.click_at(cx, cy, settle=0.02)
                ev.wait(0.10)
