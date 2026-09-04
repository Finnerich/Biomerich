import { useState } from "react";
import { Modal } from "./Modal";

interface Props {
  label: string;
  coord: string;
  isSet: boolean;
  value?: number[];
  region?: boolean;
  disabled?: boolean;
  onCapture: () => Promise<{ ok?: boolean; error?: string } | null>;
  onManual?: (value: number[]) => Promise<{ ok?: boolean; error?: string } | null>;
}

export function CaptureRow({ label, coord, isSet, value, region, disabled, onCapture, onManual }: Props) {
  const [status, setStatus] = useState<"idle" | "listening" | "failed">("idle");
  const [failText, setFailText] = useState("");
  const [manualOpen, setManualOpen] = useState(false);
  const [manualText, setManualText] = useState("");
  const [manualError, setManualError] = useState("");

  async function run() {
    if (disabled || status === "listening") return;
    setStatus("listening");
    let result: { ok?: boolean; error?: string } | null;
    try {
      result = await onCapture();
    } catch {
      result = { ok: false, error: "connection_failed" };
    }
    if (result && result.ok) {
      setStatus("idle");
      return;
    }
    const timedOut = result?.error === "timeout";
    const robloxMissing = result?.error === "roblox_not_found";
    setFailText(
      robloxMissing
        ? "Roblox not found"
        : timedOut
          ? region
            ? "No clicks detected"
            : "No click detected"
          : "Failed",
    );
    setStatus("failed");
    setTimeout(() => {
      setStatus("idle");
      setFailText("");
    }, 1300);
  }

  function openManual() {
    setManualText(Array.isArray(value) ? value.join(", ") : "");
    setManualError("");
    setManualOpen(true);
  }

  async function saveManual() {
    const expected = region ? 4 : 2;
    let parsed: unknown;
    try {
      parsed = manualText.trim().startsWith("[")
        ? JSON.parse(manualText)
        : manualText.trim().split(/[\s,;]+/).filter(Boolean).map(Number);
    } catch {
      parsed = null;
    }
    if (!Array.isArray(parsed) || parsed.length !== expected || parsed.some((item) => !Number.isFinite(Number(item)))) {
      setManualError(region ? "Enter exactly: X, Y, width, height" : "Enter exactly: X, Y");
      return false;
    }
    const clean = parsed.map((item) => Math.round(Number(item)));
    if (region && (clean[2] <= 0 || clean[3] <= 0)) {
      setManualError("Width and height must be greater than zero.");
      return false;
    }
    const result = await onManual?.(clean);
    if (!result?.ok) {
      setManualError(result?.error === "tracking_active" ? "Stop the macro first." : "The coordinate could not be saved.");
      return false;
    }
    return true;
  }

  const coordText =
    status === "listening"
      ? region
        ? "Click top-left, then bottom-right…"
        : "Click your target…"
      : status === "failed"
        ? failText
        : coord;

  return (
    <>
      <div className={`pixel-row${isSet ? " set" : ""}${status === "listening" ? " listening" : ""}`}>
        <span className="px-name">{label}</span>
        <span className="px-coord">{coordText}</span>
        {onManual && (
          <button className="px-edit-btn" disabled={disabled || status === "listening"} onClick={openManual} aria-label={`Type ${label} coordinates`} title="Enter coordinates as text">
            <i className="fa-solid fa-keyboard"></i>
          </button>
        )}
        <button className="px-set-btn" disabled={disabled || status === "listening"} onClick={() => void run()}>
          {status === "listening" ? (
            <><i className="fa-solid fa-spinner fa-spin"></i> Waiting…</>
          ) : (
            <><i className={`fa-solid ${region ? "fa-vector-square" : "fa-crosshairs"}`}></i> Set</>
          )}
        </button>
      </div>
      {manualOpen && (
        <Modal
          open
          title={`Enter ${label}`}
          onCancel={() => setManualOpen(false)}
          onSave={saveManual}
          saveLabel="Apply coordinates"
        >
          <label className="calib-manual-label">{region ? "X, Y, width, height" : "X, Y"}</label>
          <input
            className="field calib-manual-input"
            autoFocus
            value={manualText}
            placeholder={region ? "760, 315, 310, 55" : "960, 540"}
            onChange={(event) => { setManualText(event.target.value); setManualError(""); }}
          />
          <p className="calib-manual-hint">Comma-separated numbers and JSON arrays are accepted.</p>
          {manualError && <div className="calib-manual-error"><i className="fa-solid fa-triangle-exclamation"></i> {manualError}</div>}
        </Modal>
      )}
    </>
  );
}
