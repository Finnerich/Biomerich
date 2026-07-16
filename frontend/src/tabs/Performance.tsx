






import { useEffect, useRef, useState, type ReactNode } from "react";
import { callPy } from "../bridge";
import { CountUp } from "../components/CountUp";
import { RangeSetting } from "../components/RangeSetting";
import { useStore } from "../store";
import { BindButton, useWindowBindPoll } from "../windowBind";
import { DEFAULT_AVATAR } from "../data/biomes";
import type { Account } from "../types";



interface PerfInstance {
  pid: number;
  name: string;
  ramBytes: number;
  cpuPercent: number;
}

interface TrimResult {
  ok?: boolean;
  count?: number;
  freedBytes?: number;
  availBefore?: number;
  availAfter?: number;
  standbyPurged?: boolean;
}

interface TrimParticle { id: number; dx: number; dy: number; c: string; s: number }

interface ThrottleState {
  supported?: boolean;
  enabled?: boolean;
  running?: boolean;
  method?: string;
  scope?: string;
  cycleMs?: number;
  quota?: number;
  focusAware?: boolean;
  onlyWhenRunning?: boolean;
  breathe?: boolean;
  ramCap?: boolean;
  ramCapMb?: number;
  breathing?: boolean;
  paused?: boolean;
  tracked?: number;
  live?: number;
  throttled?: number;
  holds?: number;
  capped?: number;
  targetPids?: number[];
  throttledPids?: number[];
  heldPids?: number[];
}

interface PerfData {
  supported?: boolean;
  ncores?: number;
  totalRamBytes?: number;
  instances?: PerfInstance[];
  robloxTotal?: { count: number; ramBytes: number; cpuPercent: number };
  macro?: { ramBytes: number; cpuPercent: number };
  throttle?: ThrottleState;
}

const fmtCpu = (percent: number | undefined) => (Number(percent) || 0).toFixed(1);

function fmtBytes(bytes: number): string {
  bytes = Number(bytes) || 0;
  if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(2) + " GB";
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(0) + " MB";
  if (bytes >= 1024) return (bytes / 1024).toFixed(0) + " KB";
  return bytes + " B";
}


let cachedPerf: PerfData | null = null;



export function Performance() {
  const [data, setData] = useState<PerfData | null>(cachedPerf);
  const inFlight = useRef(false);
  const [trimming, setTrimming] = useState(false);
  const [trimResult, setTrimResult] = useState<TrimResult | null>(null);
  const [particles, setParticles] = useState<TrimParticle[]>([]);
  const particleId = useRef(0);

  useWindowBindPoll();

  async function trimRam() {
    if (trimming) return;
    setTrimming(true);
    try {
      const result = await callPy<TrimResult>("trim_system_ram");
      if (result?.ok) {
        setTrimResult(result);
        const colors = ["var(--accent)", "var(--accent-2)", "#22d3ee", "#34d399", "#a855f7"];
        const fresh: TrimParticle[] = Array.from({ length: 22 }, (_, i) => {
          const angle = (Math.PI * 2 * i) / 22 + Math.random() * 0.5;
          const distance = 40 + Math.random() * 70;
          return {
            id: ++particleId.current,
            dx: Math.cos(angle) * distance,
            dy: Math.sin(angle) * distance,
            c: colors[i % colors.length],
            s: 3 + Math.random() * 4,
          };
        });
        const freshIds = new Set(fresh.map((particle) => particle.id));
        setParticles((prev) => [...prev, ...fresh]);
        window.setTimeout(() => setParticles((prev) => prev.filter((particle) => !freshIds.has(particle.id))), 900);
      }
    } finally {
      setTrimming(false);
    }
  }

  useEffect(() => {
    let alive = true;

    async function poll() {
      if (inFlight.current) return;
      inFlight.current = true;
      try {
        const perf = await callPy<PerfData>("get_performance");
        if (alive && perf) {
          cachedPerf = perf;
          setData(perf);
        }
      } catch {
      } finally {
        inFlight.current = false;
      }
    }

    poll();
    const intervalId = setInterval(poll, 1000);
    return () => {
      alive = false;
      clearInterval(intervalId);
    };
  }, []);

  const totalRam = data?.totalRamBytes || 0;
  const instances = data?.instances || [];
  const robloxTotal = data?.robloxTotal || { count: 0, ramBytes: 0, cpuPercent: 0 };
  const macro = data?.macro || { ramBytes: 0, cpuPercent: 0 };
  const supported = data?.supported;
  const throttle = data?.throttle;

  const ramShare = totalRam > 0 ? ((robloxTotal.ramBytes / totalRam) * 100).toFixed(1) : "0";

  const heldSet = new Set(throttle?.heldPids || []);
  const throttledSet = new Set(throttle?.throttledPids || []);
  const targetSet = new Set(throttle?.targetPids || []);

  function refreshThrottle() {
    void callPy<ThrottleState>("get_throttle_state").then((state) => {
      if (state) setData((prev) => (prev ? { ...prev, throttle: state } : prev));
    });
  }

  return (
    <section className="tab active-tab" id="performance">
      <header className="page-head">
        <h1>Performance</h1>
        <p>Live CPU and memory usage for every Roblox instance, plus throttling to slash
          background usage.</p>
      </header>

      <div className="perf-summary" data-reveal>
        <div className="glass card perf-stat">
          <div className="perf-stat-top">
            <i className="fa-solid fa-cubes"></i> Roblox instances
          </div>
          <div className="perf-stat-val">{robloxTotal.count}</div>
          <div className="perf-stat-sub">
            {robloxTotal.count === 0
              ? "none running"
              : `${robloxTotal.count} process${robloxTotal.count === 1 ? "" : "es"}`}
          </div>
        </div>
        <div className="glass card perf-stat">
          <div className="perf-stat-top">
            <i className="fa-solid fa-memory"></i> Roblox total RAM
          </div>
          <div className="perf-stat-val">{fmtBytes(robloxTotal.ramBytes)}</div>
          <div className="perf-stat-sub">{`${ramShare}% of ${fmtBytes(totalRam)} system RAM`}</div>
        </div>
        <div className="glass card perf-stat">
          <div className="perf-stat-top">
            <i className="fa-solid fa-microchip"></i> Roblox total CPU
          </div>
          <div className="perf-stat-val">{fmtCpu(robloxTotal.cpuPercent)}%</div>
          <div className="perf-stat-sub">{`across ${data?.ncores || "?"} cores`}</div>
        </div>
        <div className="glass card perf-stat macro">
          <div className="perf-stat-top">
            <i className="fa-solid fa-satellite-dish"></i> SolRich (macro)
          </div>
          <div className="perf-stat-val">{fmtBytes(macro.ramBytes)}</div>
          <div className="perf-stat-sub">{fmtCpu(macro.cpuPercent)}% CPU</div>
        </div>
      </div>

      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title">
            <i className="fa-solid fa-list"></i> Per instance
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              className="perf-trim-btn"
              disabled={trimming || !supported}
              onClick={() => void trimRam()}
              title="Empty every process's working set + purge the standby cache, like Mem Reduct"
            >
              <i className={`fa-solid ${trimming ? "fa-rotate fa-spin-pulse" : "fa-broom"}`}></i>
              {trimming ? "Trimming…" : "Trim RAM"}
            </button>
            <span className="badge badge-soft">
              {data ? (supported ? "live" : "n/a") : "idle"}
            </span>
          </div>
        </div>

        {trimResult && (
          <div className="perf-trim-result fx-beam" style={{ ["--fx-beam-r" as string]: "14px" }}>
            <div className="perf-trim-ico">
              <i className="fa-solid fa-broom"></i>
              {particles.map((particle) => (
                <span
                  key={particle.id}
                  className="perf-trim-p"
                  style={{
                    left: "50%", top: "50%",
                    width: particle.s, height: particle.s, background: particle.c,
                    ["--dx" as string]: `${particle.dx}px`, ["--dy" as string]: `${particle.dy}px`,
                  }}
                ></span>
              ))}
            </div>
            <div className="perf-trim-meta">
              <span className="perf-trim-freed">
                <CountUp from={0} value={Math.round((trimResult.freedBytes || 0) / 1048576)} /> MB freed
              </span>
              <span className="perf-trim-sub">
                {trimResult.count} process{trimResult.count === 1 ? "" : "es"} trimmed system-wide
                {trimResult.standbyPurged
                  ? " · standby cache purged"
                  : " · run as admin to also purge the standby cache"}
                {" · "}{fmtBytes(trimResult.availBefore || 0)} → {fmtBytes(trimResult.availAfter || 0)} free
              </span>
            </div>
            <button className="perf-trim-close" title="Dismiss" onClick={() => setTrimResult(null)}>
              <i className="fa-solid fa-xmark"></i>
            </button>
          </div>
        )}

        <div className="perf-list">
          {instances.map((instance) => {
            const ramPct = totalRam > 0 ? Math.min(100, (instance.ramBytes / totalRam) * 100) : 0;
            const cpuPct = Math.min(100, Number(instance.cpuPercent) || 0);
            const throttleTag = heldSet.has(instance.pid)
              ? "held"
              : throttledSet.has(instance.pid)
                ? "throttled"
                : targetSet.has(instance.pid)
                  ? "target"
                  : null;
            return (
              <div className={`perf-row${instance.cpuPercent >= 35 ? " hot" : ""}`} key={instance.pid}>
                <div className="perf-row-id">
                  <span className="perf-dot"></span>
                  <span className="perf-name">{instance.name}</span>
                  <span className="perf-pid">PID {instance.pid}</span>
                  {throttleTag === "held" && (
                    <span className="perf-thr-tag held"><i className="fa-solid fa-bolt" /> full speed</span>
                  )}
                  {throttleTag === "throttled" && (
                    <span className="perf-thr-tag throttled"><i className="fa-solid fa-gauge-low" /> throttled</span>
                  )}
                  {throttleTag === "target" && (
                    <span className="perf-thr-tag target"><i className="fa-solid fa-snowflake" /> throttling</span>
                  )}
                </div>
                <div className="perf-metric">
                  <div className="perf-metric-head">
                    <span>RAM</span>
                    <span className="perf-ram-val">{fmtBytes(instance.ramBytes)}</span>
                  </div>
                  <div className="perf-bar">
                    <i className="perf-ram-bar" style={{ width: `${ramPct}%` }}></i>
                  </div>
                </div>
                <div className="perf-metric">
                  <div className="perf-metric-head">
                    <span>CPU</span>
                    <span className="perf-cpu-val">{fmtCpu(instance.cpuPercent)}%</span>
                  </div>
                  <div className="perf-bar">
                    <i className="perf-cpu-bar" style={{ width: `${cpuPct}%` }}></i>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div className={`empty-state${instances.length === 0 ? " show" : ""}`}>
          <i className="fa-solid fa-ghost"></i>
          <p>No Roblox instances detected. Launch some from the Account Manager.</p>
        </div>
      </div>

      <ThrottlePanel throttle={throttle} supported={supported} onChanged={refreshThrottle} />

      {data && !supported && (
        <div className="glass glass-warning card auto-note" data-reveal>
          <i className="fa-solid fa-circle-info"></i>
          <p>Live performance monitoring is only available on Windows.</p>
        </div>
      )}
    </section>
  );
}



type Scope = "all" | "allExcept" | "onlyThese";

const SCOPES: { id: Scope; label: string; icon: string }[] = [
  { id: "all", label: "All windows", icon: "fa-asterisk" },
  { id: "allExcept", label: "All except", icon: "fa-circle-minus" },
  { id: "onlyThese", label: "Only picked", icon: "fa-circle-check" },
];

const SCOPE_HINT: Record<Scope, string> = {
  all: "Every open Roblox window is throttled. The focused window still runs full speed.",
  allExcept: "Every Roblox window is throttled except the ones you mark below.",
  onlyThese: "Only the windows you pick below are throttled. Everything else runs normally.",
};

function ThrToggle(props: {
  on: boolean;
  icon: string;
  title: string;
  desc: string;
  onToggle: () => void;
  children?: ReactNode;
}) {
  return (
    <>
      <div className={`mb-global${props.on ? " on" : ""}`}>
        <div className="mb-global-ico"><i className={`fa-solid ${props.icon}`} /></div>
        <div className="mb-global-meta">
          <span className="mb-global-name">{props.title}</span>
          <span className="mb-global-desc">{props.desc}</span>
        </div>
        <div className="mb-global-actions">
          <label className="switch">
            <input type="checkbox" checked={props.on} onChange={props.onToggle} />
            <span className="slider"></span>
          </label>
        </div>
      </div>
      {props.children}
    </>
  );
}


function ThrottlePanel(props: {
  throttle?: ThrottleState;
  supported?: boolean;
  onChanged: () => void;
}) {
  const { throttle, supported, onChanged } = props;
  const settings = useStore((s) => s.settings);
  const patchSettings = useStore((s) => s.patchSettings);
  const accounts = useStore((s) => s.accounts) as Account[];

  const enabled = !!settings.throttleEnabled;
  const method: "suspend" | "efficiency" = settings.throttleMethod === "suspend" ? "suspend" : "efficiency";
  const cycleMs = Number(settings.throttleCycleMs ?? 50);
  const quota = Number(settings.throttleQuota ?? 12);
  const focusAware = settings.throttleFocusAware !== false;
  const onlyWhenRunning = settings.throttleOnlyWhenRunning === true;
  const breathe = settings.throttleBreathe !== false;
  const ramCap = settings.throttleRamCap === true;
  const ramCapMb = Number(settings.throttleRamCapMb ?? 400);
  const scope: Scope = (["all", "allExcept", "onlyThese"] as Scope[]).includes(
    settings.throttleScope as Scope,
  )
    ? (settings.throttleScope as Scope)
    : "onlyThese";
  const selected: number[] = Array.isArray(settings.throttleAccounts)
    ? (settings.throttleAccounts as number[])
    : [];

  function setSetting(key: string, value: unknown) {
    patchSettings({ [key]: value });
    void callPy("set_setting", key, value).then(onChanged);
  }

  function toggleAccount(id: number) {
    const next = selected.includes(id)
      ? selected.filter((accId) => accId !== id)
      : [...selected, id];
    setSetting("throttleAccounts", next);
  }

  const running = !!throttle?.running;
  const enabledAccounts = (accounts || []).filter((account) => account.enabled !== false);
  const collapsed = settings.throttleCollapsed === true;


  return (
    <div className={`glass card panel thr-panel calib-panel${enabled ? " on" : ""}${collapsed ? " collapsed" : ""}`} data-reveal>
      <div className="panel-head calib-toggle" onClick={() => setSetting("throttleCollapsed", !collapsed)}>
        <div className="panel-title">
          <i className="fa-solid fa-gauge-high"></i> Process Throttling
        </div>
        <div className="calib-head-right">
          <div className="mb-acc-enable" onClick={(e) => e.stopPropagation()}>
            <span className="mb-enable-label">{enabled ? "Enabled" : "Disabled"}</span>
            <label className="switch" title={enabled ? "Disable throttling" : "Enable throttling"}>
              <input type="checkbox" checked={enabled} onChange={(e) => setSetting("throttleEnabled", e.target.checked)} />
              <span className="slider"></span>
            </label>
          </div>
          <i className="fa-solid fa-chevron-down calib-chevron"></i>
        </div>
      </div>

      {}
      <div className="thr-status">
        <span className={`thr-stat${running && !throttle?.paused ? " live" : ""}`}>
          <span className="thr-stat-dot" />{" "}
          {throttle?.paused ? "Waiting for macro" : running ? "Running" : enabled ? "Idle" : "Off"}
        </span>
        <span className="thr-stat"><b>{throttle?.tracked ?? 0}</b> Tracked</span>
        <span className="thr-stat throttled"><b>{throttle?.throttled ?? 0}</b> Throttled</span>
        <span className="thr-stat held"><b>{throttle?.holds ?? 0}</b> Holds</span>
        {ramCap && (throttle?.capped ?? 0) > 0 && (
          <span className="thr-stat capped"><b>{throttle?.capped}</b> Capped</span>
        )}
      </div>

      {supported === false && (
        <div className="thr-note"><i className="fa-solid fa-circle-info" /> Throttling is only available on Windows.</div>
      )}

      {}
      <div className="thr-section">
        <div className="thr-subhead"><i className="fa-solid fa-window-restore" /> Target windows</div>
        <div className="thr-scope" role="tablist">
          {SCOPES.map((scopeOption) => (
            <button
              key={scopeOption.id}
              role="tab"
              aria-selected={scope === scopeOption.id}
              className={`thr-scope-opt${scope === scopeOption.id ? " on" : ""}`}
              onClick={() => setSetting("throttleScope", scopeOption.id)}
            >
              <i className={`fa-solid ${scopeOption.icon}`} /> {scopeOption.label}
            </button>
          ))}
        </div>
        <p className="thr-scope-hint">{SCOPE_HINT[scope]}</p>

        {scope === "all" ? (
          <div className="thr-all-note">
            <i className="fa-solid fa-circle-check" />
            All Roblox windows are throttled. Switch to <b>All except</b> or <b>Only picked</b>
            {" "}to choose specific windows.
          </div>
        ) : enabledAccounts.length === 0 ? (
          <p className="thr-list-empty">No enabled accounts. Add and enable accounts in the Accounts tab first.</p>
        ) : (
          <div className="thr-acc-list">
            {enabledAccounts.map((account) => {
              const bound = !!account.window;
              const inList = selected.includes(account.id);
              const isThrottled = scope === "allExcept" ? !inList : inList;
              const label = scope === "allExcept"
                ? (isThrottled ? "Throttled" : "Excepted")
                : (isThrottled ? "Throttling" : "Throttle");
              const icon = scope === "allExcept"
                ? (isThrottled ? "fa-gauge-low" : "fa-shield-halved")
                : (isThrottled ? "fa-check" : "fa-plus");
              return (
                <div className={`thr-acc${isThrottled ? " on" : ""}${bound ? "" : " unbound"}`} key={account.id}>
                  <img
                    className="thr-acc-avatar"
                    src={account.avatar || DEFAULT_AVATAR}
                    alt=""
                    onError={(ev) => { (ev.target as HTMLImageElement).src = DEFAULT_AVATAR; }}
                  />
                  <div className="thr-acc-meta">
                    <span className="thr-acc-name">{account.name}</span>
                    <span className={`thr-acc-state ${bound ? "ok" : "warn"}`}>
                      <i className={`fa-solid ${bound ? "fa-link" : "fa-link-slash"}`} />
                      {bound ? account.window : "no window"}
                    </span>
                  </div>
                  {bound ? (
                    <button
                      className={`thr-acc-toggle${isThrottled ? " on" : ""}`}
                      onClick={() => toggleAccount(account.id)}
                    >
                      <i className={`fa-solid ${icon}`} /> {label}
                    </button>
                  ) : (
                    <BindButton
                      acc={account}
                      baseClass="thr-acc-bind"
                      activeClass="on"
                      labels={{ bind: "Bind Window", bound: "Bound", waiting: "Cancel" }}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {}
      <div className="calib-body">
        <p className="section-hint">
          Throttles background Roblox windows to cut their CPU, GPU and memory load.
          The window you <b>focus runs at full speed</b>, and re-throttles when you click away.
        </p>

        {}
        <div className="thr-section">
          <div className="thr-subhead"><i className="fa-solid fa-microchip" /> Method</div>
          <div className="thr-scope" role="tablist">
            <button
              role="tab" aria-selected={method === "efficiency"}
              className={`thr-scope-opt${method === "efficiency" ? " on" : ""}`}
              onClick={() => setSetting("throttleMethod", "efficiency")}
            ><i className="fa-solid fa-leaf" /> Efficiency</button>
            <button
              role="tab" aria-selected={method === "suspend"}
              className={`thr-scope-opt${method === "suspend" ? " on" : ""}`}
              onClick={() => setSetting("throttleMethod", "suspend")}
            ><i className="fa-solid fa-pause" /> Suspend</button>
          </div>
          <p className="thr-scope-hint">
            {method === "efficiency"
              ? "Background windows run at idle priority + Windows Efficiency mode (E-cores, lower clock). Stays smooth (no GPU stutter) with solid CPU/power savings. Best for active multi-boxing."
              : "Background windows get rapidly paused and resumed. Maximum CPU/GPU/RAM savings, but the window you're playing in can stutter. Best for parked alts."}
          </p>
        </div>

        {}
        {method === "suspend" && (
          <div className="thr-section">
            <div className="thr-subhead"><i className="fa-solid fa-sliders" /> Tuning</div>
            <div className="thr-tune">
              <RangeSetting
                name="Background CPU budget"
                desc="Lower = more aggressive. Throttled windows keep about this much CPU."
                min={2} max={95} step={1} value={quota}
                fmt={(x) => `${x}%`}
                onCommit={(value) => setSetting("throttleQuota", value)}
                recommended={12}
              />
              <div className="afk-setting afk-setting-col">
                <div className="afk-setting-info">
                  <span className="afk-setting-name">
                    Cycle length
                    <span className={`thr-rec-chip${cycleMs === 50 ? " on" : ""}`}>
                      <i className="fa-solid fa-wand-magic-sparkles" /> Recommended 50 ms
                    </span>
                  </span>
                  <span className="afk-setting-desc">Shorter cycles feel smoother; longer cycles cut a touch more CPU.</span>
                </div>
                <div className="thr-scope">
                  {[20, 30, 50, 100].map((ms) => (
                    <button
                      key={ms}
                      className={`thr-scope-opt${cycleMs === ms ? " on" : ""}${ms === 50 ? " thr-rec-opt" : ""}`}
                      onClick={() => setSetting("throttleCycleMs", ms)}
                    >
                      {ms} ms
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

          {}
          <div className="thr-section">
            <div className="thr-subhead"><i className="fa-solid fa-wand-magic-sparkles" /> Behaviour</div>
            <div className="mb-globals">
              <ThrToggle
                on={onlyWhenRunning} icon="fa-power-off"
                title="Only while the macro is running"
                desc="Throttling only kicks in once you start the macro (idle or auto mode). When the engine is stopped, every window runs full speed."
                onToggle={() => setSetting("throttleOnlyWhenRunning", !onlyWhenRunning)}
              />
              <ThrToggle
                on={focusAware} icon="fa-bullseye"
                title="Unthrottle the focused window"
                desc="The window you click into runs full speed; the rest stay throttled."
                onToggle={() => setSetting("throttleFocusAware", !focusAware)}
              />
              {method === "suspend" && (
                <ThrToggle
                  on={breathe} icon="fa-heart-pulse"
                  title="Disconnect protection (breathe)"
                  desc="Lets throttled windows run full speed for a moment every few seconds so Roblox's heartbeat survives. Prevents kicks at aggressive settings."
                  onToggle={() => setSetting("throttleBreathe", !breathe)}
                />
              )}
              <ThrToggle
                on={ramCap} icon="fa-compress"
                title="Hard RAM cap"
                desc="Forces each throttled window under a fixed RAM ceiling instead of growing back. Strongest memory saving, but causes more paging. The focused window is uncapped."
                onToggle={() => setSetting("throttleRamCap", !ramCap)}
              >
                {ramCap && (
                  <div className="thr-cap-sub">
                    <RangeSetting
                      name="Ceiling per window"
                      desc="Each throttled window is forced to stay under this much RAM."
                      min={150} max={2000} step={50} value={ramCapMb}
                      fmt={(x) => `${x} MB`}
                      onCommit={(value) => setSetting("throttleRamCapMb", value)}
                      recommended={400}
                    />
                  </div>
                )}
              </ThrToggle>
            </div>
          </div>
      </div>
    </div>
  );
}
