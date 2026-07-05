import { useEffect } from "react";
import { useTesseract } from "../tesseract";

function mb(bytes: number): string {
  return (bytes / 1048576).toFixed(1);
}

export function TesseractModal() {
  const open = useTesseract((s) => s.modalOpen);
  const prompt = useTesseract((s) => s.prompt);
  const phase = useTesseract((s) => s.phase);
  const downloaded = useTesseract((s) => s.downloaded);
  const total = useTesseract((s) => s.total);
  const percent = useTesseract((s) => s.percent);
  const error = useTesseract((s) => s.error);

  const busy = phase === "downloading" || phase === "extracting";

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) useTesseract.getState().close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, busy]);

  if (!open) return null;

  const close = () => useTesseract.getState().close();
  const later = () => useTesseract.getState().later();
  const install = () => void useTesseract.getState().install();

  const hasTotal = total > 0;
  const pct = phase === "extracting" ? 100 : phase === "done" ? 100 : Math.max(0, Math.min(100, percent));

  return (
    <div className="modal-overlay open" onClick={(e) => { if (e.target === e.currentTarget && !busy) close(); }}>
      <div className="modal glass tess-modal" role="dialog" aria-modal="true" aria-label="Tesseract installer">
        <div className="tess-icon"><i className="fa-solid fa-eye"></i></div>

        {}
        {phase === "idle" && (
          <>
            <div className="tess-head">
              <span className="tess-title">Unlock OCR features</span>
              <span className="tess-sub">
                SolRich uses Tesseract (OCR) for <b>Merchant Detection</b>, <b>Auto Buy</b> and every
                OCR failsafe. That's a big chunk of what SolRich can do. It's not installed yet.
                Want me to set it up for you? One click, no manual install.
              </span>
            </div>
            <div className="modal-foot">
              {prompt && <button className="btn-cancel" onClick={later}>Later</button>}
              {!prompt && <button className="btn-cancel" onClick={close}>Cancel</button>}
              <button className="btn-save" onClick={install}>
                <i className="fa-solid fa-download"></i> Install Tesseract
              </button>
            </div>
          </>
        )}

        {}
        {busy && (
          <>
            <div className="tess-head">
              <span className="tess-title">
                {phase === "downloading" ? "Downloading Tesseract…" : "Installing…"}
              </span>
              <span className="tess-sub">
                {phase === "downloading"
                  ? "Grabbing the OCR engine. This only happens once."
                  : "Almost there. If Windows asks for permission, click Yes. (SolRich itself doesn't need admin.)"}
              </span>
            </div>

            <div className={`tess-bar${!hasTotal && phase === "downloading" ? " indeterminate" : ""}${phase === "extracting" ? " indeterminate" : ""}`}>
              <div className="tess-bar-fill" style={{ width: `${pct}%` }}></div>
            </div>

            <div className="tess-stats">
              {phase === "downloading" ? (
                hasTotal ? (
                  <>
                    <span className="tess-mb">{mb(downloaded)} / {mb(total)} MB</span>
                    <span className="tess-pct">{pct}%</span>
                  </>
                ) : (
                  <span className="tess-mb">{mb(downloaded)} MB downloaded…</span>
                )
              ) : (
                <span className="tess-mb">Installing…</span>
              )}
            </div>
          </>
        )}

        {}
        {phase === "done" && (
          <>
            <div className="tess-head">
              <span className="tess-title"><i className="fa-solid fa-circle-check tess-ok"></i> Tesseract installed</span>
              <span className="tess-sub">Merchant Detection, Auto Buy and the OCR failsafes are unlocked. You're good to go.</span>
            </div>
            <div className="modal-foot">
              <button className="btn-save" onClick={close}>Done</button>
            </div>
          </>
        )}

        {}
        {phase === "error" && (
          <>
            <div className="tess-head">
              <span className="tess-title"><i className="fa-solid fa-triangle-exclamation tess-err"></i> Install failed</span>
              <span className="tess-sub">{error}</span>
            </div>
            <div className="modal-foot">
              <button className="btn-cancel" onClick={close}>Close</button>
              <button className="btn-save" onClick={install}>
                <i className="fa-solid fa-rotate-right"></i> Retry
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
