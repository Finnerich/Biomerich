import { useStore } from "../store";

const MODULE_VISUALS: Record<string, { icon: string; sub: string }> = {
  offline: { icon: "fa-power-off", sub: "Press Start to run modules" },
  idle: { icon: "fa-moon", sub: "Engine on, nothing scheduled" },
  waiting: { icon: "fa-hourglass-half", sub: "Waiting for next action" },
  biomeLogging: { icon: "fa-satellite-dish", sub: "Watching Roblox logs" },
  antiAfk: { icon: "fa-person-running", sub: "Keeping the session awake" },
  strangeController: { icon: "fa-gamepad", sub: "Using Strange Controller" },
  biomeRandomizer: { icon: "fa-shuffle", sub: "Rolling a new biome" },
  fishing: { icon: "fa-fish", sub: "Auto-fishing active" },
  merchantTeleporter: { icon: "fa-store", sub: "Detecting merchants" },
  autopop: { icon: "fa-wand-magic-sparkles", sub: "Popping items" },
};
const FISHING_PHASE_SUB: Record<string, string> = {
  casting: "Casting the line", waiting: "Waiting for a bite",
  reeling: "Reeling it in", selling: "Selling the catch", idle: "Auto-fishing active",
};
const EVENT_KIND_ICON: Record<string, string> = {
  good: "fa-circle-check", bad: "fa-circle-xmark", warn: "fa-triangle-exclamation", info: "fa-magnifying-glass",
};

function fmtElapsed(secs: number): string {
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

export function EngineModule() {
  const running = useStore((s) => s.running);
  const signal = useStore((s) => s.engineSignal);

  const activeModule = running ? signal?.module ?? { key: "idle", label: "Idle" } : { key: "offline", label: "Engine offline" };
  const key = activeModule.key || "offline";
  const visual = MODULE_VISUALS[key] || MODULE_VISUALS.offline;
  const label = activeModule.label || "Idle";

  let baseSub = key === "fishing" && activeModule.phase ? FISHING_PHASE_SUB[activeModule.phase] || visual.sub : visual.sub;
  if (activeModule.account) baseSub += " · " + activeModule.account;

  const status = signal?.status;
  const event = status?.event;
  const detail = status?.detail;

  let subNode = <>{baseSub}</>;
  let eventKind: string | undefined;
  if (running && event?.text) {
    eventKind = event.kind || "info";
    subNode = (
      <>
        <i className={`fa-solid ${EVENT_KIND_ICON[eventKind] || EVENT_KIND_ICON.info} tm-event-icon`}></i> {event.text}
      </>
    );
  } else if (running && detail?.text) {
    subNode = <>{`${detail.text} · ${fmtElapsed(detail.elapsed || 0)}`}</>;
  }

  return (
    <div className={`topbar-module${key !== "offline" ? " is-live" : ""}`} data-key={key} data-event={eventKind}>
      <span className="tm-frame">
        <span className="tm-icon"><i className={`fa-solid ${visual.icon}`}></i></span>
        <span className="tm-text">
          <span className="tm-label">{label}</span>
          <span className="tm-sub tm-event-in">{subNode}</span>
        </span>
      </span>
      <span className="tm-pulse"></span>
    </div>
  );
}
