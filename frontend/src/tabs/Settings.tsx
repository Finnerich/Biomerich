import { useStore } from "../store";
import { callPy } from "../bridge";
import { alertDialog } from "../dialog";
import { ACCENTS, applyAccent, getAccentIndex } from "../data/accents";
import { CustomSelect } from "../components/CustomSelect";
import { THEME_ANIMS, NAV_ANIMS, applyNavAnim } from "../components/ThemeCanvas";
import { ThemePicker } from "../components/ThemePicker";
import { withColorTransition } from "../themeFlash";

const F_KEYS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"];

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
  const themeLock = useStore((s) => s.themeLock);
  const locked = !!themeLock;

  const accentIndex = getAccentIndex(settings.accentIndex);
  const hotkey = (settings.hotkey as string) || "F5";
  const modeHotkey = (settings.modeHotkey as string) || "none";
  const themeAnim = (settings.themeAnim as string) || localStorage.getItem("themeAnim") || "none";
  const navAnim = (settings.navAnim as string) || localStorage.getItem("navAnim") || "none";

  function setAccent(i: number) {
    withColorTransition(() => applyAccent(i));
    patchSettings({ accentIndex: i });
    localStorage.setItem("accentIndex", String(i));
    void callPy("set_setting", "accentIndex", i);
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


  function onHotkeyChange(v: string) {
    if (v === modeHotkey) {
      void alertDialog(`${v} is already used for Mode Toggle. Pick a different key.`, { title: "F-key conflict" });
      return;
    }
    patchSettings({ hotkey: v });
    void callPy("set_setting", "hotkey", v);
  }
  function onModeHotkeyChange(v: string) {
    if (v !== "none" && v === hotkey) {
      void alertDialog(`${v} is already used for Start/Stop. Pick a different key.`, { title: "F-key conflict" });
      return;
    }
    patchSettings({ modeHotkey: v });
    void callPy("set_setting", "modeHotkey", v);
  }

  const startOptions = F_KEYS.filter((k) => k === hotkey || k !== modeHotkey).map((k) => ({ value: k, label: k }));
  const modeOptions = [{ value: "none", label: "- Off -" }, ...F_KEYS.filter((k) => k === modeHotkey || k !== hotkey).map((k) => ({ value: k, label: k }))];

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
          {ACCENTS.map((a, i) => (
            <button
              key={i}
              className={`swatch-btn${i === accentIndex ? " sel" : ""}`}
              style={{ background: a.c }}
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
          {THEME_ANIMS.map((a) => (
            <button key={a.key} className={`anim-btn${a.key === (locked ? themeLock!.anim : themeAnim) ? " sel" : ""}`} disabled={locked} onClick={() => setThemeAnim(a.key)}>
              <i className={`fa-solid ${a.icon}`}></i><span>{a.label}</span>
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
          {NAV_ANIMS.map((a) => (
            <button key={a.key} className={`anim-btn nav-anim-btn${a.key === navAnim ? " sel" : ""}`} onClick={() => setNavAnim(a.key)}>
              <i className={`fa-solid ${a.icon}`}></i><span>{a.label}</span>
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

    </section>
  );
}

