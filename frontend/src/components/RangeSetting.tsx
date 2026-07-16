import { useEffect, useState } from "react";

export function RangeSetting(props: {
  name: string;
  desc: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onCommit: (v: number) => void;
  fmt?: (v: number) => string;
  disabled?: boolean;
  recommended?: number;
}) {
  const { name, desc, min, max, step, value, onCommit, fmt, disabled, recommended } = props;
  const clamp = (v: number) => Math.max(min, Math.min(max, Math.round((v || min) / step) * step));
  const [sliderValue, setSliderValue] = useState(clamp(value));
  useEffect(() => setSliderValue(clamp(value)), [value]); // eslint-disable-line react-hooks/exhaustive-deps
  const pct = ((sliderValue - min) / (max - min)) * 100;
  const formatValue = fmt ?? ((n: number) => String(n));
  const recPct = recommended != null ? ((clamp(recommended) - min) / (max - min)) * 100 : null;
  const atRec = recommended != null && sliderValue === clamp(recommended);
  const commit = (raw: string) => onCommit(clamp(parseInt(raw, 10)));

  const inputEl = (
    <input
      type="range" className="afk-range" min={min} max={max} step={step} disabled={disabled}
      value={sliderValue}
      style={{ backgroundSize: `${pct}% 100%` }}
      onChange={(e) => setSliderValue(clamp(parseInt(e.target.value, 10)))}
      onPointerUp={(e) => commit((e.target as HTMLInputElement).value)}
      onKeyUp={(e) => commit((e.target as HTMLInputElement).value)}
    />
  );

  return (
    <div className="afk-setting afk-setting-col">
      <div className="afk-setting-info">
        <span className="afk-setting-name">
          {name}
          {recommended != null && (
            <span className={`thr-rec-chip${atRec ? " on" : ""}`}>
              <i className="fa-solid fa-wand-magic-sparkles" /> Recommended {formatValue(clamp(recommended))}
            </span>
          )}
        </span>
        <span className="afk-setting-desc">{desc}</span>
      </div>
      <div className="afk-slider-row">
        {recommended != null ? (
          <div className="thr-slider-wrap">
            {inputEl}
            {recPct != null && (
              <span className="thr-rec-tick" style={{ left: `${recPct}%` }} title={`Recommended: ${formatValue(clamp(recommended!))}`} />
            )}
          </div>
        ) : inputEl}
        <span className="afk-interval-value">{formatValue(sliderValue)}</span>
      </div>
    </div>
  );
}
