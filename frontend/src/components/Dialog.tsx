import { useEffect, useRef, useState } from "react";
import { useDialog } from "../dialog";

const TITLES: Record<string, string> = { alert: "Notice", confirm: "Confirm", prompt: "Input" };

export function Dialog() {
  const dialog = useDialog();
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!dialog.open) return;
    setValue(dialog.defaultValue);
    if (dialog.kind === "prompt") {
      const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 40);
      return () => clearTimeout(focusTimer);
    }
  }, [dialog.open, dialog.kind, dialog.defaultValue]);

  useEffect(() => {
    if (!dialog.open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        cancel();
      } else if (e.key === "Enter" && dialog.kind !== "prompt") {
        confirm();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dialog.open, dialog.kind, value]);

  if (!dialog.open) return null;

  function confirm() {
    const state = useDialog.getState();
    state.close(state.kind === "alert" ? null : state.kind === "confirm" ? true : value);
  }
  function cancel() {
    const state = useDialog.getState();
    state.close(state.kind === "alert" ? null : state.kind === "confirm" ? false : null);
  }

  return (
    <div className="modal-overlay open dialog-overlay" onClick={(e) => { if (e.target === e.currentTarget) cancel(); }}>
      <div className="modal glass dialog-modal">
        <div className="modal-head">
          <span className="modal-title">{dialog.title || TITLES[dialog.kind]}</span>
          {dialog.kind !== "alert" && (
            <button className="modal-close" onClick={cancel}>
              <i className="fa-solid fa-xmark"></i>
            </button>
          )}
        </div>
        <div className="modal-body">
          <p className="dialog-message">{dialog.message}</p>
          {dialog.kind === "prompt" && (
            <input
              ref={inputRef}
              className="field"
              value={value}
              placeholder={dialog.placeholder}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") confirm(); }}
            />
          )}
        </div>
        <div className="modal-foot">
          {dialog.kind !== "alert" && (
            <button className="btn-cancel" onClick={cancel}>{dialog.cancelLabel}</button>
          )}
          <button className={`btn-save${dialog.danger ? " dialog-danger" : ""}`} onClick={confirm}>
            {dialog.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
