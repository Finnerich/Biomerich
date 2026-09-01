

import { useStore } from "../store";
import { toggleMacro } from "../engine";
import { computeSetupSteps } from "../readiness";
import { isUpdateAvailable } from "../update";
import { TesseractInstallButton } from "../components/TesseractInstallButton";
import { useTutorial } from "../tutorial";
import { TUTORIALS } from "../data/tutorials";
import { callPy } from "../bridge";
import { getMacroAccounts, getMacroMode } from "../data/macroMode";


function formatTime(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(totalSeconds % 60)}`;
}



export function Home() {
  const running = useStore((s) => s.running);
  const uptime = useStore((s) => s.uptime);
  const settings = useStore((s) => s.settings);
  const accounts = useStore((s) => s.accounts);
  const webhooks = useStore((s) => s.webhooks);
  const automation = useStore((s) => s.automation);
  const timeTracking = useStore((s) => s.timeTracking);
  const ocrAvailable = useStore((s) => s.ocrAvailable);
  const engineSignal = useStore((s) => s.engineSignal);
  const setCurrentTab = useStore((s) => s.setCurrentTab);
  const updateAvailable = isUpdateAvailable(useStore((s) => s.releases));

  const steps = computeSetupSteps({ accounts, webhooks, settings, automation, running, timeTracking });
  const required = steps.filter((step) => !step.optional);
  const doneCount = steps.filter((step) => step.done).length;
  const setupComplete = required.every((step) => step.done);
  const hotkey = (settings.hotkey as string) || "F5";
  const moduleLabel = engineSignal?.module?.label;

  const macroMode = getMacroMode(settings);
  const enabledAccounts = getMacroAccounts(accounts, settings);
  const autopopAccounts = (automation.autopop as { accounts?: Record<string, { enabled?: boolean }> } | undefined)?.accounts || {};
  const modCount = (key: string) =>
    enabledAccounts.filter((account) => (account.modules as Record<string, boolean> | undefined)?.[key]).length;
  const autopopCount = enabledAccounts.filter((account) => autopopAccounts[String(account.id)]?.enabled).length;
  const runningKey = running ? engineSignal?.module?.key : undefined;
  const acctDetail = (count: number) => (count ? `${count} account${count === 1 ? "" : "s"}` : "Per account");

  const moduleStats = [
    { key: "biomeLogging", name: "Biome Logging", icon: "fa-satellite-dish", active: true, scope: "Global", detail: "Always on" },
    { key: "antiAfk", name: "Anti-AFK", icon: "fa-person-running", active: !!settings.antiAfkEnabled, scope: "Global", detail: "Runs while active" },
    { key: "ramTrim", name: "Auto-Trim RAM", icon: "fa-memory", active: !!settings.ramTrimEnabled, scope: "Global", detail: "Runs while active" },
    ...[
      { key: "strangeController", name: "Strange Controller", icon: "fa-gamepad" },
      { key: "biomeRandomizer", name: "Biome Randomizer", icon: "fa-shuffle" },
      { key: "merchantTeleporter", name: "Merchant Detection", icon: "fa-store" },
      { key: "auraDetection", name: "Aura Detection", icon: "fa-star" },
      { key: "fishing", name: "Fishing", icon: "fa-fish" },
    ].map((mod) => { const count = modCount(mod.key); return { ...mod, active: count > 0, scope: "Automation", detail: acctDetail(count) }; }),
    { key: "autopop", name: "Auto Pop", icon: "fa-wand-magic-sparkles", active: autopopCount > 0, scope: "Automation", detail: acctDetail(autopopCount) },
  ];
  const activeModCount = moduleStats.filter((mod) => mod.active).length;

  return (
    <section className="tab active-tab" id="home">
      <header className="page-head">
        <h1>Welcome to SolRich</h1>
        <p>Everything you need to get the macro running, in order.</p>
      </header>

      {}
      <div className={`glass card panel home-hero${running ? " live" : ""}`} data-reveal>
        <div className="home-hero-status">
          <span className={`home-hero-dot${running ? " on" : ""}`} aria-hidden="true"></span>
          <div className="home-hero-text">
            <span className="home-hero-title">{running ? "Engine running" : "Engine offline"}</span>
            <span className="home-hero-sub">
              {running
                ? (moduleLabel ? `Working: ${moduleLabel}` : "Watching your accounts.")
                : "Press Start when the checklist below is done."}
            </span>
          </div>
        </div>
        <div className="home-hero-right">
          {running && <span className="time-value">{formatTime(uptime)}</span>}
          <button className={`power-btn ${running ? "running" : "stopped"}`} onClick={() => void toggleMacro()}>
            <i className={`fa-solid ${running ? "fa-stop" : "fa-play"}`}></i>
            <span>{running ? "Stop" : "Start"}</span>
            <span className="pb-key">{hotkey}</span>
          </button>
        </div>
      </div>

      {}
      {ocrAvailable === false && (
        <div className="glass glass-warning card auto-note" data-reveal>
          <i className="fa-solid fa-triangle-exclamation"></i>
          <p><b>Tesseract is not installed.</b> Modules that read the screen (Merchant &amp; Aura Detection, OCR failsafes) stay locked until it is. One click installs it.</p>
          <TesseractInstallButton />
        </div>
      )}
      {updateAvailable && (
        <div className="glass card auto-note home-update" data-reveal>
          <i className="fa-solid fa-circle-up"></i>
          <p><b>A new version is available.</b> Update to get the latest fixes.</p>
          <button className="btn-add" onClick={() => setCurrentTab("patchlog")}>View update</button>
        </div>
      )}

      {}
      {setupComplete ? (
        <div className="glass card panel home-done" data-reveal>
          <i className="fa-solid fa-circle-check"></i>
          <div>
            <span className="setting-name">You're all set</span>
            <span className="setting-desc">Setup is complete. Tune what the macro does in the <b>Macro</b> tab, or check your stats while it runs.</span>
          </div>
        </div>
      ) : (
        <div className="glass card panel" data-reveal>
          <div className="panel-head">
            <div className="panel-title"><i className="fa-solid fa-list-check"></i> First-time setup</div>
            <span className="badge badge-soft">{doneCount} / {steps.length} done</span>
          </div>
          <div className="home-steps">
            {steps.map((step, i) => (
              <div className={`home-step${step.done ? " done" : ""}`} key={step.key}>
                <span className="hs-mark">
                  {step.done ? <i className="fa-solid fa-check"></i> : i + 1}
                </span>
                <div className="hs-body">
                  <span className="hs-title">
                    {step.title}
                    {step.optional && <span className="hs-optional">optional</span>}
                  </span>
                  <span className="hs-desc">{step.desc}</span>
                </div>
                {!step.done && step.key !== "start" && (
                  <button className="hs-go" onClick={() => setCurrentTab(step.tab)}>
                    {step.actionLabel} <i className="fa-solid fa-arrow-right"></i>
                  </button>
                )}
                {!step.done && step.key === "start" && (
                  <button className="hs-go hs-go-start" onClick={() => void toggleMacro()}>
                    <i className="fa-solid fa-play"></i> Start
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {}
      <div className="tab-section home-modules" data-reveal>
        <div className="tab-section-head">
          <i className="fa-solid fa-cubes"></i>
          <h2>Modules</h2>
          <div className="home-mod-badges">
            <span className="badge badge-soft">{activeModCount} / {moduleStats.length} active</span>
            <span className="badge badge-soft">{macroMode === "normal" ? "Normal mode" : "Multi-Macro mode"}</span>
          </div>
        </div>
        <div className="home-mod-grid">
          {moduleStats.map((mod) => {
            const isRunning = runningKey === mod.key;
            return (
              <button
                key={mod.key}
                className={`home-mod-card${mod.active ? " active" : ""}${isRunning ? " running" : ""}`}
                onClick={() => setCurrentTab("modules")}
                title="Open the Macro tab to configure"
              >
                <span className="hmc-icon"><i className={`fa-solid ${mod.icon}`}></i></span>
                <span className="hmc-body">
                  <span className="hmc-name">{mod.name}</span>
                  <span className="hmc-detail">{mod.scope} · {mod.detail}</span>
                </span>
                <span className={`hmc-status${isRunning ? " running" : mod.active ? " on" : ""}`}>
                  {isRunning ? "Running" : mod.active ? "Active" : "Off"}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {}
      <div className="home-help" data-reveal>
        <button className="glass card home-help-card" onClick={() => useTutorial.getState().start(TUTORIALS.setupGuide)}>
          <i className="fa-solid fa-graduation-cap"></i>
          <span className="hh-title">Setup Guide</span>
          <span className="hh-sub">A guided tour through every step.</span>
        </button>
        <button className="glass card home-help-card" onClick={() => setCurrentTab("safety")}>
          <i className="fa-solid fa-shield-halved"></i>
          <span className="hh-title">Safety</span>
          <span className="hh-sub">Configure protections for your macro session.</span>
        </button>
        <button className="glass card home-help-card" onClick={() => void callPy("open_url", "https://discord.gg/X7dbbQ5pXV")}>
          <i className="fa-brands fa-discord"></i>
          <span className="hh-title">Support Server</span>
          <span className="hh-sub">Stuck? Ask us on Discord.</span>
        </button>
      </div>
    </section>
  );
}
