

from datetime import datetime
import hashlib
import json
import os
import threading
import time
import uuid

from . import perf


def benchmark_settings(settings):
    
    source = settings or {}



    raw_method = source.get("throttleMethod")
    method = "cpuLimit" if raw_method in {"suspend", "cpuLimit"} else "efficiency"
    return {
        "throttleMethod": method,
        "throttleQuota": max(2, min(95, int(source.get("throttleQuota", 12) or 12))),
        "throttleRamCap": bool(source.get("throttleRamCap", False)),
        "throttleRamCapMb": max(150, min(2000, int(source.get("throttleRamCapMb", 400) or 400))),


        "throttleScope": "all",
        "throttleFocusAware": False,
        "throttleOnlyWhenRunning": False,
    }


def settings_fingerprint(settings):
    normalized = benchmark_settings(settings)
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _percent_saved(before, after):
    before = float(before or 0)
    if before <= 0:
        return 0.0
    return round(((before - float(after or 0)) / before) * 100.0, 1)


def _metric_stats(values, *, integer=False):
    
    clean = [max(0.0, float(value)) for value in values or []]
    if not clean:
        empty = 0 if integer else 0.0
        return {"min": empty, "max": empty, "average": empty, "estimate": empty, "samples": 0}

    ordered = sorted(clean)
    robust = ordered[1:-1] if len(ordered) >= 5 else ordered
    average = sum(ordered) / len(ordered)
    estimate = sum(robust) / len(robust)

    def format_value(value):
        return round(value) if integer else round(value, 2)

    return {
        "min": format_value(ordered[0]),
        "max": format_value(ordered[-1]),
        "average": format_value(average),
        "estimate": format_value(estimate),
        "samples": len(ordered),
    }


def _summarize_windows(pids, samples):
    windows = []
    for index, pid in enumerate(pids or []):
        window_samples = samples.get(pid, {})
        ram = _metric_stats(window_samples.get("ramBytes", []), integer=True)
        cpu = _metric_stats(window_samples.get("cpuPercent", []))
        if not ram["samples"] and not cpu["samples"]:
            continue
        windows.append({
            "pid": int(pid),
            "label": f"Roblox #{index + 1}",
            "ram": ram,
            "cpu": cpu,
        })

    return {
        "windows": windows,
        "ramBytes": sum(item["ram"]["estimate"] for item in windows),
        "ramMinBytes": sum(item["ram"]["min"] for item in windows),
        "ramMaxBytes": sum(item["ram"]["max"] for item in windows),
        "cpuPercent": round(sum(item["cpu"]["estimate"] for item in windows), 1),
        "cpuMinPercent": round(sum(item["cpu"]["min"] for item in windows), 1),
        "cpuMaxPercent": round(sum(item["cpu"]["max"] for item in windows), 1),
        "samples": sum(max(item["ram"]["samples"], item["cpu"]["samples"]) for item in windows),
        "liveProcesses": len(windows),
    }


class PerformanceBenchmark:
    def __init__(self, config, throttler, phase_seconds=60.0, sample_interval=0.5):
        self.config = config
        self.throttler = throttler
        self.phase_seconds = max(0.01, float(phase_seconds))
        self.sample_interval = max(0.01, float(sample_interval))
        self._lock = threading.RLock()
        self._thread = None
        self._cancel = threading.Event()
        self._state = {
            "running": False,
            "phase": "idle",
            "progress": 0.0,
            "secondsRemaining": 0.0,
            "error": None,
        }

    def _history(self):
        history = self.config.settings.get("performanceBenchmarks", [])
        return list(history) if isinstance(history, list) else []

    def status(self):
        with self._lock:
            state = dict(self._state)
        history = self._history()
        current_fingerprint = settings_fingerprint(self.config.settings)
        state.update({
            "supported": perf.IS_WINDOWS,
            "durationSeconds": round(self.phase_seconds * 2),
            "history": history,
            "latest": history[-1] if history else None,
            "currentSettingsFingerprint": current_fingerprint,
            "settingsChanged": bool(history and history[-1].get("settingsFingerprint") != current_fingerprint),
        })
        return state

    def start(self):
        if not perf.IS_WINDOWS:
            return {**self.status(), "ok": False, "error": "not_windows"}
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return {**self.status(), "ok": False, "error": "already_running"}
            self._cancel = threading.Event()
            self._state = {
                "running": True,
                "phase": "preparing",
                "progress": 0.0,
                "secondsRemaining": round(self.phase_seconds * 2, 1),
                "error": None,
            }
            self._thread = threading.Thread(
                target=self._run,
                name="performance-benchmark",
                daemon=True,
            )
            self._thread.start()
        return {**self.status(), "ok": True}

    def stop(self):
        self._cancel.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self.throttler.restore_after_benchmark()

    def _set_progress(self, phase, phase_progress):
        phase_progress = max(0.0, min(1.0, float(phase_progress)))
        base = 0.0 if phase == "unthrottled" else 0.5
        total_progress = base + (phase_progress * 0.5)
        remaining = self.phase_seconds * 2 * (1.0 - total_progress)
        with self._lock:
            self._state.update({
                "phase": phase,
                "progress": round(total_progress, 4),
                "secondsRemaining": round(max(0.0, remaining), 1),
            })

    def _measure_phase(self, pids, phase):
        start = time.monotonic()
        baseline = perf.process_counters(pids)
        previous = baseline
        previous_time = start
        samples = {
            pid: {"ramBytes": [], "cpuPercent": []}
            for pid in pids
        }
        for pid, counter in baseline.items():
            samples.setdefault(pid, {"ramBytes": [], "cpuPercent": []})["ramBytes"].append(
                counter["ramBytes"]
            )

        def collect(current, current_time):
            interval = max(0.001, current_time - previous_time)
            for pid, counter in current.items():
                window_samples = samples.setdefault(pid, {"ramBytes": [], "cpuPercent": []})
                window_samples["ramBytes"].append(counter["ramBytes"])
                prior = previous.get(pid)
                if prior:
                    cpu_delta = max(
                        0,
                        int(counter["cpuTime100ns"]) - int(prior["cpuTime100ns"]),
                    )
                    cpu_percent = (
                        (cpu_delta * 1e-7)
                        / interval
                        / max(1, os.cpu_count() or 1)
                        * 100.0
                    )
                    window_samples["cpuPercent"].append(cpu_percent)

        while not self._cancel.is_set():
            elapsed = time.monotonic() - start
            if elapsed >= self.phase_seconds:
                break
            self._set_progress(phase, elapsed / self.phase_seconds)
            wait_for = min(self.sample_interval, self.phase_seconds - elapsed)
            if self._cancel.wait(wait_for):
                break
            current_time = time.monotonic()
            current = perf.process_counters(pids)
            if current:
                collect(current, current_time)
                previous = current
                previous_time = current_time

        elapsed = max(0.001, time.monotonic() - start)
        current_time = time.monotonic()
        current = perf.process_counters(pids)
        if current:
            collect(current, current_time)
        self._set_progress(phase, 1.0)
        summary = _summarize_windows(pids, samples)
        summary["seconds"] = round(elapsed, 2)
        return summary

    def _run(self):
        prepared = False
        try:
            if not self.throttler.prepare_benchmark():
                raise RuntimeError("benchmark_unavailable")
            prepared = True

            pids = sorted(set(perf.roblox_pids()))
            if not pids:
                raise RuntimeError("no_roblox_windows")

            settings = benchmark_settings(self.config.settings)
            fingerprint = settings_fingerprint(settings)
            with self._lock:
                self._state["windowCount"] = len(pids)

            unthrottled = self._measure_phase(pids, "unthrottled")
            if self._cancel.is_set():
                raise RuntimeError("cancelled")
            if not self.throttler.apply_benchmark(pids, settings):
                raise RuntimeError("throttle_start_failed")
            throttled = self._measure_phase(pids, "throttled")
            if self._cancel.is_set():
                raise RuntimeError("cancelled")

            ram_saved = int(unthrottled["ramBytes"] - throttled["ramBytes"])
            cpu_saved = round(unthrottled["cpuPercent"] - throttled["cpuPercent"], 1)
            result = {
                "id": uuid.uuid4().hex,
                "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
                "accountCount": len(pids),
                "durationSeconds": round(self.phase_seconds * 2),
                "settings": settings,
                "settingsFingerprint": fingerprint,
                "unthrottled": unthrottled,
                "throttled": throttled,
                "savings": {
                    "ramBytes": ram_saved,
                    "ramPercent": _percent_saved(unthrottled["ramBytes"], throttled["ramBytes"]),
                    "cpuPercent": cpu_saved,
                    "cpuReductionPercent": _percent_saved(unthrottled["cpuPercent"], throttled["cpuPercent"]),
                },
            }
            with self.config._lock:
                history = self.config.settings.setdefault("performanceBenchmarks", [])
                if not isinstance(history, list):
                    history = []
                    self.config.settings["performanceBenchmarks"] = history
                history.append(result)
                self.config.save()
            with self._lock:
                self._state.update({
                    "running": False,
                    "phase": "complete",
                    "progress": 1.0,
                    "secondsRemaining": 0.0,
                    "error": None,
                    "result": result,
                })
        except RuntimeError as error:
            code = str(error)
            with self._lock:
                self._state.update({
                    "running": False,
                    "phase": "error" if code != "cancelled" else "cancelled",
                    "secondsRemaining": 0.0,
                    "error": code,
                })
        except Exception as error:
            print(f"[Benchmark] Failed: {error}")
            with self._lock:
                self._state.update({
                    "running": False,
                    "phase": "error",
                    "secondsRemaining": 0.0,
                    "error": "benchmark_failed",
                })
        finally:
            if prepared:
                self.throttler.restore_after_benchmark()
