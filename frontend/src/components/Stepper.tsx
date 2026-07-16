import { useState } from "react";

export function Stepper(props: {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (v: number) => void;
  disabled?: boolean;
  suffix?: string;
  width?: number;
}) {
  const { value, min = 0, max = 99999, step = 1, onChange, disabled, suffix, width } = props;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  const clamp = (v: number) => Math.max(min, Math.min(max, Math.round(v)));
  const bump = (delta: number) => {
    if (disabled) return;
    const next = clamp(value + delta);
    if (next !== value) onChange(next);
  };
  const startEdit = () => {
    if (disabled) return;
    setDraft(String(value));
    setEditing(true);
  };
  const commit = () => {
    const parsed = parseInt(draft, 10);
    onChange(Number.isNaN(parsed) ? value : clamp(parsed));
    setEditing(false);
  };

  return (
    <div className={`stepper${disabled ? " disabled" : ""}`}>
      <button
        className="stepper-btn" tabIndex={-1} aria-label="Decrease"
        disabled={disabled || value <= min}
        onClick={() => bump(-step)}
      >
        <i className="fa-solid fa-minus" />
      </button>
      <div className="stepper-val" style={width ? { minWidth: width } : undefined} onClick={startEdit}>
        {editing ? (
          <input
            autoFocus
            className="stepper-input"
            value={draft}
            inputMode="numeric"
            onChange={(e) => setDraft(e.target.value.replace(/[^0-9]/g, ""))}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit();
              else if (e.key === "Escape") setEditing(false);
            }}
          />
        ) : (
          <span key={value} className="stepper-num">{value}</span>
        )}
        {suffix && !editing && <span className="stepper-suffix">{suffix}</span>}
      </div>
      <button
        className="stepper-btn" tabIndex={-1} aria-label="Increase"
        disabled={disabled || value >= max}
        onClick={() => bump(step)}
      >
        <i className="fa-solid fa-plus" />
      </button>
    </div>
  );
}
