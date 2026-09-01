







import { memo, useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useStore } from "../store";
import { callPy } from "../bridge";
import { alertDialog, confirmDialog } from "../dialog";
import { isRobloxLink } from "../utils";
import { DEFAULT_AVATAR } from "../data/biomes";
import { Modal } from "../components/Modal";
import type { Account, BackendState } from "../types";

type TokenSecurityStatus = {
  status: "protected" | "warning" | "unavailable";
  encryption: "windows_dpapi" | "unavailable";
  encrypted: boolean;
  scope: "current_windows_user" | "none";
  storageFile: string;
  fileExists: boolean;
  storedTokens: number;
  encryptedTokens: number;
  legacyTokens: number;
  unreadableTokens: number;
  legacyConfigTokens: number;
  migrationFailed: boolean;
  corruptStore: boolean;
};



function showErrors(errors: string[]) {
  void alertDialog("• " + errors.join("\n• "), { title: "Could not complete" });
}

function tokenErrorText(err: unknown): string {
  if (!err) return "unknown error";
  const code = String(err);
  if (code === "invalid" || code === "token_invalid") return "token is invalid or expired";
  if (code === "no_token") return "no token linked";
  if (code.startsWith("duplicate_account")) {
    const name = code.split(":").slice(1).join(":");
    return name ? `account "${name}" has already been added` : "this account has already been added";
  }
  if (code.startsWith("already_linked")) {
    const name = code.split(":").slice(1).join(":");
    return name
      ? `this Roblox account is already linked to "${name}"`
      : "this Roblox account is already linked to another entry";
  }
  if (code.startsWith("wrong_account:")) return `logged in as "${code.split(":").slice(1).join(":")}" (that's a different account)`;
  if (code === "closed") return "browser closed before login finished";
  if (code === "timeout") return "timed out: login wasn't completed";
  if (code === "cancelled") return "cancelled";
  if (code === "no_browser") return "no Chrome or Edge found";
  if (code === "cleanup_failed") return "temporary browser data could not be removed; sign out of Roblox in that browser and restart SolRich";
  if (code === "secure_storage_unavailable") return "Windows could not protect the login data, so SolRich refused to save it";
  if (code === "delete_failed") return "the stored login data could not be deleted";
  if (code === "not_windows") return "launching only works on Windows";
  if (code === "bad_link") return "couldn't read the private server link";
  if (code === "multi_instance_guard_late") {
    return "Multi-Roblox started too late. Close every Roblox window once, then press Launch again. SolRich will keep all following windows open.";
  }
  if (code.startsWith("no_ticket")) {
    const reason = code.split(":").slice(1).join(":");
    if (reason.startsWith("http_401")) return "auth ticket rejected: token may be expired";
    if (reason.startsWith("http_429")) return "Roblox is rate-limiting you. Wait about 30 seconds, then launch again";
    if (reason.startsWith("http_403")) return "Roblox blocked the request (Cloudflare). Wait a moment, then try again";
    if (reason.startsWith("network")) return "network error getting auth ticket";
    return "could not get an auth ticket from Roblox";
  }
  if (code.startsWith("http_429") || code.startsWith("token_http_429")) return "Roblox is rate-limiting you. Wait about 30 seconds and try again (your token is fine)";
  if (code.startsWith("http_403") || code.startsWith("token_http_403")) return "Roblox blocked the request for now. Try again shortly (your token is fine)";
  if (code.startsWith("token_network") || code === "network") return "couldn't reach Roblox. Check your connection, then try again";
  if (code.startsWith("token_")) return "token check failed (" + code.slice(6) + ")";
  if (code.startsWith("launch_failed")) return "Roblox failed to launch. Is it installed?";
  if (code.startsWith("network")) return "network error";
  if (code.startsWith("http_")) return "Roblox returned " + code;
  return code;
}



const CONSENT_STAGES = [
  {
    title: "Your Roblox login is sensitive",
    body: (
      <>
        <p>A <code>.ROBLOSECURITY</code> cookie can give someone access to your Roblox account. Treat it like a password.</p>
        <p>Linking it is <b>optional</b>. Without it, you can still launch Roblox yourself and bind the window manually.</p>
        <p>If linked, it is stored in a separate local file protected by <b>Windows DPAPI</b> for your current Windows user. It is not stored in <code>config.json</code>.</p>
        <p>SolRich only sends it to official Roblox services to validate or launch your account. It is never sent to the SolRich developer, Discord, webhooks or analytics.</p>
      </>
    ),
    btn: "I understand, continue",
  },
  {
    title: "One more confirmation",
    body: (
      <>
        <p>Only continue on your own trusted Windows device. Never share the cookie, <code>tokens.dat</code>, or screenshots containing login data.</p>
        <p>Browser login opens <b>roblox.com</b> in an isolated temporary browser profile. SolRich reads only the Roblox login cookie after sign-in; it never receives your password. The temporary profile is removed afterward.</p>
        <p>Windows encryption protects the saved file at rest, but it cannot make an unlocked or infected PC safe.</p>
        <p>You can remove local login data from SolRich at any time. If you think it was exposed, also sign out of Roblox sessions or change your password to revoke it.</p>
        <p>By continuing, you confirm this is your account and device and that you want SolRich to store the login cookie locally.</p>
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
  const [security, setSecurity] = useState<TokenSecurityStatus | null>(null);
  const [securityGuideOpen, setSecurityGuideOpen] = useState(
    () => localStorage.getItem("robloxLoginSafetyCollapsed") !== "1",
  );

  async function refreshSecurity() {
    const next = await callPy<TokenSecurityStatus>("get_token_security_status").catch(() => null);
    if (next) setSecurity(next);
  }

  useEffect(() => { void refreshSecurity(); }, []);

  useEffect(() => {
    function onResult(event: Event) {
      const { accId, success, info } = (event as CustomEvent).detail as { accId: number; success: boolean; info: string };
      setBrowserBusy((prev) => { const next = new Set(prev); next.delete(accId); return next; });
      setTokenStatus((prev) => ({ ...prev, [accId]: success ? "" : `Login failed: ${tokenErrorText(info)}` }));
      void refreshSecurity();
    }
    window.addEventListener("solrich:browser-login", onResult);
    return () => window.removeEventListener("solrich:browser-login", onResult);
  }, []);

  async function browserLogin(id: number) {
    if (running || browserBusy.has(id)) return;
    requireConsent(async () => {
      setBrowserBusy((prev) => new Set(prev).add(id));
      setTokenStatus((prev) => ({ ...prev, [id]: "Opening browser. Log in there…" }));
      const response = await callPy<{ ok?: boolean; error?: string; browser?: string }>("start_browser_login", id).catch(() => null);
      if (!response?.ok) {
        setBrowserBusy((prev) => { const next = new Set(prev); next.delete(id); return next; });
        const reason = response?.error === "no_browser" ? "no Chrome/Edge found" : tokenErrorText(response?.error);
        setTokenStatus((prev) => ({ ...prev, [id]: `Couldn't start: ${reason}` }));
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

  
  const markLoading = (key: string, ms = 1500) => {
    setLoading((prev) => new Set(prev).add(key));
    setTimeout(() => setLoading((prev) => { const next = new Set(prev); next.delete(key); return next; }), ms);
  };

  async function addAccount() {
    if (running) return;
    const username = accName.trim();
    const link = accLink.trim();
    if (!username) return;
    const duplicate = accounts.find((account) => account.name.trim().toLocaleLowerCase() === username.toLocaleLowerCase());
    if (duplicate) return showErrors([`Account "${duplicate.name}" has already been added.`]);
    if (!link) return showErrors(["Please provide a private server link (required)."]);
    if (!isRobloxLink(link)) return showErrors(["The private server link must be a valid roblox.com URL."]);
    const response = await callPy<{ ok?: boolean; error?: unknown; state?: BackendState }>("add_account", username, link);
    if (!response?.ok) return showErrors([tokenErrorText(response?.error)]);
    if (response.state) applyState(response.state);
    setAccName("");
    setAccLink("");
  }
  async function deleteAccount(id: number) {
    if (running) return;
    const account = accounts.find((a) => a.id === id);
    const nameLabel = account?.name ? ` "${account.name}"` : "";
    if (!(await confirmDialog(
      `Delete this account${nameLabel} and all of its settings? ` +
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
    setCollapsed((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  }

  async function submitToken(id: number) {
    if (running) return;
    const token = (tokenInputs[id] || "").trim();
    if (!token) return;
    setTokenInputs((prev) => ({ ...prev, [id]: "" }));
    setTokenStatus((prev) => ({ ...prev, [id]: "Checking token…" }));
    const response = await callPy<{ ok?: boolean; error?: unknown; state?: BackendState; security?: TokenSecurityStatus }>("set_account_token", id, token);
    if (response?.state) applyState(response.state);
    if (response?.security) setSecurity(response.security); else void refreshSecurity();
    setTokenStatus((prev) => ({ ...prev, [id]: "" }));
    if (response && !response.ok) showErrors([`Token check failed: ${tokenErrorText(response.error)}`]);
  }
  async function clearToken(id: number) {
    if (running) return;
    if (!(await confirmDialog("Remove the stored token for this account?", { title: "Remove token", confirmLabel: "Remove", danger: true }))) return;
    const response = await callPy<{ ok?: boolean; error?: unknown; state?: BackendState; security?: TokenSecurityStatus }>("clear_account_token", id);
    if (response?.state) applyState(response.state);
    if (response?.security) setSecurity(response.security); else void refreshSecurity();
    if (response && !response.ok) showErrors([tokenErrorText(response.error)]);
  }

  async function clearAllTokens() {
    if (running || !security || (!security.storedTokens && !security.fileExists)) return;
    const count = security.storedTokens;
    if (!(await confirmDialog(
      `${count ? `Delete all ${count} stored Roblox token${count === 1 ? "" : "s"}` : "Delete the damaged login-data file"} from this PC? ` +
      "SolRich will keep your account names, modules, webhooks and other settings, but automatic account launching will stop until you link the tokens again. This cannot be undone.",
      { title: "Delete all login data", confirmLabel: "Delete all tokens", danger: true },
    ))) return;
    const response = await callPy<{ ok?: boolean; error?: unknown; state?: BackendState; security?: TokenSecurityStatus }>("clear_all_account_tokens");
    if (response?.state) applyState(response.state);
    if (response?.security) setSecurity(response.security); else void refreshSecurity();
    if (!response?.ok) showErrors([tokenErrorText(response?.error)]);
  }
  async function recheckToken(id: number) {
    if (recheckCD.has(id)) return;
    setRecheckCD((prev) => new Set(prev).add(id));
    setTokenStatus((prev) => ({ ...prev, [id]: "Re-checking…" }));
    const response = await callPy<{ ok?: boolean; transient?: boolean; error?: unknown; state?: BackendState }>("revalidate_account_token", id);
    if (response?.state) applyState(response.state);
    if (response?.transient) {
      setTokenStatus((prev) => ({ ...prev, [id]: "Couldn't verify right now: Roblox is rate-limiting you. Token kept; try again in a moment." }));
      setTimeout(() => setTokenStatus((prev) => ({ ...prev, [id]: "" })), 6000);
    } else {
      setTokenStatus((prev) => ({ ...prev, [id]: "" }));
    }
    setTimeout(() => setRecheckCD((prev) => { const next = new Set(prev); next.delete(id); return next; }), 6000);
  }
  function launchOne(id: number, mode: string) {
    requireConsent(async () => {
      const account = accounts.find((a) => a.id === id);
      if (!account || !account.hasToken) return showErrors(["This account has no linked token yet."]);
      markLoading(`one-${id}-${mode}`);
      const response = await callPy<{ ok?: boolean; error?: unknown }>("launch_account", id, mode);
      if (response && !response.ok) showErrors([`Could not launch ${account.name}: ${tokenErrorText(response.error)}`]);
    });
  }
  function launchAll(mode: string) {
    requireConsent(async () => {
      const tokenAccounts = accounts.filter((a) => a.hasToken && a.enabled !== false);
      if (!tokenAccounts.length) return showErrors(["No enabled accounts have a linked token yet."]);
      markLoading(`all-${mode}`);
      const response = await callPy<{ results?: Array<{ ok?: boolean; name: string; error?: unknown }> }>("launch_all_accounts", mode);
      const failed = (response?.results || []).filter((result) => !result.ok);
      if (failed.length) showErrors(failed.map((result) => `${result.name}: ${tokenErrorText(result.error)}`));
    });
  }

  async function saveEdit(): Promise<boolean> {
    if (!edit) return true;
    if (!edit.name.trim()) return false;
    const duplicate = accounts.find((account) =>
      account.id !== edit.id && account.name.trim().toLocaleLowerCase() === edit.name.trim().toLocaleLowerCase());
    if (duplicate) {
      showErrors([`Account "${duplicate.name}" has already been added.`]);
      return false;
    }
    const response = await callPy<{ ok?: boolean; error?: unknown; state?: BackendState }>(
      "update_account", edit.id, edit.name.trim(), edit.link.trim(),
    );
    if (!response?.ok) {
      showErrors([tokenErrorText(response?.error)]);
      return false;
    }
    if (response.state) applyState(response.state);
    return true;
  }

  const withTokenCount = accounts.filter((a) => a.hasToken).length;
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
              {withTokenCount} of {accounts.length} account{accounts.length === 1 ? "" : "s"} have a linked token · {enabledCount} enabled
            </span>
          </div>
          <div className="am-launch-actions">
            <button className={`am-btn${loading.has("all-home") ? " am-loading" : ""}`} disabled={withTokenCount === 0} onClick={() => launchAll("home")}>
              <i className="fa-solid fa-house"></i> Launch all
            </button>
            <button className={`am-btn am-btn-primary${loading.has("all-private") ? " am-loading" : ""}`} disabled={withTokenCount === 0} onClick={() => launchAll("private")}>
              <i className="fa-solid fa-right-to-bracket"></i> Launch + teleport
            </button>
            <button className={`am-btn am-btn-sols${loading.has("all-public") ? " am-loading" : ""}`} disabled={withTokenCount === 0} onClick={() => launchAll("public")}>
              <i className="fa-solid fa-dice"></i> Teleport to Sols
            </button>
          </div>
        </div>

        <div className={`glass card am-security-card${security && !security.encrypted ? " warning" : ""}`}>
          <div className="am-security-icon">
            <i className={`fa-solid ${security?.encrypted ? "fa-shield-halved" : "fa-triangle-exclamation"}`}></i>
          </div>
          <div className="am-security-main">
            <div className="am-security-heading">
              <span>{security?.encrypted ? "Protected local login storage" : "Local login storage"}</span>
              {security && (
                <span className={`am-security-badge ${security.encrypted ? "ok" : "warn"}`}>
                  {security.encrypted
                    ? "Windows protected"
                    : security.encryption === "windows_dpapi"
                      ? "Needs attention"
                      : "Protection unavailable"}
                </span>
              )}
            </div>
            <p>
              {security?.encrypted
                ? "Roblox login cookies use Windows DPAPI for your current Windows user. This protects the saved file, but not an unlocked or infected PC."
                : security
                  ? security.encryption === "windows_dpapi"
                    ? "Windows encryption works, but older or unreadable login data still needs attention."
                    : "SolRich cannot confirm Windows encryption. New tokens will not be saved until secure storage works."
                  : "Checking how your local Roblox login data is protected…"}
            </p>
            {security && (security.corruptStore || security.legacyConfigTokens > 0 || security.legacyTokens > 0 || security.unreadableTokens > 0) && (
              <p className="am-security-alert">
                <i className="fa-solid fa-circle-exclamation"></i>
                {security.corruptStore
                  ? "The login-data file is damaged. SolRich will not read or overwrite it. Delete it here, then link your accounts again."
                  : security.legacyConfigTokens > 0
                  ? `${security.legacyConfigTokens} old plaintext token${security.legacyConfigTokens === 1 ? " is" : "s are"} not being used. Delete it or restart when Windows encryption works.`
                  : security.legacyTokens > 0
                  ? `${security.legacyTokens} older token${security.legacyTokens === 1 ? " needs" : "s need"} migration to Windows encryption.`
                  : `${security.unreadableTokens} stored token${security.unreadableTokens === 1 ? " is" : "s are"} unreadable.`}
              </p>
            )}
            {security && (
              <div className="am-security-meta">
                <span><i className="fa-solid fa-key"></i> {security.storedTokens} stored</span>
                <span className="am-security-path" title={security.storageFile}>
                  <i className="fa-solid fa-folder-closed"></i> {security.storageFile}
                </span>
              </div>
            )}
          </div>
          <button
            className="am-security-delete"
            disabled={running || !security || (!security.storedTokens && !security.fileExists)}
            onClick={() => void clearAllTokens()}
          >
            <i className="fa-solid fa-trash-can"></i> Delete login data
          </button>
        </div>

        <div className={`glass card am-cookie-guide${securityGuideOpen ? "" : " collapsed"}`}>
          <button
            type="button"
            className="am-cookie-guide-head"
            aria-expanded={securityGuideOpen}
            onClick={() => {
              const isOpen = !securityGuideOpen;
              setSecurityGuideOpen(isOpen);
              localStorage.setItem("robloxLoginSafetyCollapsed", isOpen ? "0" : "1");
            }}
          >
            <span className="am-cookie-guide-icon"><i className="fa-solid fa-shield-halved"></i></span>
            <div>
              <strong>Roblox login safety</strong>
              <p>Linking a login cookie is optional. Read these rules before using automatic account launching.</p>
            </div>
            <i className="fa-solid fa-chevron-down am-cookie-guide-chevron"></i>
          </button>
          <div className="am-cookie-guide-body">
            <div className="am-cookie-guide-grid">
              <div><i className="fa-solid fa-user-lock"></i><span><b>Your account and PC only</b>Never link someone else's account or use a shared Windows profile.</span></div>
              <div><i className="fa-solid fa-eye-slash"></i><span><b>Never share login data</b>Do not send the cookie or <code>tokens.dat</code> through Discord or support messages.</span></div>
              <div><i className="fa-solid fa-globe"></i><span><b>Check the browser address</b>Browser login must open <code>https://www.roblox.com/login</code>. SolRich never asks for your password.</span></div>
              <div><i className="fa-solid fa-ban"></i><span><b>Know how to revoke it</b>Remove it here. If exposure is possible, also sign out of Roblox sessions or change your password.</span></div>
            </div>
            <p className="am-cookie-guide-note"><i className="fa-solid fa-circle-info"></i> The cookie is kept outside <code>config.json</code>, protected locally, and used only with official Roblox services.</p>
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
          {accounts.map((account, i) => (
            <AccountCard
              key={account.id}
              acc={account}
              running={running}
              canUp={i > 0}
              canDown={i < accounts.length - 1}
              onMove={(dir) => void moveAccount(account.id, dir)}
              collapsed={collapsed.has(account.id)}
              tokenInput={tokenInputs[account.id] || ""}
              tokenStatus={tokenStatus[account.id] || ""}
              loading={loading}
              onToggleCollapse={() => toggleCollapse(account.id)}
              onToggleEnabled={(v) => void toggleEnabled(account.id, v)}
              onEdit={() => setEdit({ id: account.id, name: account.name, link: account.link || "" })}
              onDelete={() => void deleteAccount(account.id)}
              onTokenInput={(v) => setTokenInputs((prev) => ({ ...prev, [account.id]: v }))}
              onTokenFocus={() => requireConsent(() => {})}
              onSubmitToken={() => void submitToken(account.id)}
              onClearToken={() => void clearToken(account.id)}
              onRecheckToken={() => void recheckToken(account.id)}
              recheckBusy={recheckCD.has(account.id)}
              onBrowserLogin={() => void browserLogin(account.id)}
              browserBusy={browserBusy.has(account.id)}
              onLaunch={(mode) => launchOne(account.id, mode)}
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

function accountCardEqual(prev: AccountCardProps, next: AccountCardProps): boolean {
  if (
    prev.running !== next.running || prev.canUp !== next.canUp || prev.canDown !== next.canDown ||
    prev.collapsed !== next.collapsed || prev.tokenInput !== next.tokenInput ||
    prev.tokenStatus !== next.tokenStatus || prev.browserBusy !== next.browserBusy ||
    prev.recheckBusy !== next.recheckBusy
  ) return false;
  const prevAcc = prev.acc, nextAcc = next.acc;
  if (
    prevAcc.id !== nextAcc.id || prevAcc.name !== nextAcc.name || prevAcc.link !== nextAcc.link ||
    prevAcc.avatar !== nextAcc.avatar || prevAcc.hasToken !== nextAcc.hasToken ||
    prevAcc.tokenValid !== nextAcc.tokenValid || prevAcc.enabled !== nextAcc.enabled
  ) return false;
  for (const mode of ["home", "private", "public"]) {
    const key = `one-${prevAcc.id}-${mode}`;
    if (prev.loading.has(key) !== next.loading.has(key)) return false;
  }
  return true;
}

const AccountCard = memo(function AccountCard(props: AccountCardProps) {
  const { acc, running, collapsed, tokenInput, tokenStatus } = props;
  const [copied, setCopied] = useState(false);
  const disabled = acc.enabled === false;

  function copyLink(event: ReactMouseEvent) {
    event.stopPropagation();
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

  const launchBtn = (mode: string, extraClass: string, icon: string, label: string) => (
    <button className={`am-btn ${extraClass}${props.loading.has(`one-${acc.id}-${mode}`) ? " am-loading" : ""}`} disabled={!acc.hasToken} onClick={() => props.onLaunch(mode)}>
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
