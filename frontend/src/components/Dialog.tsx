import { useEffect, useRef, useState } from "react";
import { useDialog } from "../dialog";

const TITLES: Record<string, string> = { alert: "Notice", confirm: "Confirm", prompt: "Input" };

export function Dialog() {
  const d = useDialog();
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!d.open) return;
    setValue(d.defaultValue);
    if (d.kind === "prompt") {
      const t = window.setTimeout(() => inputRef.current?.focus(), 40);
      return () => clearTimeout(t);
    }
  }, [d.open, d.kind, d.defaultValue]);

  useEffect(() => {
    if (!d.open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        cancel();
      } else if (e.key === "Enter" && d.kind !== "prompt") {
        confirm();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d.open, d.kind, value]);

  if (!d.open) return null;

  function confirm() {
    const s = useDialog.getState();
    s.close(s.kind === "alert" ? null : s.kind === "confirm" ? true : value);
  }
  function cancel() {
    const s = useDialog.getState();
    s.close(s.kind === "alert" ? null : s.kind === "confirm" ? false : null);
  }

  return (
    <div className="modal-overlay open dialog-overlay" onClick={(e) => { if (e.target === e.currentTarget) cancel(); }}>
      <div className="modal glass dialog-modal">
        <div className="modal-head">
          <span className="modal-title">{d.title || TITLES[d.kind]}</span>
          {d.kind !== "alert" && (
            <button className="modal-close" onClick={cancel}>
              <i className="fa-solid fa-xmark"></i>
            </button>
          )}
        </div>
        <div className="modal-body">
          <p className="dialog-message">{d.message}</p>
          {d.kind === "prompt" && (
            <input
              ref={inputRef}
              className="field"
              value={value}
              placeholder={d.placeholder}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") confirm(); }}
            />
          )}
        </div>
        <div className="modal-foot">
          {d.kind !== "alert" && (
            <button className="btn-cancel" onClick={cancel}>{d.cancelLabel}</button>
          )}
          <button className={`btn-save${d.danger ? " dialog-danger" : ""}`} onClick={confirm}>
            {d.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
