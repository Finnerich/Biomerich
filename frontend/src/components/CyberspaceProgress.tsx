import { useState } from "react";
import { useStore } from "../store";
import type { CyberspaceAccountProgress, CyberspaceProgress } from "../types";
import { Collapse } from "./Collapse";

const CYBERSPACE_COLLAPSE_KEY = "cyberspaceStatsCollapsed";

function formatNumber(value: number): string {
  return Math.max(0, Math.round(value)).toLocaleString("en-US");
}

function formatEta(totalSeconds: number | null): string {
  if (totalSeconds == null || !Number.isFinite(totalSeconds)) return "No active item rate";
  const seconds = Math.max(0, Math.round(totalSeconds));
  const days = Math.floor(seconds / 86_400);
  const hours = Math.floor((seconds % 86_400) / 3_600);
  const minutes = Math.floor((seconds % 3_600) / 60);
  if (days >= 365) {
    const years = Math.floor(days / 365);
    return `~${years}y ${days % 365}d`;
  }
  if (days > 0) return `~${days}d ${hours}h`;
  if (hours > 0) return `~${hours}h ${minutes}m`;
  return `~${Math.max(1, minutes)}m`;
}

function formatChance(value: number): string {
  if (value <= 0) return "0%";
  if (value < 0.1) return `${value.toFixed(3)}%`;
  if (value < 10) return `${value.toFixed(2)}%`;
  return `${value.toFixed(1)}%`;
}

function formatRate(value: number): string {
  if (value <= 0) return "Inactive";
  return `${value.toFixed(value < 10 ? 2 : 1)}/h`;
}

function UsageValue({ lifetime, session }: { lifetime: number; session: number }) {
  return (
    <span className="cyber-use-value">
      <b>{formatNumber(lifetime)}</b>
      <small>{formatNumber(session)} this session</small>
    </span>
  );
}

function AccountRow({ account }: { account: CyberspaceAccountProgress }) {
  const active = account.active || account.usesPerHour > 0;
  return (
    <div className={`cyber-account-row${active ? " active" : ""}`}>
      <div className="cyber-account-name">
        <span className={`cyber-account-dot${active ? " active" : ""}`}></span>
        <span>
          <b>{account.name}</b>
          <small>{formatRate(account.usesPerHour)} configured rate</small>
        </span>
      </div>
      <UsageValue
        lifetime={account.lifetime.strangeController}
        session={account.session.strangeController}
      />
      <UsageValue
        lifetime={account.lifetime.biomeRandomizer}
        session={account.session.biomeRandomizer}
      />
      <UsageValue lifetime={account.combinedLifetime} session={account.combinedSession} />
    </div>
  );
}

function RemainingLabel({ progress }: { progress: CyberspaceProgress }) {
  if (progress.estimatedRemaining > 0) {
    return <>{formatNumber(progress.estimatedRemaining)} to average mark</>;
  }
  if (progress.averageCycleOverdue === 0) return <>Average mark reached</>;
  return <>{formatNumber(progress.averageCycleOverdue)} beyond average mark</>;
}

function attemptPeriodLabel(progress: CyberspaceProgress): string {
  if (progress.anchorReason === "cyberspace") return "uses since last Cyberspace";
  if (progress.anchorReason === "statsReset") return "uses since statistics reset";
  if (progress.anchorReason === "migration") return "uses tracked since this update";
  return "uses tracked toward first Cyberspace";
}

export function CyberspaceStatsPanel() {
  const progress = useStore((state) => state.cyberspaceProgress);
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(CYBERSPACE_COLLAPSE_KEY) === "1",
  );
  if (!progress) return null;

  function toggleCollapsed() {
    setCollapsed((current) => {
      localStorage.setItem(CYBERSPACE_COLLAPSE_KEY, current ? "0" : "1");
      return !current;
    });
  }

  const hasUnattributed = progress.unattributed.combined > 0;
  const etaTitle = progress.etaMode === "fromNow"
    ? "Expected time for another 5,000 independent attempts from now"
    : "Cooldown-based continuous time to the 5,000-use average mark";

  return (
    <section className={`glass card panel cyber-panel${collapsed ? " collapsed" : ""}`} data-reveal>
      <div
        className="panel-head cyber-panel-head fx-coll-head"
        onClick={toggleCollapsed}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleCollapsed();
          }
        }}
        role="button"
        tabIndex={0}
        aria-expanded={!collapsed}
      >
        <div className="panel-title">
          <i className="fa-solid fa-satellite-dish"></i> Cyberspace Progress
        </div>
        <div className="cyber-panel-actions">
          <span className="badge badge-soft">1 in {formatNumber(progress.odds)} per use</span>
          <i className={`fa-solid fa-chevron-down fx-coll-chevron${collapsed ? " closed" : ""}`}></i>
        </div>
      </div>

      <div className="cyber-hero">
        <div className="cyber-progress-block">
          <div className="cyber-progress-copy">
            <span>
              <b>{formatNumber(progress.sinceLast.combined)}</b>
              <small> / {formatNumber(progress.odds)} {attemptPeriodLabel(progress)}</small>
            </span>
            <strong><RemainingLabel progress={progress} /></strong>
          </div>
          <div className="cyber-track" aria-label={`${progress.progressPercent.toFixed(1)} percent of average cycle`}>
            <span style={{ width: `${Math.max(0, Math.min(100, progress.progressPercent))}%` }}></span>
          </div>
          <div className="cyber-split">
            <span>SC <b>{formatNumber(progress.sinceLast.strangeController)}</b></span>
            <span>BR <b>{formatNumber(progress.sinceLast.biomeRandomizer)}</b></span>
          </div>
        </div>

        <div className="cyber-metrics">
          <div className="cyber-metric" title={etaTitle}>
            <i className="fa-solid fa-hourglass-half"></i>
            <span><b>{formatEta(progress.etaSeconds)}</b><small>{progress.etaMode === "fromNow" ? "expected from now" : "cooldown-based ETA"}</small></span>
          </div>
          <div className="cyber-metric">
            <i className="fa-solid fa-percent"></i>
            <span><b>{formatChance(progress.chanceSinceLastPercent)}</b><small>chance across recorded uses</small></span>
          </div>
          <div className="cyber-metric">
            <i className="fa-solid fa-gauge-high"></i>
            <span><b>{formatRate(progress.usesPerHour)}</b><small>{progress.activeAccounts} active account{progress.activeAccounts === 1 ? "" : "s"}</small></span>
          </div>
          <div className="cyber-metric">
            <i className="fa-solid fa-cloud"></i>
            <span><b>{formatNumber(progress.cyberspaceCount)}</b><small>Cyberspaces logged</small></span>
          </div>
        </div>
      </div>

      <Collapse open={!collapsed}>
      <div className="cyber-collapse-body">
      {!progress.accurateSinceLastCyberspace && (
        <div className="cyber-note warning">
          <i className="fa-solid fa-circle-info"></i>
          Exact post-Cyberspace tracking started with this update; older uses cannot be reconstructed.
        </div>
      )}

      <div className="cyber-account-table">
        <div className="cyber-account-header">
          <span>Account</span><span>Strange Controller</span><span>Biome Randomizer</span><span>Combined</span>
        </div>
        {progress.accounts.map((account) => <AccountRow key={account.id} account={account} />)}
        {hasUnattributed && (
          <div className="cyber-account-row legacy">
            <div className="cyber-account-name">
              <i className="fa-solid fa-clock-rotate-left"></i>
              <span><b>Before account tracking</b><small>Legacy or removed-account uses</small></span>
            </div>
            <UsageValue lifetime={progress.unattributed.strangeController} session={0} />
            <UsageValue lifetime={progress.unattributed.biomeRandomizer} session={0} />
            <UsageValue lifetime={progress.unattributed.combined} session={0} />
          </div>
        )}
        {!progress.accounts.length && !hasUnattributed && (
          <div className="cyber-account-empty">Add an account to start tracking item uses.</div>
        )}
      </div>

      <p className="cyber-disclaimer">
        <i className="fa-solid fa-dice"></i>
        The 5,000-use mark is a statistical average, not pity or a guaranteed Cyberspace.
      </p>
      </div>
      </Collapse>
    </section>
  );
}

export function CyberspaceMonitorStrip() {
  const progress = useStore((state) => state.cyberspaceProgress);
  if (!progress) return null;
  const overdue = progress.averageCycleOverdue > 0;
  const remainingText = overdue
    ? `+${formatNumber(progress.averageCycleOverdue)} past average`
    : progress.estimatedRemaining === 0
      ? "average mark reached"
      : `~${formatNumber(progress.estimatedRemaining)} uses left`;

  return (
    <div className="mon-cyber" title="Each recorded macro SC or BR use is one independent 1-in-5,000 Cyberspace attempt. ETA uses configured cooldowns.">
      <div className="mon-cyber-top">
        <span><i className="fa-solid fa-satellite-dish"></i> Cyberspace</span>
        <b>{formatNumber(progress.sinceLast.combined)} / {formatNumber(progress.odds)}</b>
      </div>
      <div className="mon-cyber-track"><span style={{ width: `${Math.max(0, Math.min(100, progress.progressPercent))}%` }}></span></div>
      <div className="mon-cyber-meta">
        <span>{remainingText}</span>
        <span>{formatEta(progress.etaSeconds)}</span>
        <span>Session SC {formatNumber(progress.session.strangeController)} · BR {formatNumber(progress.session.biomeRandomizer)}</span>
      </div>
    </div>
  );
}
