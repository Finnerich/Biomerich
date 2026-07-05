import {
  Fragment,
  memo,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useStore } from "../../store";
import { callPy } from "../../bridge";
import { confirmDialog, promptDialog } from "../../dialog";
import { BIOMES, DEFAULT_AVATAR, RARE_KEYS, SEMI_RARE_KEYS } from "../../data/biomes";
import { MERCHANT_DISPLAY_NAMES, MERCHANT_META, type AutobuyMerchant } from "../../data/merchantItems";
import { MERCHANT_CALIB_GROUPS } from "../../data/calibGroups";
import { } from "../../data/slots";
import { CustomSelect, type SelectOption } from "../../components/CustomSelect";
import { ProgressRing } from "../../components/ProgressRing";
import { RangeSetting } from "../../components/RangeSetting";
import { TesseractInstallButton } from "../../components/TesseractInstallButton";
import { useTesseract } from "../../tesseract";
import { BindButton } from "../../windowBind";
import type {
  Account,
  AutopopAccountEntry,
  BackendState,
  FishingAccCfg,
} from "../../types";


export const ITEM_TASKS = [
  { key: "strangeController", name: "Strange Ctrl.", full: "Strange Controller", icon: "fa-gamepad" },
  { key: "biomeRandomizer", name: "Biome Rand.", full: "Biome Randomizer", icon: "fa-shuffle" },
] as const;


export const OCR_FAILSAFE_DESC: Record<string, string> = {
  strangeController: "Reads the first item slot with OCR and confirms it matches before using. Retries 3×, then skips.",
  biomeRandomizer: "Reads the first item slot and confirms it matches before using.",
  merchantTeleporter: "Confirms the Merchant Teleporter is in the slot before using it.",
  fishingFailed: 'Before clicking Close / Collect, reads the result text (red "Fishing Failed" vs white "Fish Caught"). Needs the Fishing Failed region.',
  sellFishShop: 'After opening the fish shop dialog, checks for "Captain Flarg". If missing, retries the route up to 3×, then skips the shop. Needs the Shop Name region.',
  noBite: "If no bite is detected for 45 seconds after casting, runs the sell route without opening the shop. No OCR / region needed.",
};

export type DrawerState =
  | { kind: "antiafk" }
  | { kind: "biomelog" }
  | { kind: "aura" }
  | { kind: "ramtrim" }
  | { kind: "misc" }
  | { kind: "strangeController" }
  | { kind: "biomeRandomizer" }
  | { kind: "merchant"; accId: number }
  | { kind: "fishing"; accId: number }
  | { kind: "limbo"; accId: number }
  | { kind: "autopop"; accId: number }
  | null;

export interface ItemDraft { name: string; amount: number; all?: boolean }
export type ApModal =
  | { kind: "items"; accId: number; biome: string; title: string; items: ItemDraft[] }
  | { kind: "import"; accId: number; name: string; json: string }
  | { kind: "export"; json: string }
  | null;
export type AbModal = { accId: number; mid: AutobuyMerchant; title: string; items: ItemDraft[] } | null;

export interface MerchantAutobuyEntry { enabled?: boolean; items?: ItemDraft[] }
export interface MerchantBuyLogEntry { ts?: string; account?: string; merchant?: string; item?: string; amount?: number }
export interface MerchantsCfg {
  calib?: Record<string, { pixels?: Record<string, unknown>; regions?: Record<string, unknown> }>;
  autobuy?: { accounts?: Record<string, Record<string, MerchantAutobuyEntry>> };
  buyLog?: MerchantBuyLogEntry[];
}

export const isUnknown = (k: string) => k.startsWith("unknown:");
export const unknownName = (k: string) => (isUnknown(k) ? k.slice("unknown:".length) : k);

export const POPULAR_KEYS = ["corruption", "rainy"];
export const isRareBiome = (k: string) => {
  const t = BIOMES.find((x) => x.key === k)?.tier;
  return t === "rare" || t === "semi-rare";
};

export const isPoint = (v: unknown) => Array.isArray(v) && v.length === 2;
export const isRegion = (v: unknown) => Array.isArray(v) && v.length === 4;
export const FISHING_REQUIRED_SLOTS = ["cast_point", "bite_indicator", "bar_sample", "zone_left",
  "zone_right", "reel_click", "claim_button"] as const;

export interface ModuleLocks {
  item: string | null;
  merchant: string | null;
  autopop: string | null;
  fishing: string | null;
  aura: string | null;
}

export function biomeMeta(key: string) {
  if (isUnknown(key)) {
    return { key, name: unknownName(key), grad: "linear-gradient(135deg,#5b5f6e,#2a2d36)", shadow: "#7e8499", unknown: true };
  }
  const b = BIOMES.find((x) => x.key === key);
  return b ? { ...b, unknown: false } : { key, name: key, grad: "linear-gradient(135deg,#3a3f4b,#23262e)", shadow: "#3a3f4b", unknown: false };
}


export const AccountRow = memo(function AccountRow(props: {
  acc: Account;
  running: boolean;
  locks: ModuleLocks;
  bindState: "waiting" | "bound" | undefined;
  autopopOn: boolean;
  autopopHasBiome: boolean;
  onToggleEnabled: (accId: number, v: boolean) => void;
  onToggleModule: (accId: number, task: string) => void;
  onToggleAutopop: (accId: number) => void;
  onOpenDrawer: (accId: number, kind: "strangeController" | "biomeRandomizer" | "merchant" | "autopop" | "aura" | "fishing") => void;
}) {
  const { acc, running, locks, bindState, autopopOn, autopopHasBiome } = props;
  const mods = acc.modules || {};
  const disabled = acc.enabled === false;

  const waiting = bindState === "waiting";
  let label: string;
  let cls: string;
  if (disabled) { label = "Disabled (excluded from the macro)"; cls = "off"; }
  else if (waiting) { label = "Click a Roblox window…"; cls = "warn"; }
  else if (acc.window) { label = "Bound to " + acc.window; cls = "live"; }
  else if (bindState === "bound") { label = "Bound ✓"; cls = "live"; }
  else if (acc.online) { label = "Online: locating window…"; cls = "warn"; }
  else if (!running) { label = "Idle: launch the account or bind a window"; cls = ""; }
  else { label = "Offline: no Roblox window found"; cls = "off"; }

  const merchOn = !!mods.merchantTeleporter;
  const fishingOn = !!mods.fishing;
  const itemLocked = (key: "strangeController" | "biomeRandomizer") => !!locks.item && !mods[key];
  const merchLocked = !!locks.merchant && !merchOn;
  const fishingLocked = !!locks.fishing && !fishingOn;
  const popLocked = (!!locks.autopop || !autopopHasBiome) && !autopopOn;
  const popLockMsg = locks.autopop || "Enable at least one biome in the Auto Pop settings (gear) first";

  return (
    <div className={`mb-acc${disabled ? " disabled" : ""}`} data-acc-id={acc.id}>
      <div className="mb-acc-top">
        <img className="prio-avatar" alt="" src={acc.avatar || DEFAULT_AVATAR} />
        <div className="prio-id">
          <span className="prio-name">{acc.name}</span>
          <span className={`prio-window ${cls}`}>
            <span className="sd"></span>
            <span className="prio-window-text">{label}</span>
          </span>
        </div>
        <div className="mb-acc-enable">
          <span className="mb-enable-label">{disabled ? "Disabled" : "Enabled"}</span>
          <label className="switch" title={disabled ? "Enable this account" : "Disable (removes it from windows, embeds, stats and all modules)"}>
            <input type="checkbox" checked={!disabled} disabled={running} onChange={(e) => props.onToggleEnabled(acc.id, e.target.checked)} />
            <span className="slider"></span>
          </label>
        </div>
      </div>

      <div className="mb-acc-chips">
        <BindButton acc={acc} baseClass="prio-chip prio-chip-bind mb-chip-single" />


        {ITEM_TASKS.map((t) => {
          const locked = itemLocked(t.key);
          return (
            <span className="mb-chip-wrap" key={t.key}>
              <button
                className={`prio-chip${mods[t.key] ? " on" : ""}${locked ? " mb-locked" : ""}`}
                title={locked ? locks.item! : undefined}
                onClick={() => { if (!locked) props.onToggleModule(acc.id, t.key); }}
              >
                <i className={`fa-solid ${locked ? "fa-lock" : t.icon}`}></i><span>{t.name}</span>
              </button>
              <button className="mb-chip-gear" title={`${t.full} settings`} onClick={() => props.onOpenDrawer(acc.id, t.key)}>
                <i className="fa-solid fa-gear"></i>
              </button>
            </span>
          );
        })}

        <span className="mb-chip-wrap">
          <button
            className={`prio-chip prio-chip-merch${merchOn ? " on" : ""}${merchLocked ? " mb-locked" : ""}`}
            title={merchLocked ? locks.merchant! : undefined}
            onClick={() => { if (!merchLocked) props.onToggleModule(acc.id, "merchantTeleporter"); }}
          >
            <i className={`fa-solid ${merchLocked ? "fa-lock" : "fa-store"}`}></i><span>Merchant Det.</span>
          </button>
          <button className="mb-chip-gear" title="Merchant Detection settings" onClick={() => props.onOpenDrawer(acc.id, "merchant")}>
            <i className="fa-solid fa-gear"></i>
          </button>
        </span>

        <span className="mb-chip-wrap">
          <button
            className={`prio-chip prio-chip-pop${autopopOn ? " on" : ""}${popLocked ? " mb-locked" : ""}`}
            title={popLocked ? popLockMsg : undefined}
            onClick={() => { if (!popLocked) props.onToggleAutopop(acc.id); }}
          >
            <i className={`fa-solid ${popLocked ? "fa-lock" : "fa-wand-magic-sparkles"}`}></i><span>Auto Pop</span>
          </button>
          <button className="mb-chip-gear" title="Auto Pop settings" onClick={() => props.onOpenDrawer(acc.id, "autopop")}>
            <i className="fa-solid fa-gear"></i>
          </button>
        </span>


        <span className="mb-chip-wrap">
          <button
            className={`prio-chip prio-chip-fish${fishingOn ? " on" : ""}${fishingLocked ? " mb-locked" : ""}`}
            title={fishingLocked ? locks.fishing! : "Fishing (only one account at a time)"}
            onClick={() => { if (!fishingLocked) props.onToggleModule(acc.id, "fishing"); }}
          >
            <i className={`fa-solid ${fishingLocked ? "fa-lock" : "fa-fish"}`}></i><span>Fishing</span>
          </button>
          <button className="mb-chip-gear" title="Fishing settings" onClick={() => props.onOpenDrawer(acc.id, "fishing")}>
            <i className="fa-solid fa-gear"></i>
          </button>
        </span>

      </div>
    </div>
  );
});


export function ToggleRow({ name, desc, checked, disabled, locked, needsTesseract, lockReason, onChange }: {
  name: ReactNode; desc: ReactNode; checked: boolean; disabled?: boolean; locked?: boolean;
  needsTesseract?: boolean; lockReason?: string; onChange: (c: boolean) => void;
}) {
  const showInstall = !!locked && (needsTesseract ?? true);
  return (
    <div className="setting-row">
      <div className="setting-info">
        <span className="setting-name">
          {name}{" "}
          {showInstall && (
            <button className="mb-lock-hint mb-lock-btn" onClick={() => useTesseract.getState().openInstall()}
              title="Install Tesseract to unlock">
              <i className="fa-solid fa-download"></i> Install Tesseract
            </button>
          )}
        </span>
        <span className="setting-desc">{desc}</span>
        {locked && !showInstall && lockReason && (
          <span className="setting-lock-reason"><i className="fa-solid fa-lock"></i> {lockReason}</span>
        )}
      </div>
      <label className="switch">
        <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
        <span className="slider"></span>
      </label>
    </div>
  );
}

export function fmtAfkInterval(sec: number): string {
  if (sec >= 60) return `${Math.floor(sec / 60)}m ${String(sec % 60).padStart(2, "0")}s`;
  return `${sec}s`;
}
export function fmtRamInterval(min: number): string {
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60);
  const rm = min % 60;
  return rm ? `${h}h ${rm}m` : `${h}h`;
}
export function fmtMerchInterval(secs: number): string {
  const m = Math.round((secs || 0) / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm ? `${h}h ${rm}m` : `${h}h`;
}

export function MiscSettings() {
  const settings = useStore((s) => s.settings);
  const patchSettings = useStore((s) => s.patchSettings);

  function setSetting(key: string, on: boolean) {
    patchSettings({ [key]: on });
    void callPy("set_setting", key, on);
  }

  return (
    <>
      <div className="mb-scope-note">
        <i className="fa-solid fa-circle-info"></i>
        <span>These options are <b>global</b>: they count for every account, not per account.</span>
      </div>
      <ToggleRow
        name="Slow UI Reset"
        desc="Adds extra wait after the in-game character reset (Esc → R → Enter) used by the fishing sell route. Turn on if Roblox is slow on your PC and the route drifts out of sync; off runs at normal speed."
        checked={!!settings.slowReset}
        onChange={(c) => setSetting("slowReset", c)}
      />
      <div className="afk-divider"></div>
      <ToggleRow
        name="Anti Fake Rare Biome Ping"
        desc="If Roblox disconnects and a rare biome (Glitched / Dreamspace / Cyberspace / Singularity) shows up right after, the biome started/ended embed is NOT sent. That would be a fake ping that can get you banned. Instead a generic error notification is posted (it never names the biome). Recommended on."
        checked={settings.fakePingGuard !== false}
        onChange={(c) => setSetting("fakePingGuard", c)}
      />
    </>
  );
}


export function AntiAfkSettings() {
  const running = useStore((s) => s.running);
  const settings = useStore((s) => s.settings);
  const patchSettings = useStore((s) => s.patchSettings);
  const action = settings.antiAfkAction === "zoom" ? "zoom" : "space";
  const interval = Math.max(30, Math.min(900, parseInt(String(settings.antiAfkInterval), 10) || 300));

  const standalone = !!settings.antiAfkStandalone;

  function setAction(a: "space" | "zoom") {
    patchSettings({ antiAfkAction: a });
    void callPy("set_setting", "antiAfkAction", a);
  }

  function setStandalone(on: boolean) {
    patchSettings({ antiAfkStandalone: on });
    void callPy("set_setting", "antiAfkStandalone", on);
  }

  return (
    <>
      <div className="mb-scope-note">
        <i className="fa-solid fa-circle-info"></i>
        <span>Global module: fires into <b>every</b> open Roblox instance. Runs while the engine
          is on, or fully on its own when <b>Run without the engine</b> is enabled below.</span>
      </div>
      <div className="afk-setting">
        <div className="afk-setting-info">
          <span className="afk-setting-name">Run without the engine</span>
          <span className="afk-setting-desc">Keep Roblox awake even when the macro isn't started, no Start needed. Turn Anti-AFK on (the chip), then it fires on its own interval.</span>
        </div>
        <label className="switch">
          <input type="checkbox" checked={standalone} onChange={(e) => setStandalone(e.target.checked)} />
          <span className="slider"></span>
        </label>
      </div>
      <div className="afk-divider"></div>
      <div className="afk-setting">
        <div className="afk-setting-info">
          <span className="afk-setting-name">Action type</span>
          <span className="afk-setting-desc">Sent into each Roblox instance on every trigger.</span>
        </div>
        <div className="segmented">
          <button className={`seg-btn${action === "space" ? " active" : ""}`} onClick={() => setAction("space")}>Space</button>
          <button className={`seg-btn${action === "zoom" ? " active" : ""}`} onClick={() => setAction("zoom")}>Zoom (I/O)</button>
        </div>
      </div>
      <div className="afk-divider"></div>
      <RangeSetting
        name="Interval" desc="Time between each Anti-AFK trigger."
        min={30} max={900} step={30} value={interval} disabled={running} fmt={fmtAfkInterval}
        onCommit={(v) => {
          patchSettings({ antiAfkInterval: v });
          void callPy("set_setting", "antiAfkInterval", v);
        }}
      />
    </>
  );
}

export function RamTrimSettings() {
  const settings = useStore((s) => s.settings);
  const patchSettings = useStore((s) => s.patchSettings);
  const ramInterval = Math.max(1, Math.min(1440, parseInt(String(settings.ramTrimInterval), 10) || 60));

  return (
    <>
      <div className="mb-scope-note">
        <i className="fa-solid fa-circle-info"></i>
        <span>
          Every so often it frees up unused RAM across all your processes and the Windows
          standby cache, so your PC stays smooth. Runs in <b>both</b> Idle and Automation mode,
          but only <b>while the engine is on</b>.
        </span>
      </div>
      <RangeSetting
        name="Trim interval" desc="Time between each automatic RAM trim."
        min={1} max={1440} step={1} value={ramInterval} fmt={fmtRamInterval}
        onCommit={(v) => {
          patchSettings({ ramTrimInterval: v });
          void callPy("set_setting", "ramTrimInterval", v);
        }}
      />
      <div className="afk-divider"></div>
      <div className="mb-scope-note">
        <i className="fa-solid fa-shield-halved"></i>
        <span>Start the macro <b>as administrator</b> to free even more. Only then can it also purge the system standby (cached) memory list, which frees the biggest numbers.</span>
      </div>
    </>
  );
}

export function MerchantSettings(props: {
  acc: Account;
  running: boolean;
  ocrAvailable: boolean | null;
  interval: number;
  screenshotOn: boolean;
  failsafeOn: boolean;
  autoBuyWebhookOn: boolean;
  onScreenshot: (c: boolean) => void;
  onFailsafe: (c: boolean) => void;
  onAutoBuyWebhook: (c: boolean) => void;
  onOpenItems: (mid: AutobuyMerchant, title: string, items: ItemDraft[]) => void;
}) {
  const patchAutomation = useStore((s) => s.patchAutomation);
  const automation = useStore((s) => s.automation);
  const applyState = useStore((s) => s.applyState);
  const { acc, running } = props;


  const merchants = (automation.merchants as MerchantsCfg) || {};
  const abAccounts = merchants.autobuy?.accounts || {};
  const buyLog = Array.isArray(merchants.buyLog) ? merchants.buyLog : [];
  const buyLogReversed = useMemo(() => buyLog.slice().reverse(), [buyLog]);

  const calib = merchants.calib || {};
  const groupReady = (key: string, withRegions: boolean) => {
    const def = MERCHANT_CALIB_GROUPS.find((g) => g.key === key);
    if (!def) return false;
    const g = calib[key] || {};
    const pts = def.points.every(([k]) => isPoint(g.pixels?.[k]));
    const regs = !withRegions || def.regions.every(([k]) => k === "item_name" || isRegion(g.regions?.[k]));
    return pts && regs;
  };
  const autobuyCalibReady = groupReady("shop", true) && groupReady("mari", false) && groupReady("jester", false);
  const autobuyLock = !props.ocrAvailable
    ? "Needs Tesseract OCR (not installed)"
    : !autobuyCalibReady
      ? "Needs the full Merchant Shop calibration plus the Mari Dialogue and Jester Dialogue calibrations"
      : null;

  const abEntry = (mid: AutobuyMerchant): MerchantAutobuyEntry => abAccounts[String(acc.id)]?.[mid] || {};
  const abItems = (mid: AutobuyMerchant) => (abEntry(mid).items || []).filter((i) => (i.name || "").trim());
  const abOpenCount = (mid: AutobuyMerchant) => abItems(mid).filter((i) => i.all || (i.amount || 0) > 0).length;

  async function toggleAutobuy(mid: AutobuyMerchant, checked: boolean) {
    if (running) return;
    if (checked && (autobuyLock || abOpenCount(mid) === 0)) return;
    applyState(await callPy<BackendState>("set_merchant_autobuy", acc.id, mid, checked));
  }
  function openItems(mid: AutobuyMerchant) {
    if (running) return;
    const draft = (abEntry(mid).items || []).map((i) => ({ name: i.name || "", amount: i.amount ?? 1, all: !!i.all }));
    if (!draft.length) draft.push({ name: "", amount: 1, all: false });
    props.onOpenItems(mid, `Auto Buy: ${MERCHANT_META[mid].name} · ${acc.name}`, draft);
  }
  async function resetBuyLog() {
    if (!(await confirmDialog("Reset the Merchant Auto Buy log? This clears every recorded purchase.", { title: "Reset Auto Buy log", confirmLabel: "Reset", danger: true }))) return;
    applyState(await callPy<BackendState>("reset_merchant_buy_log"));
  }
  const fmtLogTime = (ts?: string) => {
    if (!ts) return "?";
    const d = new Date(ts);
    return isNaN(d.getTime())
      ? ts
      : d.toLocaleString([], { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  };

  let intervalRow = (
    <RangeSetting
      name="Teleporter interval" desc="How often each account uses the Merchant Teleporter."
      min={30} max={7200} step={30} value={props.interval} disabled={props.running} fmt={fmtMerchInterval}
      onCommit={(v) => {
        const intervals = (automation.intervals as Record<string, number>) || {};
        patchAutomation({ intervals: { ...intervals, merchantTeleporter: v } });
        void callPy("set_merchant_interval", v);
      }}
    />
  );

  return (
    <>
      <div className="mb-scope-note">
        <i className="fa-solid fa-circle-info"></i>
        <span>
          Interval, screenshot, failsafe and webhooks are <b>global</b>. The module uses the Merchant
          Teleporter item, skips the dialogue, and OCR-reads which merchant arrived. It therefore
          needs <b>Tesseract</b> plus the <b>Merchant General</b> calibration (Dialogue Skip + Name region).
          Auto Buy below is configured <b>per account</b>.
        </span>
        {props.ocrAvailable === false && <TesseractInstallButton className="sm" />}
      </div>
      {intervalRow}
      <div className="afk-divider"></div>
      <ToggleRow
        name="Attach screenshot" desc="Attaches a screenshot of the Roblox window to the embed. Mari and Jester open their shop first, Rin is shot in the dialogue."
        checked={props.screenshotOn} onChange={props.onScreenshot}
      />
      <div className="afk-divider"></div>
      <ToggleRow
        name="OCR Item Failsafe" desc={OCR_FAILSAFE_DESC.merchantTeleporter}
        checked={props.failsafeOn}
        disabled={props.running || (!props.ocrAvailable && !props.failsafeOn)}
        locked={!props.ocrAvailable}
        onChange={props.onFailsafe}
      />

      {}
      <div className="afk-divider" style={{ margin: "14px 0" }}></div>
      <div className="mb-scope-note per-acc">
        <i className="fa-solid fa-cart-shopping"></i>
        <span>
          <b>Auto Buy · {acc.name}</b>: when this merchant arrives, it opens the shop and buys your
          wanted items. Needs the <b>Merchant Shop</b> calibration plus the <b>Mari</b> and{" "}
          <b>Jester</b> dialogue calibrations.
        </span>
      </div>
      <div className="mb-ap-list">
        {(["mari", "jester"] as AutobuyMerchant[]).map((mid) => {
          const meta = MERCHANT_META[mid];
          const on = !!abEntry(mid).enabled;
          const count = abOpenCount(mid);
          const total = abItems(mid).length;
          const needsItem = !on && count === 0;
          const locked = !!autobuyLock && !on;
          return (
            <div key={mid} className={`mb-ap-row rare${on ? " on" : ""}`} style={{ ["--rg" as string]: meta.shadow }}>
              <span className="mb-ap-dot" style={{ ["--bg" as string]: meta.shadow, ["--gl" as string]: on ? meta.shadow : "transparent" }}></span>
              <span className="mb-ap-name">{meta.name}</span>
              <span className="mb-ap-tag rare" style={{ ["--biome-grad" as string]: meta.grad, ["--biome-shadow" as string]: meta.shadow }}>
                <i className="fa-solid fa-cart-shopping"></i> AUTO BUY
              </span>
              {mid === "jester" && <span className="mb-ap-tag popular"><i className="fa-solid fa-fire"></i> Popular</span>}
              <span className={`mb-ap-count${count ? " has" : ""}${needsItem ? " need" : ""}`}>
                {count ? `${count} item${count === 1 ? "" : "s"}` : total ? "all bought" : "add an item"}
              </span>
              <button className="mb-ap-edit" title="Edit items" disabled={running} onClick={() => openItems(mid)}>
                <i className="fa-solid fa-pen"></i>
              </button>
              <label
                className="switch" style={{ transform: "scale(0.85)" }}
                title={locked ? autobuyLock! : needsItem ? "Add at least one wanted item before enabling Auto Buy" : undefined}
              >
                <input type="checkbox" checked={on} disabled={running || locked || needsItem} onChange={(e) => void toggleAutobuy(mid, e.target.checked)} />
                <span className="slider"></span>
              </label>
            </div>
          );
        })}
      </div>
      <div className="afk-divider"></div>
      <ToggleRow
        name="Auto Buy webhook" desc="Sends a Discord embed for every purchase: purchase amount, wanted amount and how much is still left."
        checked={props.autoBuyWebhookOn} onChange={props.onAutoBuyWebhook}
      />

      {}
      <div className="afk-divider"></div>
      <div className="afk-setting">
        <div className="afk-setting-info">
          <span className="afk-setting-name">Auto Buy log</span>
          <span className="afk-setting-desc">Every purchase the macro made, across all accounts. Stored persistently.</span>
        </div>
        <button className="btn-show" disabled={!buyLog.length} onClick={() => void resetBuyLog()}>
          <i className="fa-solid fa-eraser"></i> Reset
        </button>
      </div>
      <div className="mb-buylog">
        {buyLog.length === 0 && <div className="mb-buylog-empty">No purchases yet.</div>}
        {buyLogReversed.map((e, i) => (
          <div className="mb-buylog-row" key={`${e.ts}-${i}`}>
            <span className="mb-buylog-time">{fmtLogTime(e.ts)}</span>
            <span className="mb-buylog-merch" style={{ color: MERCHANT_META[(e.merchant || "") as AutobuyMerchant]?.shadow }}>
              {MERCHANT_DISPLAY_NAMES[e.merchant || ""] || e.merchant || "?"}
            </span>
            <span className="mb-buylog-item">{e.amount ?? "?"}× {e.item || "?"}</span>
            <span className="mb-buylog-acc">{e.account || ""}</span>
          </div>
        ))}
      </div>
    </>
  );
}

export function FishingSettings(props: {
  acc: Account;
  running: boolean;
  ocrAvailable: boolean | null;
  cfg: FishingAccCfg;
  isActive: boolean;
  fishingStatus: { caught: number; sinceSell: number; sells: number };
  routeNames: string[];
  ocrFailsafe: Record<string, boolean>;
  onOcrFailsafe: (task: string, c: boolean) => void;
}) {
  const applyState = useStore((s) => s.applyState);
  const automation = useStore((s) => s.automation);
  const { acc, running, cfg, routeNames, isActive, fishingStatus } = props;
  const routeOptions: SelectOption[] = routeNames.map((n) => ({ value: n, label: n }));
  const sellAfter = cfg.sellAfter ?? 20;

  const fishRegions = ((automation.fishing as { regions?: Record<string, unknown> })?.regions) || {};
  
  
  
  const FAILSAFE_REGION: Record<string, { key: string; label: string }> = {
    fishingFailed: { key: "fishing_failed", label: "Fishing Failed / Caught Text" },
    sellFishShop: { key: "shop_name", label: "Shop Name" },
  };

  async function commit(key: string, value: unknown) {
    applyState(await callPy<BackendState>("set_fishing_account_setting", acc.id, key, value));
  }

  return (
    <>
      <div className="mb-scope-note per-acc">
        <i className="fa-solid fa-user"></i>
        <span>
          These settings belong to <b>{acc.name}</b>. Every account keeps its own fishing
          tuning, so switching the fishing chip between accounts never loses a setup.
          Only one account fishes at a time.
        </span>
      </div>

      {isActive && running && (
        <div className={`mb-ap-acc${cfg.autoSell ? " fx-beam" : ""}`} style={{ ["--fx-beam-r" as string]: "10px" }}>
          <ProgressRing id={`fish-${acc.id}`} value={fishingStatus.sinceSell || 0} max={Math.max(1, sellAfter)} size={56} stroke={6}>
            <span style={{ fontFamily: "Poppins", fontWeight: 800, fontSize: 13 }}>{fishingStatus.sinceSell || 0}</span>
          </ProgressRing>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
            <span className="name">{cfg.autoSell ? `${fishingStatus.sinceSell || 0} / ${sellAfter} until auto-sell` : "Fishing live"}</span>
            <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
              {(fishingStatus.caught || 0).toLocaleString("en-US")} caught · {fishingStatus.sells || 0} sell run{(fishingStatus.sells || 0) === 1 ? "" : "s"}
            </span>
          </div>
        </div>
      )}

      <ToggleRow
        name="Auto Sell" desc="Automatically sell fish after a certain number of catches."
        checked={!!cfg.autoSell} disabled={running}
        onChange={(c) => void commit("autoSell", c)}
      />
      <div className="afk-divider"></div>
      <RangeSetting
        name="Sell after" desc="Number of catches before selling."
        min={1} max={500} step={1} value={sellAfter} disabled={running}
        onCommit={(v) => void commit("sellAfter", v)}
      />
      <div className="afk-divider"></div>
      <RangeSetting
        name="Sell cycle" desc="How many times the shop sell action repeats per route run."
        min={1} max={56} step={1} value={cfg.sellCycle ?? 1} disabled={running}
        onCommit={(v) => void commit("sellCycle", v)}
      />
      <div className="afk-divider"></div>
      <div className="afk-setting">
        <div className="afk-setting-info">
          <span className="afk-setting-name">Walk speed (gamepass)</span>
          <span className="afk-setting-desc">Pick the profile that matches this account's walk speed.</span>
        </div>
        <div className="preset-row">
          <div className="custom-select-wrap">
            <CustomSelect
              options={routeOptions}
              value={cfg.route && cfg.route !== "None" ? cfg.route : ""}
              onChange={(v) => { if (!running) void commit("route", v); }}
              placeholder={routeNames.length ? "Select route…" : "No routes yet"}
              disabled={running || routeNames.length === 0}
            />
          </div>
        </div>
      </div>
      <div className="afk-divider"></div>
      <ToggleRow
        name="Walk route first (no shop)"
        desc="Before the first cast, walk the sell route once WITHOUT opening the shop, just to traverse it into position. Needs a route selected."
        checked={!!cfg.primeRoute} disabled={running || !cfg.route || cfg.route === "None"}
        onChange={(c) => void commit("primeRoute", c)}
      />
      <div className="afk-divider"></div>
      <p className="section-hint" style={{ margin: "4px 0" }}>
        The catch-result webhook toggle lives in the <b>Webhooks</b> tab. Failsafes below are global.
      </p>
      {(["fishingFailed", "sellFishShop", "noBite"] as const).map((task, i) => {
        const on = !!props.ocrFailsafe[task];
        const noOcr = task !== "noBite" && !props.ocrAvailable;
        const reg = FAILSAFE_REGION[task];
        const regionMissing = !!reg && !isRegion(fishRegions[reg.key]);
        const lockedByRegion = regionMissing && !noOcr;
        const locked = noOcr || lockedByRegion;
        return (
          <span key={task} style={{ display: "contents" }}>
            {i > 0 && <div className="afk-divider"></div>}
            <ToggleRow
              name={task === "fishingFailed" ? "Failsafe: Fishing Failed" : task === "sellFishShop" ? "Failsafe: Sell Fish Shop" : "Failsafe: No Bite"}
              desc={OCR_FAILSAFE_DESC[task]}
              checked={on && !locked}
              disabled={props.running || locked}
              locked={locked}
              needsTesseract={noOcr}
              lockReason={lockedByRegion ? `Needs the ${reg!.label} region, set it in the Calibration tab.` : undefined}
              onChange={(c) => props.onOcrFailsafe(task, c)}
            />
          </span>
        );
      })}
    </>
  );
}

export function EdenModePanel(props: { accounts: Account[]; running: boolean }) {
  const automation = useStore((s) => s.automation);
  const applyState = useStore((s) => s.applyState);
  const { accounts, running } = props;

  const runMode = (automation.mode as string) || "idle";
  const edenOnly = runMode !== "eden";
  const eden = (automation.eden as { account?: number | null }) || {};
  const enabledAccs = accounts.filter((a) => a.enabled !== false);
  const edenCalib = ((automation.calib as Record<string, { pixels?: Record<string, unknown> }>) || {}).eden || {};
  const clickSet = isPoint(edenCalib.pixels?.eden_click);

  const accOptions: SelectOption[] = [
    { value: "", label: "- none -" },
    ...enabledAccs.map((a) => ({ value: String(a.id), label: a.name })),
  ];

  async function setAccount(v: string) {
    if (running) return;
    applyState(await callPy<BackendState>("set_eden_account", v ? Number(v) : null));
  }

  return (
    <div className="glass card panel" data-reveal>
      <div className="panel-head">
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div className="panel-title"><i className="fa-solid fa-circle-dot"></i> Eden Mode</div>
          <span className={`cyc-mode-tag${edenOnly ? " warn" : " ok"}`} title="Eden Mode only runs when the top-left mode switch is set to Eden.">
            <i className={`fa-solid ${edenOnly ? "fa-triangle-exclamation" : "fa-circle-dot"}`} />
            {edenOnly ? "Runs only in Eden mode" : "Eden mode active"}
          </span>
        </div>
      </div>

      <p className="section-hint">
        Park your main account where Eden spawns. The macro spams <b>E</b> and clicks the
        <b> Eden Click Point</b> non-stop to claim Eden the instant it appears. Set the top-left mode
        to <b>Eden</b> to run it.
      </p>

      {!clickSet && (
        <div className="glass-warning auto-note">
          <i className="fa-solid fa-triangle-exclamation"></i>
          <p>Set the <b>Eden Click Point</b> under <b>Eden Calibrations</b> in the{" "}
            <button className="mb-cal-link" onClick={() => useStore.getState().setCurrentTab("calibration")}>Calibration tab</button>.</p>
        </div>
      )}

      <div className="afk-setting">
        <div className="afk-setting-info">
          <span className="afk-setting-name">Main Eden account</span>
          <span className="afk-setting-desc">The single account that stands at the Eden spawn, spams E and clicks the Eden Click Point.</span>
        </div>
        <div className="preset-row">
          <div className="custom-select-wrap">
            <CustomSelect options={accOptions} value={eden.account != null ? String(eden.account) : ""}
              onChange={setAccount} disabled={running} placeholder="Select account…" />
          </div>
        </div>
      </div>
    </div>
  );
}


export function AutopopSettings(props: {
  acc: Account;
  running: boolean;
  ocrAvailable: boolean | null;
  autopop: { accounts?: Record<string, AutopopAccountEntry>; presets?: Record<string, unknown>; ocrFailsafe?: boolean; amountRegion?: number[] | null; leaveLimboOnRareBiome?: boolean };
  biomeKeys: string[];
  unknownKeys: string[];
  onOpenItems: (biome: string, title: string, items: ItemDraft[]) => void;
  onOpenImport: () => void;
  onOpenExport: (json: string) => void;
}) {
  const applyState = useStore((s) => s.applyState);
  const { acc, running, autopop } = props;
  const [presetSel, setPresetSel] = useState("");
  const [presetMsg, setPresetMsg] = useState("");

  const entry = autopop.accounts?.[String(acc.id)] || {};
  const biomes = entry.biomes || {};
  const presets = autopop.presets || {};
  const presetNames = Object.keys(presets);
  const amountRegion = autopop.amountRegion;

  const biomeEntry = (k: string) => biomes[k] || { enabled: false, items: [] };
  const itemCount = (k: string) => (biomeEntry(k).items || []).filter((i) => (i.name || "").trim()).length;

  const allUnknown = (() => {
    const set = new Set(props.unknownKeys);
    Object.keys(biomes).forEach((k) => { if (isUnknown(k)) set.add(k); });
    return [...set].sort();
  })();
  const sections = (() => {
    const known = (props.biomeKeys.length ? props.biomeKeys : BIOMES.map((b) => b.key)).filter((k) => !isUnknown(k));
    const has = new Set(known);
    const tierOf = (k: string) => BIOMES.find((x) => x.key === k)?.tier;
    const rarityOf = (k: string) => BIOMES.find((x) => x.key === k)?.rarity || 0;
    const byRarity = (a: string, b: string) => rarityOf(b) - rarityOf(a);

    const rare = [...RARE_KEYS, ...SEMI_RARE_KEYS].filter((k) => has.has(k));
    const popular = POPULAR_KEYS.filter((k) => has.has(k) && tierOf(k) === "normal");
    const usedPop = new Set(popular);
    const normal = [...popular, ...known.filter((k) => tierOf(k) === "normal" && !usedPop.has(k)).sort(byRarity)];
    const event = known.filter((k) => tierOf(k) === "event").sort(byRarity);

    return [
      { key: "rare", label: null as string | null, keys: rare },
      { key: "normal", label: "Normal Biomes", keys: normal },
      { key: "event", label: "Event Biomes", keys: event },
      { key: "unknown", label: "Unknown Biomes (new biomes)", keys: allUnknown },
    ].filter((s) => s.keys.length);
  })();
  const list = sections.flatMap((s) => s.keys);
  const activeCount = list.filter((k) => biomeEntry(k).enabled).length;

  async function toggleBiome(key: string, checked: boolean) {
    if (running) return;
    if (checked && itemCount(key) === 0) return;
    applyState(await callPy<BackendState>("set_autopop_account_biome_enabled", acc.id, key, checked));
  }
  function openItems(key: string) {
    if (running) return;
    const draft = (biomeEntry(key).items || []).map((i) => ({ name: i.name || "", amount: i.amount || 1, all: !!i.all }));
    if (!draft.length) draft.push({ name: "", amount: 1, all: false });
    props.onOpenItems(key, `Auto Pop: ${biomeMeta(key).name} · ${acc.name}`, draft);
  }
  async function savePreset() {
    if (running) return;
    const name = ((await promptDialog(`Save ${acc.name}'s Auto Pop layout as preset:`, { title: "Save preset", confirmLabel: "Save", placeholder: "Preset name" })) || "").trim();
    if (!name) return;
    const r = await callPy<{ state?: BackendState }>("save_autopop_preset", acc.id, name);
    if (r?.state) applyState(r.state);
    setPresetSel(name);
  }
  async function loadPreset() {
    if (running || !presetSel) return;
    if (!(await confirmDialog(`Load preset "${presetSel}" into ${acc.name}? This replaces the account's current biome layout.`, { title: "Load preset", confirmLabel: "Load" }))) return;
    const r = await callPy<{ state?: BackendState }>("load_autopop_preset", acc.id, presetSel);
    if (r?.state) applyState(r.state);
  }
  async function deletePreset() {
    if (running || !presetSel) return;
    if (!(await confirmDialog(`Delete Auto Pop preset "${presetSel}"?`, { title: "Delete preset", confirmLabel: "Delete", danger: true }))) return;
    const r = await callPy<{ state?: BackendState }>("delete_autopop_preset", presetSel);
    if (r?.state) applyState(r.state);
    setPresetSel("");
  }
  async function exportPreset() {
    const name = presetSel || `${acc.name} current`;
    const r = await callPy<{ json?: string; name?: string }>("export_autopop_preset", name, acc.id);
    if (!r?.json) return;
    try {
      await navigator.clipboard.writeText(r.json);
      setPresetMsg(`"${r.name}" copied to clipboard. Share it!`);
      setTimeout(() => setPresetMsg(""), 2600);
    } catch {
      props.onOpenExport(r.json);
    }
  }
  async function captureRegion() {
    if (running) return;
    const res = await callPy<{ ok?: boolean }>("capture_autopop_amount_region");
    if (res?.ok) applyState(await callPy<BackendState>("get_state"));
  }
  async function clearRegion() {
    if (running) return;
    applyState(await callPy<BackendState>("clear_autopop_amount_region"));
  }

  const regionSet = Array.isArray(amountRegion) && amountRegion.length === 4;

  return (
    <>
      <div className="mb-scope-note per-acc">
        <i className="fa-solid fa-user"></i>
        <span>
          <b>Per-account config</b>: this biome/item layout belongs to <b>{acc.name}</b> only.
          Every account can pop completely different items. Auto Pop fires at top priority the
          instant an enabled biome starts on this account.
        </span>
      </div>

      <div className="mb-ap-acc">
        <img src={acc.avatar || DEFAULT_AVATAR} alt="" />
        <span className="name">{acc.name}</span>
        <span className="badge badge-soft">{activeCount} biome{activeCount === 1 ? "" : "s"} active</span>
      </div>

      {}
      <div className="mb-ap-preset-bar">
        <div className="custom-select-wrap">
          <CustomSelect options={presetNames.map((n) => ({ value: n, label: n }))} value={presetSel} onChange={setPresetSel}
            placeholder={presetNames.length ? "Select preset…" : "No presets yet"} disabled={running || !presetNames.length} />
        </div>
        <button className="btn-add" disabled={running || !presetSel} onClick={() => void loadPreset()}><i className="fa-solid fa-download"></i> Load</button>
        <button className="btn-show" disabled={running} onClick={() => void savePreset()}><i className="fa-solid fa-floppy-disk"></i> Save</button>
        <button className="btn-show" disabled={running || !presetSel} onClick={() => void deletePreset()}><i className="fa-solid fa-trash"></i></button>
        <button className="btn-show" onClick={() => void exportPreset()}><i className="fa-solid fa-file-export"></i></button>
        <button className="btn-show" disabled={running} onClick={props.onOpenImport}><i className="fa-solid fa-file-import"></i></button>
      </div>
      <div className="mb-ap-msg">{presetMsg}</div>

      {}
      <div className="mb-ap-list">
        {sections.map((sec) => (
          <Fragment key={sec.key}>
            {sec.label && <div className="mb-ap-sep"><span>{sec.label}</span></div>}
            {sec.keys.map((key) => {
              const meta = biomeMeta(key);
              const on = !!biomeEntry(key).enabled;
              const count = itemCount(key);
              const needsItem = !on && count === 0;
              return (
                <div
                  key={key}
                  className={`mb-ap-row${on ? " on" : ""}${isRareBiome(key) ? " rare" : ""}`}
                  style={isRareBiome(key) ? { ["--rg" as string]: meta.shadow } : undefined}
                >
                  <span className="mb-ap-dot" style={{ ["--bg" as string]: meta.shadow, ["--gl" as string]: on ? meta.shadow : "transparent" }}></span>
                  <span className="mb-ap-name">{meta.name}{meta.unknown ? " (unknown)" : ""}</span>
                  {isRareBiome(key) && (
                    <span className="mb-ap-tag rare" style={{ ["--biome-grad" as string]: meta.grad, ["--biome-shadow" as string]: meta.shadow }}>
                      <i className="fa-solid fa-gem"></i> RARE BIOME
                    </span>
                  )}
                  {POPULAR_KEYS.includes(key) && <span className="mb-ap-tag popular"><i className="fa-solid fa-fire"></i> Popular</span>}
                  <span className={`mb-ap-count${count ? " has" : ""}${needsItem ? " need" : ""}`}>{count ? `${count} item${count === 1 ? "" : "s"}` : "add an item"}</span>
                  <button className="mb-ap-edit" title="Edit items" disabled={running} onClick={() => openItems(key)}>
                    <i className="fa-solid fa-pen"></i>
                  </button>
                  <label className="switch" style={{ transform: "scale(0.85)" }} title={needsItem ? "Add at least one item before enabling this biome" : undefined}>
                    <input type="checkbox" checked={on} disabled={running || needsItem} onChange={(e) => void toggleBiome(key, e.target.checked)} />
                    <span className="slider"></span>
                  </label>
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>

      <div className="afk-divider" style={{ margin: "14px 0" }}></div>

      {}
      <ToggleRow
        name="OCR Item Failsafe (global)" desc="Scans the item before every use; skips it when the searched item isn't there. Shared by all accounts."
        checked={!!autopop.ocrFailsafe}
        disabled={!props.ocrAvailable && !autopop.ocrFailsafe}
        locked={!props.ocrAvailable}
        onChange={async (c) => applyState(await callPy<BackendState>("set_autopop_option", "ocrFailsafe", c))}
      />
      <div className="afk-divider"></div>
      <div className="afk-setting">
        <div className="afk-setting-info">
          <span className="afk-setting-name">Amount Scan Region <span className="ap-required">required</span></span>
          <span className="afk-setting-desc">Reads the owned amount so a request of 10 with 9 in stock uses all 9. Global (also settable in Calibration). Click top-left then bottom-right of the amount label.</span>
        </div>
        <div className="preset-row">
          <span className={`ap-region-state${regionSet ? " set" : " missing"}`}>
            {regionSet ? `Set · ${amountRegion![0]},${amountRegion![1]} · ${amountRegion![2]}×${amountRegion![3]}` : "Not set"}
          </span>
          <button className="btn-add" disabled={running} onClick={() => void captureRegion()}><i className="fa-solid fa-crop-simple"></i> Set</button>
          <button className="btn-show" disabled={running} onClick={() => void clearRegion()}><i className="fa-solid fa-eraser"></i></button>
        </div>
      </div>
    </>
  );
}
