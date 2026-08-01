






import { useEffect, useRef, useState, type ReactNode } from "react";
import { useStore } from "../store";
import { TimeTrackingPanel } from "../components/TimeTrackingPanel";
import { Collapse } from "../components/Collapse";
import { CountUp } from "../components/CountUp";
import { CyberspaceStatsPanel } from "../components/CyberspaceProgress";
import { getMacroAccounts } from "../data/macroMode";
import {
  BIOMES,
  TIERS,
  RARE_KEYS,
  SEMI_RARE_KEYS,
  DEFAULT_AVATAR,
  biomeMeta,
  type Biome,
} from "../data/biomes";

interface Account {
  id: number;
  name: string;
  avatar?: string;
  enabled?: boolean;
  currentBiome?: string | null;
  online?: boolean;
  window?: string | null;
}
interface Webhook {
  active?: boolean;
}




function formatTime(sec: number): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(Math.floor(sec / 3600))}:${pad(Math.floor((sec % 3600) / 60))}:${pad(sec % 60)}`;
}
function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}
function fmtRarity(rarity: number | null): string {
  if (!rarity) return "1 in ?";
  return "1 in " + formatNumber(Number(rarity));
}

const MERCHANT_META = [
  { key: "mari", name: "Mari", color: "#FFFFFF" },
  { key: "jester", name: "Jester", color: "#9B59B6" },
  { key: "rin", name: "Rin", color: "#FAA61A" },
];



export function Stats() {
  const running = useStore((s) => s.running);
  const uptime = useStore((s) => s.uptime);
  const accounts = useStore((s) => s.accounts) as Account[];
  const settings = useStore((s) => s.settings);
  const webhooks = useStore((s) => s.webhooks) as Webhook[];
  const biomeCounts = useStore((s) => s.biomeCounts);
  const unknownBiomes = useStore((s) => s.unknownBiomes);
  const merchantCounts = useStore((s) => s.merchantCounts);
  const timeTracking = useStore((s) => s.timeTracking);

  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const toggleTier = (key: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const [countsCollapsed, setCountsCollapsed] = useState(() => localStorage.getItem("biomeCountsCollapsed") === "1");
  const [countsFlush, setCountsFlush] = useState(countsCollapsed);
  const flushTimer = useRef<number | undefined>(undefined);
  useEffect(() => {
    window.clearTimeout(flushTimer.current);
    if (countsCollapsed) {
      flushTimer.current = window.setTimeout(() => setCountsFlush(true), 400);
    } else {
      setCountsFlush(false);
    }
    return () => window.clearTimeout(flushTimer.current);
  }, [countsCollapsed]);
  const toggleCounts = () =>
    setCountsCollapsed((current) => {
      localStorage.setItem("biomeCountsCollapsed", current ? "0" : "1");
      return !current;
    });

  const count = (key: string) => biomeCounts[key] || 0;
  const total = Object.values(biomeCounts).reduce((a, b) => a + b, 0);
  const maxCount = Math.max(1, ...Object.values(biomeCounts), ...Object.values(unknownBiomes));

  
  const tierTotals = { normal: 0, event: 0, rare: 0 } as Record<string, number>;
  BIOMES.forEach((biome) => {
    const target = biome.tier === "semi-rare" ? "rare" : biome.tier;
    if (tierTotals[target] !== undefined) tierTotals[target] += count(biome.key);
  });

  const fishCaught = Number((timeTracking?.fishCaught as number) || 0);
  const activeWebhooks = webhooks.filter((w) => w.active).length;

  const totalSafe = total || 1;
  const pct = (value: number) => ((value / totalSafe) * 100).toFixed(value && value / totalSafe < 0.01 ? 2 : 1);

  const groups: Array<{ key: string; label: string; color: string; total: number; rows: Biome[]; unknown?: boolean }> = [];
  TIERS.forEach((tier) => {
    let list = BIOMES.filter((biome) =>
      tier.key === "rare" ? biome.tier === "rare" || biome.tier === "semi-rare" : biome.tier === tier.key,
    );
    if (tier.key === "rare") {
      const order = [...RARE_KEYS, ...SEMI_RARE_KEYS];
      list = [...list].sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
    } else {
      list = [...list].sort((a, b) => (b.rarity || 0) - (a.rarity || 0));
    }
    if (!list.length) return;
    groups.push({
      key: tier.key,
      label: tier.label,
      color: tier.color,
      total: list.reduce((sum, biome) => sum + count(biome.key), 0),
      rows: list,
    });
  });

  const unknownNames = Object.keys(unknownBiomes).sort(
    (a, b) => (unknownBiomes[b] || 0) - (unknownBiomes[a] || 0),
  );

  const merchantStats = MERCHANT_META.map((meta) => ({ ...meta, found: merchantCounts[meta.key] || 0 }));
  const merchantTotal = merchantStats.reduce((sum, merchant) => sum + merchant.found, 0);
  const merchantSafe = merchantTotal || 1;
  const merchantPct = (value: number) => ((value / merchantSafe) * 100).toFixed(value && value / merchantSafe < 0.01 ? 2 : 1);

  const liveAccounts = getMacroAccounts(accounts, settings);
  const onlineCount = running ? liveAccounts.filter((account) => account.online).length : 0;

  return (
    <section className="tab active-tab" id="stats">
      <header className="page-head">
        <h1>Statistics</h1>
        <p>Live biome monitoring, rarity breakdown and lifetime counts.</p>
      </header>

      {}
      <div className="stat-row stats-head" data-reveal>
        <StatCard ico="fa-solid fa-user-check" icoClass="ico-accent" value={String(accounts.length)} cap="Accounts" />
        <StatCard ico="fa-brands fa-discord" icoClass="ico-blurple" value={String(activeWebhooks)} cap="Active Webhooks" />
        <StatCard ico="fa-solid fa-stopwatch" icoClass="ico-accent" value={formatTime(uptime)} cap="Tracking Time" small />
        <StatCard ico="fa-solid fa-fish" icoClass="ico-accent" value={<CountUp value={fishCaught} />} cap="Fish Caught" small />
      </div>

      <TimeTrackingPanel />

      <CyberspaceStatsPanel />

      {}
      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-signal-stream"></i> Active Accounts</div>
          <span className="badge badge-soft">{onlineCount} online</span>
        </div>
        <div className="log-list">
          {liveAccounts.length === 0 ? (
            <div className="log-empty">No active accounts. Add or enable one under the Accounts tab.</div>
          ) : (
            liveAccounts.map((account) => <LogRow key={account.id} acc={account} running={running} />)
          )}
        </div>
      </div>

      {}
      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-layer-group"></i> Rarity Breakdown</div>
          <span className="badge badge-soft">{formatNumber(total)} logged</span>
        </div>
        <div className="rarity-bar">
          <div className="rarity-seg normal" style={{ flexGrow: tierTotals.normal }}></div>
          <div className="rarity-seg event" style={{ flexGrow: tierTotals.event }}></div>
          <div className="rarity-seg rare" style={{ flexGrow: tierTotals.rare }}></div>
        </div>
        <div className="rarity-legend">
          {[
            { color: "#5b6075", name: "Normal", value: tierTotals.normal },
            { color: "var(--t-event)", name: "Event", value: tierTotals.event },
            { color: "linear-gradient(90deg,#22c55e,#f368d4 38%,#38bdf8 68%,#fb923c)", name: "Rare", value: tierTotals.rare },
          ].map((item) => (
            <div className="rl-item" key={item.name}>
              <span className="rl-swatch" style={{ background: item.color }}></span>
              <span className="rl-text">
                <span className="rl-name">{item.name}</span>
                <span className="rl-val">{formatNumber(item.value)} · {pct(item.value)}%</span>
              </span>
            </div>
          ))}
        </div>
      </div>

      {}
      <div className="glass card panel rare-panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-gem"></i> Rare Biome Spotlight</div>
          <span className="badge badge-rare"><i className="fa-solid fa-bolt"></i> Extremely Rare</span>
        </div>
        <div className="rare-spotlight">
          {[...RARE_KEYS, ...SEMI_RARE_KEYS].map((key) => {
            const meta = biomeMeta(key)!;
            const found = count(key);
            return (
              <div className={`rare-card ${found > 0 ? "hit" : ""}`} key={key}
                style={{ ["--biome-grad" as string]: meta.grad, ["--biome-shadow" as string]: meta.shadow }}>
                <div className="rc-top"><span className="rc-swatch"></span><span className="rc-name">{meta.name}</span></div>
                <div className={`rc-count ${found === 0 ? "zero" : ""}`}>{formatNumber(found)}</div>
                <div className="rc-cap">{found === 0 ? "not yet found" : found === 1 ? "time found" : "times found"}</div>
              </div>
            );
          })}
        </div>
      </div>

      {}
      <div className="glass card panel" data-reveal>
        <div className={`panel-head fx-coll-head${countsFlush ? " coll-flush" : ""}`} onClick={toggleCounts}>
          <div className="panel-title"><i className="fa-solid fa-mountain-sun"></i> Biome Counts</div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span className="badge badge-sync"><CountUp value={total} /> total</span>
            <i className={`fa-solid fa-chevron-down fx-coll-chevron${countsCollapsed ? " closed" : ""}`}></i>
          </div>
        </div>
        <Collapse open={!countsCollapsed}>
        <div className="biome-groups">
          {groups.map((group) => (
            <div className={`biome-group${collapsed.has(group.key) ? " collapsed" : ""}`} key={group.key}>
              <div className="tier-head" onClick={() => toggleTier(group.key)}>
                <i className="fa-solid fa-chevron-down tier-chevron"></i>
                <span className="tier-dot" style={{ background: group.color }}></span>
                <span className="tier-label" style={{ color: group.color }}>{group.label}</span>
                <span className="tier-line"></span>
                <span className="tier-meta">{formatNumber(group.total)}</span>
              </div>
              <div className="biome-rows">
                {group.rows.map((biome) => <BiomeRow key={biome.key} b={biome} count={count(biome.key)} max={maxCount} />)}
              </div>
            </div>
          ))}
          {unknownNames.length > 0 && (
            <div className={`biome-group${collapsed.has("unknown") ? " collapsed" : ""}`}>
              <div className="tier-head" onClick={() => toggleTier("unknown")}>
                <i className="fa-solid fa-chevron-down tier-chevron"></i>
                <span className="tier-dot" style={{ background: "var(--text-faint)" }}></span>
                <span className="tier-label" style={{ color: "var(--text-faint)" }}>Unknown</span>
                <span className="tier-line"></span>
                <span className="tier-meta">{formatNumber(unknownNames.reduce((sum, name) => sum + (unknownBiomes[name] || 0), 0))}</span>
              </div>
              <div className="biome-rows">
                {unknownNames.map((name) => <UnknownRow key={name} name={name} count={unknownBiomes[name] || 0} max={maxCount} />)}
              </div>
            </div>
          )}
        </div>
        </Collapse>
      </div>

      {}
      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-store"></i> Merchant Breakdown</div>
          <span className="badge badge-soft">{formatNumber(merchantTotal)} found</span>
        </div>
        <div className="rarity-bar">
          {merchantStats.map((merchant) => (
            <div className="rarity-seg" key={merchant.key} style={{ flexGrow: merchant.found, background: merchant.color }}></div>
          ))}
        </div>
        <div className="rarity-legend">
          {merchantStats.map((merchant) => (
            <div className="rl-item" key={merchant.key}>
              <span className="rl-swatch" style={{ background: merchant.color }}></span>
              <span className="rl-text">
                <span className="rl-name">{merchant.name}</span>
                <span className="rl-val">{formatNumber(merchant.found)} · {merchantPct(merchant.found)}%</span>
              </span>
            </div>
          ))}
        </div>
        <div className="merchant-counts">
          {merchantStats.map((merchant) => (
            <div className={`merchant-count-card ${merchant.found > 0 ? "hit" : ""}`} key={merchant.key} style={{ ["--m-color" as string]: merchant.color }}>
              <div className="mc-top"><span className="mc-swatch" style={{ background: merchant.color }}></span><span className="mc-name">{merchant.name}</span></div>
              <div className={`mc-count ${merchant.found === 0 ? "zero" : ""}`}>{formatNumber(merchant.found)}</div>
              <div className="mc-cap">{merchant.found === 0 ? "not yet found" : merchant.found === 1 ? "time found" : "times found"}</div>
            </div>
          ))}
        </div>
      </div>

    </section>
  );
}



function StatCard({ ico, icoClass, value, cap, small }: { ico: string; icoClass: string; value: ReactNode; cap: string; small?: boolean }) {
  return (
    <div className="glass card stat">
      <div className={`stat-ico ${icoClass}`}><i className={ico}></i></div>
      <div className="stat-body">
        <span className={`stat-num ${small ? "sm" : ""}`}>{value}</span>
        <span className="stat-cap">{cap}</span>
      </div>
    </div>
  );
}

function BiomeRow({ b, count, max }: { b: Biome; count: number; max: number }) {
  const pct = Math.max(2, (count / max) * 100);
  const rare = b.tier === "rare" || b.tier === "semi-rare";
  return (
    <div className={`biome-row2 ${rare ? "rare" : ""}`} style={{ ["--biome-grad" as string]: b.grad, ["--biome-shadow" as string]: b.shadow }}>
      <span className="b2-swatch"></span>
      <span className="b2-name">{b.name} {rare && <span className="rare-tag">RARE</span>}</span>
      <span className="b2-bar"><i style={{ width: `${pct}%` }}></i></span>
      <span className="b2-rarity">{b.rarity ? fmtRarity(b.rarity) : ""}</span>
      <span className={`b2-count ${count === 0 ? "zero" : ""}`}>{count.toLocaleString("en-US")}</span>
    </div>
  );
}

function UnknownRow({ name, count, max }: { name: string; count: number; max: number }) {
  const pct = Math.max(2, (count / max) * 100);
  return (
    <div className="biome-row2 unknown" style={{ ["--biome-grad" as string]: "linear-gradient(135deg,#9aa0b5,#5b6075)", ["--biome-shadow" as string]: "#7e8499" }}>
      <span className="b2-swatch"></span>
      <span className="b2-name">{name} <span className="rare-tag unknown-tag">NEW</span></span>
      <span className="b2-bar"><i style={{ width: `${pct}%` }}></i></span>
      <span className="b2-rarity">1 in ?</span>
      <span className={`b2-count ${count === 0 ? "zero" : ""}`}>{count.toLocaleString("en-US")}</span>
    </div>
  );
}

function LogRow({ acc, running }: { acc: Account; running: boolean }) {
  const disabled = acc.enabled === false;
  const meta = disabled ? null : biomeMeta(acc.currentBiome);
  const isRare = !!(meta && (meta.tier === "rare" || meta.tier === "semi-rare"));
  const online = !!acc.online;
  const windowLabel = acc.window ? ` · ${acc.window}` : "";

  return (
    <div className={`log-row${isRare && running ? " is-rare" : ""}${disabled ? " acc-disabled" : ""}`}
      style={{ ["--row-accent" as string]: meta ? meta.shadow : "var(--stroke)" }}>
      <img className="log-avatar" alt="" src={acc.avatar || DEFAULT_AVATAR} />
      <div className="log-meta">
        <span className="log-name">{acc.name}</span>
        <span className="log-pill-slot">
          {meta ? (
            <span className={`biome-pill ${isRare ? "rare" : ""}`}>
              <span className="d" style={{ ["--g" as string]: meta.shadow }}></span>
              {meta.name}{windowLabel}
            </span>
          ) : (
            <span className="biome-pill">
              {disabled ? "Disabled" : running ? (online ? `Awaiting biome…${windowLabel}` : "Searching window…") : "Idle"}
            </span>
          )}
        </span>
      </div>
      <div className="log-status">
        {running && isRare && <span className="rare-flash">RARE FIND</span>}
        <span className={`lp${running && online ? " live" : ""}`}>
          <span className="sd"></span>
          <span className="lp-text">{disabled ? "Disabled" : running ? (online ? "Online" : "Offline") : "Idle"}</span>
        </span>
      </div>
    </div>
  );
}
