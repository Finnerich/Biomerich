import { useStore } from "../store";
import { setMode, toggleMacro } from "../engine";
import { EngineModule } from "./EngineModule";
import { StreakPill } from "./StreakPill";

function formatTime(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(h)}:${p(m)}:${p(s)}`;
}

export function Topbar() {
  const running = useStore((s) => s.running);
  const uptime = useStore((s) => s.uptime);
  const settings = useStore((s) => s.settings);
  const automation = useStore((s) => s.automation);

  const hotkey = (settings.hotkey as string) || "F5";
  const modeHotkey = (settings.modeHotkey as string) || "none";
  const mode = (automation.mode as string) || "idle";

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

        <div id="modeSeg" className={`mode-seg mode-seg-3 ${mode === "automation" ? "auto" : mode}`} role="group" title="Switch run mode">
          <span className="mode-seg-glider"></span>
          <button
            className={`mode-seg-opt${mode === "idle" ? " active" : ""}`}
            data-mode="idle"
            onClick={() => void setMode("idle")}
          >
            <i className="fa-solid fa-moon"></i>
            <span>Idle</span>
          </button>
          <button
            className={`mode-seg-opt${mode === "automation" ? " active" : ""}`}
            data-mode="automation"
            onClick={() => void setMode("automation")}
          >
            <i className="fa-solid fa-robot"></i>
            <span>Auto</span>
          </button>
          <button
            className={`mode-seg-opt${mode === "eden" ? " active" : ""}`}
            data-mode="eden"
            onClick={() => void setMode("eden")}
          >
            <i className="fa-solid fa-circle-dot"></i>
            <span>Eden</span>
          </button>
        </div>
        {modeHotkey !== "none" && <span className="mode-hotkey-badge visible">{modeHotkey}</span>}
      </div>

      <EngineModule />

      <div className="topbar-right">
        <StreakPill />
        <div className={`topbar-time${running ? " live" : ""}`} title="Current session uptime">
          {running ? (
            <span className="time-live-dot" aria-hidden="true"></span>
          ) : (
            <i className="fa-solid fa-stopwatch topbar-time-icon"></i>
          )}
          <span className="time-value">{formatTime(uptime)}</span>
        </div>
      </div>
    </div>
  );
}
