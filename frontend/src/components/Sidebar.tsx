import { useEffect, useState } from "react";
import { groupOfTab, navGroupsFor, isTabHidden } from "../navConfig";
import { getMacroMode } from "../data/macroMode";
import { NavGroup, spotlightMove } from "./NavGroup";
import { useStore } from "../store";
import { callPy } from "../bridge";
import { isUpdateAvailable } from "../update";
import { useTutorial } from "../tutorial";
import { TUTORIALS } from "../data/tutorials";

const STORAGE_KEY = "navGroupsCollapsed";

function loadCollapsed(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

export function Sidebar() {
  const version = useStore((s) => s.version);
  const running = useStore((s) => s.running);
  const currentTab = useStore((s) => s.currentTab);
  const setCurrentTab = useStore((s) => s.setCurrentTab);
  const updateAvailable = isUpdateAvailable(useStore((s) => s.releases));
  const macroMode = useStore((s) => getMacroMode(s.settings));
  const [collapsed, setCollapsed] = useState<Set<string>>(loadCollapsed);


  useEffect(() => {
    if (isTabHidden(currentTab, macroMode)) setCurrentTab("home");
  }, [currentTab, macroMode, setCurrentTab]);

  useEffect(() => {
    const activeGroup = groupOfTab(currentTab);
    if (!activeGroup) return;
    setCollapsed((previous) => {
      if (!previous.has(activeGroup)) return previous;
      const next = new Set(previous);
      next.delete(activeGroup);
      return next;
    });
  }, [currentTab]);

  const gatedItems: { tab: string; icon: string; label: string }[] = [
  ];

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...collapsed]));
    } catch {
    }
  }, [collapsed]);

  function toggleGroup(id: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <aside className={`sidebar glass sb2${running ? " live" : ""}`}>
      <div className="brand">
        <span
          className={`brand-mark-wrap${running ? " fx-beam" : ""}`}
          style={{ ["--fx-beam-r" as string]: "15px" }}
        >
          <div className="brand-mark">
            <i className="fa-solid fa-satellite-dish"></i>
          </div>
        </span>
        <div className="brand-text">
          <div className="brand-top">
            <span className="brand-name">SolRich</span>
            {running && <span className="brand-live-dot" title="Engine running"></span>}
          </div>
          <span className="brand-sub">Sol's RNG Macro</span>
        </div>
      </div>

      <div className="nav-scroll-wrap">
        <nav className="nav">
          {navGroupsFor(macroMode).map((group, i) => (
            <div key={group.id}>
              {i > 0 && group.id === "system" && <div className="nav-sep"></div>}
              <NavGroup
                group={group}
                collapsed={collapsed.has(group.id)}
                onToggleCollapse={() => toggleGroup(group.id)}
              />
            </div>
          ))}
          {gatedItems.length > 0 && (
            <NavGroup
              group={{ id: "plugins-injected", label: "Plugins", icon: "fa-puzzle-piece", items: gatedItems }}
              collapsed={collapsed.has("plugins-injected")}
              onToggleCollapse={() => toggleGroup("plugins-injected")}
            />
          )}
        </nav>
      </div>

      <div className="sidebar-footer">
        <button
          className="version-badge"
          title={updateAvailable ? "Update available: open Patchlog" : "Open Patchlog"}
          data-rail-tip={updateAvailable ? "Update available" : `Version v${version || "0.0.1"}`}
          onClick={() => setCurrentTab("patchlog")}
        >
          <span className="vb-glyph">
            <i className="fa-solid fa-satellite-dish"></i>
          </span>
          <span className="vb-text">
            <span className="vb-label">Version</span>
            <span className="vb-value">v{version || "0.0.1"}</span>
          </span>
          {updateAvailable && <span className="vb-update">Update</span>}
          <span className="vb-shine"></span>
        </button>
        <button
          className={`nav-item nav-item-creator${currentTab === "creator" ? " active" : ""}`}
          data-tab="creator"
          data-rail-tip="Credits"
          onMouseMove={spotlightMove}
          onClick={() => setCurrentTab("creator")}
        >
          <i className="fa-solid fa-heart"></i>
          <span>Credits</span>
        </button>
        <span
          className="support-link setup-guide-link"
          data-rail-tip="Setup Guide"
          onMouseMove={spotlightMove}
          onClick={() => useTutorial.getState().start(TUTORIALS.setupGuide)}
        >
          <i className="fa-solid fa-graduation-cap"></i>
          <span>Setup Guide</span>
        </span>
        <span
          className="support-link"
          data-rail-tip="Support Server"
          onMouseMove={spotlightMove}
          onClick={() => void callPy("open_url", "https://discord.gg/X7dbbQ5pXV")}
        >
          <i className="fa-brands fa-discord"></i>
          <span>Support Server</span>
        </span>
        <div className="made-by">Made by Finnerich</div>
      </div>
      <span className="sb2-edge" aria-hidden="true"></span>
    </aside>
  );
}
