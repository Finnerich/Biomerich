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
    const t0 = performance.now();
    const dur = 900;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / dur);
      const eased = 1 - Math.pow(2, -10 * p);
      const v = Math.round(from + (value - from) * eased);
      shownRef.current = v;
      setShown(v);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return <>{format ? format(shown) : shown.toLocaleString("en-US")}</>;
}
