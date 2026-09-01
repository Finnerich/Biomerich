

from __future__ import annotations

import re
import threading

from .aura import aura_key
from . import decision_trace


CLIP_BIOMES = ("glitched", "dreamspace", "cyberspace", "singularity")
MAX_DELAY_SECONDS = 60 * 60
MAX_PENDING_CLIPS = 50


def _positive_int(value):
    try:
        number = int(str(value or "").replace(",", "").replace("_", "").strip())
    except (TypeError, ValueError):
        return None
    return number if number >= 1 else None


def _delay(value, default=0) -> int:
    try:
        number = int(str(value or "").strip())
    except (TypeError, ValueError):
        number = default
    return max(0, min(MAX_DELAY_SECONDS, number))


def _name_keys(value) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {
        key
        for part in re.split(r"[,\n;]+", value)
        if (key := aura_key(part))
    }


def biome_clip_decision(biome_key, settings, result) -> dict:
    
    settings = settings or {}
    result = result or {}
    key = str(biome_key or "").strip().casefold()
    display = key.replace("_", " ").title() or "Unknown biome"
    selected = settings.get("clipBiomes", list(CLIP_BIOMES))
    selected = {str(item).strip().casefold() for item in selected} if isinstance(selected, list) else set()
    enabled = bool(settings.get("clippingEnabled", False))
    hotkey = str(settings.get("clipHotkey") or "F8").strip() or "Not set"
    delay = _delay(settings.get("clipBiomeDelay", 60), 60)
    error = str(result.get("error") or "")
    scheduled = bool(result.get("ok"))
    checks = [
        decision_trace.check("Automatic Clipping is enabled", enabled),
        decision_trace.check("Biome is selected for clipping", key in selected),
        decision_trace.check("Clip hotkey is valid and available", error != "invalid_or_conflicting_hotkey"),
        decision_trace.check("Clip was scheduled", scheduled),
    ]
    facts = [
        decision_trace.fact("Biome", display),
        decision_trace.fact("Clip delay", f"{delay} seconds"),
        decision_trace.fact("Clip hotkey", hotkey),
    ]
    next_step = {"label": "Open Clip Settings", "tab": "modules", "drawer": "clipping"}
    if scheduled:
        return decision_trace.make(
            "waiting", "clip_scheduled", "Automatic Clipping",
            f"A {display} clip was scheduled and will use {hotkey} after {delay} seconds.",
            checks=checks, facts=facts, next_step=next_step,
        )
    summaries = {
        "not_selected": f"No clip was scheduled because {display} is not selected in Biome clips.",
        "disabled": "No clip was scheduled because Automatic Clipping is disabled.",
        "invalid_or_conflicting_hotkey": "No clip was scheduled because the clip hotkey is invalid or conflicts with another macro hotkey.",
        "too_many_pending": "No clip was scheduled because too many clips are already waiting.",
    }
    status = "failed" if error in {"invalid_or_conflicting_hotkey", "too_many_pending"} else "skipped"
    return decision_trace.make(
        status, error or "clip_not_scheduled", "Automatic Clipping",
        summaries.get(error, "SolRich could not schedule the biome clip."),
        checks=checks, facts=facts, next_step=next_step,
    )


def _clip_fire_decision(status, reason_code, reason, hotkey, summary):
    return decision_trace.make(
        status, reason_code, "Automatic Clipping", summary,
        checks=[
            decision_trace.check("Scheduled delay finished", True),
            decision_trace.check("Clip hotkey is valid and available", status != "cancelled"),
            decision_trace.check("Clip hotkey was sent", status == "acted"),
        ],
        facts=[
            decision_trace.fact("Trigger", reason),
            decision_trace.fact("Clip hotkey", hotkey or "Not set"),
        ],
        next_step={"label": "Open Clip Settings", "tab": "modules", "drawer": "clipping"},
    )


class ClippingController:
    

    def __init__(self, config, sender=None):
        self.config = config
        self._sender = sender or self._send_keyboard_hotkey
        self._lock = threading.RLock()
        self._timers = set()

    @property
    def settings(self):
        return getattr(self.config, "settings", {}) or {}

    def enabled(self) -> bool:
        return bool(self.settings.get("clippingEnabled", False))

    def _hotkey(self) -> str:
        hotkey = str(self.settings.get("clipHotkey") or "F8").strip()
        normalized = hotkey.casefold()
        if not hotkey or len(hotkey) > 80 or any(char in hotkey for char in "\r\n"):
            return ""
        try:
            import keyboard



            if len(keyboard.parse_hotkey(normalized)) != 1:
                return ""
        except (ImportError, KeyError, TypeError, ValueError):
            return ""
        conflicts = {
            str(self.settings.get("hotkey") or "").strip().casefold(),
            str(self.settings.get("modeHotkey") or "").strip().casefold(),
        }
        return "" if normalized in conflicts else hotkey

    @staticmethod
    def _send_keyboard_hotkey(hotkey):
        import keyboard

        keyboard.send(hotkey)

    def _schedule(self, reason, delay_seconds, require_enabled=True,
                  account=None, account_id=None) -> dict:
        hotkey = self._hotkey()
        if not hotkey:
            return {"ok": False, "error": "invalid_or_conflicting_hotkey"}
        if require_enabled and not self.enabled():
            return {"ok": False, "error": "disabled"}

        delay_seconds = _delay(delay_seconds)
        timer = None

        def fire():
            try:
                if require_enabled and not self.enabled():
                    try:
                        from . import status_events
                        status_events.push_event(
                            f"Clip cancelled · {reason}", kind="warn", ttl=5.0,
                            account=account, account_id=account_id, category="clip",
                            decision=_clip_fire_decision(
                                "cancelled", "clipping_disabled_during_delay", reason,
                                hotkey, "The scheduled clip was cancelled because Automatic Clipping was disabled during the delay.",
                            ),
                        )
                    except Exception:
                        pass
                    return
                current_hotkey = self._hotkey()
                if not current_hotkey:
                    print(
                        f"[Clipping] Cancelled {reason}: the clip hotkey is now "
                        "invalid or conflicts with another macro hotkey."
                    )
                    try:
                        from . import status_events
                        status_events.push_event(
                            f"Clip cancelled · {reason}", kind="warn", ttl=5.0,
                            account=account, account_id=account_id, category="clip",
                            decision=_clip_fire_decision(
                                "cancelled", "clip_hotkey_became_invalid", reason,
                                hotkey, "The scheduled clip was cancelled because the hotkey became invalid or conflicting during the delay.",
                            ),
                        )
                    except Exception:
                        pass
                    return
                self._sender(current_hotkey)
                try:
                    from . import status_events

                    status_events.push_event(
                        f"Clip saved · {reason}", kind="good", ttl=4.0,
                        account=account, account_id=account_id, category="clip",
                        decision=_clip_fire_decision(
                            "acted", "clip_hotkey_sent", reason, current_hotkey,
                            f"SolRich sent {current_hotkey} after the configured delay for {reason}.",
                        ),
                    )
                except Exception:
                    pass
                print(f"[Clipping] Sent {current_hotkey} for {reason}.")
            except Exception as exc:
                print(f"[Clipping] Could not send {hotkey}: {exc}")
                try:
                    from . import status_events
                    status_events.push_event(
                        f"Clip failed · {reason}", kind="bad", ttl=5.0,
                        account=account, account_id=account_id, category="clip",
                        decision=_clip_fire_decision(
                            "failed", "clip_hotkey_send_failed", reason, hotkey,
                            "The delay finished, but Windows could not send the configured clip hotkey.",
                        ),
                    )
                except Exception:
                    pass
            finally:
                with self._lock:
                    self._timers.discard(timer)

        with self._lock:
            if len(self._timers) >= MAX_PENDING_CLIPS:
                return {"ok": False, "error": "too_many_pending"}
            timer = threading.Timer(delay_seconds, fire)
            timer.daemon = True
            self._timers.add(timer)
            timer.start()
        print(f"[Clipping] Scheduled {hotkey} in {delay_seconds}s for {reason}.")
        return {"ok": True, "hotkey": hotkey, "delay": delay_seconds}

    def on_biome(self, biome_key, account=None, account_id=None) -> dict:
        selected = self.settings.get("clipBiomes", list(CLIP_BIOMES))
        selected = (
            {str(item).strip().casefold() for item in selected}
            if isinstance(selected, list)
            else set()
        )
        key = str(biome_key or "").strip().casefold()
        if key not in CLIP_BIOMES or key not in selected:
            return {"ok": False, "error": "not_selected"}
        return self._schedule(
            f"{key} biome",
            self.settings.get("clipBiomeDelay", 60),
            account=account,
            account_id=account_id,
        )

    def on_aura(self, event) -> dict:
        event = event or {}
        names = {
            aura_key(event.get("rawAura")),
            aura_key(event.get("aura")),
        }
        names.discard("")
        explicit = bool(names & _name_keys(self.settings.get("clipAuraNames")))
        minimum = _positive_int(
            self.settings.get("clipAuraMinimumRarity", 99_999_999)
        )
        rarity = event.get("rarity")
        meets_rarity = (
            minimum is not None
            and isinstance(rarity, int)
            and rarity >= minimum
        )
        if not explicit and not meets_rarity:
            return {"ok": False, "error": "not_selected"}
        return self._schedule(
            f"{event.get('aura') or event.get('rawAura') or 'aura'} aura",
            self.settings.get("clipAuraDelay", 60),
            account=event.get("account"),
            account_id=event.get("accountId"),
        )

    def test_hotkey(self) -> dict:
        
        return self._schedule("hotkey test", 5, require_enabled=False)

    def stop(self):
        with self._lock:
            timers = list(self._timers)
            self._timers.clear()
        for timer in timers:
            timer.cancel()
