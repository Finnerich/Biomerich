import { useState } from "react";

interface Props {
  label: string;
  coord: string;
  isSet: boolean;
  region?: boolean;
  disabled?: boolean;
  onCapture: () => Promise<{ ok?: boolean; error?: string } | null>;
}

export function CaptureRow({ label, coord, isSet, region, disabled, onCapture }: Props) {
  const [status, setStatus] = useState<"idle" | "listening" | "failed">("idle");
  const [failText, setFailText] = useState("");

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

  const coordText =
    status === "listening"
      ? region
        ? "Click top-left, then bottom-right…"
        : "Click your target…"
      : status === "failed"
        ? failText
        : coord;

  return (
    <div className={`pixel-row${isSet ? " set" : ""}${status === "listening" ? " listening" : ""}`}>
      <span className="px-name">{label}</span>
      <span className="px-coord">{coordText}</span>
      <button className="px-set-btn" disabled={disabled || status === "listening"} onClick={() => void run()}>
        {status === "listening" ? (
          <>
            <i className="fa-solid fa-spinner fa-spin"></i> Waiting…
          </>
        ) : (
          <>
            <i className={`fa-solid ${region ? "fa-vector-square" : "fa-crosshairs"}`}></i> Set
          </>
        )}
      </button>
    </div>
  );
}
