import { useState } from "react";
import { useStore } from "../store";
import { Collapse } from "./Collapse";
import type { TimeTracking } from "../types";

const TT_MODULES = [
  { key: "biomeLogging", name: "Biome Logging", icon: "fa-satellite-dish" },
  { key: "antiAfk", name: "Anti-AFK", icon: "fa-person-running" },
  { key: "strangeController", name: "Strange Controller", icon: "fa-gamepad" },
  { key: "biomeRandomizer", name: "Biome Randomizer", icon: "fa-shuffle" },
  { key: "merchantTeleporter", name: "Merchant Detection", icon: "fa-store" },
  { key: "fishing", name: "Fishing", icon: "fa-fish" },
];

function fmtDuration(sec: number): string {
  sec = Math.max(0, Math.floor(sec || 0));
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}
function fmtSinceDate(iso?: string): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "-";
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

const TT_COLLAPSE_KEY = "ttPanelCollapsed";

export function TimeTrackingPanel() {
  const running = useStore((s) => s.running);
  const tt: TimeTracking = useStore((s) => s.timeTracking) || {};
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(TT_COLLAPSE_KEY) !== "0");

  function toggleCollapsed() {
    setCollapsed((c) => {
      localStorage.setItem(TT_COLLAPSE_KEY, c ? "0" : "1");
      return !c;
    });
  }

  const idle = Number(tt.idle) || 0;
  const auto = Number(tt.automation) || 0;
  const modeMax = Math.max(idle, auto, 1);
  const mods = tt.modules || {};
  const activeMods = tt.activeModules || [];
  const modMax = Math.max(1, ...TT_MODULES.map((m) => Number(mods[m.key]) || 0));
  const activeMode = tt.activeMode || "";

  return (
    <div className="glass card panel tt-panel" data-reveal>
      <div className="panel-head fx-coll-head" onClick={toggleCollapsed}>
        <div className="panel-title"><i className="fa-solid fa-hourglass-half"></i> Time Tracking</div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <i className={`fa-solid fa-chevron-down fx-coll-chevron${collapsed ? " closed" : ""}`}></i>
        </div>
      </div>

      <div className="tt-hero">
        <div className="tt-hero-main">
          <span className="tt-hero-cap">Lifetime engine time</span>
          <span className="tt-hero-val">{fmtDuration(Number(tt.totalEngine) || 0)}</span>
        </div>
        <div className="tt-hero-meta">
          <span className="tt-meta-item"><i className="fa-solid fa-play"></i> <b>{(Number(tt.sessions) || 0).toLocaleString("en-US")}</b> sessions</span>
          <span className="tt-meta-item"><i className="fa-solid fa-trophy"></i> <b>{fmtDuration(Number(tt.longestSession) || 0)}</b> longest</span>
          <span className="tt-meta-item"><i className="fa-solid fa-calendar-day"></i> since <b>{fmtSinceDate(tt.firstStart)}</b></span>
        </div>
      </div>

      <Collapse open={!collapsed}>
      <div className="tt-split">
        <div className={`tt-mode idle${running && activeMode === "idle" ? " live" : ""}`}>
          <div className="tt-mode-top"><span className="tt-mode-dot"></span><i className="fa-solid fa-moon"></i> Idle mode</div>
          <span className="tt-mode-val">{fmtDuration(idle)}</span>
          <div className="tt-mode-bar"><i style={{ width: `${(idle / modeMax) * 100}%` }}></i></div>
        </div>
        <div className={`tt-mode auto${running && activeMode === "automation" ? " live" : ""}`}>
          <div className="tt-mode-top"><span className="tt-mode-dot"></span><i className="fa-solid fa-robot"></i> Automation mode</div>
          <span className="tt-mode-val">{fmtDuration(auto)}</span>
          <div className="tt-mode-bar"><i style={{ width: `${(auto / modeMax) * 100}%` }}></i></div>
        </div>
      </div>

      <div className="tt-mod-head"><i className="fa-solid fa-layer-group"></i> Time per module</div>
      <div className="tt-mods">
        {TT_MODULES.map((m) => {
          const val = Number(mods[m.key]) || 0;
          const pct = Math.max(val > 0 ? 3 : 0, (val / modMax) * 100);
          const live = running && activeMods.includes(m.key);
          return (
            <div className={`tt-mod ${live ? "live" : ""} ${val > 0 ? "has" : "empty"}`} key={m.key}>
              <span className="tt-mod-ico"><i className={`fa-solid ${m.icon}`}></i></span>
              <span className="tt-mod-name">
                {m.name}
                {live && <span className="tt-mod-live"><span className="dot running"></span>live</span>}
              </span>
              <span className="tt-mod-bar"><i style={{ width: `${pct}%` }}></i></span>
              <span className="tt-mod-val">{fmtDuration(val)}</span>
            </div>
          );
        })}
      </div>
      </Collapse>
    </div>
  );
}
