import { useEffect, useRef, useState } from "react";

export function CountUp({ value, from: fromProp, format }: { value: number; from?: number; format?: (v: number) => string }) {
  const [shown, setShown] = useState(fromProp ?? value);
  const shownRef = useRef(fromProp ?? value);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      if (fromProp === undefined) {
        shownRef.current = value;
        setShown(value);
        return;
      }
    }
    const from = shownRef.current;
    if (from === value) return;
    const start = performance.now();
    const duration = 900;
    let raf = 0;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(2, -10 * progress);
      const current = Math.round(from + (value - from) * eased);
      shownRef.current = current;
      setShown(current);
      if (progress < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return <>{format ? format(shown) : shown.toLocaleString("en-US")}</>;
}
