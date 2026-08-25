






import { useRef, useState } from "react";

import { callPy } from "../bridge";
import { CustomSelect } from "../components/CustomSelect";
import { NAV_ANIMS, THEME_ANIMS, applyNavAnim } from "../components/ThemeCanvas";
import { ThemePicker } from "../components/ThemePicker";
import { ACCENTS, applyAccent, getAccentIndex } from "../data/accents";
import { alertDialog, confirmDialog } from "../dialog";
import { useStore } from "../store";
import { withColorTransition } from "../themeFlash";

const F_KEYS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"];

interface RobloxLogCleanupResult {
  ok?: boolean;
  error?: string | null;
  closedInstances?: number;
  deletedItems?: number;
  remainingItems?: number;
  failedFiles?: string[];
}



function LockPill({ name }: { name: string }) {
  return (
    <span className="lock-pill">
      <i className="fa-solid fa-lock"></i> {name} theme
    </span>
  );
}



export function Settings() {
  const settings = useStore((s) => s.settings);
  const patchSettings = useStore((s) => s.patchSettings);
  const running = useStore((s) => s.running);
  const pushToast = useStore((s) => s.pushToast);
  const themeLock = useStore((s) => s.themeLock);
  const locked = !!themeLock;
  const dimDebounce = useRef<number | null>(null);
  const [clearingLogs, setClearingLogs] = useState(false);

  const accentIndex = getAccentIndex(settings.accentIndex);
  const hotkey = (settings.hotkey as string) || "F5";
  const modeHotkey = (settings.modeHotkey as string) || "none";
  const themeAnim = (settings.themeAnim as string) || localStorage.getItem("themeAnim") || "none";
  const navAnim = (settings.navAnim as string) || localStorage.getItem("navAnim") || "none";

  function setAccent(index: number) {
    withColorTransition(() => applyAccent(index));
    patchSettings({ accentIndex: index });
    localStorage.setItem("accentIndex", String(index));
    void callPy("set_setting", "accentIndex", index);
  }
  function setThemeAnim(key: string) {
    patchSettings({ themeAnim: key });
    localStorage.setItem("themeAnim", key);
    void callPy("set_setting", "themeAnim", key);
  }
  function setNavAnim(key: string) {
    applyNavAnim(key);
    patchSettings({ navAnim: key });
    localStorage.setItem("navAnim", key);
    void callPy("set_setting", "navAnim", key);
  }

  function onHotkeyChange(key: string) {
    if (key === modeHotkey) {
      void alertDialog(`${key} is already used for Mode Toggle. Pick a different key.`, { title: "F-key conflict" });
      return;
    }
    patchSettings({ hotkey: key });
    void callPy("set_setting", "hotkey", key);
  }
  function onModeHotkeyChange(key: string) {
    if (key !== "none" && key === hotkey) {
      void alertDialog(`${key} is already used for Start/Stop. Pick a different key.`, { title: "F-key conflict" });
      return;
    }
    patchSettings({ modeHotkey: key });
    void callPy("set_setting", "modeHotkey", key);
  }

  const dimEnabled = !!settings.monitorDimEnabled;
  const dimLevel = Math.max(0, Math.min(80, Number(settings.monitorDimLevel ?? 40)));
  function onDimToggle(checked: boolean) {
    patchSettings({ monitorDimEnabled: checked });
    void callPy("set_setting", "monitorDimEnabled", checked);
  }
  function onDimLevel(value: number) {
    patchSettings({ monitorDimLevel: value });
    if (dimDebounce.current) window.clearTimeout(dimDebounce.current);
    dimDebounce.current = window.setTimeout(() => {
      void callPy("set_setting", "monitorDimLevel", value);
    }, 300);
  }

  async function clearRobloxLogs() {
    if (running || clearingLogs) return;
    const confirmed = await confirmDialog(
      "This closes every open Roblox instance, including background/tray instances, and permanently deletes everything inside %LOCALAPPDATA%\\Roblox\\logs. Continue?",
      {
        title: "Clear Roblox logs",
        confirmLabel: "Close Roblox & clear logs",
        cancelLabel: "Cancel",
        danger: true,
      },
    );
    if (!confirmed) return;

    setClearingLogs(true);
    let result: RobloxLogCleanupResult | null = null;
    try {
      result = await callPy<RobloxLogCleanupResult>("clear_roblox_logs");
    } catch {
      result = { ok: false, error: "backend_unavailable" };
    } finally {
      setClearingLogs(false);
    }

    const closed = Number(result?.closedInstances) || 0;
    const deleted = Number(result?.deletedItems) || 0;
    if (result?.ok) {
      const detail = closed || deleted
        ? `Closed ${closed} Roblox instance${closed === 1 ? "" : "s"} and deleted ${deleted} log item${deleted === 1 ? "" : "s"}.`
        : "The Roblox logs folder is already clean.";
      pushToast({ icon: "fa-circle-check", title: "Roblox logs cleared", detail });
      return;
    }

    const remaining = Number(result?.remainingItems) || 0;
    let detail = "The log files could not be deleted. Try again.";
    if (result?.error === "running") detail = "Stop the macro before clearing Roblox logs.";
    else if (result?.error === "busy") detail = "A Roblox log cleanup is already running.";
    else if (result?.error === "roblox_still_running") detail = "One or more Roblox instances could not be closed.";
    else if (result?.error === "delete_failed") detail = `${deleted} items were deleted, but ${remaining} could not be removed.`;
    else if (result?.error === "invalid_log_path") detail = "The Roblox logs folder path looks invalid or unsafe.";
    else if (result?.error === "localappdata_unavailable") detail = "The Local AppData folder could not be found.";
    else if (result?.error === "unsupported_platform") detail = "Roblox log cleanup is only available on Windows.";
    else if (result?.error === "backend_unavailable") detail = "The SolRich backend did not respond.";
    pushToast({ icon: "fa-triangle-exclamation", title: "Failed to delete Roblox log files", detail });
  }

  const startOptions = F_KEYS.filter((key) => key === hotkey || key !== modeHotkey).map((key) => ({ value: key, label: key }));
  const modeOptions = [{ value: "none", label: "- Off -" }, ...F_KEYS.filter((key) => key === modeHotkey || key !== hotkey).map((key) => ({ value: key, label: key }))];

  return (
    <section className="tab active-tab" id="settings">
      <header className="page-head">
        <h1>Settings</h1>
        <p>Optimize your experience.</p>
      </header>

      <div className="glass card setting-row" data-reveal>
        <div className="setting-info">
          <span className="setting-name">Accent color{locked && <LockPill name={themeLock!.name} />}</span>
          <span className="setting-desc">Recolor highlights and buttons.</span>
        </div>
        <div className={`swatches${locked ? " picker-locked" : ""}`}>
          {ACCENTS.map((accent, i) => (
            <button
              key={i}
              className={`swatch-btn${i === accentIndex ? " sel" : ""}`}
              style={{ background: accent.c }}
              disabled={locked}
              onClick={() => setAccent(i)}
            ></button>
          ))}
        </div>
      </div>

      <div className="glass card setting-row" data-reveal>
        <div className="setting-info">
          <span className="setting-name">Theme Animation{locked && <LockPill name={themeLock!.name} />}</span>
          <span className="setting-desc">Background particle effect, accent-colored.</span>
        </div>
        <div className={`anim-picker${locked ? " picker-locked" : ""}`}>
          {THEME_ANIMS.map((anim) => (
            <button key={anim.key} className={`anim-btn${anim.key === (locked ? themeLock!.anim : themeAnim) ? " sel" : ""}`} disabled={locked} onClick={() => setThemeAnim(anim.key)}>
              <i className={`fa-solid ${anim.icon}`}></i><span>{anim.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="glass card" data-reveal style={{ padding: "18px 20px", marginBottom: 12 }}>
        <div className="setting-info" style={{ marginBottom: 14 }}>
          <span className="setting-name">Theme</span>
          <span className="setting-desc">Animated background image.</span>
        </div>
        <ThemePicker />
      </div>

      <div className="glass card setting-row" data-reveal id="navAnimRow">
        <div className="setting-info">
          <span className="setting-name">Topbar &amp; Sidebar Effect</span>
          <span className="setting-desc">Extra animation on the top bar and side menu.</span>
        </div>
        <div className="anim-picker" style={{ justifyContent: "flex-end" }}>
          {NAV_ANIMS.map((anim) => (
            <button key={anim.key} className={`anim-btn nav-anim-btn${anim.key === navAnim ? " sel" : ""}`} onClick={() => setNavAnim(anim.key)}>
              <i className={`fa-solid ${anim.icon}`}></i><span>{anim.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="glass card setting-row" data-reveal>
        <div className="setting-info">
          <span className="setting-name">Start / Stop Hotkey</span>
          <span className="setting-desc">Keyboard shortcut to Start and Stop the macro.</span>
        </div>
        <CustomSelect className="cs-hotkey" options={startOptions} value={hotkey} onChange={onHotkeyChange} />
      </div>

      <div className="glass card setting-row" data-reveal>
        <div className="setting-info">
          <span className="setting-name">Idle / Auto Mode Hotkey</span>
          <span className="setting-desc">Toggles between Idle and Automation mode.</span>
        </div>
        <CustomSelect className="cs-hotkey" options={modeOptions} value={modeHotkey} onChange={onModeHotkeyChange} placeholder="- Off -" />
      </div>

      <div className="glass card setting-row monitor-dim-row" data-reveal>
        <div className="setting-info">
          <span className="setting-name">Dim monitors while running</span>
          <span className="setting-desc">
            Darkens all monitors while the macro runs. The macro itself still sees the screen normally.
          </span>
        </div>
        <div className="monitor-dim-controls">
          <input
            type="range"
            className="afk-range dim-range"
            aria-label="Monitor dim level"
            min={0}
            max={80}
            step={5}
            value={dimLevel}
            disabled={!dimEnabled}
            style={{ backgroundSize: `${(dimLevel / 80) * 100}% 100%`, opacity: dimEnabled ? 1 : 0.4 }}
            onChange={(e) => onDimLevel(Number(e.target.value))}
          />
          <output className="monitor-dim-value">{dimLevel}%</output>
          <label className="switch" aria-label="Dim monitors while running">
            <input type="checkbox" checked={dimEnabled} onChange={(e) => onDimToggle(e.target.checked)} />
            <span className="slider"></span>
          </label>
        </div>
      </div>

      <div className="settings-section-label" data-reveal>
        <i className="fa-solid fa-screwdriver-wrench"></i>
        <span>Troubleshooting</span>
      </div>

      <div className="glass card setting-row roblox-log-cleanup-row" data-reveal>
        <div className="setting-info">
          <span className="setting-name">Clear Roblox logs</span>
          <span className="setting-desc">
            Fixes biome detection problems caused by broken logs. This closes every Roblox instance first.
          </span>
        </div>
        <button
          className="roblox-log-clear-btn"
          disabled={running || clearingLogs}
          title={running ? "Stop the macro first" : "Close Roblox and clear its logs"}
          onClick={() => void clearRobloxLogs()}
        >
          <i className={`fa-solid ${clearingLogs ? "fa-spinner fa-spin" : "fa-trash-can"}`}></i>
          <span>{clearingLogs ? "Clearing…" : "Clear logs"}</span>
        </button>
      </div>

    </section>
  );
}



