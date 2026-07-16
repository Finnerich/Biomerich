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
  const days = Math.floor(sec / 86400);
  const hours = Math.floor((sec % 86400) / 3600);
  const minutes = Math.floor((sec % 3600) / 60);
  const seconds = sec % 60;
  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}
function fmtSinceDate(iso?: string): string {
  if (!iso) return "-";
  const date = new Date(iso);
  if (isNaN(date.getTime())) return "-";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

const TT_COLLAPSE_KEY = "ttPanelCollapsed";

export function TimeTrackingPanel() {
  const running = useStore((s) => s.running);
  const tracking: TimeTracking = useStore((s) => s.timeTracking) || {};
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(TT_COLLAPSE_KEY) !== "0");

  function toggleCollapsed() {
    setCollapsed((wasCollapsed) => {
      localStorage.setItem(TT_COLLAPSE_KEY, wasCollapsed ? "0" : "1");
      return !wasCollapsed;
    });
  }

  const idleTime = Number(tracking.idle) || 0;
  const automationTime = Number(tracking.automation) || 0;
  const modeMax = Math.max(idleTime, automationTime, 1);
  const moduleTimes = tracking.modules || {};
  const activeModules = tracking.activeModules || [];
  const moduleMax = Math.max(1, ...TT_MODULES.map((m) => Number(moduleTimes[m.key]) || 0));
  const activeMode = tracking.activeMode || "";

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
          <span className="tt-hero-val">{fmtDuration(Number(tracking.totalEngine) || 0)}</span>
        </div>
        <div className="tt-hero-meta">
          <span className="tt-meta-item"><i className="fa-solid fa-play"></i> <b>{(Number(tracking.sessions) || 0).toLocaleString("en-US")}</b> sessions</span>
          <span className="tt-meta-item"><i className="fa-solid fa-trophy"></i> <b>{fmtDuration(Number(tracking.longestSession) || 0)}</b> longest</span>
          <span className="tt-meta-item"><i className="fa-solid fa-calendar-day"></i> since <b>{fmtSinceDate(tracking.firstStart)}</b></span>
        </div>
      </div>

      <Collapse open={!collapsed}>
      <div className="tt-split">
        <div className={`tt-mode idle${running && activeMode === "idle" ? " live" : ""}`}>
          <div className="tt-mode-top"><span className="tt-mode-dot"></span><i className="fa-solid fa-moon"></i> Idle mode</div>
          <span className="tt-mode-val">{fmtDuration(idleTime)}</span>
          <div className="tt-mode-bar"><i style={{ width: `${(idleTime / modeMax) * 100}%` }}></i></div>
        </div>
        <div className={`tt-mode auto${running && activeMode === "automation" ? " live" : ""}`}>
          <div className="tt-mode-top"><span className="tt-mode-dot"></span><i className="fa-solid fa-robot"></i> Automation mode</div>
          <span className="tt-mode-val">{fmtDuration(automationTime)}</span>
          <div className="tt-mode-bar"><i style={{ width: `${(automationTime / modeMax) * 100}%` }}></i></div>
        </div>
      </div>

      <div className="tt-mod-head"><i className="fa-solid fa-layer-group"></i> Time per module</div>
      <div className="tt-mods">
        {TT_MODULES.map((mod) => {
          const val = Number(moduleTimes[mod.key]) || 0;
          const pct = Math.max(val > 0 ? 3 : 0, (val / moduleMax) * 100);
          const live = running && activeModules.includes(mod.key);
          return (
            <div className={`tt-mod ${live ? "live" : ""} ${val > 0 ? "has" : "empty"}`} key={mod.key}>
              <span className="tt-mod-ico"><i className={`fa-solid ${mod.icon}`}></i></span>
              <span className="tt-mod-name">
                {mod.name}
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
