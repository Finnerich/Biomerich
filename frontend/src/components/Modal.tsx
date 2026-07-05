import type { ReactNode } from "react";

interface ModalProps {
  open: boolean;
  title: string;
  onCancel: () => void;
  onSave: () => boolean | void | Promise<boolean | void>;
  children: ReactNode;
}

export function Modal({ open, title, onCancel, onSave, children }: ModalProps) {
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
      <div className="modal glass" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <span className="modal-title">{title}</span>
          <button className="modal-close" onClick={onCancel}>
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div className="modal-body">{children}</div>
        <div className="modal-foot">
          <button className="btn-cancel" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn-save" onClick={() => void handleSave()}>
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
