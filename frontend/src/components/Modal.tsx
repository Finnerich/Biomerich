import type { ReactNode } from "react";

interface ModalProps {
  open: boolean;
  title: string;
  onCancel: () => void;
  onSave: () => boolean | void | Promise<boolean | void>;
  saveLabel?: string;
  saveDisabled?: boolean;
  cancelLabel?: string;
  className?: string;
  children: ReactNode;
}

export function Modal({ open, title, onCancel, onSave, saveLabel = "Save", saveDisabled = false, cancelLabel = "Cancel", className = "", children }: ModalProps) {
  async function handleSave() {
    const ok = await onSave();
    if (ok !== false) onCancel();
  }

  return (
    <div
      className={`modal-overlay${open ? " open" : ""}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div className={`modal glass${className ? ` ${className}` : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <span className="modal-title">{title}</span>
          <button className="modal-close" onClick={onCancel}>
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div className="modal-body">{children}</div>
        <div className="modal-foot">
          <button className="btn-cancel" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button className="btn-save" disabled={saveDisabled} onClick={() => void handleSave()}>
            {saveLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
