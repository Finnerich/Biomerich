import { useEffect, useState, type ReactNode } from "react";
import { useStore } from "../store";
import { callPy } from "../bridge";
import { CaptureRow } from "../components/CaptureRow";
import { PresetPicker } from "../components/PresetPicker";
import { PIXEL_SLOTS, FISHING_PIXEL_SLOTS, FISHING_REGION_SLOTS } from "../data/slots";
import { MERCHANT_CALIB_GROUPS, EXTRA_CALIB_GROUPS, type CalibGroup } from "../data/calibGroups";
import { TesseractInstallButton } from "../components/TesseractInstallButton";
import type { BackendState } from "../types";

type Pos = number[] | undefined;
const pixelInfo = (p: Pos) => {
  const isSet = Array.isArray(p) && p.length === 2;
  return { isSet, coord: isSet ? `${p![0]}, ${p![1]}` : "Not set" };
};
const regionInfo = (b: Pos) => {
  const isSet = Array.isArray(b) && b.length === 4;
  return { isSet, coord: isSet ? `${b![0]},${b![1]} · ${b![2]}×${b![3]}` : "Not set" };
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
  const [copyFb, setCopyFb] = useState<Record<string, "ok" | "fail">>({});
  const [showBusy, setShowBusy] = useState<Set<string>>(new Set());
  const [loadedPreset, setLoadedPreset] = useState<string | null>(null);


  useEffect(() => {
    let alive = true;
    (async () => {
      const [inv, fish, merch, extra] = await Promise.all([
        callPy<{ presets?: string[] }>("get_automation_presets").catch(() => null),
        callPy<{ presets?: string[] }>("get_fishing_presets").catch(() => null),
        callPy<{ presets?: string[] }>("get_merchant_presets").catch(() => null),
        callPy<{ presets?: string[] }>("get_extra_presets").catch(() => null),
      ]);
      if (!alive) return;
      const invNames = inv?.presets || [], fishNames = fish?.presets || [], merchNames = merch?.presets || [], extraNames = extra?.presets || [];
      const seen = new Set<string>(), allNames: string[] = [];
      [invNames, fishNames, merchNames, extraNames].forEach((names) => names.forEach((name) => { if (!seen.has(name)) { seen.add(name); allNames.push(name); } }));
      setPresets({ inv: invNames, fish: fishNames, merch: merchNames, extra: extraNames, global: allNames });
    })();
    return () => { alive = false; };
  }, []);

  const toggle = (id: string) =>
    setCollapsed((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  async function runCapture(name: string, ...args: unknown[]) {
    const res = await callPy<{ ok?: boolean; error?: string }>(name, ...args);
    if (res?.ok) applyState(await callPy<BackendState>("get_state"));
    return res;
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
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; } catch { ok = false; }
    setCopyFb((p) => ({ ...p, [scope]: ok ? "ok" : "fail" }));
    setTimeout(() => setCopyFb((p) => { const n = { ...p }; delete n[scope]; return n; }), 1600);
  }
  async function showPoints(scope: string) {
    if (running || showBusy.has(scope)) return;
    setShowBusy((p) => new Set(p).add(scope));
    await callPy("show_calibration_points", scope, 4.0).catch(() => {});
    setTimeout(() => setShowBusy((p) => { const n = new Set(p); n.delete(scope); return n; }), 4000);
  }

  const pixels = (automation.pixels as Record<string, Pos>) || {};
  const firstItemRegion = automation.firstItemRegion as Pos;
  const fishing = (automation.fishing as { pixels?: Record<string, Pos>; regions?: Record<string, Pos> }) || {};
  const merchCalib = ((automation.merchants as { calib?: Record<string, { pixels?: Record<string, Pos>; regions?: Record<string, Pos> }> })?.calib) || {};
  const extraCalib = (automation.calib as Record<string, { pixels?: Record<string, Pos>; regions?: Record<string, Pos> }>) || {};
  const autopopRegion = (automation.autopop as { amountRegion?: Pos })?.amountRegion;

  const invNormal = PIXEL_SLOTS.filter(([k]) => k !== "first_item_slot");
  const invSet = (regionInfo(firstItemRegion).isSet ? 1 : 0) + invNormal.filter(([k]) => pixelInfo(pixels[k]).isSet).length;
  const fishSet = FISHING_PIXEL_SLOTS.filter(([k]) => pixelInfo(fishing.pixels?.[k]).isSet).length;
  const merchCount = (() => {
    let total = 0, set = 0;
    MERCHANT_CALIB_GROUPS.forEach((g) => {
      const calib = merchCalib[g.key] || {};
      g.points.forEach(([k]) => { total++; if (pixelInfo(calib.pixels?.[k]).isSet) set++; });
      g.regions.forEach(([k]) => { total++; if (regionInfo(calib.regions?.[k]).isSet) set++; });
    });
    return { total, set };
  })();
  const extraCount = (g: CalibGroup) => {
    const calib = extraCalib[g.key] || {};
    let total = 0, set = 0;
    const pt = (k: string) => { total++; if (pixelInfo(calib.pixels?.[k]).isSet) set++; };
    const rg = (k: string) => { total++; if (regionInfo(calib.regions?.[k]).isSet) set++; };
    g.points.forEach(([k]) => pt(k));
    g.regions.forEach(([k]) => rg(k));
    (g.subgroups || []).forEach((sg) => { sg.points.forEach(([k]) => pt(k)); sg.regions.forEach(([k]) => rg(k)); });
    return { total, set };
  };

  
  
  
  const presetGaps: string[] = (() => {
    const out: string[] = [];
    if (!regionInfo(firstItemRegion).isSet) out.push("Inventory: First Item Slot");
    invNormal.forEach(([k, label]) => { if (!pixelInfo(pixels[k]).isSet) out.push(`Inventory: ${label}`); });
    if (!regionInfo(autopopRegion).isSet) out.push("Auto Pop: Amount Label Region");
    FISHING_PIXEL_SLOTS.forEach(([k, label]) => { if (!pixelInfo(fishing.pixels?.[k]).isSet) out.push(`Fishing: ${label}`); });
    FISHING_REGION_SLOTS.forEach(([k, label]) => { if (!regionInfo(fishing.regions?.[k]).isSet) out.push(`Fishing: ${label} (OCR region)`); });
    MERCHANT_CALIB_GROUPS.forEach((g) => {
      const c = merchCalib[g.key] || {};
      g.points.forEach(([k, label]) => { if (!pixelInfo(c.pixels?.[k]).isSet) out.push(`${g.label}: ${label}`); });
      g.regions.forEach(([k, label]) => { if (!regionInfo(c.regions?.[k]).isSet) out.push(`${g.label}: ${label}`); });
    });
    EXTRA_CALIB_GROUPS.forEach((g) => {
      const c = extraCalib[g.key] || {};
      g.points.forEach(([k, label]) => { if (!pixelInfo(c.pixels?.[k]).isSet) out.push(`${g.label}: ${label}`); });
      g.regions.forEach(([k, label]) => { if (!regionInfo(c.regions?.[k]).isSet) out.push(`${g.label}: ${label}`); });
      (g.subgroups || []).forEach((sg) => {
        sg.points.forEach(([k, label]) => { if (!pixelInfo(c.pixels?.[k]).isSet) out.push(`${g.label} · ${sg.label}: ${label}`); });
        sg.regions.forEach(([k, label]) => { if (!regionInfo(c.regions?.[k]).isSet) out.push(`${g.label} · ${sg.label}: ${label}`); });
      });
    });
    return out;
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
                {presetGaps.map((g) => (
                  <span key={g} className="badge badge-soft" style={{ fontSize: 11 }}>{g}</span>
                ))}
              </div>
            </div>
          </div>
        )}
        <div className="calib-foot">
          <p className="pixel-hint"><i className="fa-solid fa-clipboard"></i> Copy every panel's calibration to clipboard at once.</p>
          <CopyButton state={copyFb.all} onClick={() => void copyCalibration("all")} label="Copy all calibrations" />
        </div>
      </div>

      {}
      <div className="calib-grid">
      <CalibPanel
        icon="fa-solid fa-boxes-stacked" title="Inventory Calibrations" badge={`${invSet}/${invNormal.length + 1} set`}
        collapsed={collapsed.has("inv")} onToggle={() => toggle("inv")}
        showBusy={showBusy.has("automation")} onShow={() => void showPoints("automation")}
        copyHint={<>Click <b>Set</b>, switch to Roblox and click the exact spot. For <b>First Item Slot</b>: click <b>top-left</b> then <b>bottom-right</b>.</>}
        copyState={copyFb.automation} onCopy={() => void copyCalibration("automation")}
      >
        <div className="pixel-list">
          <CaptureRow label="First Item Slot (Region)" region {...regionInfo(firstItemRegion)} disabled={running} onCapture={() => runCapture("capture_item_region")} />
          {invNormal.map(([k, label]) => (
            <CaptureRow key={k} label={label} {...pixelInfo(pixels[k])} disabled={running} onCapture={() => runCapture("capture_pixel", k)} />
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
        icon="fa-solid fa-fish" title="Fishing Calibrations" badge={`${fishSet}/${FISHING_PIXEL_SLOTS.length} set`}
        collapsed={collapsed.has("fish")} onToggle={() => toggle("fish")}
        showBusy={showBusy.has("fishing")} onShow={() => void showPoints("fishing")}
        copyHint={<>Click <b>Set</b>, switch to Roblox and click <b>top-left</b> then <b>bottom-right</b> of the text area.</>}
        copyState={copyFb.fishing} onCopy={() => void copyCalibration("fishing")}
      >
        <div className="pixel-list">
          {FISHING_PIXEL_SLOTS.map(([k, label]) => (
            <CaptureRow key={k} label={label} {...pixelInfo(fishing.pixels?.[k])} disabled={running} onCapture={() => runCapture("capture_fishing_pixel", k)} />
          ))}
        </div>
        <div className="afk-divider"></div>
        <div className="px-section-label"><i className="fa-solid fa-vector-square"></i> OCR Regions</div>
        <div className="pixel-list">
          {FISHING_REGION_SLOTS.map(([k, label]) => (
            <CaptureRow key={k} label={label} region {...regionInfo(fishing.regions?.[k])} disabled={running} onCapture={() => runCapture("capture_fishing_region", k)} />
          ))}
        </div>
      </CalibPanel>

      {}
      <CalibPanel
        icon="fa-solid fa-store" title="Merchant Calibrations" badge={`${merchCount.set}/${merchCount.total} set`}
        collapsed={collapsed.has("merch")} onToggle={() => toggle("merch")}
        showBusy={showBusy.has("merchants")} onShow={() => void showPoints("merchants")}
        copyHint={<>For <b>points</b>: click <b>Set</b>, then click the spot in Roblox. For <b>regions</b>: click <b>top-left</b> then <b>bottom-right</b>.</>}
        copyState={copyFb.merchants} onCopy={() => void copyCalibration("merchants")}
      >
        <div className="inline-note">
          <i className="fa-solid fa-circle-info"></i>
          <span><b>General</b> is shared by every merchant. <b>Mari</b>, <b>Jester</b> and <b>Rin</b> each have their own dialogue buttons.</span>
        </div>
        {MERCHANT_CALIB_GROUPS.map((g, idx) => (
          <div key={g.key}>
            {idx > 0 && <div className="afk-divider"></div>}
            <div className="px-section-label"><i className="fa-solid fa-layer-group"></i> {g.label}<span className="px-scope-hint">{g.scope}</span></div>
            <div className="pixel-list">
              {g.points.map(([k, label]) => (
                <CaptureRow key={k} label={label} {...pixelInfo(merchCalib[g.key]?.pixels?.[k])} disabled={running} onCapture={() => runCapture("capture_merchant_pixel", g.key, k)} />
              ))}
              {g.regions.map(([k, label]) => (
                <CaptureRow key={k} label={label} region {...regionInfo(merchCalib[g.key]?.regions?.[k])} disabled={running} onCapture={() => runCapture("capture_merchant_region", g.key, k)} />
              ))}
            </div>
          </div>
        ))}
      </CalibPanel>

      {}
      {EXTRA_CALIB_GROUPS.map((g) => {
        const count = extraCount(g);
        const calib = extraCalib[g.key] || {};
        const ptRow = (k: string, label: string) => (
          <CaptureRow key={k} label={label} {...pixelInfo(calib.pixels?.[k])} disabled={running} onCapture={() => runCapture("capture_extra_pixel", g.key, k)} />
        );
        const rgRow = (k: string, label: string) => (
          <CaptureRow key={k} label={label} region {...regionInfo(calib.regions?.[k])} disabled={running} onCapture={() => runCapture("capture_extra_region", g.key, k)} />
        );
        return (
          <CalibPanel
            key={g.key} icon={g.icon || "fa-solid fa-sliders"} title={`${g.label} Calibrations`} badge={`${count.set}/${count.total} set`}
            collapsed={collapsed.has(g.key)} onToggle={() => toggle(g.key)}
            showBusy={showBusy.has(g.key)} onShow={() => void showPoints(g.key)}
            copyHint={<>Click <b>Set</b>, switch to Roblox and click the spot. For <b>regions</b> click <b>top-left</b> then <b>bottom-right</b>.</>}
            copyState={copyFb[g.key]} onCopy={() => void copyCalibration(g.key)}
          >
            {g.points.length > 0 && <div className="pixel-list">{g.points.map(([k, l]) => ptRow(k, l))}</div>}
            {g.regions.length > 0 && (
              <>
                {g.points.length > 0 && <><div className="afk-divider"></div><div className="px-section-label"><i className="fa-solid fa-vector-square"></i> OCR Regions</div></>}
                <div className="pixel-list">{g.regions.map(([k, l]) => rgRow(k, l))}</div>
              </>
            )}
            {(g.subgroups || []).map((sg) => (
              <div key={sg.key}>
                <div className="afk-divider"></div>
                <div className="px-section-label"><i className="fa-solid fa-layer-group"></i> {sg.label}<span className="px-scope-hint">{g.label}</span></div>
                <div className="pixel-list">{sg.points.map(([k, l]) => ptRow(k, l))}</div>
                {sg.regions.length > 0 && (
                  <>
                    <div className="afk-divider"></div>
                    <div className="px-section-label"><i className="fa-solid fa-vector-square"></i> OCR Regions</div>
                    <div className="pixel-list">{sg.regions.map(([k, l]) => rgRow(k, l))}</div>
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
