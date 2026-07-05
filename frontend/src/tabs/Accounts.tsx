import { memo, useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useStore } from "../store";
import { callPy } from "../bridge";
import { alertDialog, confirmDialog } from "../dialog";
import { isRobloxLink } from "../utils";
import { DEFAULT_AVATAR } from "../data/biomes";
import { Modal } from "../components/Modal";
import type { Account, BackendState } from "../types";

function showErrors(errors: string[]) {
  void alertDialog("• " + errors.join("\n• "), { title: "Could not complete" });
}

function tokenErrorText(err: unknown): string {
  if (!err) return "unknown error";
  const e = String(err);
  if (e === "invalid" || e === "token_invalid") return "token is invalid or expired";
  if (e === "no_token") return "no token linked";
  if (e.startsWith("wrong_account:")) return `logged in as "${e.split(":").slice(1).join(":")}" (that's a different account)`;
  if (e === "closed") return "browser closed before login finished";
  if (e === "timeout") return "timed out: login wasn't completed";
  if (e === "cancelled") return "cancelled";
  if (e === "no_browser") return "no Chrome or Edge found";
  if (e === "not_windows") return "launching only works on Windows";
  if (e === "bad_link") return "couldn't read the private server link";
  if (e.startsWith("no_ticket")) {
    const reason = e.split(":").slice(1).join(":");
    if (reason.startsWith("http_401")) return "auth ticket rejected: token may be expired";
    if (reason.startsWith("http_429")) return "Roblox is rate-limiting you. Wait about 30 seconds, then launch again";
    if (reason.startsWith("http_403")) return "Roblox blocked the request (Cloudflare). Wait a moment, then try again";
    if (reason.startsWith("network")) return "network error getting auth ticket";
    return "could not get an auth ticket from Roblox";
  }
  if (e.startsWith("http_429") || e.startsWith("token_http_429")) return "Roblox is rate-limiting you. Wait about 30 seconds and try again (your token is fine)";
  if (e.startsWith("http_403") || e.startsWith("token_http_403")) return "Roblox blocked the request for now. Try again shortly (your token is fine)";
  if (e.startsWith("token_network") || e === "network") return "couldn't reach Roblox. Check your connection, then try again";
  if (e.startsWith("token_")) return "token check failed (" + e.slice(6) + ")";
  if (e.startsWith("launch_failed")) return "Roblox failed to launch. Is it installed?";
  if (e.startsWith("network")) return "network error";
  if (e.startsWith("http_")) return "Roblox returned " + e;
  return e;
}

const CONSENT_STAGES = [
  {
    title: "Your tokens stay on your PC",
    body: (
      <>
        <p>Linking a Roblox token lets SolRich open Roblox and join private servers for you, just like Roblox Account Manager.</p>
        <p><b>Your <code>.ROBLOSECURITY</code> tokens are only ever stored locally</b> on this computer, in your own config file. They are never uploaded anywhere.</p>
        <p>SolRich is fully open source. You are welcome to read every line of the code before continuing.</p>
        <p>Only continue if you are completely comfortable with this.</p>
      </>
    ),
    btn: "I understand, continue",
  },
  {
    title: "One more confirmation",
    body: (
      <>
        <p>A Roblox token is as sensitive as your password. Anyone with the file could use your account.</p>
        <p>Make sure this device is yours and secure. By continuing you confirm you understand the risk and want to use local token storage.</p>
        <p><b>Are you absolutely sure?</b></p>
      </>
    ),
    btn: "Yes, I'm sure",
  },
];

type EditState = { id: number; name: string; link: string } | null;

export function Accounts() {
  const running = useStore((s) => s.running);
  const accounts = useStore((s) => s.accounts) as Account[];
  const settings = useStore((s) => s.settings);
  const applyState = useStore((s) => s.applyState);
  const patchSettings = useStore((s) => s.patchSettings);

  const [accName, setAccName] = useState("");
  const [accLink, setAccLink] = useState("");
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [tokenInputs, setTokenInputs] = useState<Record<number, string>>({});
  const [tokenStatus, setTokenStatus] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState<Set<string>>(new Set());
  const [edit, setEdit] = useState<EditState>(null);
  const [consent, setConsent] = useState<{ stage: number; action: () => void } | null>(null);
  const [browserBusy, setBrowserBusy] = useState<Set<number>>(new Set());
  const [recheckCD, setRecheckCD] = useState<Set<number>>(new Set());

  useEffect(() => {
    function onResult(e: Event) {
      const { accId, success, info } = (e as CustomEvent).detail as { accId: number; success: boolean; info: string };
      setBrowserBusy((p) => { const n = new Set(p); n.delete(accId); return n; });
      setTokenStatus((p) => ({ ...p, [accId]: success ? "" : `Login failed: ${tokenErrorText(info)}` }));
    }
    window.addEventListener("solrich:browser-login", onResult);
    return () => window.removeEventListener("solrich:browser-login", onResult);
  }, []);

  async function browserLogin(id: number) {
    if (running || browserBusy.has(id)) return;
    requireConsent(async () => {
      setBrowserBusy((p) => new Set(p).add(id));
      setTokenStatus((p) => ({ ...p, [id]: "Opening browser. Log in there…" }));
      const res = await callPy<{ ok?: boolean; error?: string; browser?: string }>("start_browser_login", id).catch(() => null);
      if (!res?.ok) {
        setBrowserBusy((p) => { const n = new Set(p); n.delete(id); return n; });
        const err = res?.error === "no_browser" ? "no Chrome/Edge found" : tokenErrorText(res?.error);
        setTokenStatus((p) => ({ ...p, [id]: `Couldn't start: ${err}` }));
      }
    });
  }

  function requireConsent(action: () => void) {
    if (settings.tokenConsent || localStorage.getItem("tokenConsent") === "1") {
      action();
      return;
    }
    setConsent({ stage: 0, action });
  }
  async function advanceConsent() {
    if (!consent) return;
    const next = consent.stage + 1;
    if (next < CONSENT_STAGES.length) {
      setConsent({ ...consent, stage: next });
      return;
    }
    const action = consent.action;
    setConsent(null);
    localStorage.setItem("tokenConsent", "1");
    patchSettings({ tokenConsent: true });
    await callPy("set_setting", "tokenConsent", true);
    action();
  }

  const loadKey = (k: string, ms = 1500) => {
    setLoading((p) => new Set(p).add(k));
    setTimeout(() => setLoading((p) => { const n = new Set(p); n.delete(k); return n; }), ms);
  };

  async function addAccount() {
    if (running) return;
    const username = accName.trim();
    const link = accLink.trim();
    if (!username) return;
    if (!link) return showErrors(["Please provide a private server link (required)."]);
    if (!isRobloxLink(link)) return showErrors(["The private server link must be a valid roblox.com URL."]);
    applyState(await callPy<BackendState>("add_account", username, link));
    setAccName("");
    setAccLink("");
  }
  async function deleteAccount(id: number) {
    if (running) return;
    const acc = accounts.find((a) => a.id === id);
    const name = acc?.name ? ` "${acc.name}"` : "";
    if (!(await confirmDialog(
      `Delete this account${name} and all of its settings? ` +
      `Its modules, biome layout, fishing setup, window and stored token are all removed. This can't be undone.`,
      { title: "Delete account", confirmLabel: "Delete account", danger: true },
    ))) return;
    applyState(await callPy<BackendState>("delete_account", id));
  }
  async function toggleEnabled(id: number, enabled: boolean) {
    if (running) return;
    applyState(await callPy<BackendState>("set_account_enabled", id, enabled));
  }
  async function moveAccount(id: number, direction: "up" | "down") {
    if (running) return;
    applyState(await callPy<BackendState>("move_account", id, direction));
  }
  function toggleCollapse(id: number) {
    setCollapsed((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }

  async function submitToken(id: number) {
    if (running) return;
    const token = (tokenInputs[id] || "").trim();
    if (!token) return;
    setTokenStatus((p) => ({ ...p, [id]: "Checking token…" }));
    const res = await callPy<{ ok?: boolean; error?: unknown; state?: BackendState }>("set_account_token", id, token);
    if (res?.state) applyState(res.state);
    setTokenStatus((p) => ({ ...p, [id]: "" }));
    if (res && !res.ok) showErrors([`Token check failed: ${tokenErrorText(res.error)}`]);
    setTokenInputs((p) => ({ ...p, [id]: "" }));
  }
  async function clearToken(id: number) {
    if (running) return;
    if (!(await confirmDialog("Remove the stored token for this account?", { title: "Remove token", confirmLabel: "Remove", danger: true }))) return;
    const res = await callPy<{ state?: BackendState }>("clear_account_token", id);
    if (res?.state) applyState(res.state);
  }
  async function recheckToken(id: number) {
    if (recheckCD.has(id)) return;
    setRecheckCD((p) => new Set(p).add(id));
    setTokenStatus((p) => ({ ...p, [id]: "Re-checking…" }));
    const res = await callPy<{ ok?: boolean; transient?: boolean; error?: unknown; state?: BackendState }>("revalidate_account_token", id);
    if (res?.state) applyState(res.state);
    if (res?.transient) {
      setTokenStatus((p) => ({ ...p, [id]: "Couldn't verify right now: Roblox is rate-limiting you. Token kept; try again in a moment." }));
      setTimeout(() => setTokenStatus((p) => ({ ...p, [id]: "" })), 6000);
    } else {
      setTokenStatus((p) => ({ ...p, [id]: "" }));
    }
    setTimeout(() => setRecheckCD((p) => { const n = new Set(p); n.delete(id); return n; }), 6000);
  }
  function launchOne(id: number, mode: string) {
    requireConsent(async () => {
      const acc = accounts.find((a) => a.id === id);
      if (!acc || !acc.hasToken) return showErrors(["This account has no linked token yet."]);
      loadKey(`one-${id}-${mode}`);
      const res = await callPy<{ ok?: boolean; error?: unknown }>("launch_account", id, mode);
      if (res && !res.ok) showErrors([`Could not launch ${acc.name}: ${tokenErrorText(res.error)}`]);
    });
  }
  function launchAll(mode: string) {
    requireConsent(async () => {
      const withToken = accounts.filter((a) => a.hasToken && a.enabled !== false);
      if (!withToken.length) return showErrors(["No enabled accounts have a linked token yet."]);
      loadKey(`all-${mode}`);
      const res = await callPy<{ results?: Array<{ ok?: boolean; name: string; error?: unknown }> }>("launch_all_accounts", mode);
      const failed = (res?.results || []).filter((r) => !r.ok);
      if (failed.length) showErrors(failed.map((r) => `${r.name}: ${tokenErrorText(r.error)}`));
    });
  }

  async function saveEdit(): Promise<boolean> {
    if (!edit) return true;
    if (!edit.name.trim()) return false;
    applyState(await callPy<BackendState>("update_account", edit.id, edit.name.trim(), edit.link.trim()));
    return true;
  }

  const withToken = accounts.filter((a) => a.hasToken).length;
  const enabledCount = accounts.filter((a) => a.enabled !== false).length;

  return (
    <section className="tab active-tab" id="accounts">
      <header className="page-head">
        <h1>Accounts</h1>
        <p>Manage accounts, link tokens, launch Roblox instances. Modules are assigned in the <b>Module Builder</b>, webhooks live in <b>Webhooks</b>.</p>
      </header>

      {}
      <div className="tab-section" data-reveal>
        <div className="tab-section-head">
          <i className="fa-solid fa-users-gear"></i>
          <h2>Account Manager</h2>
        </div>
        <div className="glass card am-launchbar">
          <div className="am-launch-info">
            <span className="am-launch-title"><i className="fa-solid fa-rocket"></i> Multi-Roblox</span>
            <span className="am-launch-sub">
              {withToken} of {accounts.length} account{accounts.length === 1 ? "" : "s"} have a linked token · {enabledCount} enabled
            </span>
          </div>
          <div className="am-launch-actions">
            <button className={`am-btn${loading.has("all-home") ? " am-loading" : ""}`} disabled={withToken === 0} onClick={() => launchAll("home")}>
              <i className="fa-solid fa-house"></i> Launch all
            </button>
            <button className={`am-btn am-btn-primary${loading.has("all-private") ? " am-loading" : ""}`} disabled={withToken === 0} onClick={() => launchAll("private")}>
              <i className="fa-solid fa-right-to-bracket"></i> Launch + teleport
            </button>
            <button className={`am-btn am-btn-sols${loading.has("all-public") ? " am-loading" : ""}`} disabled={withToken === 0} onClick={() => launchAll("public")}>
              <i className="fa-solid fa-dice"></i> Teleport to Sols
            </button>
          </div>
        </div>

        <div className="glass card input-bar" style={{ marginTop: 12 }}>
          <input type="text" className="field" placeholder="Username" value={accName} disabled={running} onChange={(e) => setAccName(e.target.value)} />
          <input type="text" className="field" placeholder="Private Server URL" value={accLink} disabled={running} onChange={(e) => setAccLink(e.target.value)} />
          <button className="btn-add" disabled={running} onClick={() => void addAccount()}>
            <i className="fa-solid fa-plus"></i> Add
          </button>
        </div>

        <div className="am-list" style={{ marginTop: 12 }}>
          {accounts.map((acc, i) => (
            <AccountCard
              key={acc.id}
              acc={acc}
              running={running}
              canUp={i > 0}
              canDown={i < accounts.length - 1}
              onMove={(dir) => void moveAccount(acc.id, dir)}
              collapsed={collapsed.has(acc.id)}
              tokenInput={tokenInputs[acc.id] || ""}
              tokenStatus={tokenStatus[acc.id] || ""}
              loading={loading}
              onToggleCollapse={() => toggleCollapse(acc.id)}
              onToggleEnabled={(v) => void toggleEnabled(acc.id, v)}
              onEdit={() => setEdit({ id: acc.id, name: acc.name, link: acc.link || "" })}
              onDelete={() => void deleteAccount(acc.id)}
              onTokenInput={(v) => setTokenInputs((p) => ({ ...p, [acc.id]: v }))}
              onTokenFocus={() => requireConsent(() => {})}
              onSubmitToken={() => void submitToken(acc.id)}
              onClearToken={() => void clearToken(acc.id)}
              onRecheckToken={() => void recheckToken(acc.id)}
              recheckBusy={recheckCD.has(acc.id)}
              onBrowserLogin={() => void browserLogin(acc.id)}
              browserBusy={browserBusy.has(acc.id)}
              onLaunch={(mode) => launchOne(acc.id, mode)}
            />
          ))}
        </div>
        {accounts.length === 0 && (
          <div className="empty-state show">
            <i className="fa-solid fa-user-plus"></i>
            <p>No accounts yet. Add one above to start.</p>
          </div>
        )}
      </div>

      {}
      <Modal open={!!edit} title="Edit Account" onCancel={() => setEdit(null)} onSave={saveEdit}>
        {edit && (
          <>
            <div>
              <div className="modal-label">Username</div>
              <input className="field" value={edit.name} placeholder="Username" onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
            </div>
            <div>
              <div className="modal-label">Private Server URL</div>
              <input className="field" value={edit.link} placeholder="roblox.com Private Server URL" onChange={(e) => setEdit({ ...edit, link: e.target.value })} />
            </div>
          </>
        )}
      </Modal>

      {}
      <ConsentModal
        consent={consent}
        onCancel={() => setConsent(null)}
        onAdvance={() => void advanceConsent()}
      />
    </section>
  );
}

type AccountCardProps = {
  acc: Account;
  running: boolean;
  canUp: boolean;
  canDown: boolean;
  onMove: (dir: "up" | "down") => void;
  collapsed: boolean;
  tokenInput: string;
  tokenStatus: string;
  loading: Set<string>;
  onToggleCollapse: () => void;
  onToggleEnabled: (v: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
  onTokenInput: (v: string) => void;
  onTokenFocus: () => void;
  onSubmitToken: () => void;
  onClearToken: () => void;
  onRecheckToken: () => void;
  recheckBusy: boolean;
  onBrowserLogin: () => void;
  browserBusy: boolean;
  onLaunch: (mode: string) => void;
};

function accountCardEqual(a: AccountCardProps, b: AccountCardProps): boolean {
  if (
    a.running !== b.running || a.canUp !== b.canUp || a.canDown !== b.canDown ||
    a.collapsed !== b.collapsed || a.tokenInput !== b.tokenInput ||
    a.tokenStatus !== b.tokenStatus || a.browserBusy !== b.browserBusy ||
    a.recheckBusy !== b.recheckBusy
  ) return false;
  const pa = a.acc, pb = b.acc;
  if (
    pa.id !== pb.id || pa.name !== pb.name || pa.link !== pb.link ||
    pa.avatar !== pb.avatar || pa.hasToken !== pb.hasToken ||
    pa.tokenValid !== pb.tokenValid || pa.enabled !== pb.enabled
  ) return false;
  for (const m of ["home", "private", "public"]) {
    const k = `one-${pa.id}-${m}`;
    if (a.loading.has(k) !== b.loading.has(k)) return false;
  }
  return true;
}

const AccountCard = memo(function AccountCard(props: AccountCardProps) {
  const { acc, running, collapsed, tokenInput, tokenStatus } = props;
  const [copied, setCopied] = useState(false);
  const disabled = acc.enabled === false;

  function copyLink(e: ReactMouseEvent) {
    e.stopPropagation();
    if (!acc.link) return;
    void navigator.clipboard.writeText(acc.link).then(
      () => { setCopied(true); window.setTimeout(() => setCopied(false), 1400); },
      () => {},
    );
  }

  const pill = !acc.hasToken ? (
    <span className="am-pill none"><i className="fa-solid fa-key"></i> No token</span>
  ) : acc.tokenValid ? (
    <span className="am-pill ok"><i className="fa-solid fa-circle-check"></i> Linked</span>
  ) : (
    <span className="am-pill bad"><i className="fa-solid fa-circle-exclamation"></i> Token invalid</span>
  );

  const launchBtn = (mode: string, cls: string, icon: string, label: string) => (
    <button className={`am-btn ${cls}${props.loading.has(`one-${acc.id}-${mode}`) ? " am-loading" : ""}`} disabled={!acc.hasToken} onClick={() => props.onLaunch(mode)}>
      <i className={`fa-solid ${icon}`}></i> {label}
    </button>
  );

  return (
    <div className={`am-card${collapsed ? " collapsed" : ""}${disabled ? " acc-disabled" : ""}`} data-acc-id={acc.id}>
      <div className="am-card-top" onClick={props.onToggleCollapse} style={{ cursor: "pointer" }}>
        <img src={acc.avatar || DEFAULT_AVATAR} className="am-avatar" alt="" />
        <div className="am-card-id">
          <span className="am-name">{acc.name}</span>
          <span className={`am-link ${acc.link ? "" : "muted"}`}>{acc.link || "No private server link"}</span>
        </div>
        {disabled && <span className="acc-disabled-tag">disabled</span>}
        {pill}
        <div className="am-card-right">
          <div className="am-reorder" onClick={(e) => e.stopPropagation()}>
            <button
              className="am-reorder-btn"
              disabled={running || !props.canUp}
              title="Move up"
              onClick={(e) => { e.stopPropagation(); props.onMove("up"); }}
            ><i className="fa-solid fa-chevron-up"></i></button>
            <button
              className="am-reorder-btn"
              disabled={running || !props.canDown}
              title="Move down"
              onClick={(e) => { e.stopPropagation(); props.onMove("down"); }}
            ><i className="fa-solid fa-chevron-down"></i></button>
          </div>
          <label
            className="switch"
            title={disabled ? "Account is disabled (excluded from the whole macro)" : "Account is enabled"}
            onClick={(e) => e.stopPropagation()}
          >
            <input type="checkbox" checked={!disabled} disabled={running} onChange={(e) => props.onToggleEnabled(e.target.checked)} />
            <span className="slider"></span>
          </label>
          <div className="am-card-edit">
            <button
              className={`edit-btn am-copy-btn${copied ? " copied" : ""}`}
              disabled={!acc.link}
              title={acc.link ? "Copy private server link" : "No private server link"}
              onClick={copyLink}
            >
              <i className={`fa-solid ${copied ? "fa-check" : "fa-copy"}`}></i>
            </button>
            <button className="edit-btn" onClick={(e) => { e.stopPropagation(); props.onEdit(); }}><i className="fa-solid fa-pen"></i></button>
            <button className="del-btn" onClick={(e) => { e.stopPropagation(); props.onDelete(); }}><i className="fa-solid fa-trash"></i></button>
          </div>
          <i className="fa-solid fa-chevron-down am-chevron"></i>
        </div>
      </div>
      <div className="am-card-body">
        {acc.hasToken ? (
          <div className="am-token">
            <span className="am-token-mask"><i className="fa-solid fa-lock"></i> ••••••••••••</span>
            <span className="am-token-status">{tokenStatus}</span>
            <div className="am-token-actions">
              <button className={`am-mini${props.recheckBusy ? " am-loading" : ""}`} onClick={props.onRecheckToken} disabled={props.recheckBusy} title={props.recheckBusy ? "Wait a moment between checks (avoids Roblox rate-limits)" : "Re-check token"}><i className="fa-solid fa-rotate"></i> Recheck</button>
              <button className={`am-mini accent${props.browserBusy ? " am-loading" : ""}`} onClick={props.onBrowserLogin} disabled={props.browserBusy} title="Re-login in a browser and grab a fresh token">
                <i className="fa-solid fa-globe"></i> {props.browserBusy ? "Waiting…" : "Re-login"}
              </button>
              <button className="am-mini danger" onClick={props.onClearToken} title="Remove token"><i className="fa-solid fa-xmark"></i> Remove</button>
            </div>
          </div>
        ) : (
          <div className="am-token">
            <input
              type="password"
              className="field am-token-input"
              placeholder="Paste .ROBLOSECURITY token"
              autoComplete="off"
              spellCheck={false}
              value={tokenInput}
              onFocus={props.onTokenFocus}
              onChange={(e) => props.onTokenInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") props.onSubmitToken(); }}
            />
            <span className="am-token-status">{tokenStatus}</span>
            <div className="am-token-actions">
              <button className={`am-mini${props.browserBusy ? " am-loading" : ""}`} onClick={props.onBrowserLogin} disabled={props.browserBusy} title="Open a browser, log in with your password, and the token is grabbed automatically">
                <i className="fa-solid fa-globe"></i> {props.browserBusy ? "Waiting for login…" : "Log in with browser"}
              </button>
              <button className="am-mini accent" onClick={props.onSubmitToken}><i className="fa-solid fa-link"></i> Link</button>
            </div>
          </div>
        )}
        <div className="am-card-launch">
          {launchBtn("home", "", "fa-house", "Launch")}
          {launchBtn("private", "am-btn-primary", "fa-right-to-bracket", "Launch + teleport")}
          {launchBtn("public", "am-btn-sols", "fa-dice", "Teleport to Sols")}
        </div>
      </div>
    </div>
  );
}, accountCardEqual);

function ConsentModal(props: {
  consent: { stage: number; action: () => void } | null;
  onCancel: () => void;
  onAdvance: () => void;
}) {
  const { consent } = props;
  const open = !!consent;
  const stageRef = useRef(0);
  if (consent) stageRef.current = consent.stage;
  const stage = CONSENT_STAGES[stageRef.current];

  return (
    <div className={`modal-overlay${open ? " open" : ""}`}>
      <div className="modal glass consent-modal" role="alertdialog" aria-modal="true" aria-label={stage.title}>
        <div className="consent-icon"><i className="fa-solid fa-triangle-exclamation"></i></div>
        <div className="consent-head">{stage.title}</div>
        <div className="consent-body">{stage.body}</div>
        <div className="consent-foot">
          <button className="btn-cancel" onClick={props.onCancel}>Cancel</button>
          <button className="consent-confirm" onClick={props.onAdvance}>{stage.btn}</button>
        </div>
      </div>
    </div>
  );
}
