import { useEffect, useMemo, useState } from "react";
import { CustomSelect } from "./CustomSelect";

const PRESET_RE = /^\[([^\]]+)\]\s+(WINDOWED|FULLSCREEN)\s+(\d+)\s*[x×]\s*(\d+)\s+\((\d+%)\)\s*$/i;

interface ModeEntry { mode: string; label: string; name: string }
interface ScaleEntry { scale: string; modes: ModeEntry[] }
interface ResEntry { value: string; label: string; w: number; h: number; scales: ScaleEntry[]; looseName?: string }

const LOOSE_PREFIX = "loose:";
const modeLabel = (mode: string) => mode.charAt(0).toUpperCase() + mode.slice(1).toLowerCase();
const scaleNum = (scale: string) => parseInt(scale, 10) || 0;

function buildTree(names: string[]): ResEntry[] {
  const byRes = new Map<string, { tag: string; w: number; h: number; scales: Map<string, Map<string, string>> }>();
  const loose: ResEntry[] = [];

  for (const name of names) {
    const match = PRESET_RE.exec(name.trim());
    if (!match) {
      loose.push({ value: LOOSE_PREFIX + name, label: name, w: 0, h: 0, scales: [], looseName: name });
      continue;
    }
    const [, tag, modeRaw, widthStr, heightStr, scale] = match;
    const resKey = `${widthStr}x${heightStr}`;
    let resGroup = byRes.get(resKey);
    if (!resGroup) { resGroup = { tag, w: +widthStr, h: +heightStr, scales: new Map() }; byRes.set(resKey, resGroup); }
    let modeMap = resGroup.scales.get(scale);
    if (!modeMap) { modeMap = new Map(); resGroup.scales.set(scale, modeMap); }
    modeMap.set(modeRaw.toUpperCase(), name);
  }

  const modeOrder = (mode: string) => (mode === "WINDOWED" ? 0 : mode === "FULLSCREEN" ? 1 : 2);
  const resolutions: ResEntry[] = [...byRes.entries()].map(([resKey, group]) => ({
    value: resKey,
    label: group.tag ? `${group.w} × ${group.h} · ${group.tag}` : `${group.w} × ${group.h}`,
    w: group.w,
    h: group.h,
    scales: [...group.scales.entries()]
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
  selectedName,
  onLoad,
}: {
  presetNames: string[];
  disabled?: boolean;
  selectedName?: string | null;
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
    if (!selectedName || !presetNames.includes(selectedName)) return;
    const match = PRESET_RE.exec(selectedName.trim());
    if (!match) {
      setRes(LOOSE_PREFIX + selectedName);
      setScale("");
      setMode("");
      return;
    }
    const [, , nextMode, width, height, nextScale] = match;
    setRes(`${width}x${height}`);
    setScale(nextScale);
    setMode(nextMode.toUpperCase());
  }, [selectedName, presetNames]);

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
    let nextScale = scale;
    if (!scales.some((x) => x.scale === nextScale)) {
      nextScale = scales.length === 1 ? scales[0].scale : "";
      if (nextScale !== scale) { setScale(nextScale); return; }
    }
    const modes = scales.find((x) => x.scale === nextScale)?.modes ?? [];
    if (!modes.some((x) => x.mode === mode)) {
      const nextMode = modes.length === 1 ? modes[0].mode : "";
      if (nextMode !== mode) setMode(nextMode);
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
