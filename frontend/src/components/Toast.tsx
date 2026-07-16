import { useEffect, useRef, useState } from "react";
import { useStore, type Toast } from "../store";

const LINGER_MS = 4200;
const EXIT_MS = 380;

export function ToastLayer() {
  const toasts = useStore((s) => s.toasts);
  if (!toasts.length) return null;
  return (
    <div className="toast-layer">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}

function ToastItem({ toast }: { toast: Toast }) {
  const dismissToast = useStore((s) => s.dismissToast);
  const [leaving, setLeaving] = useState(false);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    timers.current.push(window.setTimeout(() => setLeaving(true), LINGER_MS));
    timers.current.push(window.setTimeout(() => dismissToast(toast.id), LINGER_MS + EXIT_MS));
    return () => { timers.current.forEach(clearTimeout); };
  }, [toast.id, dismissToast]);

  function close() {
    setLeaving(true);
    window.setTimeout(() => dismissToast(toast.id), EXIT_MS);
  }

  return (
    <div className={`toast${leaving ? " leaving" : ""}`} onClick={close} role="status">
      <div className="toast-ico"><i className={`fa-solid ${toast.icon}`}></i></div>
      <div className="toast-body">
        <span className="toast-title">{toast.title}</span>
        {toast.detail && <span className="toast-detail">{toast.detail}</span>}
      </div>
    </div>
  );
}
