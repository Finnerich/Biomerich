import { useEffect, useMemo, useState } from "react";
import { useStore } from "../store";
import { callPy } from "../bridge";
import { alertDialog } from "../dialog";
import { CustomSelect } from "../components/CustomSelect";
import { ModuleDrawer } from "../components/ModuleDrawer";
import { BiomePingSettings } from "../components/BiomePingSettings";
import { TesseractInstallButton } from "../components/TesseractInstallButton";
import { MacroModeToggle } from "../components/MacroModeToggle";
import { Modal } from "../components/Modal";
import { MerchantItemSelect } from "../components/MerchantItemSelect";
import { PotionSelect } from "../components/PotionSelect";
import { Stepper } from "../components/Stepper";
import { MERCHANT_AUTOBUY_ITEMS, type AutobuyMerchant } from "../data/merchantItems";
import { PIXEL_SLOTS } from "../data/slots";
import { DEFAULT_AVATAR } from "../data/biomes";
import { getNormalAccountId, setNormalAccount } from "../data/macroMode";
import type { Account, BackendState } from "../types";
import {
  AntiAfkSettings,
  ApModal,
  AutopopSettings,
  FISHING_REQUIRED_SLOTS,
  FishingSettings,
  MerchantSettings,
  MiscSettings,
  OCR_FAILSAFE_DESC,
  RamTrimSettings,
  ToggleRow,
  fmtRamInterval,
  isPoint,
  isRegion,
} from "./moduleBuilder/parts";

interface WebhookLite { url?: string; active?: boolean; routedAccounts?: unknown[] }

type ModKey =
  | "strangeController"
  | "biomeRandomizer"
  | "merchantTeleporter"
  ;
type DrawerKind = ModKey | "merchant" | "aura" | "antiafk" | "autopop" | "fishing" | "biomelog" | "ramtrim" | "misc" | null;
type AbModal = { mid: AutobuyMerchant; title: string; items: { name: string; amount?: number; all?: boolean }[] } | null;

interface ModuleDef { key: ModKey; name: string; desc: string; icon: string; drawer: DrawerKind; lock: keyof Locks; beta?: boolean }
interface Locks { item: string | null; merchant: string | null; aura: string | null; autopop: string | null; fishing: string | null }

const MODULES: ModuleDef[] = [
  { key: "strangeController", name: "Strange Controller", desc: "Use Strange Controllers automatically to reroll your biome.", icon: "fa-gamepad", drawer: "strangeController", lock: "item" },
  { key: "biomeRandomizer", name: "Biome Randomizer", desc: "Use Biome Randomizers automatically to shuffle the biome.", icon: "fa-shuffle", drawer: "biomeRandomizer", lock: "item" },
  { key: "merchantTeleporter", name: "Merchant Detection", desc: "Teleport to merchants, read who arrived, and optionally auto-buy.", icon: "fa-store", drawer: "merchant", lock: "merchant" },
];

export function NormalMode() {
  const running = useStore((s) => s.running);
  const accounts = useStore((s) => s.accounts) as Account[];
  const automation = useStore((s) => s.automation);
  const settings = useStore((s) => s.settings);
  const webhooks = useStore((s) => s.webhooks);
  const ocrAvailable = useStore((s) => s.ocrAvailable);
  const fishingStatus = useStore((s) => s.fishingStatus);
  const cycleStatus = useStore((s) => s.cycleStatus);
  const applyState = useStore((s) => s.applyState);
  const patchSettings = useStore((s) => s.patchSettings);

  const [drawer, setDrawer] = useState<DrawerKind>(null);
  const [abModal, setAbModal] = useState<AbModal>(null);
  const [apModal, setApModal] = useState<ApModal>(null);
  const [apBiomeKeys, setApBiomeKeys] = useState<string[]>([]);
  const [apUnknownKeys, setApUnknownKeys] = useState<string[]>([]);
  const [routeNames, setRouteNames] = useState<string[]>([]);

  const selectedId = getNormalAccountId(settings) ?? accounts[0]?.id ?? null;
  const acc = accounts.find((a) => a.id === selectedId) || null;

  useEffect(() => {
    if (getNormalAccountId(settings) == null && accounts[0]) void setNormalAccount(accounts[0].id);
  }, [settings, accounts]);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [ap, fp] = await Promise.all([
        callPy<{ biomes?: string[]; unknown?: string[] }>("get_autopop_biomes").catch(() => null),
        callPy<{ routes?: string[] }>("get_fishing_presets").catch(() => null),
      ]);
      if (!alive) return;
      if (ap?.biomes) setApBiomeKeys(ap.biomes);
      if (ap?.unknown) setApUnknownKeys(ap.unknown);
      if (fp?.routes) setRouteNames(fp.routes);
    })();
    return () => { alive = false; };
  }, []);

  const fishing = automation.fishing || {};
  const autopop = automation.autopop || {};
  const pixels = automation.pixels || {};
  const invReady = PIXEL_SLOTS.every(([k]) => isPoint(pixels[k]));
  const merchGeneral = (automation.merchants?.calib || {}).general || {};
  const merchReady = isPoint(merchGeneral.pixels?.dialogue_skip) && isRegion(merchGeneral.regions?.merchant_name);
  const chatCalibAll = (automation.calib || {}).chat || {};
  const auraReady = isPoint(chatCalibAll.pixels?.chat_button) && isPoint(chatCalibAll.pixels?.server_messages_button) && isRegion(chatCalibAll.regions?.chat_region);
  const apAmountReady = isRegion(autopop.amountRegion);
  const fishReady = FISHING_REQUIRED_SLOTS.every((k) => isPoint(fishing.pixels?.[k]));
  const locks: Locks = useMemo(() => ({
    item: invReady ? null : "Set the Inventory calibration first (Calibration tab).",
    merchant: !ocrAvailable ? "Needs Tesseract (not installed)." : !invReady ? "Set the Inventory calibration first." : !merchReady ? "Set the Merchant calibration first." : null,
    aura: !ocrAvailable ? "Needs Tesseract (not installed)." : !auraReady ? "Set the Chat calibration first." : null,
    autopop: !invReady ? "Set the Inventory calibration first." : !apAmountReady ? "Set the Auto Pop amount region first." : null,
    fishing: fishReady ? null : "Set the Fishing calibration first (Calibration tab).",
  }), [invReady, merchReady, auraReady, apAmountReady, fishReady, ocrAvailable]);

  const afkOn = !!settings.antiAfkEnabled;
  const intervals = automation.intervals || {};
  const ocrFailsafe = automation.ocrFailsafe || {};
  const notif = automation.notifications || {};

  const apAcc = acc ? autopop.accounts?.[String(acc.id)] : undefined;
  const apOn = !!apAcc?.enabled;
  const apBiomeCount = Object.values((apAcc?.biomes || {}) as Record<string, { enabled?: boolean }>).filter((b) => b?.enabled).length;
  const fishingOn = !!acc?.modules?.fishing;

  const loggingMet = useMemo(() => {
    const enabled = accounts.filter((a) => a.enabled !== false);
    const whs = (webhooks || []) as WebhookLite[];
    if (!enabled.length || !whs.length) return false;
    if (!whs.some((w) => (w.url || "").trim())) return false;
    return whs.some((w) => (w.active ?? true) && (w.routedAccounts || []).length > 0);
  }, [accounts, webhooks]);
  const loggingOn = !!settings.biomeLogging;
  const ramTrimOn = !!settings.ramTrimEnabled;
  const ramInterval = Math.max(1, Math.min(1440, parseInt(String(settings.ramTrimInterval), 10) || 60));
  const slowResetOn = !!settings.slowReset;
  const fakePingOn = settings.fakePingGuard !== false;

  async function toggleModule(task: ModKey) {
    if (running || !acc) return;
    const cur = !!acc.modules?.[task];
    if (!cur && locks[MODULES.find((m) => m.key === task)!.lock]) return;
    applyState(await callPy<BackendState>("set_account_module", acc.id, task, !cur));
  }
  async function toggleAutopop() {
    if (running || !acc) return;
    if (!apOn && (locks.autopop || apBiomeCount === 0)) return;
    applyState(await callPy<BackendState>("set_autopop_account", acc.id, !apOn));
  }
  async function toggleFishing() {
    if (running || !acc) return;
    if (!fishingOn && locks.fishing) return;
    
    
    
    applyState(await callPy<BackendState>("set_account_module", acc.id, "fishing", !fishingOn));
  }
  async function toggleAfk(checked: boolean) {
    if (running) return;
    patchSettings({ antiAfkEnabled: checked });
    applyState(await callPy<BackendState>("set_setting", "antiAfkEnabled", checked));
  }
  async function toggleRamTrim(checked: boolean) {
    patchSettings({ ramTrimEnabled: checked });
    applyState(await callPy<BackendState>("set_setting", "ramTrimEnabled", checked));
  }
  const onNotif = async (key: string, c: boolean) => applyState(await callPy<BackendState>("set_notification", key, c));
  const onFailsafe = async (task: string, c: boolean) => applyState(await callPy<BackendState>("set_ocr_failsafe", task, c));

  return (
    <section className="tab active-tab" id="normal-mode">
      <header className="page-head">
        <h1>Macro</h1>
        <p>Pick one account and turn on what you want it to do. That's it.</p>
      </header>

      <MacroModeToggle />

      {accounts.length === 0 ? (
        <div className="glass card panel" data-reveal>
          <div className="empty-state show">
            <i className="fa-solid fa-user-plus"></i>
            <p>No accounts yet. Add one in the <b>Accounts</b> tab, then come back here.</p>
          </div>
        </div>
      ) : (
        <>
          {}
          <div className="glass card panel nm-account" data-reveal>
            <div className="panel-head">
              <div className="panel-title"><i className="fa-solid fa-user"></i> Account</div>
              <span className="badge badge-soft">runs only this account</span>
            </div>
            <div className="nm-account-row">
              <img src={acc?.avatar || DEFAULT_AVATAR} className="nm-avatar" alt="" />
              <div className="nm-account-pick">
                <CustomSelect
                  value={String(selectedId ?? "")}
                  disabled={running}
                  options={accounts.map((a) => ({ value: String(a.id), label: a.name + (a.hasToken ? "" : "  (no token)") }))}
                  onChange={(v) => void setNormalAccount(Number(v))}
                />
                <span className="nm-account-hint">
                  {acc?.window ? <><i className="fa-solid fa-circle-check" /> Window bound</> : "Launch this account from the Accounts tab, then press Start."}
                </span>
              </div>
            </div>
          </div>

          {}
          {ocrAvailable === false && (
            <div className="glass glass-warning card auto-note" data-reveal>
              <i className="fa-solid fa-lock"></i>
              <p><b>Tesseract not installed.</b> Merchant &amp; Aura Detection are locked. One click installs it.</p>
              <TesseractInstallButton />
            </div>
          )}

          {}
          <div className="glass card panel" data-reveal>
            <div className="panel-head">
              <div className="panel-title"><i className="fa-solid fa-toggle-on"></i> What should it do?</div>
            </div>
            <div className="nm-modules">
              <NmModule icon="fa-satellite-dish" name="Biome Logging" on={loggingOn} alwaysOn
                lock={!loggingMet ? "Always on. Add an active webhook and route it to an account (Webhooks tab)." : null}
                desc="Always on. Posts a Discord embed for each biome."
                onGear={() => setDrawer("biomelog")} />

              {MODULES.map((m) => {
                const on = !!acc?.modules?.[m.key];
                const lock = !on ? locks[m.lock] : null;
                return (
                  <NmModule key={m.key} icon={m.icon} name={m.name} on={on} lock={lock} desc={m.desc} beta={m.beta}
                    onGear={() => setDrawer(m.drawer)} onToggle={() => void toggleModule(m.key)}
                    disabled={running || (!on && !!lock)} />
                );
              })}

              {}
              {(() => {
                const lock = !apOn ? locks.autopop : null;
                const needBiome = !apOn && !lock && apBiomeCount === 0;
                return (
                  <NmModule icon="fa-wand-magic-sparkles" name="Auto Pop" on={apOn} lock={lock}
                    desc={needBiome ? "Open settings and pick at least one biome first." : "Pop your chosen potions automatically when a biome starts."}
                    onGear={() => setDrawer("autopop")} onToggle={() => void toggleAutopop()}
                    disabled={running || (!apOn && (!!lock || needBiome))} />
                );
              })()}

              {}
              <NmModule icon="fa-fish" name="Fishing" on={fishingOn} lock={locks.fishing}
                desc="Fish on this account non-stop (auto-cast, reel, and optional auto-sell)."
                onGear={() => setDrawer("fishing")} onToggle={() => void toggleFishing()}
                disabled={running || (!fishingOn && !!locks.fishing)} />
            </div>
          </div>

          {}
          <div className="glass card panel" data-reveal>
            <div className="panel-head"><div className="panel-title"><i className="fa-solid fa-shield-halved"></i> Extras</div></div>
            <div className="nm-modules">
              <NmModule icon="fa-person-running" name="Anti-AFK" on={afkOn} lock={null}
                desc="Keeps the Roblox window awake so it never kicks you."
                onGear={() => setDrawer("antiafk")} onToggle={() => void toggleAfk(!afkOn)} disabled={running} />

              <NmModule icon="fa-memory" name="Auto-Trim RAM" on={ramTrimOn} lock={null}
                desc={`Frees system memory on a timer (${fmtRamInterval(ramInterval)}). Set the interval with the gear.`}
                onGear={() => setDrawer("ramtrim")} onToggle={() => void toggleRamTrim(!ramTrimOn)} disabled={false} />

              <NmModule icon="fa-sliders" name="Misc" beta={false}
                desc={[
                  slowResetOn && "Slow UI",
                  fakePingOn && "Anti Fake Ping",
                ].filter(Boolean).join(" · ") || "Global failsafes. Open to configure."}
                onGear={() => setDrawer("misc")} />
            </div>
          </div>

          <div className="nm-advanced-note">
            <i className="fa-solid fa-circle-info"></i>
            <span>Want fishing rotations across accounts, or several accounts at once? Switch to <b>Multi-Macro</b> mode up top.</span>
          </div>
        </>
      )}

      {}
      <ModuleDrawer open={drawer === "strangeController"} icon="fa-gamepad" title="Strange Controller" sub="Item module: uses the inventory click points" onClose={() => setDrawer(null)}>
        <ItemModuleSettings task="strangeController" running={running} ocrAvailable={ocrAvailable} ocrFailsafe={ocrFailsafe} notif={notif} onNotif={onNotif} onFailsafe={onFailsafe} />
      </ModuleDrawer>
      <ModuleDrawer open={drawer === "biomeRandomizer"} icon="fa-shuffle" title="Biome Randomizer" sub="Item module: uses the inventory click points" onClose={() => setDrawer(null)}>
        <ItemModuleSettings task="biomeRandomizer" running={running} ocrAvailable={ocrAvailable} ocrFailsafe={ocrFailsafe} notif={notif} onNotif={onNotif} onFailsafe={onFailsafe} />
      </ModuleDrawer>
      <ModuleDrawer open={drawer === "antiafk"} icon="fa-person-running" title="Anti-AFK" sub="Keeps the Roblox window awake" onClose={() => setDrawer(null)}>
        <AntiAfkSettings />
      </ModuleDrawer>
      <ModuleDrawer open={drawer === "biomelog"} icon="fa-satellite-dish" title="Biome Logging" wide sub="Per-biome Discord pings" onClose={() => setDrawer(null)}>
        <BiomePingSettings />
      </ModuleDrawer>
      <ModuleDrawer open={drawer === "ramtrim"} icon="fa-memory" title="Auto-Trim RAM" sub="Frees system memory on a timer" onClose={() => setDrawer(null)}>
        <RamTrimSettings />
      </ModuleDrawer>
      <ModuleDrawer open={drawer === "misc"} icon="fa-sliders" title="Misc" sub="Global failsafes" onClose={() => setDrawer(null)}>
        <MiscSettings />
      </ModuleDrawer>
      {acc && (
        <>
          <ModuleDrawer open={drawer === "merchant"} icon="fa-store" title="Merchant Detection" wide sub={`Detection + Auto Buy · ${acc.name}`} onClose={() => setDrawer(null)}>
            {drawer === "merchant" && (
              <MerchantSettings
                acc={acc} running={running} ocrAvailable={ocrAvailable}
                interval={Number(intervals.merchantTeleporter) || 1800}
                screenshotOn={!!notif.merchantScreenshot}
                failsafeOn={!!ocrFailsafe.merchantTeleporter}
                autoBuyWebhookOn={!!notif.merchantAutoBuy}
                onScreenshot={(c) => void onNotif("merchantScreenshot", c)}
                onFailsafe={(c) => void onFailsafe("merchantTeleporter", c)}
                onAutoBuyWebhook={(c) => void onNotif("merchantAutoBuy", c)}
                onOpenItems={(mid, title, items) => setAbModal({ mid, title, items })}
              />
            )}
          </ModuleDrawer>
          <ModuleDrawer open={drawer === "autopop"} icon="fa-wand-magic-sparkles" title="Auto Pop" wide sub={`Per-account config · ${acc.name}`} onClose={() => setDrawer(null)}>
            {drawer === "autopop" && (
              <AutopopSettings
                acc={acc} running={running} ocrAvailable={ocrAvailable} autopop={autopop}
                biomeKeys={apBiomeKeys} unknownKeys={apUnknownKeys}
                onOpenItems={(biome, title, items) => setApModal({ kind: "items", accId: acc.id, biome, title, items })}
                onOpenImport={() => setApModal({ kind: "import", accId: acc.id, name: "", json: "" })}
                onOpenExport={(json) => setApModal({ kind: "export", json })}
              />
            )}
          </ModuleDrawer>
          <ModuleDrawer open={drawer === "fishing"} icon="fa-fish" title="Fishing" sub={`Per-account settings · ${acc.name}`} onClose={() => setDrawer(null)}>
            {drawer === "fishing" && (
              <FishingSettings
                acc={acc} running={running} ocrAvailable={ocrAvailable}
                cfg={fishing.accounts?.[String(acc.id)] || {}}
                isActive={cycleStatus.type === "fishing" && cycleStatus.accId === acc.id}
                fishingStatus={fishingStatus} routeNames={routeNames} ocrFailsafe={ocrFailsafe}
                onOcrFailsafe={(task, c) => void onFailsafe(task, c)}
              />
            )}
          </ModuleDrawer>
        </>
      )}

      {}
      <Modal
        open={!!abModal}
        title={abModal?.title || ""}
        onCancel={() => setAbModal(null)}
        onSave={async () => {
          if (!abModal || !acc) return true;
          const items = abModal.items.map((i) => ({ name: (i.name || "").trim(), amount: Math.max(0, i.amount ?? 1), all: !!i.all })).filter((i) => i.name);
          applyState(await callPy<BackendState>("set_merchant_autobuy_items", acc.id, abModal.mid, items));
          return true;
        }}
      >
        {abModal && (() => {
          const catalog = MERCHANT_AUTOBUY_ITEMS[abModal.mid] || [];
          const used = new Set(abModal.items.map((i) => i.name).filter(Boolean));
          return (
            <div className="ap-modal">
              <p className="ap-modal-hint"><i className="fa-solid fa-circle-info"></i> Amount = how many you still want in total. Every purchase counts it down. At 0 it's done. Tick <b>Buy all</b> to always buy the whole stack.</p>
              <div className="ap-item-head"><span>Item</span><span>Amount</span><span></span></div>
              <div>
                {abModal.items.map((it, i) => (
                  <div className="ap-item-row" key={i}>
                    <MerchantItemSelect className="ap-item-name" mid={abModal.mid} value={it.name}
                      exclude={new Set([...used].filter((n) => n !== it.name))}
                      onChange={(name) => setAbModal({ ...abModal, items: abModal.items.map((x, j) => (j === i ? { ...x, name } : x)) })} />
                    {it.all ? <span className="ap-item-amt ap-item-all-tag">All</span> : (
                      <div className="ap-item-amt"><Stepper value={it.amount ?? 1} min={0} onChange={(v) => setAbModal({ ...abModal, items: abModal.items.map((x, j) => (j === i ? { ...x, amount: Math.max(0, v) } : x)) })} /></div>
                    )}
                    <button className="ap-item-del" title="Remove" onClick={() => { const next = abModal.items.filter((_, j) => j !== i); setAbModal({ ...abModal, items: next.length ? next : [{ name: "", amount: 1 }] }); }}><i className="fa-solid fa-trash"></i></button>
                    <div className="ap-item-all">
                      <span>Always buy all</span>
                      <label className="switch" style={{ transform: "scale(0.85)" }}>
                        <input type="checkbox" checked={!!it.all} onChange={(e) => setAbModal({ ...abModal, items: abModal.items.map((x, j) => (j === i ? { ...x, all: e.target.checked } : x)) })} />
                        <span className="slider"></span>
                      </label>
                    </div>
                  </div>
                ))}
              </div>
              <button className="btn-add ap-add-item" disabled={abModal.items.length >= catalog.length} onClick={() => setAbModal({ ...abModal, items: [...abModal.items, { name: "", amount: 1 }] })}>
                <i className="fa-solid fa-plus"></i> Add item
              </button>
            </div>
          );
        })()}
      </Modal>

      {}
      <Modal
        open={!!apModal}
        title={apModal?.kind === "items" ? apModal.title : apModal?.kind === "import" ? "Import Auto Pop Preset" : "Export Auto Pop Preset"}
        onCancel={() => setApModal(null)}
        onSave={async () => {
          if (!apModal || !acc) return true;
          if (apModal.kind === "items") {
            const items = apModal.items.map((i) => ({ name: (i.name || "").trim(), amount: Math.max(1, i.amount || 1), all: !!i.all })).filter((i) => i.name);
            applyState(await callPy<BackendState>("set_autopop_account_items", apModal.accId, apModal.biome, items));
            return true;
          }
          if (apModal.kind === "import") {
            if (!apModal.json.trim()) return false;
            const r = await callPy<{ ok?: boolean; state?: BackendState }>("import_autopop_preset", apModal.name.trim(), apModal.json.trim());
            if (r?.ok) { if (r.state) applyState(r.state); return true; }
            void alertDialog("Import failed. Make sure you pasted a valid exported preset.", { title: "Import failed" });
            return false;
          }
          return true;
        }}
      >
        {apModal?.kind === "items" && (
          <div className="ap-modal">
            <p className="ap-modal-hint"><i className="fa-solid fa-circle-info"></i> Items are used top-to-bottom the moment this biome starts. Tick <b>Use all</b> to always pop the whole stack.</p>
            <div className="ap-item-head"><span>Potion</span><span>Amount</span><span></span></div>
            <div>
              {apModal.items.map((it, i) => (
                <div className="ap-item-row" key={i}>
                  <PotionSelect className="ap-item-name" value={it.name} onChange={(name) => setApModal({ ...apModal, items: apModal.items.map((x, j) => (j === i ? { ...x, name } : x)) })} />
                  {it.all ? <span className="ap-item-amt ap-item-all-tag">All</span> : (
                    <div className="ap-item-amt"><Stepper value={it.amount} min={1} onChange={(v) => setApModal({ ...apModal, items: apModal.items.map((x, j) => (j === i ? { ...x, amount: Math.max(1, v) } : x)) })} /></div>
                  )}
                  <button className="ap-item-del" title="Remove" onClick={() => { const next = apModal.items.filter((_, j) => j !== i); setApModal({ ...apModal, items: next.length ? next : [{ name: "", amount: 1 }] }); }}><i className="fa-solid fa-trash"></i></button>
                  <div className="ap-item-all">
                    <span>Always use all</span>
                    <label className="switch" style={{ transform: "scale(0.85)" }}>
                      <input type="checkbox" checked={!!it.all} onChange={(e) => setApModal({ ...apModal, items: apModal.items.map((x, j) => (j === i ? { ...x, all: e.target.checked } : x)) })} />
                      <span className="slider"></span>
                    </label>
                  </div>
                </div>
              ))}
            </div>
            <button className="btn-add ap-add-item" onClick={() => setApModal({ ...apModal, items: [...apModal.items, { name: "", amount: 1 }] })}>
              <i className="fa-solid fa-plus"></i> Add item
            </button>
          </div>
        )}
        {apModal?.kind === "import" && (
          <>
            <div><div className="modal-label">Preset name (optional)</div><input className="field" placeholder="My imported preset" value={apModal.name} onChange={(e) => setApModal({ ...apModal, name: e.target.value })} /></div>
            <div><div className="modal-label">Paste exported preset JSON</div><textarea className="field" rows={8} style={{ fontFamily: "monospace", fontSize: 11 }} value={apModal.json} onChange={(e) => setApModal({ ...apModal, json: e.target.value })} /></div>
          </>
        )}
        {apModal?.kind === "export" && (
          <>
            <p className="modal-label">Copy this and share it:</p>
            <textarea className="field" rows={8} style={{ fontFamily: "monospace", fontSize: 11 }} readOnly value={apModal.json} />
          </>
        )}
      </Modal>
    </section>
  );
}

function NmModule(props: {
  icon: string; name: string; desc: string; lock?: string | null; on?: boolean;
  beta?: boolean; alwaysOn?: boolean; disabled?: boolean; onGear: () => void; onToggle?: () => void;
}) {
  const { icon, name, desc, on = false, lock = null, beta = false, disabled = false, onGear, onToggle } = props;
  return (
    <div className={`nm-module${on ? " on" : ""}${lock ? " locked" : ""}`}>
      <div className="nm-module-ico"><i className={`fa-solid ${icon}`}></i></div>
      <div className="nm-module-meta">
        <span className="nm-module-name">
          {name}
          {beta && <span className="beta-badge">BETA</span>}
          {lock && <span className="nm-lock" title={lock}><i className="fa-solid fa-lock"></i></span>}
        </span>
        <span className="nm-module-desc">{lock || desc}</span>
      </div>
      <div className="nm-module-actions">
        <button className="mb-chip-gear" title={`${name} settings`} onClick={onGear}><i className="fa-solid fa-gear"></i></button>
        {onToggle && (
          <label className="switch">
            <input type="checkbox" checked={on} disabled={disabled} onChange={onToggle} />
            <span className="slider"></span>
          </label>
        )}
      </div>
    </div>
  );
}

function ItemModuleSettings(props: {
  task: "strangeController" | "biomeRandomizer";
  running: boolean;
  ocrAvailable: boolean | null;
  ocrFailsafe: Record<string, unknown>;
  notif: Record<string, unknown>;
  onNotif: (key: string, c: boolean) => void;
  onFailsafe: (task: string, c: boolean) => void;
}) {
  const { task, running, ocrAvailable, ocrFailsafe, notif, onNotif, onFailsafe } = props;
  return (
    <>
      <div className="mb-scope-note">
        <i className="fa-solid fa-circle-info"></i>
        <span>These settings are <b>global</b>: they apply whenever this module runs.</span>
      </div>
      <ToggleRow name="OCR Item Failsafe" desc={OCR_FAILSAFE_DESC[task]}
        checked={!!ocrFailsafe[task]} disabled={running || (!ocrAvailable && !ocrFailsafe[task])} locked={!ocrAvailable}
        onChange={(c) => onFailsafe(task, c)} />
      <div className="afk-divider"></div>
      <ToggleRow name="Run notifications" desc="Sends a Discord embed each run: green when used, red when skipped."
        checked={!!notif[task]} onChange={(c) => onNotif(task, c)} />
    </>
  );
}
