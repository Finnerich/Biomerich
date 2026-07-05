import { useEffect, useMemo, useState } from "react";
import { CustomSelect } from "./CustomSelect";

const PRESET_RE = /^\[([^\]]+)\]\s+(WINDOWED|FULLSCREEN)\s+(\d+)\s*[x×]\s*(\d+)\s+\((\d+%)\)\s*$/i;

interface ModeEntry { mode: string; label: string; name: string }
interface ScaleEntry { scale: string; modes: ModeEntry[] }
interface ResEntry { value: string; label: string; w: number; h: number; scales: ScaleEntry[]; looseName?: string }

const LOOSE_PREFIX = "loose:";
const modeLabel = (m: string) => m.charAt(0).toUpperCase() + m.slice(1).toLowerCase();
const scaleNum = (s: string) => parseInt(s, 10) || 0;

function buildTree(names: string[]): ResEntry[] {
  const byRes = new Map<string, { tag: string; w: number; h: number; scales: Map<string, Map<string, string>> }>();
  const loose: ResEntry[] = [];

  for (const name of names) {
    const m = PRESET_RE.exec(name.trim());
    if (!m) {
      loose.push({ value: LOOSE_PREFIX + name, label: name, w: 0, h: 0, scales: [], looseName: name });
      continue;
    }
    const [, tag, modeRaw, wStr, hStr, scale] = m;
    const res = `${wStr}x${hStr}`;
    let r = byRes.get(res);
    if (!r) { r = { tag, w: +wStr, h: +hStr, scales: new Map() }; byRes.set(res, r); }
    let s = r.scales.get(scale);
    if (!s) { s = new Map(); r.scales.set(scale, s); }
    s.set(modeRaw.toUpperCase(), name);
  }

  const modeOrder = (mode: string) => (mode === "WINDOWED" ? 0 : mode === "FULLSCREEN" ? 1 : 2);
  const resolutions: ResEntry[] = [...byRes.entries()].map(([res, r]) => ({
    value: res,
    label: r.tag ? `${r.w} × ${r.h} · ${r.tag}` : `${r.w} × ${r.h}`,
    w: r.w,
    h: r.h,
    scales: [...r.scales.entries()]
      .sort((a, b) => scaleNum(a[0]) - scaleNum(b[0]))
      .map(([scale, modes]) => ({
        scale,
        modes: [...modes.entries()]
          .sort((a, b) => modeOrder(a[0]) - modeOrder(b[0]))
          .map(([mode, name]) => ({ mode, label: modeLabel(mode), name })),
      })),
  }));

  resolutions.sort((a, b) => a.w * a.h - b.w * b.h || a.w - b.w);
  return [...resolutions, ...loose];
}

export function PresetPicker({
  presetNames,
  disabled,
  onLoad,
}: {
  presetNames: string[];
  disabled?: boolean;
  onLoad: (name: string) => void;
}) {
  const resolutions = useMemo(() => buildTree(presetNames), [presetNames]);

  const [res, setRes] = useState("");
  const [scale, setScale] = useState("");
  const [mode, setMode] = useState("");

  const resEntry = resolutions.find((r) => r.value === res);
  const isLoose = !!resEntry?.looseName;
  const scaleEntry = resEntry?.scales.find((s) => s.scale === scale);
  const modeEntry = scaleEntry?.modes.find((m) => m.mode === mode);
  const resolvedName = isLoose ? resEntry!.looseName! : modeEntry?.name;

  useEffect(() => {
    if (!resolutions.some((r) => r.value === res)) {
      setRes(resolutions.length === 1 ? resolutions[0].value : "");
      return;
    }
    if (isLoose) {
      if (scale) setScale("");
      if (mode) setMode("");
      return;
    }
    const scales = resEntry?.scales ?? [];
    let s = scale;
    if (!scales.some((x) => x.scale === s)) {
      s = scales.length === 1 ? scales[0].scale : "";
      if (s !== scale) { setScale(s); return; }
    }
    const modes = scales.find((x) => x.scale === s)?.modes ?? [];
    if (!modes.some((x) => x.mode === mode)) {
      const m = modes.length === 1 ? modes[0].mode : "";
      if (m !== mode) setMode(m);
    }
  }, [resolutions, res, scale, mode, isLoose, resEntry]);

  const hasPresets = resolutions.length > 0;
  const resOptions = resolutions.map((r) => ({ value: r.value, label: r.label }));
  const scaleOptions = (resEntry?.scales ?? []).map((s) => ({ value: s.scale, label: s.scale }));
  const modeOptions = (scaleEntry?.modes ?? []).map((m) => ({ value: m.mode, label: m.label }));

  return (
    <div className="preset-row preset-row-steps">
      <div className="custom-select-wrap">
        <CustomSelect
          options={resOptions}
          value={res}
          onChange={setRes}
          placeholder={hasPresets ? "Resolution…" : "No presets yet"}
          disabled={disabled || !hasPresets}
          aria-label="Resolution"
        />
      </div>
      {!isLoose && (
        <>
          <div className="custom-select-wrap">
            <CustomSelect
              options={scaleOptions}
              value={scale}
              onChange={setScale}
              placeholder={res ? "Scale…" : "Scale"}
              disabled={disabled || !res}
              aria-label="UI scale"
            />
          </div>
          <div className="custom-select-wrap">
            <CustomSelect
              options={modeOptions}
              value={mode}
              onChange={setMode}
              placeholder={scale ? "Window…" : "Window"}
              disabled={disabled || !scale}
              aria-label="Window mode"
            />
          </div>
        </>
      )}
      <button
        className="btn-add"
        disabled={disabled || !resolvedName}
        onClick={() => resolvedName && onLoad(resolvedName)}
      >
        Load
      </button>
    </div>
  );
}
