import { useEffect, useRef, useState } from "react";
import { callPy } from "../bridge";
import { useStore } from "../store";

interface DecisionResult {
  ok?: boolean;
  error?: string;
}

export function RarePingWarning() {
  const warning = useStore((s) => s.rarePingWarnings[0] ?? null);
  const warningCount = useStore((s) => s.rarePingWarnings.length);
  const dismissWarning = useStore((s) => s.dismissRarePingWarning);
  const [confirmationStep, setConfirmationStep] = useState<0 | 1>(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const modalRef = useRef<HTMLElement>(null);

  useEffect(() => {
    setConfirmationStep(0);
    setBusy(false);
    setError("");
  }, [warning?.id]);

  useEffect(() => {
    if (!warning) return;
    const app = document.querySelector<HTMLElement>(".app-shell");
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    app?.setAttribute("inert", "");
    document.body.classList.add("rare-ping-lock-active");
    document.body.style.overflow = "hidden";
    window.setTimeout(() => {
      modalRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    }, 0);
    return () => {
      app?.removeAttribute("inert");
      document.body.classList.remove("rare-ping-lock-active");
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus?.();
    };
  }, [warning?.id]);

  if (!warning) return null;
  const pingTarget = warning.pingTarget || "@everyone";

  async function keepBlocked() {
    if (!warning || busy) return;
    if (warning.test) {
      dismissWarning(warning.id);
      return;
    }
    setBusy(true);
    await callPy<DecisionResult>("dismiss_blocked_rare_ping", warning.id).catch(() => null);
    dismissWarning(warning.id);
  }

  async function releasePing() {
    if (!warning || busy) return;
    if (confirmationStep === 0) {
      setConfirmationStep(1);
      setError("");
      return;
    }
    if (warning.test) {
      
      
      dismissWarning(warning.id);
      return;
    }
    setBusy(true);
    const result = await callPy<DecisionResult>("confirm_blocked_rare_ping", warning.id)
      .catch(() => ({ ok: false, error: "connection" }));
    if (result?.ok) {
      dismissWarning(warning.id);
      return;
    }
    setBusy(false);
    setError(result?.error === "expired"
      ? "This blocked ping has expired. No webhook was sent."
      : "Could not reach the macro backend. No webhook was sent.");
  }

  return (
    <div className={`rare-ping-lock${confirmationStep ? " is-confirming" : ""}${busy ? " is-dispatching" : ""}`}>
      <div className="rare-ping-lock__alarm" aria-hidden="true"></div>
      <section
        ref={modalRef}
        className="rare-ping-warning"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="rare-ping-warning-title"
        aria-describedby="rare-ping-warning-copy"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            return;
          }
          if (event.key !== "Tab") return;
          const buttons = Array.from(
            modalRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [],
          );
          if (!buttons.length) {
            event.preventDefault();
            return;
          }
          const first = buttons[0];
          const last = buttons[buttons.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }}
      >
        <div className="rare-ping-warning__icon" aria-hidden="true">
          <i className={`fa-solid ${confirmationStep ? "fa-radiation" : "fa-triangle-exclamation"}`}></i>
        </div>
        <div className="rare-ping-warning__body">
          <div className="rare-ping-warning__eyebrow">
            {confirmationStep
              ? "FINAL PING CONFIRMATION"
              : "ANTI FAKE PING SAFETY STOP"}
            {warningCount > 1 ? ` · ${warningCount} PENDING` : ""}
          </div>
          <h2 id="rare-ping-warning-title">
            {confirmationStep ? "STOP. Verify the biome again." : "Rare Biome Ping Blocked"}
          </h2>
          {confirmationStep ? (
            <p id="rare-ping-warning-copy">
              Your next red click will send the normal Biome Started embed and alert
              <strong> {pingTarget}</strong>. Continue only if you personally verified that the rare biome is real.
            </p>
          ) : (
            <p id="rare-ping-warning-copy">
              Anti Fake Ping blocked a suspicious rare biome ping{warning.account ? ` for ${warning.account}` : ""}.
              Nothing will be pinged until you make a deliberate decision.
            </p>
          )}
          {error && <div className="rare-ping-warning__error">{error}</div>}
          <div className="rare-ping-warning__actions">
            {confirmationStep ? (
              <button className="rare-ping-btn rare-ping-btn--safe" disabled={busy} onClick={() => setConfirmationStep(0)}>
                <i className="fa-solid fa-arrow-left"></i> No, go back
              </button>
            ) : (
              <button className="rare-ping-btn rare-ping-btn--safe" disabled={busy} onClick={() => void keepBlocked()}>
                <i className="fa-solid fa-shield-halved"></i> Keep it blocked
              </button>
            )}
            <button className="rare-ping-btn rare-ping-btn--danger" disabled={busy} onClick={() => void releasePing()}>
              <i className={`fa-solid ${confirmationStep ? "fa-bullhorn" : "fa-arrow-right"}`}></i>
              {confirmationStep ? "YES — RELEASE PING" : "Review ping"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
