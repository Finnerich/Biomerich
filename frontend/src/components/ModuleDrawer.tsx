import { useEffect, type ReactNode } from "react";

interface ModuleDrawerProps {
  open: boolean;
  title: string;
  sub?: string;
  icon: string;
  wide?: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function ModuleDrawer({ open, title, sub, icon, wide, onClose, children }: ModuleDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <div className={`mb-drawer-overlay${open ? " open" : ""}`} onClick={onClose}></div>
      <aside className={`mb-drawer${open ? " open" : ""}${wide ? " wide" : ""}`} aria-hidden={!open}>
        <div className="mb-drawer-head">
          <div className="mb-drawer-ico"><i className={`fa-solid ${icon}`}></i></div>
          <div className="mb-drawer-titles">
            <span className="mb-drawer-title">{title}</span>
            {sub && <span className="mb-drawer-sub">{sub}</span>}
          </div>
          <button className="mb-drawer-close" onClick={onClose} title="Close">
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div className="mb-drawer-body">{children}</div>
      </aside>
    </>
  );
}
