






import { useEffect, useState, type ReactNode } from "react";
import { useStore } from "../store";
import { callPy, callPyWithTimeout } from "../bridge";
import { CaptureRow } from "../components/CaptureRow";
import { PresetPicker } from "../components/PresetPicker";
import { PIXEL_SLOTS, FISHING_PIXEL_SLOTS, FISHING_REGION_SLOTS } from "../data/slots";
import { MERCHANT_CALIB_GROUPS, EXTRA_CALIB_GROUPS, type CalibGroup } from "../data/calibGroups";
import { TesseractInstallButton } from "../components/TesseractInstallButton";
import type { BackendState } from "../types";



type Pos = number[] | undefined;
const CALIBRATION_RPC_TIMEOUT_MS = 70_000;
const pixelInfo = (pos: Pos) => {
  const isSet = Array.isArray(pos) && pos.length === 2;
  return { isSet, coord: isSet ? `${pos![0]}, ${pos![1]}` : "Not set" };
};
const regionInfo = (box: Pos) => {
  const isSet = Array.isArray(box) && box.length === 4;
  return { isSet, coord: isSet ? `${box![0]},${box![1]} · ${box![2]}×${box![3]}` : "Not set" };
};



export function Calibration() {
  const running = useStore((s) => s.running);
  const automation = useStore((s) => s.automation);
  const applyState = useStore((s) => s.applyState);
  const ocrAvailable = useStore((s) => s.ocrAvailable);

  const [collapsed, setCollapsed] = useState<Set<string>>(
    () => new Set(["inv", "fish", "merch", ...EXTRA_CALIB_GROUPS.map((g) => g.key)]),
  );
  const [presets, setPresets] = useState({ inv: [] as string[], fish: [] as string[], merch: [] as string[], extra: [] as string[], global: [] as string[] });
  const [copyFeedback, setCopyFeedback] = useState<Record<string, "ok" | "fail">>({});
  const [showBusy, setShowBusy] = useState<Set<string>>(new Set());
  const [loadedPreset, setLoadedPreset] = useState<string | null>(null);


  useEffect(() => {
    let alive = true;
    (async () => {
      const [invRes, fishRes, merchRes, extraRes] = await Promise.all([
        callPy<{ presets?: string[] }>("get_automation_presets").catch(() => null),
        callPy<{ presets?: string[] }>("get_fishing_presets").catch(() => null),
        callPy<{ presets?: string[] }>("get_merchant_presets").catch(() => null),
        callPy<{ presets?: string[] }>("get_extra_presets").catch(() => null),
      ]);
      if (!alive) return;
      const invNames = invRes?.presets || [], fishNames = fishRes?.presets || [], merchNames = merchRes?.presets || [], extraNames = extraRes?.presets || [];
      const seen = new Set<string>(), allNames: string[] = [];
      [invNames, fishNames, merchNames, extraNames].forEach((names) => names.forEach((name) => { if (!seen.has(name)) { seen.add(name); allNames.push(name); } }));
      setPresets({ inv: invNames, fish: fishNames, merch: merchNames, extra: extraNames, global: allNames });
    })();
    return () => { alive = false; };
  }, []);

  const togglePanel = (id: string) =>
    setCollapsed((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });

  async function runCapture(name: string, ...args: unknown[]) {
    const response = await callPyWithTimeout<{ ok?: boolean; error?: string }>(
      CALIBRATION_RPC_TIMEOUT_MS,
      name,
      ...args,
    );
    if (response?.ok) applyState(await callPy<BackendState>("get_state"));
    return response;
  }

  async function loadGlobal(name: string) {
    if (running || !name) return;
    await Promise.all([
      callPy("load_automation_preset", name), callPy("load_fishing_preset", name),
      callPy("load_merchant_preset", name), callPy("load_extra_preset", name),
    ]);
    applyState(await callPy<BackendState>("get_state"));
    setLoadedPreset(name);
  }

  async function copyCalibration(scope: string) {
    const text = await callPy<string>("get_calibration_text", scope);
    if (!text) return;
    let copied = false;
    try { await navigator.clipboard.writeText(text); copied = true; } catch { copied = false; }
    setCopyFeedback((prev) => ({ ...prev, [scope]: copied ? "ok" : "fail" }));
    setTimeout(() => setCopyFeedback((prev) => { const next = { ...prev }; delete next[scope]; return next; }), 1600);
  }
  async function showPoints(scope: string) {
    if (running || showBusy.has(scope)) return;
    setShowBusy((prev) => new Set(prev).add(scope));
    await callPy("show_calibration_points", scope, 4.0).catch(() => {});
    setTimeout(() => setShowBusy((prev) => { const next = new Set(prev); next.delete(scope); return next; }), 4000);
  }

  const pixels = (automation.pixels as Record<string, Pos>) || {};
  const firstItemRegion = automation.firstItemRegion as Pos;
  const fishing = (automation.fishing as { pixels?: Record<string, Pos>; regions?: Record<string, Pos> }) || {};
  const merchCalib = ((automation.merchants as { calib?: Record<string, { pixels?: Record<string, Pos>; regions?: Record<string, Pos> }> })?.calib) || {};
  const extraCalib = (automation.calib as Record<string, { pixels?: Record<string, Pos>; regions?: Record<string, Pos> }>) || {};
  const autopopRegion = (automation.autopop as { amountRegion?: Pos })?.amountRegion;

  
  const invPixelSlots = PIXEL_SLOTS.filter(([key]) => key !== "first_item_slot");
  const invSetCount = (regionInfo(firstItemRegion).isSet ? 1 : 0) + invPixelSlots.filter(([key]) => pixelInfo(pixels[key]).isSet).length;
  const fishSetCount = FISHING_PIXEL_SLOTS.filter(([key]) => pixelInfo(fishing.pixels?.[key]).isSet).length;
  const merchProgress = (() => {
    let total = 0, set = 0;
    MERCHANT_CALIB_GROUPS.forEach((group) => {
      const calib = merchCalib[group.key] || {};
      group.points.forEach(([key]) => { total++; if (pixelInfo(calib.pixels?.[key]).isSet) set++; });
      group.regions.forEach(([key]) => { total++; if (regionInfo(calib.regions?.[key]).isSet) set++; });
    });
    return { total, set };
  })();
  const extraProgress = (group: CalibGroup) => {
    const calib = extraCalib[group.key] || {};
    let total = 0, set = 0;
    const countPixel = (key: string) => { total++; if (pixelInfo(calib.pixels?.[key]).isSet) set++; };
    const countRegion = (key: string) => { total++; if (regionInfo(calib.regions?.[key]).isSet) set++; };
    group.points.forEach(([key]) => countPixel(key));
    group.regions.forEach(([key]) => countRegion(key));
    (group.subgroups || []).forEach((subgroup) => { subgroup.points.forEach(([key]) => countPixel(key)); subgroup.regions.forEach(([key]) => countRegion(key)); });
    return { total, set };
  };

  
  
  
  const presetGaps: string[] = (() => {
    const gaps: string[] = [];
    if (!regionInfo(firstItemRegion).isSet) gaps.push("Inventory: First Item Slot");
    invPixelSlots.forEach(([key, label]) => { if (!pixelInfo(pixels[key]).isSet) gaps.push(`Inventory: ${label}`); });
    if (!regionInfo(autopopRegion).isSet) gaps.push("Auto Pop: Amount Label Region");
    FISHING_PIXEL_SLOTS.forEach(([key, label]) => { if (!pixelInfo(fishing.pixels?.[key]).isSet) gaps.push(`Fishing: ${label}`); });
    FISHING_REGION_SLOTS.forEach(([key, label]) => { if (!regionInfo(fishing.regions?.[key]).isSet) gaps.push(`Fishing: ${label} (OCR region)`); });
    MERCHANT_CALIB_GROUPS.forEach((group) => {
      const calib = merchCalib[group.key] || {};
      group.points.forEach(([key, label]) => { if (!pixelInfo(calib.pixels?.[key]).isSet) gaps.push(`${group.label}: ${label}`); });
      group.regions.forEach(([key, label]) => { if (!regionInfo(calib.regions?.[key]).isSet) gaps.push(`${group.label}: ${label}`); });
    });
    EXTRA_CALIB_GROUPS.forEach((group) => {
      const calib = extraCalib[group.key] || {};
      group.points.forEach(([key, label]) => { if (!pixelInfo(calib.pixels?.[key]).isSet) gaps.push(`${group.label}: ${label}`); });
      group.regions.forEach(([key, label]) => { if (!regionInfo(calib.regions?.[key]).isSet) gaps.push(`${group.label}: ${label}`); });
      (group.subgroups || []).forEach((subgroup) => {
        subgroup.points.forEach(([key, label]) => { if (!pixelInfo(calib.pixels?.[key]).isSet) gaps.push(`${group.label} · ${subgroup.label}: ${label}`); });
        subgroup.regions.forEach(([key, label]) => { if (!regionInfo(calib.regions?.[key]).isSet) gaps.push(`${group.label} · ${subgroup.label}: ${label}`); });
      });
    });
    return gaps;
  })();

  return (
    <section className="tab active-tab" id="calibration">
      <header className="page-head">
        <h1>Calibration</h1>
        <p>Set every needed coordinate for the macro here.</p>
      </header>

      {}
      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-layer-group"></i> Load preset</div>
        </div>
        <div className="afk-setting">
          <div className="afk-setting-info">
            <span className="afk-setting-name">Resolution preset</span>
            <span className="afk-setting-desc">Pick your resolution, scale and window mode, then load. Applied to every calibration panel at once. Fine-tune each panel below.</span>
          </div>
          <PresetPicker presetNames={presets.global} disabled={running} onLoad={(name) => void loadGlobal(name)} />
        </div>
        {loadedPreset && presetGaps.length > 0 && (
          <div className="glass-warning auto-note" style={{ marginTop: 10 }} data-reveal>
            <i className="fa-solid fa-triangle-exclamation"></i>
            <div>
              <p style={{ margin: 0 }}>
                <b>{loadedPreset}</b> doesn't cover {presetGaps.length} setting{presetGaps.length === 1 ? "" : "s"}.
                Set {presetGaps.length === 1 ? "it" : "them"} manually in the panels below for now, missing presets get
                patched in a future update.
              </p>
              <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 6 }}>
                {presetGaps.map((gap) => (
                  <span key={gap} className="badge badge-soft" style={{ fontSize: 11 }}>{gap}</span>
                ))}
              </div>
            </div>
          </div>
        )}
        <div className="calib-foot">
          <p className="pixel-hint"><i className="fa-solid fa-clipboard"></i> Copy every panel's calibration to clipboard at once.</p>
          <CopyButton state={copyFeedback.all} onClick={() => void copyCalibration("all")} label="Copy all calibrations" />
        </div>
      </div>

      {}
      <div className="calib-grid">
      <CalibPanel
        icon="fa-solid fa-boxes-stacked" title="Inventory Calibrations" badge={`${invSetCount}/${invPixelSlots.length + 1} set`}
        collapsed={collapsed.has("inv")} onToggle={() => togglePanel("inv")}
        showBusy={showBusy.has("automation")} onShow={() => void showPoints("automation")}
        copyHint={<>Click <b>Set</b>, switch to Roblox and click the exact spot. For <b>First Item Slot</b>: click <b>top-left</b> then <b>bottom-right</b>.</>}
        copyState={copyFeedback.automation} onCopy={() => void copyCalibration("automation")}
      >
        <div className="pixel-list">
          <CaptureRow label="First Item Slot (Region)" region {...regionInfo(firstItemRegion)} disabled={running} onCapture={() => runCapture("capture_item_region")} />
          {invPixelSlots.map(([key, label]) => (
            <CaptureRow key={key} label={label} {...pixelInfo(pixels[key])} disabled={running} onCapture={() => runCapture("capture_pixel", key)} />
          ))}
        </div>
        <div className="afk-divider"></div>
        <div className="px-section-label"><i className="fa-solid fa-vector-square"></i> Auto Pop: Amount Label <span className="ap-required">required for Auto Pop</span></div>
        <div className="pixel-list">
          <CaptureRow label="Amount Label Region" region {...regionInfo(autopopRegion)} disabled={running} onCapture={() => runCapture("capture_autopop_amount_region")} />
        </div>
      </CalibPanel>

      {}
      <CalibPanel
        icon="fa-solid fa-fish" title="Fishing Calibrations" badge={`${fishSetCount}/${FISHING_PIXEL_SLOTS.length} set`}
        collapsed={collapsed.has("fish")} onToggle={() => togglePanel("fish")}
        showBusy={showBusy.has("fishing")} onShow={() => void showPoints("fishing")}
        copyHint={<>Click <b>Set</b>, switch to Roblox and click <b>top-left</b> then <b>bottom-right</b> of the text area.</>}
        copyState={copyFeedback.fishing} onCopy={() => void copyCalibration("fishing")}
      >
        <div className="pixel-list">
          {FISHING_PIXEL_SLOTS.map(([key, label]) => (
            <CaptureRow key={key} label={label} {...pixelInfo(fishing.pixels?.[key])} disabled={running} onCapture={() => runCapture("capture_fishing_pixel", key)} />
          ))}
        </div>
        <div className="afk-divider"></div>
        <div className="px-section-label"><i className="fa-solid fa-vector-square"></i> OCR Regions</div>
        <div className="pixel-list">
          {FISHING_REGION_SLOTS.map(([key, label]) => (
            <CaptureRow key={key} label={label} region {...regionInfo(fishing.regions?.[key])} disabled={running} onCapture={() => runCapture("capture_fishing_region", key)} />
          ))}
        </div>
      </CalibPanel>

      {}
      <CalibPanel
        icon="fa-solid fa-store" title="Merchant Calibrations" badge={`${merchProgress.set}/${merchProgress.total} set`}
        collapsed={collapsed.has("merch")} onToggle={() => togglePanel("merch")}
        showBusy={showBusy.has("merchants")} onShow={() => void showPoints("merchants")}
        copyHint={<>For <b>points</b>: click <b>Set</b>, then click the spot in Roblox. For <b>regions</b>: click <b>top-left</b> then <b>bottom-right</b>.</>}
        copyState={copyFeedback.merchants} onCopy={() => void copyCalibration("merchants")}
      >
        <div className="inline-note">
          <i className="fa-solid fa-circle-info"></i>
          <span><b>General</b> is shared by every merchant. <b>Mari</b>, <b>Jester</b> and <b>Rin</b> each have their own dialogue buttons.</span>
        </div>
        {MERCHANT_CALIB_GROUPS.map((group, index) => (
          <div key={group.key}>
            {index > 0 && <div className="afk-divider"></div>}
            <div className="px-section-label"><i className="fa-solid fa-layer-group"></i> {group.label}<span className="px-scope-hint">{group.scope}</span></div>
            <div className="pixel-list">
              {group.points.map(([key, label]) => (
                <CaptureRow key={key} label={label} {...pixelInfo(merchCalib[group.key]?.pixels?.[key])} disabled={running} onCapture={() => runCapture("capture_merchant_pixel", group.key, key)} />
              ))}
              {group.regions.map(([key, label]) => (
                <CaptureRow key={key} label={label} region {...regionInfo(merchCalib[group.key]?.regions?.[key])} disabled={running} onCapture={() => runCapture("capture_merchant_region", group.key, key)} />
              ))}
            </div>
          </div>
        ))}
      </CalibPanel>

      {}
      {EXTRA_CALIB_GROUPS.map((group) => {
        const progress = extraProgress(group);
        const calib = extraCalib[group.key] || {};
        const pixelRow = (key: string, label: string) => (
          <CaptureRow key={key} label={label} {...pixelInfo(calib.pixels?.[key])} disabled={running} onCapture={() => runCapture("capture_extra_pixel", group.key, key)} />
        );
        const regionRow = (key: string, label: string) => (
          <CaptureRow key={key} label={label} region {...regionInfo(calib.regions?.[key])} disabled={running} onCapture={() => runCapture("capture_extra_region", group.key, key)} />
        );
        return (
          <CalibPanel
            key={group.key} icon={group.icon || "fa-solid fa-sliders"} title={`${group.label} Calibrations`} badge={`${progress.set}/${progress.total} set`}
            collapsed={collapsed.has(group.key)} onToggle={() => togglePanel(group.key)}
            showBusy={showBusy.has(group.key)} onShow={() => void showPoints(group.key)}
            copyHint={<>Click <b>Set</b>, switch to Roblox and click the spot. For <b>regions</b> click <b>top-left</b> then <b>bottom-right</b>.</>}
            copyState={copyFeedback[group.key]} onCopy={() => void copyCalibration(group.key)}
          >
            {group.points.length > 0 && <div className="pixel-list">{group.points.map(([key, label]) => pixelRow(key, label))}</div>}
            {group.regions.length > 0 && (
              <>
                {group.points.length > 0 && <><div className="afk-divider"></div><div className="px-section-label"><i className="fa-solid fa-vector-square"></i> OCR Regions</div></>}
                <div className="pixel-list">{group.regions.map(([key, label]) => regionRow(key, label))}</div>
              </>
            )}
            {(group.subgroups || []).map((subgroup) => (
              <div key={subgroup.key}>
                <div className="afk-divider"></div>
                <div className="px-section-label"><i className="fa-solid fa-layer-group"></i> {subgroup.label}<span className="px-scope-hint">{group.label}</span></div>
                <div className="pixel-list">{subgroup.points.map(([key, label]) => pixelRow(key, label))}</div>
                {subgroup.regions.length > 0 && (
                  <>
                    <div className="afk-divider"></div>
                    <div className="px-section-label"><i className="fa-solid fa-vector-square"></i> OCR Regions</div>
                    <div className="pixel-list">{subgroup.regions.map(([key, label]) => regionRow(key, label))}</div>
                  </>
                )}
              </div>
            ))}
          </CalibPanel>
        );
      })}
      </div>

      {}
      <div className="tab-section" data-reveal>
        <div className="tab-section-head"><i className="fa-solid fa-eye"></i><h2>OCR</h2></div>
        <div className="glass card panel" data-reveal>
          <div className="panel-head">
            <div className="panel-title"><i className="fa-solid fa-eye"></i> Tesseract Status</div>
            <span className="badge badge-soft">{ocrAvailable == null ? "checking…" : ocrAvailable ? "Tesseract ready" : "OCR not found"}</span>
          </div>
          <p className="section-hint">
            OCR failsafes are configured per module in the <b>Module Builder</b> (gear on each chip).
            Without Tesseract they stay locked, and Merchant Detection can't be enabled.
          </p>
          {ocrAvailable === false && (
            <div className="glass-warning auto-note">
              <i className="fa-solid fa-triangle-exclamation"></i>
              <p>Tesseract not detected. Install it with one click, no manual setup needed.</p>
              <TesseractInstallButton />
            </div>
          )}
        </div>
      </div>
    </section>
  );
}



function CopyButton({ state, onClick, label }: { state?: "ok" | "fail"; onClick: () => void; label: string }) {
  return (
    <button className="btn-show" onClick={onClick}>
      {state === "ok" ? <><i className="fa-solid fa-check"></i> Copied!</> : state === "fail" ? <><i className="fa-solid fa-xmark"></i> Failed</> : <><i className="fa-solid fa-clipboard"></i> {label}</>}
    </button>
  );
}

function CalibPanel(props: {
  icon: string; title: string; badge: string;
  collapsed: boolean; onToggle: () => void;
  showBusy: boolean; onShow: () => void;
  copyHint: ReactNode; copyState?: "ok" | "fail"; onCopy: () => void;
  children: ReactNode;
}) {
  return (
    <div className={`glass card panel calib-panel${props.collapsed ? " collapsed" : ""}`} data-reveal>
      <div className="panel-head calib-toggle" onClick={props.onToggle}>
        <div className="panel-title"><i className={props.icon}></i> {props.title}</div>
        <div className="calib-head-right">
          <button className="calib-show-btn" disabled={props.showBusy} onClick={(e) => { e.stopPropagation(); props.onShow(); }} title="Show on screen"><i className="fa-solid fa-eye"></i></button>
          <span className="badge badge-soft">{props.badge}</span>
          <i className="fa-solid fa-chevron-down calib-chevron"></i>
        </div>
      </div>
      <div className="calib-body">
        {props.children}
        <div className="calib-foot">
          <p className="pixel-hint"><i className="fa-solid fa-hand-pointer"></i> {props.copyHint}</p>
          <CopyButton state={props.copyState} onClick={props.onCopy} label="Copy calibration" />
        </div>
      </div>
    </div>
  );
}
