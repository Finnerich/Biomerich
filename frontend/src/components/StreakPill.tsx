import { useEffect, useRef, useState } from "react";
import { useStore } from "../store";

function streakTier(count: number): number {
  if (count >= 28) return 3;
  if (count >= 7) return 2;
  if (count >= 3) return 1;
  return 0;
}

export function StreakPill() {
  const streak = useStore((s) => s.streak);
  const [display, setDisplay] = useState(0);
  const [pop, setPop] = useState(false);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    if (!streak) return;
    if (!streak.advanced) {
      setDisplay(streak.count);
      return;
    }
    const from = streak.previous;
    const to = streak.count;
    const start = performance.now();
    const duration = 850;
    setPop(true);
    const frame = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(from + (to - from) * eased));
      if (progress < 1) raf.current = requestAnimationFrame(frame);
      else setDisplay(to);
    };
    raf.current = requestAnimationFrame(frame);
    const popTimer = setTimeout(() => setPop(false), 900);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
      clearTimeout(popTimer);
    };
  }, [streak]);

  if (!streak) return null;
  const tier = streakTier(display);

  return (
    <div className={`streak-pill st-${tier}${pop ? " streak-pop" : ""}`} title="Daily streak">
      <span className="streak-flame"><i className={`fa-solid ${tier >= 2 ? "fa-fire-flame-curved" : "fa-fire"}`}></i></span>
      <span className="streak-count">{display}</span>
    </div>
  );
}
