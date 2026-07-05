import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useStore } from "../store";
import { callPy } from "../bridge";
import { alertDialog } from "../dialog";
import { BIOMES } from "../data/biomes";
import { MERCHANT_AUTOBUY_ITEMS } from "../data/merchantItems";
import { PIXEL_SLOTS } from "../data/slots";
import { MerchantItemSelect } from "../components/MerchantItemSelect";
import { PotionSelect } from "../components/PotionSelect";
import { Modal } from "../components/Modal";
import { ModuleDrawer } from "../components/ModuleDrawer";
import { BiomePingSettings } from "../components/BiomePingSettings";
import { Stepper } from "../components/Stepper";
import { TesseractInstallButton } from "../components/TesseractInstallButton";
import { useWindowBindPoll } from "../windowBind";
import { MacroModeToggle } from "../components/MacroModeToggle";
import { getMacroMode } from "../data/macroMode";
import { NormalMode } from "./NormalMode";
import type { Account, BackendState, CycleStep } from "../types";

import {
  AbModal,
  AccountRow,
  AntiAfkSettings,
  ApModal,
  AutopopSettings,
  DrawerState,
  EdenModePanel,
  FISHING_REQUIRED_SLOTS,
  FishingSettings,
  ITEM_TASKS,
  MerchantSettings,
  MiscSettings,
  ModuleLocks,
  OCR_FAILSAFE_DESC,
  RamTrimSettings,
  ToggleRow,
  fmtRamInterval,
  isPoint,
  isRegion,
} from "./moduleBuilder/parts";

interface WebhookLite { url?: string; active?: boolean; routedAccounts?: unknown[] }

function loggingRequirementsMet(accounts: Account[], webhooks: unknown[]): boolean {
  const enabled = accounts.filter((a) => a.enabled !== false);
  if (!enabled.length || !webhooks.length) return false;
  const whs = webhooks as WebhookLite[];
  if (!whs.some((w) => (w.url || "").trim())) return false;
  return whs.some((w) => (w.active ?? true) && (w.routedAccounts || []).length > 0);
}


export function ModuleBuilder() {
  const macroMode = useStore((s) => getMacroMode(s.settings));
  return macroMode === "normal" ? <NormalMode /> : <MultiMacroBuilder />;
}

function MultiMacroBuilder() {
  const running = useStore((s) => s.running);
  const accounts = useStore((s) => s.accounts) as Account[];
  const webhooks = useStore((s) => s.webhooks);
  const automation = useStore((s) => s.automation);
  const settings = useStore((s) => s.settings);
  const ocrAvailable = useStore((s) => s.ocrAvailable);
  const fishingStatus = useStore((s) => s.fishingStatus);
  const cycleStatus = useStore((s) => s.cycleStatus);
  const applyState = useStore((s) => s.applyState);
  const patchSettings = useStore((s) => s.patchSettings);
  const bindStates = useStore((s) => s.bindStates);

  const [drawer, setDrawer] = useState<DrawerState>(null);
  const [apModal, setApModal] = useState<ApModal>(null);
  const [abModal, setAbModal] = useState<AbModal>(null);

  
  const tutorialDrawer = useStore((s) => s.tutorialDrawer);
  useEffect(() => {
    if (tutorialDrawer) {
      const { kind, accId } = tutorialDrawer;
      setDrawer((accId != null ? { kind, accId } : { kind }) as DrawerState);
    } else {
      setDrawer(null);
    }
  }, [tutorialDrawer]);
  const [apBiomeKeys, setApBiomeKeys] = useState<string[]>(BIOMES.map((b) => b.key));
  const [apUnknownKeys, setApUnknownKeys] = useState<string[]>([]);
  const [routeNames, setRouteNames] = useState<string[]>([]);

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

  useWindowBindPoll();

  const fishing = automation.fishing || {};
  let cycleSteps: CycleStep[] = [];
  const ocrFailsafe = automation.ocrFailsafe || {};
  const notif = automation.notifications || {};
  const intervals = automation.intervals || {};
  const autopop = automation.autopop || {};
  const apAccounts = autopop.accounts || {};

  const pixels = automation.pixels || {};
  const invReady = PIXEL_SLOTS.every(([k]) => isPoint(pixels[k]));
  const merchGeneral = (automation.merchants?.calib || {}).general || {};
  const merchReady = isPoint(merchGeneral.pixels?.dialogue_skip) && isRegion(merchGeneral.regions?.merchant_name);
  const fishReady = FISHING_REQUIRED_SLOTS.every((k) => isPoint(fishing.pixels?.[k]));
  const chatCalibAll = (automation.calib || {}).chat || {};
  const auraReady = isPoint(chatCalibAll.pixels?.chat_button) && isPoint(chatCalibAll.pixels?.server_messages_button) && isRegion(chatCalibAll.regions?.chat_region);
  const apAmountReady = isRegion(autopop.amountRegion);
  const locks: ModuleLocks = useMemo(() => ({
    item: invReady ? null : "Needs the Inventory calibration (all 6 click points)",
    merchant: !ocrAvailable
      ? "Needs Tesseract OCR (not installed)"
      : !invReady
        ? "Needs the Inventory calibration (all 6 click points)"
        : !merchReady
          ? "Needs the Merchant General calibration (Dialogue Skip + Merchant Name region)"
          : null,
    autopop: !invReady
      ? "Needs the Inventory calibration (all 6 click points)"
      : !apAmountReady
        ? "Needs the Amount Scan Region (set it in the Auto Pop settings or Calibration)"
        : null,
    fishing: fishReady ? null : "Needs the Fishing calibration (the 7 core click points)",
    aura: !ocrAvailable
      ? "Needs Tesseract OCR (not installed)"
      : !auraReady
        ? "Needs the Chat calibration (Chat + Server Messages buttons and Chat Region)"
        : null,
  }), [invReady, merchReady, apAmountReady, fishReady, auraReady, ocrAvailable]);
  const locksRef = useRef(locks);
  locksRef.current = locks;
  const anyLocked = !!(locks.item || locks.merchant || locks.autopop || locks.fishing);

  const loggingMet = loggingRequirementsMet(accounts, webhooks);
  const loggingOn = !!settings.biomeLogging;
  const afkOn = !!settings.antiAfkEnabled;
  const ramTrimOn = !!settings.ramTrimEnabled;
  const ramInterval = Math.max(1, Math.min(1440, parseInt(String(settings.ramTrimInterval), 10) || 60));
  const slowResetOn = !!settings.slowReset;
  const fakePingOn = settings.fakePingGuard !== false;
  let miscOn = slowResetOn || fakePingOn;
  const boundCount = accounts.filter((a) => a.enabled !== false && a.window).length;

  async function toggleAfk(checked: boolean) {
    if (running) return;
    patchSettings({ antiAfkEnabled: checked });
    applyState(await callPy<BackendState>("set_setting", "antiAfkEnabled", checked));
  }
  async function toggleRamTrim(checked: boolean) {
    patchSettings({ ramTrimEnabled: checked });
    applyState(await callPy<BackendState>("set_setting", "ramTrimEnabled", checked));
  }
  const toggleAccountEnabled = useCallback(async (accId: number, enabled: boolean) => {
    const st = useStore.getState();
    if (st.running) return;
    st.applyState(await callPy<BackendState>("set_account_enabled", accId, enabled));
  }, []);
  const toggleModule = useCallback(async (accId: number, task: string) => {
    const st = useStore.getState();
    if (st.running) return;
    const acc = (st.accounts as Account[]).find((a) => a.id === accId);
    if (!acc || acc.enabled === false) return;
    const cur = !!acc.modules?.[task as keyof NonNullable<Account["modules"]>];
    if (!cur) {
      if (task === "merchantTeleporter" && locksRef.current.merchant) return;
      if (task === "auraDetection" && locksRef.current.aura) return;
      if (task === "fishing" && locksRef.current.fishing) return;
      if ((task === "strangeController" || task === "biomeRandomizer") && locksRef.current.item) return;
    }
    st.applyState(await callPy<BackendState>("set_account_module", accId, task, !cur));
  }, []);
  const enabledBiomeCount = (accId: number) => {
    const bm = (apAccounts[String(accId)]?.biomes || {}) as Record<string, { enabled?: boolean }>;
    return Object.values(bm).filter((b) => b?.enabled).length;
  };

  const toggleAutopop = useCallback(async (accId: number) => {
    const st = useStore.getState();
    if (st.running) return;
    const acc = (st.accounts as Account[]).find((a) => a.id === accId);
    if (!acc || acc.enabled === false) return;
    const apAcc = (st.automation.autopop?.accounts || {})[String(accId)];
    const on = !!apAcc?.enabled;
    if (!on && locksRef.current.autopop) return;
    const biomeCount = Object.values((apAcc?.biomes || {}) as Record<string, { enabled?: boolean }>).filter((b) => b?.enabled).length;
    if (!on && biomeCount === 0) return;
    st.applyState(await callPy<BackendState>("set_autopop_account", accId, !on));
  }, []);
  const openDrawer = useCallback((accId: number, kind: "strangeController" | "biomeRandomizer" | "merchant" | "autopop" | "aura" | "fishing") => {
    setDrawer(kind === "autopop" || kind === "merchant" || kind === "fishing" ? { kind, accId } : ({ kind } as DrawerState));
  }, []);

  async function onOcrFailsafe(task: string, checked: boolean) {
    if (running) return;
    if (checked && task !== "noBite" && !ocrAvailable) return;
    applyState(await callPy<BackendState>("set_ocr_failsafe", task, checked));
  }
  async function onNotif(key: string, checked: boolean) {
    applyState(await callPy<BackendState>("set_notification", key, checked));
  }

  const enabledAccounts = useMemo(() => accounts.filter((a) => a.enabled !== false), [accounts]);
  const steps = useMemo(() => {
    const out: Array<{ icon: string; label: string }> = [];
    [...ITEM_TASKS,
     { key: "merchantTeleporter", name: "Merchant Det.", full: "Merchant Detection", icon: "fa-store" },
     { key: "fishing", name: "Fishing", full: "Fishing", icon: "fa-fish" },
    ].forEach((t) => {
      enabledAccounts
        .filter((a) => a.modules?.[t.key as keyof NonNullable<Account["modules"]>])
        .forEach((a) => out.push({ icon: t.icon, label: `${t.name} · ${a.name}` }));
    });
    return out;
  }, [enabledAccounts]);
  const autoMode = automation.mode === "automation";
  const popAccounts = useMemo(
    () => (autoMode ? enabledAccounts.filter((a) => !!apAccounts[String(a.id)]?.enabled) : []),
    [autoMode, enabledAccounts, apAccounts]);

  const drawerAcc =
    drawer?.kind === "autopop" || drawer?.kind === "fishing" || drawer?.kind === "merchant" || drawer?.kind === "limbo"
      ? accounts.find((a) => a.id === drawer.accId)
      : null;

  return (
    <section className="tab active-tab" id="modules">
      <header className="page-head">
        <h1>Module Builder</h1>
        <p>
          One place for everything: enable accounts, assign modules per account, and tune each
          module via its <i className="fa-solid fa-gear" style={{ fontSize: 11 }}></i> settings.
        </p>
      </header>

      <MacroModeToggle />

      {}
      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-globe"></i> Global Modules</div>
          <span className="badge badge-soft">run for all accounts</span>
        </div>
        <div className="mb-globals">
          <div className={`mb-global${loggingOn ? " on" : ""}`}>
            <div className="mb-global-ico"><i className="fa-solid fa-satellite-dish"></i></div>
            <div className="mb-global-meta">
              <span className="mb-global-name">Biome Logging</span>
              <span className="mb-global-desc">
                {loggingMet
                  ? "Always on. Watches Roblox logs and posts a biome embed for each biome. Locked while running."
                  : "Always on, but it needs an active webhook: add one and route it to an account (Webhooks tab)."}
              </span>
            </div>
            <div className="mb-global-actions">
              <button className="mb-chip-gear mb-chip-single" title="Biome ping settings" onClick={() => setDrawer({ kind: "biomelog" })}>
                <i className="fa-solid fa-gear"></i>
              </button>
            </div>
          </div>

          <div className={`mb-global${afkOn ? " on" : ""}`}>
            <div className="mb-global-ico"><i className="fa-solid fa-person-running"></i></div>
            <div className="mb-global-meta">
              <span className="mb-global-name">Anti-AFK</span>
              <span className="mb-global-desc">Keeps every open Roblox instance awake while the engine runs.</span>
            </div>
            <div className="mb-global-actions">
              <button className="mb-chip-gear mb-chip-single" title="Anti-AFK settings" onClick={() => setDrawer({ kind: "antiafk" })}>
                <i className="fa-solid fa-gear"></i>
              </button>
              <label className="switch">
                <input type="checkbox" checked={afkOn} disabled={running} onChange={(e) => void toggleAfk(e.target.checked)} />
                <span className="slider"></span>
              </label>
            </div>
          </div>

          <div className={`mb-global${ramTrimOn ? " on" : ""}`}>
            <div className="mb-global-ico"><i className="fa-solid fa-memory"></i></div>
            <div className="mb-global-meta">
              <span className="mb-global-name">Auto-Trim RAM</span>
              <span className="mb-global-desc">Frees system memory on a timer ({fmtRamInterval(ramInterval)}) while the engine runs. Set the interval with the gear.</span>
            </div>
            <div className="mb-global-actions">
              <button className="mb-chip-gear mb-chip-single" title="Auto-Trim RAM settings" onClick={() => setDrawer({ kind: "ramtrim" })}>
                <i className="fa-solid fa-gear"></i>
              </button>
              <label className="switch">
                <input type="checkbox" checked={ramTrimOn} onChange={(e) => void toggleRamTrim(e.target.checked)} />
                <span className="slider"></span>
              </label>
            </div>
          </div>

          <div className={`mb-global${miscOn ? " on" : ""}`}>
            <div className="mb-global-ico"><i className="fa-solid fa-sliders"></i></div>
            <div className="mb-global-meta">
              <span className="mb-global-name">
                Misc
                {slowResetOn && <span className="po-chip passive" style={{ marginLeft: 6 }}><i className="fa-solid fa-hourglass-half"></i> Slow UI</span>}
                {fakePingOn && <span className="po-chip passive" style={{ marginLeft: 6 }}><i className="fa-solid fa-shield-halved"></i> Anti Fake Ping</span>}
              </span>
              <span className="mb-global-desc">Global failsafes: Slow UI Reset and Anti Fake Rare Biome Ping.</span>
            </div>
            <div className="mb-global-actions">
              <button className="mb-chip-gear mb-chip-single" title="Misc settings" onClick={() => setDrawer({ kind: "misc" })}>
                <i className="fa-solid fa-gear"></i>
              </button>
            </div>
          </div>
        </div>
      </div>

      {}
      {ocrAvailable === false && (
        <div className="glass glass-warning card auto-note" data-reveal>
          <i className="fa-solid fa-lock"></i>
          <p>
            <b>Tesseract not installed.</b> Merchant Detection and all OCR failsafes are locked.
            One click installs it, no manual setup.
          </p>
          <TesseractInstallButton />
        </div>
      )}

      {}
      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-cubes"></i> Accounts &amp; Modules</div>
          <span className="badge badge-soft">
            {boundCount > 0 ? `${boundCount} window${boundCount === 1 ? "" : "s"} bound` : running ? "no windows bound" : "engine off"}
          </span>
        </div>
        {anyLocked && accounts.length > 0 && (
          <div className="mb-locks-note">
            <i className="fa-solid fa-lock"></i>
            <span>
              Chips with a lock are missing their calibration. Hover them to see what's needed,
              then set it in the{" "}
              <button className="mb-cal-link" onClick={() => useStore.getState().setCurrentTab("calibration")}>
                Calibration tab
              </button>.
            </span>
          </div>
        )}
        <div className="mb-list">
          {accounts.map((acc) => (
            <AccountRow
              key={acc.id}
              acc={acc}
              running={running}
              locks={locks}
              bindState={bindStates[acc.id]}
              autopopOn={!!apAccounts[String(acc.id)]?.enabled}
              autopopHasBiome={enabledBiomeCount(acc.id) > 0}
              onToggleEnabled={toggleAccountEnabled}
              onToggleModule={toggleModule}
              onToggleAutopop={toggleAutopop}
              onOpenDrawer={openDrawer}
            />
          ))}
        </div>
        {accounts.length === 0 && (
          <div className="empty-state show">
            <i className="fa-solid fa-user-plus"></i>
            <p>No accounts yet. Add accounts in the Accounts tab first.</p>
          </div>
        )}
      </div>

      {}
      {}

      {}
      <EdenModePanel accounts={accounts as Account[]} running={running} />

      {}
      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-list-ol"></i> Run Order</div>
          <span className="badge badge-soft">{automation.mode === "automation" ? "Automation mode" : "Idle mode"}</span>
        </div>
        <div>
          {(loggingOn || afkOn || ramTrimOn || popAccounts.length > 0) && (
            <div className="mb-order-passive">
              <span className="mb-order-label">While running</span>
              {loggingOn && <span className="po-chip passive"><i className="fa-solid fa-satellite-dish"></i> Biome Logging</span>}
              {afkOn && <span className="po-chip passive"><i className="fa-solid fa-person-running"></i> Anti-AFK</span>}
              {ramTrimOn && <span className="po-chip passive"><i className="fa-solid fa-memory"></i> Auto-Trim RAM</span>}
              {popAccounts.map((a) => (
                <span className="po-chip passive" key={a.id}><i className="fa-solid fa-wand-magic-sparkles"></i> Auto Pop · {a.name}</span>
              ))}
            </div>
          )}
          {!steps.length && cycleSteps.length === 0 ? (
            <div className="mod-empty">
              <i className="fa-solid fa-ban"></i> No item modules routed yet. Toggle modules on the accounts above (they run in Automation mode).
            </div>
          ) : (
            <>
              {steps.length > 0 && (
                <div className="prio-order-chain">
                  {steps.map((s, i) => (
                    <span key={i} style={{ display: "contents" }}>
                      {i > 0 && (
                        <span className="po-arrow"><i className="fa-solid fa-arrow-right"></i></span>
                      )}
                      <span className="po-chip"><i className={`fa-solid ${s.icon}`}></i> {s.label}</span>
                    </span>
                  ))}
                  <span className="po-arrow po-loop"><i className="fa-solid fa-rotate-right"></i></span>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {}
      <ModuleDrawer
        open={drawer?.kind === "antiafk"} icon="fa-person-running" title="Anti-AFK"
        sub="Global module: applies to every Roblox instance" onClose={() => setDrawer(null)}
      >
        <AntiAfkSettings />
      </ModuleDrawer>

      <ModuleDrawer
        open={drawer?.kind === "biomelog"} icon="fa-satellite-dish" title="Biome Logging" wide
        sub="Per-biome Discord pings" onClose={() => setDrawer(null)}
      >
        <BiomePingSettings />
      </ModuleDrawer>


      <ModuleDrawer
        open={drawer?.kind === "ramtrim"} icon="fa-memory" title="Auto-Trim RAM"
        sub="Global utility: frees system memory on a timer" onClose={() => setDrawer(null)}
      >
        <RamTrimSettings />
      </ModuleDrawer>

      <ModuleDrawer
        open={drawer?.kind === "misc"} icon="fa-sliders" title="Misc"
        sub="Global options: apply to every account" onClose={() => setDrawer(null)}
      >
        <MiscSettings />
      </ModuleDrawer>

      {ITEM_TASKS.map((t) => (
        <ModuleDrawer
          key={t.key}
          open={drawer?.kind === t.key} icon={t.icon} title={t.full}
          sub="Item module: uses the inventory click points" onClose={() => setDrawer(null)}
        >
          <div className="mb-scope-note">
            <i className="fa-solid fa-circle-info"></i>
            <span>These settings are <b>global</b>: they apply to every account running this module. Item name and amount are fixed (the in-game item never changes).</span>
          </div>
          <ToggleRow
            name="OCR Item Failsafe" desc={OCR_FAILSAFE_DESC[t.key]}
            checked={!!ocrFailsafe[t.key]}
            disabled={running || (!ocrAvailable && !ocrFailsafe[t.key])}
            locked={!ocrAvailable}
            onChange={(c) => void onOcrFailsafe(t.key, c)}
          />
          <div className="afk-divider"></div>
          <ToggleRow
            name="Run notifications" desc="Sends a Discord embed each run: green when used, red when the failsafe skipped it."
            checked={!!notif[t.key]} onChange={(c) => void onNotif(t.key, c)}
          />
        </ModuleDrawer>
      ))}

      <ModuleDrawer
        open={drawer?.kind === "merchant"} icon="fa-store" title="Merchant Detection" wide
        sub={drawerAcc ? `Detection global · Auto Buy per account · ${drawerAcc.name}` : "Teleports to merchants, OCR-reads who arrived, posts the embed"}
        onClose={() => setDrawer(null)}
      >
        {drawer?.kind === "merchant" && drawerAcc && (
          <MerchantSettings
            acc={drawerAcc}
            running={running}
            ocrAvailable={ocrAvailable}
            interval={Number(intervals.merchantTeleporter) || 1800}
            screenshotOn={!!notif.merchantScreenshot}
            failsafeOn={!!ocrFailsafe.merchantTeleporter}
            autoBuyWebhookOn={!!notif.merchantAutoBuy}
            onScreenshot={(c) => void onNotif("merchantScreenshot", c)}
            onFailsafe={(c) => void onOcrFailsafe("merchantTeleporter", c)}
            onAutoBuyWebhook={(c) => void onNotif("merchantAutoBuy", c)}
            onOpenItems={(mid, title, items) => setAbModal({ accId: drawerAcc.id, mid, title, items })}
          />
        )}
      </ModuleDrawer>

      <ModuleDrawer
        open={drawer?.kind === "fishing"} icon="fa-fish" title="Fishing"
        sub={drawerAcc ? `Per-account settings · ${drawerAcc.name}` : "Per-account settings"}
        onClose={() => setDrawer(null)}
      >
        {drawer?.kind === "fishing" && drawerAcc && (
          <FishingSettings
            acc={drawerAcc}
            running={running}
            ocrAvailable={ocrAvailable}
            cfg={fishing.accounts?.[String(drawerAcc.id)] || {}}
            isActive={cycleStatus.type === "fishing" && cycleStatus.accId === drawerAcc.id}
            fishingStatus={fishingStatus}
            routeNames={routeNames}
            ocrFailsafe={ocrFailsafe}
            onOcrFailsafe={(task, c) => void onOcrFailsafe(task, c)}
          />
        )}
      </ModuleDrawer>


      <ModuleDrawer
        open={drawer?.kind === "autopop"} icon="fa-wand-magic-sparkles" title="Auto Pop" wide
        sub={drawerAcc ? `Per-account config · ${drawerAcc.name}` : "Per-account config"} onClose={() => setDrawer(null)}
      >
        {drawer?.kind === "autopop" && drawerAcc && (
          <AutopopSettings
            acc={drawerAcc}
            running={running}
            ocrAvailable={ocrAvailable}
            autopop={autopop}
            biomeKeys={apBiomeKeys}
            unknownKeys={apUnknownKeys}
            onOpenItems={(biome, title, items) => setApModal({ kind: "items", accId: drawerAcc.id, biome, title, items })}
            onOpenImport={() => setApModal({ kind: "import", accId: drawerAcc.id, name: "", json: "" })}
            onOpenExport={(json) => setApModal({ kind: "export", json })}
          />
        )}
      </ModuleDrawer>

      {}
      <Modal
        open={!!apModal}
        title={apModal?.kind === "items" ? apModal.title : apModal?.kind === "import" ? "Import Auto Pop Preset" : "Export Auto Pop Preset"}
        onCancel={() => setApModal(null)}
        onSave={async () => {
          if (!apModal) return true;
          if (apModal.kind === "items") {
            const items = apModal.items
              .map((i) => ({ name: (i.name || "").trim(), amount: Math.max(1, i.amount || 1), all: !!i.all }))
              .filter((i) => i.name);
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
            <p className="ap-modal-hint"><i className="fa-solid fa-circle-info"></i> Items are used top-to-bottom the moment this biome starts on this account. With the amount scan on, if stock is lower than the amount, the macro uses all it has. Tick <b>Use all</b> to always pop the whole stack.</p>
            <div className="ap-item-head"><span>Potion</span><span>Amount</span><span></span></div>
            <div>
              {apModal.items.map((it, i) => (
                <div className="ap-item-row" key={i}>
                  <PotionSelect className="ap-item-name" value={it.name}
                    onChange={(name) => setApModal({ ...apModal, items: apModal.items.map((x, j) => (j === i ? { ...x, name } : x)) })} />
                  {it.all ? (
                    <span className="ap-item-amt ap-item-all-tag">All</span>
                  ) : (
                    <div className="ap-item-amt">
                      <Stepper value={it.amount} min={1}
                        onChange={(v) => setApModal({ ...apModal, items: apModal.items.map((x, j) => (j === i ? { ...x, amount: Math.max(1, v) } : x)) })} />
                    </div>
                  )}
                  <button className="ap-item-del" title="Remove"
                    onClick={() => {
                      const next = apModal.items.filter((_, j) => j !== i);
                      setApModal({ ...apModal, items: next.length ? next : [{ name: "", amount: 1 }] });
                    }}><i className="fa-solid fa-trash"></i></button>
                  <div className="ap-item-all">
                    <span>Always use all</span>
                    <label className="switch" style={{ transform: "scale(0.85)" }}>
                      <input type="checkbox" checked={!!it.all}
                        onChange={(e) => setApModal({ ...apModal, items: apModal.items.map((x, j) => (j === i ? { ...x, all: e.target.checked } : x)) })} />
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
            <div>
              <div className="modal-label">Preset name (optional, uses the file's name if blank)</div>
              <input className="field" placeholder="My imported preset" value={apModal.name} onChange={(e) => setApModal({ ...apModal, name: e.target.value })} />
            </div>
            <div>
              <div className="modal-label">Paste exported preset JSON</div>
              <textarea className="field" rows={8} style={{ fontFamily: "monospace", fontSize: 11 }} value={apModal.json} onChange={(e) => setApModal({ ...apModal, json: e.target.value })} />
            </div>
          </>
        )}
        {apModal?.kind === "export" && (
          <>
            <p className="modal-label">Copy this and share it:</p>
            <textarea className="field" rows={8} style={{ fontFamily: "monospace", fontSize: 11 }} readOnly value={apModal.json} />
          </>
        )}
      </Modal>

      {}
      <Modal
        open={!!abModal}
        title={abModal?.title || ""}
        onCancel={() => setAbModal(null)}
        onSave={async () => {
          if (!abModal) return true;
          const items = abModal.items
            .map((i) => ({ name: (i.name || "").trim(), amount: Math.max(0, i.amount ?? 1), all: !!i.all }))
            .filter((i) => i.name);
          applyState(await callPy<BackendState>("set_merchant_autobuy_items", abModal.accId, abModal.mid, items));
          return true;
        }}
      >
        {abModal && (() => {
          const catalog = MERCHANT_AUTOBUY_ITEMS[abModal.mid];
          const used = new Set(abModal.items.map((i) => i.name).filter(Boolean));
          return (
            <div className="ap-modal">
              <p className="ap-modal-hint">
                <i className="fa-solid fa-circle-info"></i> Amount = how many you still want in total.
                Every purchase counts it down. At 0 the item is done and won't be bought again.
                Tick <b>Buy all</b> to always buy the whole stock every visit.
              </p>
              <div className="ap-item-head"><span>Item</span><span>Amount</span><span></span></div>
              <div>
                {abModal.items.map((it, i) => (
                  <div className="ap-item-row" key={i}>
                    <MerchantItemSelect
                      className="ap-item-name"
                      mid={abModal.mid}
                      value={it.name}
                      exclude={new Set([...used].filter((n) => n !== it.name))}
                      onChange={(name) => setAbModal({ ...abModal, items: abModal.items.map((x, j) => (j === i ? { ...x, name } : x)) })}
                    />
                    {it.all ? (
                      <span className="ap-item-amt ap-item-all-tag">All</span>
                    ) : (
                      <div className="ap-item-amt">
                        <Stepper value={it.amount ?? 1} min={0}
                          onChange={(v) => setAbModal({ ...abModal, items: abModal.items.map((x, j) => (j === i ? { ...x, amount: Math.max(0, v) } : x)) })} />
                      </div>
                    )}
                    <button className="ap-item-del" title="Remove"
                      onClick={() => {
                        const next = abModal.items.filter((_, j) => j !== i);
                        setAbModal({ ...abModal, items: next.length ? next : [{ name: "", amount: 1 }] });
                      }}><i className="fa-solid fa-trash"></i></button>
                    <div className="ap-item-all">
                      <span>Always buy all</span>
                      <label className="switch" style={{ transform: "scale(0.85)" }}>
                        <input type="checkbox" checked={!!it.all}
                          onChange={(e) => setAbModal({ ...abModal, items: abModal.items.map((x, j) => (j === i ? { ...x, all: e.target.checked } : x)) })} />
                        <span className="slider"></span>
                      </label>
                    </div>
                  </div>
                ))}
              </div>
              <button
                className="btn-add ap-add-item"
                disabled={abModal.items.length >= catalog.length}
                onClick={() => setAbModal({ ...abModal, items: [...abModal.items, { name: "", amount: 1 }] })}
              >
                <i className="fa-solid fa-plus"></i> Add item
              </button>
            </div>
          );
        })()}
      </Modal>
    </section>
  );
}
