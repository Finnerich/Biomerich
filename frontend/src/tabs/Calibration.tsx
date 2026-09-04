






import { useEffect, useState, type ReactNode } from "react";
import { useStore } from "../store";
import { callPy, callPyWithTimeout } from "../bridge";
import { CaptureRow } from "../components/CaptureRow";
import { PresetPicker } from "../components/PresetPicker";
import { CustomSelect } from "../components/CustomSelect";
import { PIXEL_SLOTS, FISHING_PIXEL_SLOTS, FISHING_REGION_SLOTS } from "../data/slots";
import { MERCHANT_CALIB_GROUPS, EXTRA_CALIB_GROUPS, type CalibGroup } from "../data/calibGroups";
import { TesseractInstallButton } from "../components/TesseractInstallButton";
import { Modal } from "../components/Modal";
import type { BackendState } from "../types";



type Pos = number[] | undefined;
type DetectedMonitor = {
  id: number;
  device: string;
  width: number;
  height: number;
  aspectRatio: string;
  scale: number;
  dpi: number;
  primary: boolean;
  robloxWindows: number;
};
type DisplayCalibrationInfo = {
  ok: boolean;
  error?: string | null;
  monitors: DetectedMonitor[];
  target?: {
    displayId: number;
    width: number;
    height: number;
    aspectRatio: string;
    x: number;
    y: number;
    scale: number;
    mode: "WINDOWED" | "FULLSCREEN";
    source: "roblox" | "primary";
    robloxWindows: number;
  } | null;
  preset?: string | null;
  match?: {
    name: string;
    strategy: "absolute";
    sourceWidth: number;
    sourceHeight: number;
    targetWidth: number;
    targetHeight: number;
    aspectRatio: string;
    scaled: boolean;
  } | null;
  reason?: "no_preset" | "mixed_displays" | "unsupported" | null;
};
type RecommendationFeedback = { kind: "success" | "warning" | "error"; text: string } | null;
type CalibrationImportReport = {
  ok: boolean;
  canApply: boolean;
  validCount: number;
  expectedCount: number;
  missing: string[];
  invalid: string[];
  unknown: string[];
  error?: string | null;
  message?: string | null;
  appliedCount?: number;
};
type CalibrationTestState = "idle" | "starting" | "active" | "stopping" | "error";
const CALIBRATION_TEST_SCOPES = [
  { value: "automation", label: "Inventory & Auto Pop" },
  { value: "fishing", label: "Fishing" },
  { value: "merchants", label: "Merchants" },
  ...EXTRA_CALIB_GROUPS.map((group) => ({ value: group.key, label: group.label })),
  { value: "all", label: "All calibrations" },
];
const CALIBRATION_RPC_TIMEOUT_MS = 70_000;
const pixelInfo = (pos: Pos) => {
  const isSet = Array.isArray(pos) && pos.length === 2;
  return { isSet, value: isSet ? pos : undefined, coord: isSet ? `${pos![0]}, ${pos![1]}` : "Not set" };
};
const regionInfo = (box: Pos) => {
  const isSet = Array.isArray(box) && box.length === 4;
  return { isSet, value: isSet ? box : undefined, coord: isSet ? `${box![0]},${box![1]} · ${box![2]}×${box![3]}` : "Not set" };
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
  const [displayInfo, setDisplayInfo] = useState<DisplayCalibrationInfo | null>(null);
  const [displayBusy, setDisplayBusy] = useState(true);
  const [recommendationFeedback, setRecommendationFeedback] = useState<RecommendationFeedback>(null);
  const [testScope, setTestScope] = useState("automation");
  const [testState, setTestState] = useState<CalibrationTestState>("idle");
  const [testMessage, setTestMessage] = useState("Choose a module to preview its saved targets.");
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [importReport, setImportReport] = useState<CalibrationImportReport | null>(null);
  const [importBusy, setImportBusy] = useState(false);


  useEffect(() => {
    let alive = true;
    (async () => {
      const [invRes, fishRes, merchRes, extraRes, displayRes] = await Promise.all([
        callPy<{ presets?: string[] }>("get_automation_presets").catch(() => null),
        callPy<{ presets?: string[] }>("get_fishing_presets").catch(() => null),
        callPy<{ presets?: string[] }>("get_merchant_presets").catch(() => null),
        callPy<{ presets?: string[] }>("get_extra_presets").catch(() => null),
        callPy<DisplayCalibrationInfo>("get_display_calibration_info").catch(() => null),
      ]);
      if (!alive) return;
      const invNames = invRes?.presets || [], fishNames = fishRes?.presets || [], merchNames = merchRes?.presets || [], extraNames = extraRes?.presets || [];
      const seen = new Set<string>(), allNames: string[] = [];
      [invNames, fishNames, merchNames, extraNames].forEach((names) => names.forEach((name) => { if (!seen.has(name)) { seen.add(name); allNames.push(name); } }));
      setPresets({ inv: invNames, fish: fishNames, merch: merchNames, extra: extraNames, global: allNames });
      setDisplayInfo(displayRes);
      setDisplayBusy(false);
    })();
    return () => { alive = false; };
  }, []);

  useEffect(() => () => {
    void callPy("stop_calibration_test").catch(() => {});
  }, []);

  useEffect(() => {
    if (!running) return;
    void callPy("stop_calibration_test").catch(() => {});
    setTestState("idle");
    setTestMessage("Test Mode stops automatically when the macro starts.");
  }, [running]);

  const togglePanel = (id: string) =>
    setCollapsed((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });

  async function runCapture(name: string, ...args: unknown[]) {
    if (testState === "active") await stopCalibrationTest(true);
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
    if (testState === "active") await stopCalibrationTest(true);
    await Promise.all([
      callPy("load_automation_preset", name), callPy("load_fishing_preset", name),
      callPy("load_merchant_preset", name), callPy("load_extra_preset", name),
    ]);
    applyState(await callPy<BackendState>("get_state"));
    setLoadedPreset(name);
  }

  async function applyRecommendedPreset() {
    if (running || displayBusy) return;
    setDisplayBusy(true);
    setRecommendationFeedback(null);
    const result = await callPy<DisplayCalibrationInfo>("get_display_calibration_info").catch(() => null);
    setDisplayInfo(result);

    if (!result?.ok) {
      setRecommendationFeedback({ kind: "error", text: "SolRich couldn't read your display setup." });
    } else if (result.reason === "mixed_displays") {
      setRecommendationFeedback({
        kind: "warning",
        text: "Your Roblox windows use different display setups. Choose a preset manually.",
      });
    } else if (!result.preset) {
      setRecommendationFeedback({
        kind: "warning",
        text: "Your resolution doesn't have a preset right now.",
      });
    } else {
      try {
        const applied = await callPy<DisplayCalibrationInfo>("apply_recommended_calibration_preset");
        if (!applied?.ok || !applied.preset) throw new Error("preset apply failed");
        setDisplayInfo(applied);
        applyState(await callPy<BackendState>("get_state"));
        setLoadedPreset(applied.preset);
        setRecommendationFeedback({
          kind: "success",
          text: `Applied ${applied.preset}`,
        });
      } catch {
        setRecommendationFeedback({ kind: "error", text: "The recommended preset couldn't be applied." });
      }
    }
    setDisplayBusy(false);
  }

  async function startCalibrationTest() {
    if (running || testState === "starting" || testState === "stopping") return;
    if (testState === "active") {
      await stopCalibrationTest();
      return;
    }

    setTestState("starting");
    setTestMessage("Preparing the preview…");
    const result = await callPy<{
      ok?: boolean;
      error?: string;
      count?: number;
      points?: number;
      regions?: number;
    }>("start_calibration_test", testScope).catch(() => null);

    if (result?.ok) {
      const points = Number(result.points) || 0;
      const regions = Number(result.regions) || 0;
      setTestState("active");
      setTestMessage(`Showing ${points} point${points === 1 ? "" : "s"} and ${regions} region${regions === 1 ? "" : "s"}. No clicks are being performed.`);
    } else if (result?.error === "no_points") {
      setTestState("error");
      setTestMessage("This module has no saved calibration targets yet.");
    } else if (result?.error === "tracking_active") {
      setTestState("error");
      setTestMessage("Stop the macro before starting Calibration Test Mode.");
    } else {
      setTestState("error");
      setTestMessage("The calibration preview couldn't be opened.");
    }
  }

  async function stopCalibrationTest(silent = false) {
    setTestState("stopping");
    const result = await callPy<{ ok?: boolean }>("stop_calibration_test").catch(() => null);
    if (result?.ok) {
      setTestState("idle");
      setTestMessage(silent ? "Choose a module to preview its saved targets." : "Calibration preview stopped.");
    } else {
      setTestState("error");
      setTestMessage("The calibration preview couldn't be closed.");
    }
  }

  async function copyCalibration(scope: string) {
    const text = await callPy<string>("get_calibration_text", scope);
    if (!text) return;
    let copied = false;
    try { await navigator.clipboard.writeText(text); copied = true; } catch { copied = false; }
    setCopyFeedback((prev) => ({ ...prev, [scope]: copied ? "ok" : "fail" }));
    setTimeout(() => setCopyFeedback((prev) => { const next = { ...prev }; delete next[scope]; return next; }), 1600);
  }

  async function saveManualCalibration(scope: string, key: string, value: number[], group?: string) {
    const result = await callPy<{ ok?: boolean; error?: string }>("set_calibration_value", scope, key, value, group ?? null).catch(() => null);
    if (result?.ok) applyState(await callPy<BackendState>("get_state"));
    return result;
  }

  async function openCalibrationImport() {
    setImportOpen(true);
    setImportReport(null);
    try {
      const clipboard = await navigator.clipboard.readText();
      if (clipboard.trim()) setImportText(clipboard);
    } catch {
      
    }
  }

  async function checkCalibrationImport() {
    if (!importText.trim()) return;
    setImportBusy(true);
    const report = await callPy<CalibrationImportReport>("preview_calibration_import", importText).catch(() => null);
    setImportReport(report ?? {
      ok: false, canApply: false, validCount: 0, expectedCount: 0,
      missing: [], invalid: [], unknown: [], message: "SolRich could not validate this text.",
    });
    setImportBusy(false);
  }

  async function applyCalibrationImport() {
    if (!importReport?.canApply || importBusy) return false;
    setImportBusy(true);
    const report = await callPy<CalibrationImportReport>("apply_calibration_import", importText).catch(() => null);
    if (report?.ok) applyState(await callPy<BackendState>("get_state"));
    setImportReport(report ?? {
      ok: false, canApply: false, validCount: 0, expectedCount: 0,
      missing: [], invalid: [], unknown: [], message: "SolRich could not import this text.",
    });
    setImportBusy(false);
    return false;
  }
  async function showPoints(scope: string) {
    if (running || showBusy.has(scope)) return;
    if (testState === "active") await stopCalibrationTest(true);
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
        <div className="calib-display-detect">
          <div className="calib-display-head">
            <div>
              <span className="afk-setting-name">Detected displays</span>
              <span className="afk-setting-desc">SolRich reads resolution, aspect ratio and Windows scale for every connected screen.</span>
            </div>
            <button
              className="btn-add calib-recommend-btn"
              disabled={running || displayBusy}
              onClick={() => void applyRecommendedPreset()}
            >
              <i className={`fa-solid ${displayBusy ? "fa-spinner fa-spin" : "fa-wand-magic-sparkles"}`}></i>
              {displayBusy ? "Checking displays…" : "Get recommended preset"}
            </button>
          </div>

          <div className="calib-monitor-grid">
            {displayBusy && !displayInfo && (
              <div className="calib-monitor-empty"><i className="fa-solid fa-spinner fa-spin"></i> Detecting your displays…</div>
            )}
            {!displayBusy && displayInfo?.monitors.length === 0 && (
              <div className="calib-monitor-empty"><i className="fa-solid fa-circle-exclamation"></i> No display information available.</div>
            )}
            {displayInfo?.monitors.map((monitor) => (
              <div
                key={`${monitor.device}-${monitor.id}`}
                className={`calib-monitor ${displayInfo.target?.displayId === monitor.id ? "recommended-target" : ""}`}
              >
                <div className="calib-monitor-icon"><i className="fa-solid fa-display"></i></div>
                <div className="calib-monitor-copy">
                  <div className="calib-monitor-title">
                    Display {monitor.id}
                    {monitor.primary && <span className="calib-monitor-badge">Primary</span>}
                    {monitor.robloxWindows > 0 && <span className="calib-monitor-badge roblox">Roblox ×{monitor.robloxWindows}</span>}
                  </div>
                  <div className="calib-monitor-details">
                    <span>{monitor.width} × {monitor.height}</span>
                    <span>{monitor.aspectRatio}</span>
                    <span>{monitor.scale}% scale</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {displayInfo?.target?.source === "primary" && !recommendationFeedback && (
            <div className="calib-display-note">
              <i className="fa-solid fa-circle-info"></i>
              No Roblox window found. The recommendation uses your primary display and assumes Windowed mode.
            </div>
          )}
          {recommendationFeedback && (
            <div className={`calib-recommend-result ${recommendationFeedback.kind}`} role="status">
              <i className={`fa-solid ${recommendationFeedback.kind === "success" ? "fa-circle-check" : recommendationFeedback.kind === "warning" ? "fa-triangle-exclamation" : "fa-circle-xmark"}`}></i>
              {recommendationFeedback.text}
            </div>
          )}
        </div>
        <div className="afk-divider"></div>
        <div className="afk-setting">
          <div className="afk-setting-info">
            <span className="afk-setting-name">Resolution preset</span>
            <span className="afk-setting-desc">Pick your resolution, scale and window mode, then load. Applied to every calibration panel at once. Fine-tune each panel below.</span>
          </div>
          <PresetPicker
            presetNames={presets.global}
            disabled={running}
            selectedName={loadedPreset}
            onLoad={(name) => void loadGlobal(name)}
          />
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
          <div className="calib-transfer-actions">
            <CopyButton state={copyFeedback.all} onClick={() => void copyCalibration("all")} label="Copy all calibrations" />
            <button className="btn-show" disabled={running} onClick={() => void openCalibrationImport()}>
              <i className="fa-solid fa-paste"></i> Paste all calibrations
            </button>
          </div>
        </div>
      </div>

      <Modal
        open={importOpen}
        title="Paste all calibrations"
        onCancel={() => setImportOpen(false)}
        onSave={applyCalibrationImport}
        saveLabel={importBusy ? "Working…" : importReport?.appliedCount != null ? `Applied ${importReport.appliedCount}` : "Apply valid calibrations"}
        saveDisabled={importBusy || !importReport?.canApply || importReport?.appliedCount != null}
        cancelLabel="Close"
        className="calib-import-modal"
      >
        <p className="calib-import-intro">Paste the JSON created by <b>Copy all calibrations</b>. Check it first; missing values stay unchanged and unknown fields are ignored.</p>
        <textarea
          className="field calib-import-text"
          value={importText}
          spellCheck={false}
          placeholder={'{\n  "format": "solrich-calibrations",\n  ...\n}'}
          onChange={(event) => { setImportText(event.target.value); setImportReport(null); }}
        />
        <div className="calib-import-check-row">
          <button className="btn-add" disabled={importBusy || !importText.trim()} onClick={() => void checkCalibrationImport()}>
            <i className={`fa-solid ${importBusy ? "fa-spinner fa-spin" : "fa-magnifying-glass"}`}></i>
            {importBusy ? "Checking…" : "Check pasted calibrations"}
          </button>
        </div>
        {importReport && (
          <div className={`calib-import-report${importReport.ok ? " ready" : " error"}`}>
            {!importReport.ok ? (
              <div className="calib-import-error"><i className="fa-solid fa-circle-xmark"></i> {importReport.message || importReport.error || "Invalid calibration export."}</div>
            ) : (
              <>
                <div className="calib-import-summary">
                  <span className="calib-import-stat valid"><b>{importReport.validCount}</b> valid</span>
                  <span className="calib-import-stat missing"><b>{importReport.missing.length}</b> missing</span>
                  <span className="calib-import-stat invalid"><b>{importReport.invalid.length}</b> invalid</span>
                  <span className="calib-import-stat unknown"><b>{importReport.unknown.length}</b> unknown</span>
                </div>
                {importReport.appliedCount != null && (
                  <div className="calib-import-applied"><i className="fa-solid fa-circle-check"></i> Imported {importReport.appliedCount} calibration values. Missing values were not cleared.</div>
                )}
                {[
                  ["Missing", importReport.missing, "missing"],
                  ["Invalid", importReport.invalid, "invalid"],
                  ["Unknown (ignored)", importReport.unknown, "unknown"],
                ].map(([label, entries, kind]) => Array.isArray(entries) && entries.length > 0 && (
                  <details className={`calib-import-details ${kind}`} key={String(kind)} open={kind === "invalid"}>
                    <summary>{String(label)} · {entries.length}</summary>
                    <div className="calib-import-list">
                      {entries.map((entry) => <code key={entry}>{entry}</code>)}
                    </div>
                  </details>
                ))}
              </>
            )}
          </div>
        )}
      </Modal>

      {}
      <div className={`glass card panel calib-test-panel${testState === "active" ? " active" : ""}`} data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-crosshairs"></i> Calibration Test Mode</div>
          <span className={`badge badge-soft calib-test-badge ${testState === "active" ? "active" : ""}`}>
            {testState === "active" ? "Preview active" : "Preview only"}
          </span>
        </div>
        <div className="calib-test-layout">
          <div className="calib-test-copy">
            <span className="afk-setting-name">Check targets without running the macro</span>
            <span className="afk-setting-desc">Saved click points and OCR regions appear as a click-through overlay. SolRich will not press any buttons.</span>
          </div>
          <div className="calib-test-controls">
            <div className="custom-select-wrap calib-test-select">
              <CustomSelect
                options={CALIBRATION_TEST_SCOPES}
                value={testScope}
                onChange={(value) => {
                  if (testState === "active") void stopCalibrationTest(true);
                  setTestScope(value);
                }}
                disabled={running || testState === "starting" || testState === "stopping"}
                aria-label="Calibration test module"
              />
            </div>
            <button
              className={`btn-add calib-test-button${testState === "active" ? " stop" : ""}`}
              disabled={running || testState === "starting" || testState === "stopping"}
              onClick={() => void startCalibrationTest()}
            >
              <i className={`fa-solid ${testState === "starting" || testState === "stopping" ? "fa-spinner fa-spin" : testState === "active" ? "fa-stop" : "fa-play"}`}></i>
              {testState === "starting" ? "Starting…" : testState === "stopping" ? "Stopping…" : testState === "active" ? "Stop preview" : "Start preview"}
            </button>
          </div>
        </div>
        <div className={`calib-test-status ${testState}`} role="status">
          <i className={`fa-solid ${testState === "active" ? "fa-circle-check" : testState === "error" ? "fa-triangle-exclamation" : "fa-circle-info"}`}></i>
          {testMessage}
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
          <CaptureRow label="First Item Slot (Region)" region {...regionInfo(firstItemRegion)} disabled={running} onCapture={() => runCapture("capture_item_region")} onManual={(value) => saveManualCalibration("inventory", "first_item_region", value)} />
          {invPixelSlots.map(([key, label]) => (
            <CaptureRow key={key} label={label} {...pixelInfo(pixels[key])} disabled={running} onCapture={() => runCapture("capture_pixel", key)} onManual={(value) => saveManualCalibration("inventory", key, value)} />
          ))}
        </div>
        <div className="afk-divider"></div>
        <div className="px-section-label"><i className="fa-solid fa-vector-square"></i> Auto Pop: Amount Label <span className="ap-required">required for Auto Pop</span></div>
        <div className="pixel-list">
          <CaptureRow label="Amount Label Region" region {...regionInfo(autopopRegion)} disabled={running} onCapture={() => runCapture("capture_autopop_amount_region")} onManual={(value) => saveManualCalibration("inventory", "autopop_amount_region", value)} />
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
            <CaptureRow key={key} label={label} {...pixelInfo(fishing.pixels?.[key])} disabled={running} onCapture={() => runCapture("capture_fishing_pixel", key)} onManual={(value) => saveManualCalibration("fishing", key, value)} />
          ))}
        </div>
        <div className="afk-divider"></div>
        <div className="px-section-label"><i className="fa-solid fa-vector-square"></i> OCR Regions</div>
        <div className="pixel-list">
          {FISHING_REGION_SLOTS.map(([key, label]) => (
            <CaptureRow key={key} label={label} region {...regionInfo(fishing.regions?.[key])} disabled={running} onCapture={() => runCapture("capture_fishing_region", key)} onManual={(value) => saveManualCalibration("fishing", key, value)} />
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
                <CaptureRow key={key} label={label} {...pixelInfo(merchCalib[group.key]?.pixels?.[key])} disabled={running} onCapture={() => runCapture("capture_merchant_pixel", group.key, key)} onManual={(value) => saveManualCalibration("merchants", key, value, group.key)} />
              ))}
              {group.regions.map(([key, label]) => (
                <CaptureRow key={key} label={label} region {...regionInfo(merchCalib[group.key]?.regions?.[key])} disabled={running} onCapture={() => runCapture("capture_merchant_region", group.key, key)} onManual={(value) => saveManualCalibration("merchants", key, value, group.key)} />
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
          <CaptureRow key={key} label={label} {...pixelInfo(calib.pixels?.[key])} disabled={running} onCapture={() => runCapture("capture_extra_pixel", group.key, key)} onManual={(value) => saveManualCalibration("extra", key, value, group.key)} />
        );
        const regionRow = (key: string, label: string) => (
          <CaptureRow key={key} label={label} region {...regionInfo(calib.regions?.[key])} disabled={running} onCapture={() => runCapture("capture_extra_region", group.key, key)} onManual={(value) => saveManualCalibration("extra", key, value, group.key)} />
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
