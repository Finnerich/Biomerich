import { useStore } from "../store";
import { setMode, toggleMacro } from "../engine";
import { getMacroMode, setMacroMode } from "../data/macroMode";
import { CustomSelect } from "./CustomSelect";
import { EngineModule } from "./EngineModule";
import { StreakPill } from "./StreakPill";

const RUN_MODE_OPTIONS = [
  { value: "idle", label: "Idle", icon: "fa-moon", iconClassName: "mode-icon-idle" },
  { value: "automation", label: "Auto", icon: "fa-robot", iconClassName: "mode-icon-auto" },
  { value: "eden", label: "Eden", icon: "fa-circle-dot", iconClassName: "mode-icon-eden" },
];

const MACRO_MODE_OPTIONS = [
  { value: "normal", label: "Normal", icon: "fa-user", iconClassName: "mode-icon-normal" },
  { value: "multi", label: "Multi-Macro", icon: "fa-users", iconClassName: "mode-icon-multi" },
];

function formatTime(sec: number): string {
  const hours = Math.floor(sec / 3600);
  const minutes = Math.floor((sec % 3600) / 60);
  const seconds = sec % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}



function SessionClock() {
  const running = useStore((s) => s.running);
  const uptime = useStore((s) => s.uptime);
  return (
    <div className={`topbar-time${running ? " live" : ""}`} title="Current session uptime">
      {running ? (
        <span className="time-live-dot" aria-hidden="true"></span>
      ) : (
        <i className="fa-solid fa-stopwatch topbar-time-icon"></i>
      )}
      <span className="time-value">{formatTime(uptime)}</span>
    </div>
  );
}

export function Topbar() {
  const running = useStore((s) => s.running);
  const settings = useStore((s) => s.settings);
  const automation = useStore((s) => s.automation);

  const hotkey = (settings.hotkey as string) || "F5";
  const modeHotkey = (settings.modeHotkey as string) || "none";
  const mode = (automation.mode as string) || "idle";
  const macroMode = getMacroMode(settings);

  return (
    <div className={`topbar glass tb4${running ? " live" : ""}`}>
      <div className="topbar-engine">
        <button
          id="toggleBtn"
          className={`power-btn ${running ? "running" : "stopped"}`}
          onClick={() => void toggleMacro()}
          title={running ? "Stop the engine" : "Start the engine"}
        >
          <i className={`pb-ico fa-solid ${running ? "fa-stop" : "fa-play"}`}></i>
          <span className="pb-label">{running ? "Stop" : "Start"}</span>
          <span className="pb-key">{hotkey}</span>
        </button>

        <div id="modeSeg" className="topbar-mode-dropdown-wrap">
          <CustomSelect
            className="topbar-mode-select topbar-run-mode-select"
            options={RUN_MODE_OPTIONS}
            value={mode}
            onChange={(value) => void setMode(value)}
            aria-label="Run mode"
          />
        </div>
        <div
          id="macroModeToggle"
          className="topbar-mode-dropdown-wrap"
        >
          <CustomSelect
            className="topbar-mode-select topbar-macro-select"
            options={MACRO_MODE_OPTIONS}
            value={macroMode}
            disabled={running}
            onChange={(value) => void setMacroMode(value === "normal" ? "normal" : "multi")}
            aria-label="Macro mode"
          />
        </div>
        {modeHotkey !== "none" && <span className="mode-hotkey-badge visible">{modeHotkey}</span>}
      </div>

      <EngineModule />

      <div className="topbar-right">
        <StreakPill />
        <SessionClock />
      </div>
    </div>
  );
}
