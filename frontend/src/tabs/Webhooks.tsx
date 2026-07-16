






import { useState } from "react";
import { useStore } from "../store";
import { callPy } from "../bridge";
import { maskWebhook } from "../utils";
import { DEFAULT_AVATAR } from "../data/biomes";
import { Modal } from "../components/Modal";
import type { Account, BackendState } from "../types";



interface Webhook {
  id: number;
  name: string;
  url?: string;
  active?: boolean;
  routedAccounts?: number[];
}

const NOTIFS = [
  { key: "strangeController", name: "Strange Controller", desc: "Sends an embed each time the Strange Controller runs: green when used, red when the item failsafe skipped it." },
  { key: "biomeRandomizer", name: "Biome Randomizer", desc: "Sends an embed each time the Biome Randomizer runs: green when used, red when skipped." },
];



type EditState = { id: number; name: string; url: string } | null;

export function Webhooks() {
  const running = useStore((s) => s.running);
  const accounts = useStore((s) => s.accounts) as Account[];
  const webhooks = useStore((s) => s.webhooks) as Webhook[];
  const automation = useStore((s) => s.automation);
  const applyState = useStore((s) => s.applyState);
  const patchWebhook = useStore((s) => s.patchWebhook);
  const patchAutomation = useStore((s) => s.patchAutomation);

  const [webhookName, setWebhookName] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [edit, setEdit] = useState<EditState>(null);

  const notifications = (automation.notifications as Record<string, boolean>) || {};
  const autopop = (automation.autopop as Record<string, unknown>) || {};
  const fishingWebhook = !!(automation.fishing as { webhookEnabled?: boolean } | undefined)?.webhookEnabled;

  async function addWebhook() {
    if (running) return;
    const name = webhookName.trim();
    const url = webhookUrl.trim();
    if (!name || !url) return;
    applyState(await callPy<BackendState>("add_webhook", name, url));
    setWebhookName("");
    setWebhookUrl("");
  }
  async function deleteWebhook(id: number) {
    if (running) return;
    applyState(await callPy<BackendState>("delete_webhook", id));
  }
  async function toggleWebhookState(id: number) {
    if (running) return;
    const webhook = webhooks.find((w) => w.id === id);
    if (!webhook) return;
    const nextActive = !webhook.active;
    patchWebhook(id, { active: nextActive });
    await callPy("set_webhook_active", id, nextActive);
  }
  async function toggleRouting(webhookId: number, accountId: number, enabled: boolean) {
    if (running) return;
    const webhook = webhooks.find((w) => w.id === webhookId);
    if (!webhook) return;
    const currentRouted = webhook.routedAccounts || [];
    const nextRouted = enabled ? [...new Set([...currentRouted, accountId])] : currentRouted.filter((routedId) => routedId !== accountId);
    patchWebhook(webhookId, { routedAccounts: nextRouted });
    await callPy("set_routing", webhookId, accountId, enabled);
  }

  async function onNotifToggle(key: string, checked: boolean) {
    patchAutomation({ notifications: { ...notifications, [key]: checked } });
    applyState(await callPy<BackendState>("set_notification", key, checked));
  }
  async function onAutopopOption(key: string, checked: boolean) {
    applyState(await callPy<BackendState>("set_autopop_option", key, checked));
  }

  async function saveEdit(): Promise<boolean> {
    if (!edit) return true;
    if (!edit.name.trim() || !edit.url.trim()) return false;
    applyState(await callPy<BackendState>("update_webhook", edit.id, edit.name.trim(), edit.url.trim()));
    return true;
  }

  return (
    <section className="tab active-tab" id="webhooks">
      <header className="page-head">
        <h1>Webhooks &amp; Notifications</h1>
        <p>Add Discord webhooks, route them to accounts, and pick which events send embeds.</p>
      </header>

      {}
      <div className="tab-section" data-reveal>
        <div className="tab-section-head">
          <i className="fa-solid fa-tower-broadcast"></i>
          <h2>Webhooks</h2>
        </div>
        <div className="glass card input-bar">
          <input type="text" className="field" placeholder="Server Name" value={webhookName} disabled={running} onChange={(e) => setWebhookName(e.target.value)} />
          <input type="text" className="field" placeholder="Webhook URL" value={webhookUrl} disabled={running} onChange={(e) => setWebhookUrl(e.target.value)} />
          <button className="btn-add" disabled={running} onClick={() => void addWebhook()}>
            <i className="fa-solid fa-plus"></i> Add
          </button>
        </div>
        <div className="wh-list" style={{ marginTop: 12 }}>
          {webhooks.map((webhook) => (
            <WebhookCard
              key={webhook.id}
              wh={webhook}
              accounts={accounts}
              onEdit={() => setEdit({ id: webhook.id, name: webhook.name, url: webhook.url || "" })}
              onDelete={() => void deleteWebhook(webhook.id)}
              onToggleActive={() => void toggleWebhookState(webhook.id)}
              onToggleRouting={(accId, enabled) => void toggleRouting(webhook.id, accId, enabled)}
            />
          ))}
        </div>
        {webhooks.length === 0 && (
          <div className="empty-state show">
            <i className="fa-solid fa-tower-broadcast"></i>
            <p>No webhooks yet.</p>
          </div>
        )}
      </div>

      {}
      <div className="tab-section" data-reveal>
        <div className="tab-section-head">
          <i className="fa-solid fa-bell"></i>
          <h2>Notifications</h2>
        </div>
        <p className="section-hint">
          Pick which events send a Discord embed to your active webhooks above. <b>Merchant Detection</b> always
          sends its embed when a merchant is found. Only the screenshot attachment is optional (in its module settings).
        </p>

        <div className="glass card panel">
          <div className="panel-head">
            <div className="panel-title"><i className="fa-solid fa-cubes"></i> Module Runs</div>
          </div>
          {NOTIFS.map((option, index) => (
            <div key={option.key}>
              {index > 0 && <div className="afk-divider"></div>}
              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-name">{option.name}</span>
                  <span className="setting-desc">{option.desc}</span>
                </div>
                <label className="switch">
                  <input type="checkbox" checked={!!notifications[option.key]} onChange={(e) => void onNotifToggle(option.key, e.target.checked)} />
                  <span className="slider"></span>
                </label>
              </div>
            </div>
          ))}
        </div>

        <div className="glass card panel">
          <div className="panel-head">
            <div className="panel-title"><i className="fa-solid fa-fish"></i> Fishing</div>
          </div>
          <div className="setting-row">
            <div className="setting-info">
              <span className="setting-name">Fishing Webhook</span>
              <span className="setting-desc">Send a Discord embed on every catch result: green for Fish Caught, red for Fishing Failed. Results are only distinguished when the Fishing Failed failsafe is calibrated.</span>
            </div>
            <label className="switch">
              <input
                type="checkbox"
                checked={fishingWebhook}
                onChange={async (e) => applyState(await callPy<BackendState>("set_fishing_webhook", e.target.checked))}
              />
              <span className="slider"></span>
            </label>
          </div>
        </div>

        <div className="glass card panel">
          <div className="panel-head">
            <div className="panel-title"><i className="fa-solid fa-shield-halved"></i> Failsafes</div>
          </div>
          <div className="setting-row">
            <div className="setting-info">
              <span className="setting-name">Failsafe Results</span>
              <span className="setting-desc">Sends an embed when a failsafe passes or triggers (wrong item, merchant item not confirmed, Sell Fish Shop check). Green for passed, red for triggered.</span>
            </div>
            <label className="switch">
              <input type="checkbox" checked={!!notifications.failsafes} onChange={(e) => void onNotifToggle("failsafes", e.target.checked)} />
              <span className="slider"></span>
            </label>
          </div>
        </div>

        <div className="glass card panel">
          <div className="panel-head">
            <div className="panel-title"><i className="fa-solid fa-wand-magic-sparkles"></i> Auto Pop</div>
          </div>
          <div className="setting-row">
            <div className="setting-info">
              <span className="setting-name">Auto Pop used</span>
              <span className="setting-desc">Sends a Discord embed each time Auto Pop fires, listing which items were used and how many.</span>
            </div>
            <label className="switch">
              <input type="checkbox" checked={!!autopop.notifyUse} onChange={(e) => void onAutopopOption("notifyUse", e.target.checked)} />
              <span className="slider"></span>
            </label>
          </div>
          <div className="afk-divider"></div>
          <div className="setting-row">
            <div className="setting-info">
              <span className="setting-name">Auto Pop failsafe failed</span>
              <span className="setting-desc">Sends a red embed when an item couldn't be found or was out of stock, naming the missing item(s).</span>
            </div>
            <label className="switch">
              <input type="checkbox" checked={!!autopop.notifyFail} onChange={(e) => void onAutopopOption("notifyFail", e.target.checked)} />
              <span className="slider"></span>
            </label>
          </div>
        </div>
      </div>

      <Modal open={!!edit} title="Edit Webhook" onCancel={() => setEdit(null)} onSave={saveEdit}>
        {edit && (
          <>
            <div>
              <div className="modal-label">Label</div>
              <input className="field" value={edit.name} placeholder="Label" onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
            </div>
            <div>
              <div className="modal-label">Webhook URL</div>
              <input className="field" value={edit.url} placeholder="Webhook URL" onChange={(e) => setEdit({ ...edit, url: e.target.value })} />
            </div>
          </>
        )}
      </Modal>
    </section>
  );
}



function WebhookCard(props: {
  wh: Webhook;
  accounts: Account[];
  onEdit: () => void;
  onDelete: () => void;
  onToggleActive: () => void;
  onToggleRouting: (accId: number, enabled: boolean) => void;
}) {
  const { wh, accounts } = props;
  const routedCount = (wh.routedAccounts || []).length;

  return (
    <div className={`wh-card${wh.active ? "" : " wh-inactive"}`} data-wh-id={wh.id}>
      <div className="wh-header">
        <div className="wh-header-left">
          <div className="wh-icon"><i className="fa-brands fa-discord"></i></div>
          <div className="wh-meta">
            <span className="wh-name">{wh.name}</span>
            <span className="wh-url">{maskWebhook(wh.url)}</span>
          </div>
        </div>
        <div className="wh-header-right">
          <span className={`wh-active-badge ${wh.active ? "on" : "off"}`}>{wh.active ? "Active" : "Paused"}</span>
          <label className="switch wh-toggle">
            <input type="checkbox" className="wh-toggle-cb" checked={!!wh.active} onChange={props.onToggleActive} />
            <span className="slider"></span>
          </label>
          <button className="am-mini" onClick={props.onEdit}><i className="fa-solid fa-pen"></i></button>
          <button className="am-mini danger" onClick={props.onDelete}><i className="fa-solid fa-trash"></i></button>
        </div>
      </div>
      <div className="wh-body">
        <div className="wh-route-head">
          <span className="wh-route-label"><i className="fa-solid fa-route"></i> Route to accounts</span>
          <span className={`wh-routed-badge ${routedCount ? "has" : "none"}`}>
            {routedCount ? `${routedCount} account${routedCount === 1 ? "" : "s"}` : "No accounts"}
          </span>
        </div>
        <div className="wh-route-list">
          {accounts.length === 0 ? (
            <span className="wh-no-acc"><i className="fa-solid fa-user-plus"></i> No accounts yet</span>
          ) : (
            accounts.map((account) => {
              const disabled = account.enabled === false;
              return (
                <label className={`wh-route-acc${disabled ? " acc-disabled" : ""}`} key={account.id}>
                  <input
                    type="checkbox"
                    className="wh-route-cb"
                    checked={(wh.routedAccounts || []).includes(account.id)}
                    onChange={(e) => props.onToggleRouting(account.id, e.target.checked)}
                  />
                  <span className="wh-route-check"><i className="fa-solid fa-check"></i></span>
                  <img src={account.avatar || DEFAULT_AVATAR} className="wh-route-avatar" alt="" />
                  <span className="wh-route-name">{account.name}</span>
                  {disabled && <span className="acc-disabled-tag">disabled</span>}
                </label>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
