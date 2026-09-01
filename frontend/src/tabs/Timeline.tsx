import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { callPy } from "../bridge";
import { CustomSelect } from "../components/CustomSelect";
import { ModuleDrawer } from "../components/ModuleDrawer";
import { confirmDialog } from "../dialog";
import { useStore } from "../store";
import type { DecisionTrace, TimelineEntry } from "../types";

interface TimelineResponse {
  entries?: TimelineEntry[];
  hasMore?: boolean;
  total?: number;
}

const PAGE_SIZE = 30;

const TIME_OPTIONS = [
  { value: "all", label: "Any time", icon: "fa-infinity" },
  { value: "today", label: "Today", icon: "fa-calendar-day" },
  { value: "24h", label: "Last 24 hours", icon: "fa-clock" },
  { value: "7d", label: "Last 7 days", icon: "fa-calendar-week" },
  { value: "30d", label: "Last 30 days", icon: "fa-calendar" },
];

const STATUS_OPTIONS = [
  { value: "all", label: "All statuses", icon: "fa-layer-group" },
  { value: "issues", label: "Problems only", icon: "fa-triangle-exclamation" },
  { value: "success", label: "Successful only", icon: "fa-circle-check" },
  { value: "info", label: "Information only", icon: "fa-circle-info" },
];

const FILTERS = [
  { key: "all", label: "All", icon: "fa-list" },
  { key: "biome", label: "Biomes", icon: "fa-earth-americas" },
  { key: "aura", label: "Auras", icon: "fa-star" },
  { key: "connection", label: "Connections", icon: "fa-plug" },
  { key: "clip", label: "Clips", icon: "fa-clapperboard" },
  { key: "actions", label: "Actions", icon: "fa-wand-magic-sparkles" },
  { key: "issues", label: "Issues", icon: "fa-triangle-exclamation" },
] as const;

const META: Record<string, { label: string; icon: string }> = {
  biome: { label: "Biome", icon: "fa-earth-americas" },
  aura: { label: "Aura", icon: "fa-star" },
  connection: { label: "Connection", icon: "fa-plug" },
  clip: { label: "Clip", icon: "fa-clapperboard" },
  fishing: { label: "Fishing", icon: "fa-fish" },
  merchant: { label: "Merchant", icon: "fa-store" },
  action: { label: "Action", icon: "fa-wand-magic-sparkles" },
  system: { label: "System", icon: "fa-circle-info" },
};

function categoriesFor(filter: string): string[] | null {
  if (filter === "all") return null;
  if (filter === "actions") return ["action", "fishing", "merchant"];
  return [filter];
}

function kindsFor(status: string): string[] | null {
  if (status === "issues") return ["bad", "warn"];
  if (status === "success") return ["good"];
  if (status === "info") return ["info", "biome"];
  return null;
}

function sinceFor(period: string): number | null {
  const now = Date.now();
  if (period === "today") {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    return start.getTime() / 1000;
  }
  if (period === "24h") return (now - 24 * 60 * 60 * 1000) / 1000;
  if (period === "7d") return (now - 7 * 24 * 60 * 60 * 1000) / 1000;
  if (period === "30d") return (now - 30 * 24 * 60 * 60 * 1000) / 1000;
  return null;
}

function dateKey(timestamp: number): string {
  const date = new Date(timestamp * 1000);
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

function dateLabel(timestamp: number): string {
  const date = new Date(timestamp * 1000);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (dateKey(timestamp) === dateKey(today.getTime() / 1000)) return "Today";
  if (dateKey(timestamp) === dateKey(yesterday.getTime() / 1000)) return "Yesterday";
  return date.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric", year: "numeric" });
}

function timeLabel(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function mergeEntries(current: TimelineEntry[], incoming: TimelineEntry[]): TimelineEntry[] {
  const map = new Map<number, TimelineEntry>();
  [...current, ...incoming].forEach((entry) => map.set(entry.id, entry));
  return Array.from(map.values()).sort((a, b) => b.id - a.id).slice(0, 750);
}

export function Timeline() {
  const accounts = useStore((state) => state.accounts);
  const setCurrentTab = useStore((state) => state.setCurrentTab);
  const setTutorialDrawer = useStore((state) => state.setTutorialDrawer);
  const pushToast = useStore((state) => state.pushToast);
  const [account, setAccount] = useState("all");
  const [filter, setFilter] = useState("all");
  const [period, setPeriod] = useState("all");
  const [status, setStatus] = useState("all");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [inspected, setInspected] = useState<TimelineEntry | null>(null);

  const accountId = account === "all" ? null : Number(account);
  const hasActiveFilters = account !== "all" || filter !== "all" || period !== "all" || status !== "all" || Boolean(search);

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const fetchLatest = useCallback(async (replace = false) => {
    const response = await callPy<TimelineResponse>(
      "get_account_timeline", accountId, null, PAGE_SIZE, categoriesFor(filter),
      search, kindsFor(status), sinceFor(period),
    ).catch(() => null);
    if (!response) {
      setLoading(false);
      setLoadError(true);
      return;
    }
    const incoming = Array.isArray(response.entries) ? response.entries : [];
    setEntries((current) => replace ? incoming : mergeEntries(current, incoming));
    setHasMore(Boolean(response.hasMore));
    setTotal(Number(response.total) || 0);
    setLoadError(false);
    setLoading(false);
  }, [accountId, filter, period, search, status]);

  useEffect(() => {
    setEntries([]);
    setLoading(true);
    void fetchLatest(true);
    const timer = window.setInterval(() => void fetchLatest(false), 4000);
    return () => window.clearInterval(timer);
  }, [fetchLatest]);

  async function loadOlder() {
    const oldest = entries[entries.length - 1]?.id;
    if (!oldest) return;
    const response = await callPy<TimelineResponse>(
      "get_account_timeline", accountId, oldest, PAGE_SIZE, categoriesFor(filter),
      search, kindsFor(status), sinceFor(period),
    ).catch(() => null);
    if (!response) return;
    setEntries((current) => mergeEntries(current, response.entries || []));
    setHasMore(Boolean(response.hasMore));
  }

  async function clearHistory() {
    const selected = accounts.find((item) => item.id === accountId)?.name;
    const scope = selected ? `the saved timeline for ${selected}` : "the complete saved account timeline";
    const confirmed = await confirmDialog(`Clear ${scope}? This cannot be undone.`, {
      title: "Clear account timeline", confirmLabel: "Clear history", danger: true,
    });
    if (!confirmed) return;
    setClearing(true);
    await callPy("clear_account_timeline", accountId).catch(() => null);
    setEntries([]);
    setHasMore(false);
    setTotal(0);
    setClearing(false);
  }

  function resetFilters() {
    setAccount("all");
    setFilter("all");
    setPeriod("all");
    setStatus("all");
    setSearchInput("");
    setSearch("");
  }

  function openNextStep(trace: DecisionTrace) {
    const next = trace.nextStep;
    if (!next) return;
    setInspected(null);
    setCurrentTab(next.tab);
    const drawer = next.drawer
      || (next.label.toLowerCase().includes("aura") ? "aura" : "")
      || (next.label.toLowerCase().includes("clip") ? "clipping" : "")
      || (next.label.toLowerCase().includes("anti fake") ? "misc" : "");
    if (next.tab === "modules" && drawer) {
      window.setTimeout(() => setTutorialDrawer({ kind: drawer, ...(next.accountId != null ? { accId: next.accountId } : {}) }), 80);
    } else if (next.anchor) {
      window.setTimeout(() => document.getElementById(next.anchor || "")?.scrollIntoView({ behavior: "smooth", block: "center" }), 120);
    }
  }

  async function copyDecision(entry: TimelineEntry) {
    if (!entry.decision) return;
    const trace = entry.decision;
    const lines = [
      `Why Didn't It Act? — ${trace.module || entry.category}`,
      `Status: ${trace.status.toUpperCase()}`,
      `Account: ${entry.account || "System"}`,
      `Time: ${new Date(entry.ts * 1000).toLocaleString()}`,
      `Reason: ${trace.summary}`,
      ...(trace.facts || []).map((item) => `${item.label}: ${item.value}`),
      ...(trace.checks || []).map((item) => `${item.state === "pass" ? "PASS" : item.state === "fail" ? "FAIL" : "INFO"}: ${item.label}${item.detail ? ` — ${item.detail}` : ""}`),
      trace.reasonCode ? `Reason code: ${trace.reasonCode}` : "",
    ].filter(Boolean);
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      pushToast({ icon: "fa-copy", title: "Decision details copied" });
    } catch {
      pushToast({ icon: "fa-triangle-exclamation", title: "Could not copy decision details" });
    }
  }

  const groups = useMemo(() => {
    const result: Array<{ key: string; label: string; entries: TimelineEntry[] }> = [];
    for (const entry of entries) {
      const key = dateKey(entry.ts);
      let group = result[result.length - 1];
      if (!group || group.key !== key) {
        group = { key, label: dateLabel(entry.ts), entries: [] };
        result.push(group);
      }
      group.entries.push(entry);
    }
    return result;
  }, [entries]);

  const biomeCount = entries.filter((entry) => entry.category === "biome").length;
  const issueCount = entries.filter((entry) => entry.kind === "bad" || entry.kind === "warn").length;

  return (
    <section className="tab active-tab timeline-tab" id="timeline">
      <header className="page-head timeline-head" data-reveal>
        <div>
          <h1>Account Timeline</h1>
          <p>A permanent local history of important events for every account.</p>
        </div>
        <button className="timeline-clear" disabled={clearing} onClick={() => void clearHistory()}>
          <i className="fa-solid fa-trash-can"></i> Clear history
        </button>
      </header>

      <div className="timeline-toolbar glass card" data-reveal>
        <div className="timeline-search-row">
          <label className="timeline-search">
            <i className="fa-solid fa-magnifying-glass"></i>
            <input
              type="search"
              aria-label="Search account timeline"
              placeholder="Search account, biome, aura, action…"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Escape") setSearchInput(""); }}
            />
            {searchInput && (
              <button type="button" aria-label="Clear timeline search" onClick={() => setSearchInput("")}>
                <i className="fa-solid fa-xmark"></i>
              </button>
            )}
          </label>
          {hasActiveFilters && (
            <button className="timeline-reset" onClick={resetFilters}>
              <i className="fa-solid fa-filter-circle-xmark"></i> Reset filters
            </button>
          )}
        </div>
        <div className="timeline-filter-row">
          <TimelineSelect label="Account">
            <CustomSelect
              aria-label="Filter account timeline by account"
              value={account}
              onChange={setAccount}
              options={[
                { value: "all", label: "All accounts", icon: "fa-users" },
                ...accounts.map((item) => ({ value: String(item.id), label: item.name, icon: "fa-user" })),
              ]}
            />
          </TimelineSelect>
          <TimelineSelect label="Time">
            <CustomSelect aria-label="Filter account timeline by time" value={period} onChange={setPeriod} options={TIME_OPTIONS} />
          </TimelineSelect>
          <TimelineSelect label="Status">
            <CustomSelect aria-label="Filter account timeline by status" value={status} onChange={setStatus} options={STATUS_OPTIONS} />
          </TimelineSelect>
        </div>
        <div className="timeline-type-row">
          <span>Event type</span>
          <div className="timeline-filters" role="group" aria-label="Timeline event filter">
            {FILTERS.map((item) => (
              <button key={item.key} className={filter === item.key ? "active" : ""} onClick={() => setFilter(item.key)}>
                <i className={`fa-solid ${item.icon}`}></i>{item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="timeline-stats" data-reveal>
        <TimelineStat label="Matches" value={total} icon="fa-filter" />
        <TimelineStat label="Shown" value={entries.length} icon="fa-list-check" />
        <TimelineStat label="Biomes shown" value={biomeCount} icon="fa-earth-americas" />
        <TimelineStat label="Issues" value={issueCount} icon="fa-triangle-exclamation" danger={issueCount > 0} />
      </div>

      <div className="timeline-history glass card" data-reveal>
        {loading ? (
          <div className="timeline-empty"><i className="fa-solid fa-spinner fa-spin"></i><b>Loading timeline…</b></div>
        ) : loadError ? (
          <div className="timeline-empty">
            <span><i className="fa-solid fa-triangle-exclamation"></i></span>
            <b>Timeline could not be loaded</b>
            <p>The local backend did not answer. You can retry without leaving this page.</p>
            <button className="timeline-reset empty" onClick={() => { setLoading(true); void fetchLatest(true); }}>Try again</button>
          </div>
        ) : !entries.length ? (
          <div className="timeline-empty">
            <span><i className={`fa-solid ${hasActiveFilters ? "fa-magnifying-glass" : "fa-clock-rotate-left"}`}></i></span>
            <b>{hasActiveFilters ? "No matching events" : "No events here yet"}</b>
            <p>{hasActiveFilters ? "Try another search or reset the filters." : "Important biomes, auras, clips, actions and connection changes will appear automatically."}</p>
            {hasActiveFilters && <button className="timeline-reset empty" onClick={resetFilters}>Reset filters</button>}
          </div>
        ) : (
          groups.map((group) => (
            <div className="timeline-day" key={group.key}>
              <div className="timeline-day-label"><span>{group.label}</span><i></i></div>
              <div className="timeline-day-events">
                {group.entries.map((entry) => <TimelineEvent key={entry.id} entry={entry} onInspect={setInspected} />)}
              </div>
            </div>
          ))
        )}
        {hasMore && !loading && (
          <button className="timeline-more" onClick={() => void loadOlder()}>
            <i className="fa-solid fa-clock-rotate-left"></i> Load {PAGE_SIZE} more
          </button>
        )}
        {!!entries.length && !loading && (
          <div className="timeline-count">Showing {entries.length} of {total} matching events</div>
        )}
      </div>
      <DecisionInspector
        entry={inspected}
        onClose={() => setInspected(null)}
        onNextStep={openNextStep}
        onCopy={(entry) => void copyDecision(entry)}
      />
    </section>
  );
}

function TimelineSelect({ label, children }: { label: string; children: ReactNode }) {
  return <div className="timeline-select"><span>{label}</span>{children}</div>;
}

function TimelineStat({ label, value, icon, danger = false }: { label: string; value: number; icon: string; danger?: boolean }) {
  return (
    <div className={`timeline-stat glass card${danger ? " danger" : ""}`}>
      <span><i className={`fa-solid ${icon}`}></i></span>
      <div><b>{value}</b><small>{label}</small></div>
    </div>
  );
}

function TimelineEvent({ entry, onInspect }: { entry: TimelineEntry; onInspect: (entry: TimelineEntry) => void }) {
  const meta = META[entry.category] || META.system;
  return (
    <article className={`timeline-event k-${entry.kind} c-${entry.category}`}>
      <div className="timeline-rail"><span><i className={`fa-solid ${meta.icon}`}></i></span></div>
      <time>{timeLabel(entry.ts)}</time>
      <div className="timeline-event-main">
        <p>{entry.text}</p>
        <div className="timeline-event-meta">
          <span className="timeline-account"><i className="fa-solid fa-user"></i>{entry.account || "System"}</span>
          <span className="timeline-category">{meta.label}</span>
          {entry.biome && <span className="timeline-biome">{entry.biome}</span>}
          {entry.decision && (
            <button className="timeline-why" onClick={() => onInspect(entry)}>
              <i className="fa-solid fa-circle-question"></i> Why?
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

const DECISION_META = {
  acted: { label: "Acted", icon: "fa-circle-check" },
  skipped: { label: "Skipped", icon: "fa-forward-step" },
  blocked: { label: "Blocked", icon: "fa-shield-halved" },
  waiting: { label: "Waiting", icon: "fa-clock" },
  cancelled: { label: "Cancelled", icon: "fa-ban" },
  failed: { label: "Failed", icon: "fa-circle-xmark" },
} as const;

function DecisionInspector({ entry, onClose, onNextStep, onCopy }: {
  entry: TimelineEntry | null;
  onClose: () => void;
  onNextStep: (trace: DecisionTrace) => void;
  onCopy: (entry: TimelineEntry) => void;
}) {
  const trace = entry?.decision;
  const status = trace ? DECISION_META[trace.status] : DECISION_META.skipped;
  return (
    <ModuleDrawer
      open={Boolean(trace)}
      title="Why Didn't It Act?"
      sub={trace?.module || "Decision details"}
      icon="fa-magnifying-glass"
      wide
      onClose={onClose}
    >
      {entry && trace && (
        <div className={`decision-inspector s-${trace.status}`}>
          <div className="decision-status-card">
            <span className="decision-status"><i className={`fa-solid ${status.icon}`}></i>{status.label}</span>
            <h3>{trace.summary}</h3>
            <p>{entry.account || "System"} · {new Date(entry.ts * 1000).toLocaleString()}</p>
          </div>

          {!!trace.checks?.length && (
            <section className="decision-section">
              <h4>Checks</h4>
              <div className="decision-checks">
                {trace.checks.map((item, index) => (
                  <div className={`decision-check ${item.state}`} key={`${item.label}-${index}`}>
                    <i className={`fa-solid ${item.state === "pass" ? "fa-check" : item.state === "fail" ? "fa-xmark" : "fa-minus"}`}></i>
                    <div><b>{item.label}</b>{item.detail && <span>{item.detail}</span>}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {!!trace.facts?.length && (
            <section className="decision-section">
              <h4>What SolRich saw</h4>
              <dl className="decision-facts">
                {trace.facts.map((item, index) => (
                  <div key={`${item.label}-${index}`}><dt>{item.label}</dt><dd>{item.value}</dd></div>
                ))}
              </dl>
            </section>
          )}

          <div className="decision-code">Reason code: <code>{trace.reasonCode || "not_recorded"}</code></div>
          <div className="decision-actions">
            <button className="decision-copy" onClick={() => onCopy(entry)}><i className="fa-solid fa-copy"></i> Copy details</button>
            {trace.nextStep && (
              <button className="decision-fix" onClick={() => onNextStep(trace)}>{trace.nextStep.label}<i className="fa-solid fa-arrow-right"></i></button>
            )}
          </div>
        </div>
      )}
    </ModuleDrawer>
  );
}
