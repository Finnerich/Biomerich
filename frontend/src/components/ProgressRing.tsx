import type { ReactNode } from "react";

export function ProgressRing({ id, value, max, size = 84, stroke = 8, children }: {
  id: string;
  value: number;
  max: number;
  size?: number;
  stroke?: number;
  children?: ReactNode;
}) {
  const r = (size - stroke) / 2 - 2;
  const c = 2 * Math.PI * r;
  const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const grad = `ringGrad-${id}`;

  return (
    <div className="fx-ring" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <linearGradient id={grad} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--accent-2)" />
          </linearGradient>
        </defs>
        <circle className="fx-ring-bg" cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} />
        <circle
          className="fx-ring-fg"
          cx={size / 2} cy={size / 2} r={r}
          strokeWidth={stroke}
          stroke={`url(#${grad})`}
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
        />
      </svg>
      <div className="fx-ring-content">{children}</div>
    </div>
  );
}
