import { useEffect, useRef } from "react";
import { useTutorial } from "../tutorial";

export function Tutorial() {
  const active = useTutorial((s) => s.active);
  const tutorialDef = useTutorial((s) => s.def);
  const stepIndex = useTutorial((s) => s.i);
  const spotRef = useRef<HTMLDivElement>(null);

  const step = active && tutorialDef ? tutorialDef.steps[stepIndex] : null;
  const hasTarget = !!step?.target;

  
  
  useEffect(() => {
    if (!active || !step) return;
    useTutorial.getState().applyStepView(step);
    if (!step.target) return;
    let tries = 0;
    const timers: number[] = [];
    const scrollToTarget = () => {
      const element = document.querySelector(step.target!) as HTMLElement | null;
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
      } else if (tries++ < 8) {
        timers.push(window.setTimeout(scrollToTarget, 120));
      }
    };
    timers.push(window.setTimeout(scrollToTarget, 90));
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [active, step]);

  useEffect(() => {
    if (!active || !step) return;
    let rafId = 0;
    const tick = () => {
      const spot = spotRef.current;
      if (spot) {
        const element = step.target ? (document.querySelector(step.target) as HTMLElement | null) : null;
        if (element) {
          const rect = element.getBoundingClientRect();
          const pad = 8;
          spot.style.opacity = "1";
          spot.style.top = `${rect.top - pad}px`;
          spot.style.left = `${rect.left - pad}px`;
          spot.style.width = `${rect.width + pad * 2}px`;
          spot.style.height = `${rect.height + pad * 2}px`;
        } else {
          spot.style.opacity = "0";
        }
      }
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [active, step]);

  useEffect(() => {
    if (!active) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.stopPropagation(); useTutorial.getState().end(true); }
      else if (event.key === "ArrowRight") useTutorial.getState().next();
      else if (event.key === "ArrowLeft") useTutorial.getState().back();
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [active]);

  if (!active || !tutorialDef || !step) return null;
  const total = tutorialDef.steps.length;
  const pct = Math.round(((stepIndex + 1) / total) * 100);

  return (
    <div className="tut2-root">
      {hasTarget
        ? <div className="tut2-spot" ref={spotRef} aria-hidden="true"></div>
        : <div className="tut2-backdrop" aria-hidden="true"></div>}

      <div className="tut2-card glass" role="dialog" aria-modal="false" aria-label={step.title}>
        <div className="tut2-head">
          <span className="tut2-badge"><i className="fa-solid fa-graduation-cap"></i> {tutorialDef.title}</span>
          <span className="tut2-count">{stepIndex + 1} / {total}</span>
        </div>
        <div className="tut2-bar"><div className="tut2-bar-fill" style={{ width: `${pct}%` }}></div></div>

        {}
        <div className="tut2-body" key={stepIndex}>
          <div className="tut2-ico"><i className={`fa-solid ${step.icon}`}></i></div>
          <div className="tut2-text">
            <h3 className="tut2-title">{step.title}</h3>
            <p className="tut2-desc">{step.body}</p>
          </div>
        </div>

        <div className="tut2-foot">
          <button className="tut2-skip" onClick={() => useTutorial.getState().end(true)}>Skip tour</button>
          <div className="tut2-nav">
            {stepIndex > 0 && <button className="tut2-back" onClick={() => useTutorial.getState().back()}><i className="fa-solid fa-arrow-left"></i> Back</button>}
            <button className="tut2-next" onClick={() => useTutorial.getState().next()}>
              {stepIndex >= total - 1 ? "Finish" : "Next"} <i className={`fa-solid ${stepIndex >= total - 1 ? "fa-check" : "fa-arrow-right"}`}></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
