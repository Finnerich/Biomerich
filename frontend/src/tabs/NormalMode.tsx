







import { useEffect, useMemo, useState } from "react";
import { useStore } from "../store";
import { callPy } from "../bridge";
import { alertDialog } from "../dialog";
import { CustomSelect } from "../components/CustomSelect";
import { ModuleDrawer } from "../components/ModuleDrawer";
import { BiomePingSettings } from "../components/BiomePingSettings";
import { TesseractInstallButton } from "../components/TesseractInstallButton";
import { Modal } from "../components/Modal";
import { MerchantItemSelect } from "../components/MerchantItemSelect";
import { PotionSelect } from "../components/PotionSelect";
import { Stepper } from "../components/Stepper";
import { MERCHANT_AUTOBUY_ITEMS, type AutobuyMerchant } from "../data/merchantItems";
import { PIXEL_SLOTS } from "../data/slots";
import { DEFAULT_AVATAR } from "../data/biomes";
import { getNormalAccountId, setNormalAccount } from "../data/macroMode";
import type { Account, BackendState } from "../types";
import { BindButton, useWindowBindPoll } from "../windowBind";
import {
  AntiAfkSettings,
  ApModal,
  AuraSettings,
  ClippingSettings,
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
  | "auraDetection"
  ;
type DrawerKind = ModKey | "merchant" | "aura" | "clipping" | "antiafk" | "autopop" | "fishing" | "biomelog" | "ramtrim" | "misc" | null;
type AutobuyModalState = { mid: AutobuyMerchant; title: string; items: { name: string; amount?: number; all?: boolean }[] } | null;

interface ModuleDef { key: ModKey; name: string; desc: string; icon: string; drawer: DrawerKind; lock: keyof Locks; beta?: boolean }
interface Locks { item: string | null; merchant: string | null; aura: string | null; autopop: string | null; fishing: string | null }

const MODULES: ModuleDef[] = [
  { key: "strangeController", name: "Strange Controller", desc: "Use Strange Controllers automatically to reroll your biome.", icon: "fa-gamepad", drawer: "strangeController", lock: "item" },
  { key: "biomeRandomizer", name: "Biome Randomizer", desc: "Use Biome Randomizers automatically to shuffle the biome.", icon: "fa-shuffle", drawer: "biomeRandomizer", lock: "item" },
  { key: "merchantTeleporter", name: "Merchant Detection", desc: "Teleport to merchants, read who arrived, and optionally auto-buy.", icon: "fa-store", drawer: "merchant", lock: "merchant" },
  { key: "auraDetection", name: "Aura Detection", desc: "Detect equipped auras directly from the Roblox logs.", icon: "fa-star", drawer: "aura", lock: "aura" },
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

  useWindowBindPoll();

  const [drawer, setDrawer] = useState<DrawerKind>(null);
  const [autobuyModal, setAutobuyModal] = useState<AutobuyModalState>(null);
  const [autopopModal, setAutopopModal] = useState<ApModal>(null);
  const [autopopBiomeKeys, setAutopopBiomeKeys] = useState<string[]>([]);
  const [autopopUnknownKeys, setAutopopUnknownKeys] = useState<string[]>([]);
  const [routeNames, setRouteNames] = useState<string[]>([]);

  const tutorialDrawer = useStore((state) => state.tutorialDrawer);
  const setTutorialDrawer = useStore((state) => state.setTutorialDrawer);

  const selectedId = getNormalAccountId(settings) ?? accounts[0]?.id ?? null;
  const account = accounts.find((candidate) => candidate.id === selectedId) || null;

  useEffect(() => {
    if (!tutorialDrawer) return;
    const { kind, accId } = tutorialDrawer;
    if (accId != null && accId !== selectedId && accounts.some((candidate) => candidate.id === accId)) {
      void setNormalAccount(accId);
    }
    setDrawer(kind as DrawerKind);
    
    
    setTutorialDrawer(null);
  }, [tutorialDrawer, selectedId, accounts, setTutorialDrawer]);

  useEffect(() => {
    if (getNormalAccountId(settings) == null && accounts[0]) void setNormalAccount(accounts[0].id);
  }, [settings, accounts]);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [autopopInfo, fishingPresets] = await Promise.all([
        callPy<{ biomes?: string[]; unknown?: string[] }>("get_autopop_biomes").catch(() => null),
        callPy<{ routes?: string[] }>("get_fishing_presets").catch(() => null),
      ]);
      if (!alive) return;
      if (autopopInfo?.biomes) setAutopopBiomeKeys(autopopInfo.biomes);
      if (autopopInfo?.unknown) setAutopopUnknownKeys(autopopInfo.unknown);
      if (fishingPresets?.routes) setRouteNames(fishingPresets.routes);
    })();
    return () => { alive = false; };
  }, []);

  const fishing = automation.fishing || {};
  const autopop = automation.autopop || {};
  const pixels = automation.pixels || {};
  const inventoryReady = PIXEL_SLOTS.every(([slotKey]) => isPoint(pixels[slotKey]));
  const merchGeneral = (automation.merchants?.calib || {}).general || {};
  const merchantReady = isPoint(merchGeneral.pixels?.dialogue_skip) && isRegion(merchGeneral.regions?.merchant_name);
  const autopopAmountReady = isRegion(autopop.amountRegion);
  const fishingReady = FISHING_REQUIRED_SLOTS.every((slotKey) => isPoint(fishing.pixels?.[slotKey]));
  const locks: Locks = useMemo(() => ({
    item: inventoryReady ? null : "Set the Inventory calibration first (Calibration tab).",
    merchant: !ocrAvailable ? "Needs Tesseract (not installed)." : !inventoryReady ? "Set the Inventory calibration first." : !merchantReady ? "Set the Merchant calibration first." : null,
    aura: null,
    autopop: !inventoryReady ? "Set the Inventory calibration first." : !autopopAmountReady ? "Set the Auto Pop amount region first." : null,
    fishing: fishingReady ? null : "Set the Fishing calibration first (Calibration tab).",
  }), [inventoryReady, merchantReady, autopopAmountReady, fishingReady, ocrAvailable]);

  const afkOn = !!settings.antiAfkEnabled;
  const intervals = automation.intervals || {};
  const ocrFailsafe = automation.ocrFailsafe || {};
  const notifications = automation.notifications || {};

  const autopopAccount = account ? autopop.accounts?.[String(account.id)] : undefined;
  const autopopOn = !!autopopAccount?.enabled;
  const autopopBiomeCount = Object.values((autopopAccount?.biomes || {}) as Record<string, { enabled?: boolean }>).filter((biome) => biome?.enabled).length;
  const fishingOn = !!account?.modules?.fishing;

  const loggingMet = useMemo(() => {
    const enabledAccounts = accounts.filter((candidate) => candidate.enabled !== false);
    const webhookList = (webhooks || []) as WebhookLite[];
    if (!enabledAccounts.length || !webhookList.length) return false;
    if (!webhookList.some((webhook) => (webhook.url || "").trim())) return false;
    return webhookList.some((webhook) => (webhook.active ?? true) && (webhook.routedAccounts || []).length > 0);
  }, [accounts, webhooks]);
  const loggingOn = !!settings.biomeLogging;
  const ramTrimOn = !!settings.ramTrimEnabled;
  const clippingOn = !!settings.clippingEnabled;
  const ramInterval = Math.max(1, Math.min(1440, parseInt(String(settings.ramTrimInterval), 10) || 60));
  const slowResetOn = !!settings.slowReset;
  const fakePingOn = settings.fakePingGuard !== false;

  async function toggleModule(task: ModKey) {
    if (running || !account) return;
    const isOn = !!account.modules?.[task];
    if (!isOn && locks[MODULES.find((moduleDef) => moduleDef.key === task)!.lock]) return;
    applyState(await callPy<BackendState>("set_account_module", account.id, task, !isOn));
  }
  async function toggleAutopop() {
    if (running || !account) return;
    if (!autopopOn && (locks.autopop || autopopBiomeCount === 0)) return;
    applyState(await callPy<BackendState>("set_autopop_account", account.id, !autopopOn));
  }
  async function toggleFishing() {
    if (running || !account) return;
    if (!fishingOn && locks.fishing) return;
    
    
    
    applyState(await callPy<BackendState>("set_account_module", account.id, "fishing", !fishingOn));
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
  async function toggleClipping(checked: boolean) {
    patchSettings({ clippingEnabled: checked });
    applyState(await callPy<BackendState>("set_setting", "clippingEnabled", checked));
  }
  const onNotif = async (key: string, checked: boolean) => applyState(await callPy<BackendState>("set_notification", key, checked));
  const onFailsafe = async (task: string, checked: boolean) => applyState(await callPy<BackendState>("set_ocr_failsafe", task, checked));

  return (
    <section className="tab active-tab" id="normal-mode">
      <header className="page-head">
        <h1>Macro</h1>
        <p>Pick one account and turn on what you want it to do. That's it.</p>
      </header>

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
              <span className="badge badge-soft">
                {automation.mode === "eden" ? "Eden uses this account automatically" : "runs only this account"}
              </span>
            </div>
            <div className="nm-account-row">
              <img src={account?.avatar || DEFAULT_AVATAR} className="nm-avatar" alt="" />
              <div className="nm-account-pick">
                <CustomSelect
                  value={String(selectedId ?? "")}
                  disabled={running}
                  options={accounts.map((option) => ({ value: String(option.id), label: option.name + (option.hasToken ? "" : "  (no token)") }))}
                  onChange={(value) => void setNormalAccount(Number(value))}
                />
                <span className="nm-account-hint">
                  {account?.window ? <><i className="fa-solid fa-circle-check" /> {account.window}</> : "Launch Roblox, or bind its window manually."}
                </span>
              </div>
              {account && (
                <BindButton
                  acc={account}
                  disabled={running}
                  baseClass="prio-chip prio-chip-bind nm-bind-window"
                />
              )}
            </div>
          </div>

          {}
          {ocrAvailable === false && (
            <div className="glass glass-warning card auto-note" data-reveal>
              <i className="fa-solid fa-lock"></i>
              <p><b>Tesseract not installed.</b> Merchant Detection and OCR failsafes are locked. One click installs it.</p>
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

              {MODULES.map((moduleDef) => {
                const on = !!account?.modules?.[moduleDef.key];
                const lock = !on ? locks[moduleDef.lock] : null;
                return (
                  <NmModule key={moduleDef.key} icon={moduleDef.icon} name={moduleDef.name} on={on} lock={lock} desc={moduleDef.desc} beta={moduleDef.beta}
                    onGear={() => setDrawer(moduleDef.drawer)} onToggle={() => void toggleModule(moduleDef.key)}
                    disabled={running || (!on && !!lock)} />
                );
              })}

              {}
              {(() => {
                const lock = !autopopOn ? locks.autopop : null;
                const needBiome = !autopopOn && !lock && autopopBiomeCount === 0;
                return (
                  <NmModule icon="fa-wand-magic-sparkles" name="Auto Pop" on={autopopOn} lock={lock}
                    desc={needBiome ? "Open settings and pick at least one biome first." : "Pop your chosen potions automatically when a biome starts."}
                    onGear={() => setDrawer("autopop")} onToggle={() => void toggleAutopop()}
                    disabled={running || (!autopopOn && (!!lock || needBiome))} />
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
              <NmModule icon="fa-film" name="Automatic Clipping" on={clippingOn} lock={null}
                desc="Presses your Medal hotkey after selected rare biomes or auras."
                onGear={() => setDrawer("clipping")} onToggle={() => void toggleClipping(!clippingOn)} />

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
        <ItemModuleSettings task="strangeController" running={running} ocrAvailable={ocrAvailable} ocrFailsafe={ocrFailsafe} notif={notifications} onNotif={onNotif} onFailsafe={onFailsafe} />
      </ModuleDrawer>
      <ModuleDrawer open={drawer === "biomeRandomizer"} icon="fa-shuffle" title="Biome Randomizer" sub="Item module: uses the inventory click points" onClose={() => setDrawer(null)}>
        <ItemModuleSettings task="biomeRandomizer" running={running} ocrAvailable={ocrAvailable} ocrFailsafe={ocrFailsafe} notif={notifications} onNotif={onNotif} onFailsafe={onFailsafe} />
      </ModuleDrawer>
      <ModuleDrawer open={drawer === "aura"} icon="fa-star" title="Aura Detection" wide sub="Reads equipped aura changes directly from Roblox logs" onClose={() => setDrawer(null)}>
        <AuraSettings open={drawer === "aura"} />
      </ModuleDrawer>
      <ModuleDrawer open={drawer === "clipping"} icon="fa-film" title="Automatic Clipping" wide sub="Global Medal hotkey triggers for trusted biomes and equipped auras" onClose={() => setDrawer(null)}>
        <ClippingSettings />
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
      {account && (
        <>
          <ModuleDrawer open={drawer === "merchant"} icon="fa-store" title="Merchant Detection" wide sub={`Detection + Auto Buy · ${account.name}`} onClose={() => setDrawer(null)}>
            {drawer === "merchant" && (
              <MerchantSettings
                acc={account} running={running} ocrAvailable={ocrAvailable}
                interval={Number(intervals.merchantTeleporter) || 1800}
                screenshotOn={!!notifications.merchantScreenshot}
                failsafeOn={!!ocrFailsafe.merchantTeleporter}
                autoBuyWebhookOn={!!notifications.merchantAutoBuy}
                onScreenshot={(checked) => void onNotif("merchantScreenshot", checked)}
                onFailsafe={(checked) => void onFailsafe("merchantTeleporter", checked)}
                onAutoBuyWebhook={(checked) => void onNotif("merchantAutoBuy", checked)}
                onOpenItems={(mid, title, items) => setAutobuyModal({ mid, title, items })}
              />
            )}
          </ModuleDrawer>
          <ModuleDrawer open={drawer === "autopop"} icon="fa-wand-magic-sparkles" title="Auto Pop" wide sub={`Per-account config · ${account.name}`} onClose={() => setDrawer(null)}>
            {drawer === "autopop" && (
              <AutopopSettings
                acc={account} running={running} ocrAvailable={ocrAvailable} autopop={autopop}
                biomeKeys={autopopBiomeKeys} unknownKeys={autopopUnknownKeys}
                onOpenItems={(biome, title, items) => setAutopopModal({ kind: "items", accId: account.id, biome, title, items })}
                onOpenImport={() => setAutopopModal({ kind: "import", accId: account.id, name: "", json: "" })}
                onOpenExport={(json) => setAutopopModal({ kind: "export", json })}
              />
            )}
          </ModuleDrawer>
          <ModuleDrawer open={drawer === "fishing"} icon="fa-fish" title="Fishing" sub={`Per-account settings · ${account.name}`} onClose={() => setDrawer(null)}>
            {drawer === "fishing" && (
              <FishingSettings
                acc={account} running={running} ocrAvailable={ocrAvailable}
                cfg={fishing.accounts?.[String(account.id)] || {}}
                isActive={cycleStatus.type === "fishing" && cycleStatus.accId === account.id}
                fishingStatus={fishingStatus} routeNames={routeNames} ocrFailsafe={ocrFailsafe}
                onOcrFailsafe={(task, checked) => void onFailsafe(task, checked)}
              />
            )}
          </ModuleDrawer>
        </>
      )}

      {}
      <Modal
        open={!!autobuyModal}
        title={autobuyModal?.title || ""}
        onCancel={() => setAutobuyModal(null)}
        onSave={async () => {
          if (!autobuyModal || !account) return true;
          const items = autobuyModal.items.map((item) => ({ name: (item.name || "").trim(), amount: Math.max(0, item.amount ?? 1), all: !!item.all })).filter((item) => item.name);
          applyState(await callPy<BackendState>("set_merchant_autobuy_items", account.id, autobuyModal.mid, items));
          return true;
        }}
      >
        {autobuyModal && (() => {
          const catalog = MERCHANT_AUTOBUY_ITEMS[autobuyModal.mid] || [];
          const usedNames = new Set(autobuyModal.items.map((item) => item.name).filter(Boolean));
          return (
            <div className="ap-modal">
              <p className="ap-modal-hint"><i className="fa-solid fa-circle-info"></i> Amount = how many you still want in total. Every purchase counts it down. At 0 it's done. Tick <b>Buy all</b> to always buy the whole stack.</p>
              <div className="ap-item-head"><span>Item</span><span>Amount</span><span></span></div>
              <div>
                {autobuyModal.items.map((item, i) => (
                  <div className="ap-item-row" key={i}>
                    <MerchantItemSelect className="ap-item-name" mid={autobuyModal.mid} value={item.name}
                      exclude={new Set([...usedNames].filter((n) => n !== item.name))}
                      onChange={(name) => setAutobuyModal({ ...autobuyModal, items: autobuyModal.items.map((entry, entryIndex) => (entryIndex === i ? { ...entry, name } : entry)) })} />
                    {item.all ? <span className="ap-item-amt ap-item-all-tag">All</span> : (
                      <div className="ap-item-amt"><Stepper value={item.amount ?? 1} min={0} onChange={(value) => setAutobuyModal({ ...autobuyModal, items: autobuyModal.items.map((entry, entryIndex) => (entryIndex === i ? { ...entry, amount: Math.max(0, value) } : entry)) })} /></div>
                    )}
                    <button className="ap-item-del" title="Remove" onClick={() => { const next = autobuyModal.items.filter((_, entryIndex) => entryIndex !== i); setAutobuyModal({ ...autobuyModal, items: next.length ? next : [{ name: "", amount: 1 }] }); }}><i className="fa-solid fa-trash"></i></button>
                    <div className="ap-item-all">
                      <span>Always buy all</span>
                      <label className="switch" style={{ transform: "scale(0.85)" }}>
                        <input type="checkbox" checked={!!item.all} onChange={(e) => setAutobuyModal({ ...autobuyModal, items: autobuyModal.items.map((entry, entryIndex) => (entryIndex === i ? { ...entry, all: e.target.checked } : entry)) })} />
                        <span className="slider"></span>
                      </label>
                    </div>
                  </div>
                ))}
              </div>
              <button className="btn-add ap-add-item" disabled={autobuyModal.items.length >= catalog.length} onClick={() => setAutobuyModal({ ...autobuyModal, items: [...autobuyModal.items, { name: "", amount: 1 }] })}>
                <i className="fa-solid fa-plus"></i> Add item
              </button>
            </div>
          );
        })()}
      </Modal>

      {}
      <Modal
        open={!!autopopModal}
        title={autopopModal?.kind === "items" ? autopopModal.title : autopopModal?.kind === "import" ? "Import Auto Pop Preset" : "Export Auto Pop Preset"}
        onCancel={() => setAutopopModal(null)}
        onSave={async () => {
          if (!autopopModal || !account) return true;
          if (autopopModal.kind === "items") {
            const items = autopopModal.items.map((item) => ({ name: (item.name || "").trim(), amount: Math.max(1, item.amount || 1), all: !!item.all })).filter((item) => item.name);
            applyState(await callPy<BackendState>("set_autopop_account_items", autopopModal.accId, autopopModal.biome, items));
            return true;
          }
          if (autopopModal.kind === "import") {
            if (!autopopModal.json.trim()) return false;
            const response = await callPy<{ ok?: boolean; state?: BackendState }>("import_autopop_preset", autopopModal.name.trim(), autopopModal.json.trim());
            if (response?.ok) { if (response.state) applyState(response.state); return true; }
            void alertDialog("Import failed. Make sure you pasted a valid exported preset.", { title: "Import failed" });
            return false;
          }
          return true;
        }}
      >
        {autopopModal?.kind === "items" && (
          <div className="ap-modal">
            <p className="ap-modal-hint"><i className="fa-solid fa-circle-info"></i> Items are used top-to-bottom the moment this biome starts. Tick <b>Use all</b> to always pop the whole stack.</p>
            <div className="ap-item-head"><span>Potion</span><span>Amount</span><span></span></div>
            <div>
              {autopopModal.items.map((item, i) => (
                <div className="ap-item-row" key={i}>
                  <PotionSelect className="ap-item-name" value={item.name} onChange={(name) => setAutopopModal({ ...autopopModal, items: autopopModal.items.map((entry, entryIndex) => (entryIndex === i ? { ...entry, name } : entry)) })} />
                  {item.all ? <span className="ap-item-amt ap-item-all-tag">All</span> : (
                    <div className="ap-item-amt"><Stepper value={item.amount} min={1} onChange={(value) => setAutopopModal({ ...autopopModal, items: autopopModal.items.map((entry, entryIndex) => (entryIndex === i ? { ...entry, amount: Math.max(1, value) } : entry)) })} /></div>
                  )}
                  <button className="ap-item-del" title="Remove" onClick={() => { const next = autopopModal.items.filter((_, entryIndex) => entryIndex !== i); setAutopopModal({ ...autopopModal, items: next.length ? next : [{ name: "", amount: 1 }] }); }}><i className="fa-solid fa-trash"></i></button>
                  <div className="ap-item-all">
                    <span>Always use all</span>
                    <label className="switch" style={{ transform: "scale(0.85)" }}>
                      <input type="checkbox" checked={!!item.all} onChange={(e) => setAutopopModal({ ...autopopModal, items: autopopModal.items.map((entry, entryIndex) => (entryIndex === i ? { ...entry, all: e.target.checked } : entry)) })} />
                      <span className="slider"></span>
                    </label>
                  </div>
                </div>
              ))}
            </div>
            <button className="btn-add ap-add-item" onClick={() => setAutopopModal({ ...autopopModal, items: [...autopopModal.items, { name: "", amount: 1 }] })}>
              <i className="fa-solid fa-plus"></i> Add item
            </button>
          </div>
        )}
        {autopopModal?.kind === "import" && (
          <>
            <div><div className="modal-label">Preset name (optional)</div><input className="field" placeholder="My imported preset" value={autopopModal.name} onChange={(e) => setAutopopModal({ ...autopopModal, name: e.target.value })} /></div>
            <div><div className="modal-label">Paste exported preset JSON</div><textarea className="field" rows={8} style={{ fontFamily: "monospace", fontSize: 11 }} value={autopopModal.json} onChange={(e) => setAutopopModal({ ...autopopModal, json: e.target.value })} /></div>
          </>
        )}
        {autopopModal?.kind === "export" && (
          <>
            <p className="modal-label">Copy this and share it:</p>
            <textarea className="field" rows={8} style={{ fontFamily: "monospace", fontSize: 11 }} readOnly value={autopopModal.json} />
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
  onNotif: (key: string, checked: boolean) => void;
  onFailsafe: (task: string, checked: boolean) => void;
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
        onChange={(checked) => onFailsafe(task, checked)} />
      <div className="afk-divider"></div>
      <ToggleRow name="Run notifications" desc="Sends a Discord embed each run: green when used, red when skipped."
        checked={!!notif[task]} onChange={(checked) => onNotif(task, checked)} />
    </>
  );
}
