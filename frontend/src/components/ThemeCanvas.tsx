import { useEffect, useRef } from "react";
import { useStore } from "../store";

export const THEME_ANIMS = [
  { key: "none", label: "None", icon: "fa-ban" },
  { key: "fireflies", label: "Fireflies", icon: "fa-circle-dot" },
  { key: "rain", label: "Rain", icon: "fa-droplet" },
  { key: "aurora", label: "Aurora", icon: "fa-wave-square" },
  { key: "stardust", label: "Stardust", icon: "fa-star" },
];

export const NAV_ANIMS = [
  { key: "none", label: "None", icon: "fa-ban", cls: "" },
  { key: "scanlines", label: "Scanlines", icon: "fa-grip-lines", cls: "nav-anim-scanlines" },
  { key: "glitch", label: "Glitch", icon: "fa-signal", cls: "nav-anim-glitch" },
  { key: "illuminate", label: "Illuminate", icon: "fa-lightbulb", cls: "nav-anim-illuminate" },
];

export function applyNavAnim(key: string): void {
  NAV_ANIMS.forEach((a) => a.cls && document.body.classList.remove(a.cls));
  const entry = NAV_ANIMS.find((a) => a.key === key);
  if (entry?.cls) document.body.classList.add(entry.cls);
}

type Part = Record<string, number | boolean | string>;
interface Accent { r: number; g: number; b: number }

function accentRgb(): Accent {
  const s = getComputedStyle(document.documentElement);
  return {
    r: parseInt(s.getPropertyValue("--ar").trim()) || 68,
    g: parseInt(s.getPropertyValue("--ag").trim()) || 85,
    b: parseInt(s.getPropertyValue("--ab").trim()) || 255,
  };
}

function buildParticles(key: string, w: number, h: number): Part[] {
  const parts: Part[] = [];
  if (key === "fireflies") {
    const n = Math.min(55, Math.floor((w * h) / 22000));
    for (let i = 0; i < n; i++) parts.push({ x: Math.random() * w, y: Math.random() * h, r: 1.2 + Math.random() * 2.2, speed: 0.18 + Math.random() * 0.28, angle: Math.random() * Math.PI * 2, drift: (Math.random() - 0.5) * 0.012, phase: Math.random() * Math.PI * 2, pulseSpeed: 0.008 + Math.random() * 0.012, glowR: 6 + Math.random() * 10 });
  }
  if (key === "rain") {
    const n = Math.min(90, Math.floor(w / 8));
    for (let i = 0; i < n; i++) parts.push({ x: Math.random() * w, y: Math.random() * h - h, len: 18 + Math.random() * 40, speed: 4 + Math.random() * 6, opacity: 0.04 + Math.random() * 0.12, width: 0.5 + Math.random() * 0.8 });
  }
  if (key === "stardust") {
    const n = Math.min(120, Math.floor((w * h) / 12000));
    for (let i = 0; i < n; i++) parts.push({ x: Math.random() * w, y: Math.random() * h, r: 0.4 + Math.random() * 1.4, vx: (Math.random() - 0.5) * 0.15, vy: (Math.random() - 0.5) * 0.12, phase: Math.random() * Math.PI * 2, twinkleSpeed: 0.015 + Math.random() * 0.025, baseOpacity: 0.1 + Math.random() * 0.55 });
  }
  return parts;
}

type Ctx = CanvasRenderingContext2D;
const f = (p: Part, k: string) => p[k] as number;

function drawFireflies(ctx: Ctx, parts: Part[], time: number, w: number, h: number, ac: Accent) {
  parts.forEach((p) => {
    p.angle = f(p, "angle") + f(p, "drift");
    p.x = f(p, "x") + Math.cos(f(p, "angle")) * f(p, "speed");
    p.y = f(p, "y") + Math.sin(f(p, "angle")) * f(p, "speed");
    if (f(p, "x") < -20) p.x = w + 10;
    if (f(p, "x") > w + 20) p.x = -10;
    if (f(p, "y") < -20) p.y = h + 10;
    if (f(p, "y") > h + 20) p.y = -10;
    const pulse = 0.45 + 0.55 * Math.sin(f(p, "phase") + time * f(p, "pulseSpeed"));
    const alpha = pulse * 0.85;
    const gR = f(p, "glowR") * (0.7 + 0.3 * pulse);
    const grd = ctx.createRadialGradient(f(p, "x"), f(p, "y"), 0, f(p, "x"), f(p, "y"), gR);
    grd.addColorStop(0, `rgba(${ac.r},${ac.g},${ac.b},${(alpha * 0.35).toFixed(3)})`);
    grd.addColorStop(1, `rgba(${ac.r},${ac.g},${ac.b},0)`);
    ctx.beginPath(); ctx.arc(f(p, "x"), f(p, "y"), gR, 0, Math.PI * 2); ctx.fillStyle = grd; ctx.fill();
    ctx.beginPath(); ctx.arc(f(p, "x"), f(p, "y"), f(p, "r") * pulse, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${ac.r},${ac.g},${ac.b},${alpha.toFixed(3)})`; ctx.fill();
  });
}

function drawRain(ctx: Ctx, parts: Part[], _t: number, w: number, h: number, ac: Accent) {
  ctx.lineCap = "round";
  parts.forEach((p) => {
    p.y = f(p, "y") + f(p, "speed");
    if (f(p, "y") - f(p, "len") > h) { p.y = -f(p, "len"); p.x = Math.random() * w; }
    const grad = ctx.createLinearGradient(f(p, "x"), f(p, "y") - f(p, "len"), f(p, "x"), f(p, "y"));
    grad.addColorStop(0, `rgba(${ac.r},${ac.g},${ac.b},0)`);
    grad.addColorStop(0.6, `rgba(${ac.r},${ac.g},${ac.b},${f(p, "opacity").toFixed(3)})`);
    grad.addColorStop(1, `rgba(${ac.r},${ac.g},${ac.b},0)`);
    ctx.beginPath(); ctx.moveTo(f(p, "x"), f(p, "y") - f(p, "len")); ctx.lineTo(f(p, "x"), f(p, "y"));
    ctx.strokeStyle = grad; ctx.lineWidth = f(p, "width"); ctx.stroke();
  });
}

function drawAurora(ctx: Ctx, _p: Part[], time: number, w: number, h: number, ac: Accent) {
  const t = time * 0.003;
  for (let b = 0; b < 4; b++) {
    const yBase = h * (0.08 + b * 0.22);
    const amp = h * (0.04 + b * 0.012);
    const freq = 0.0018 + b * 0.0006;
    const speed = t * (0.4 + b * 0.15);
    const thick = h * (0.055 + b * 0.018);
    const alpha = 0.028 - b * 0.004;
    const r2 = Math.min(255, ac.r + b * 18), g2 = Math.min(255, ac.g + b * 7), b2 = Math.min(255, ac.b - b * 5);
    ctx.beginPath();
    for (let x = 0; x <= w; x += 3) {
      const y = yBase + Math.sin(x * freq + speed) * amp + Math.sin(x * freq * 1.7 + speed * 1.3 + b) * amp * 0.4;
      x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = `rgba(${r2},${g2},${b2},${(alpha * 3).toFixed(3)})`; ctx.lineWidth = 1; ctx.stroke();
    for (let layer = 0; layer < 6; layer++) {
      const lA = alpha * (1 - layer / 6);
      const lOff = (layer / 6) * thick;
      ctx.beginPath();
      for (let x = 0; x <= w; x += 4) {
        const y = yBase + Math.sin(x * freq + speed) * amp + Math.sin(x * freq * 1.7 + speed * 1.3 + b) * amp * 0.4;
        x === 0 ? ctx.moveTo(x, y - lOff) : ctx.lineTo(x, y - lOff);
      }
      for (let x = w; x >= 0; x -= 4) {
        const y = yBase + Math.sin(x * freq + speed) * amp + Math.sin(x * freq * 1.7 + speed * 1.3 + b) * amp * 0.4;
        ctx.lineTo(x, y + lOff);
      }
      ctx.closePath(); ctx.fillStyle = `rgba(${r2},${g2},${b2},${lA.toFixed(4)})`; ctx.fill();
    }
  }
}

function drawStardust(ctx: Ctx, parts: Part[], time: number, w: number, h: number, ac: Accent) {
  parts.forEach((p) => {
    p.x = f(p, "x") + f(p, "vx"); p.y = f(p, "y") + f(p, "vy");
    if (f(p, "x") < 0) p.x = w; if (f(p, "x") > w) p.x = 0;
    if (f(p, "y") < 0) p.y = h; if (f(p, "y") > h) p.y = 0;
    const tw = f(p, "baseOpacity") * (0.3 + 0.7 * Math.abs(Math.sin(f(p, "phase") + time * f(p, "twinkleSpeed"))));
    const gr = ctx.createRadialGradient(f(p, "x"), f(p, "y"), 0, f(p, "x"), f(p, "y"), f(p, "r") * 4);
    gr.addColorStop(0, `rgba(${ac.r},${ac.g},${ac.b},${(tw * 0.4).toFixed(3)})`);
    gr.addColorStop(1, `rgba(${ac.r},${ac.g},${ac.b},0)`);
    ctx.beginPath(); ctx.arc(f(p, "x"), f(p, "y"), f(p, "r") * 4, 0, Math.PI * 2); ctx.fillStyle = gr; ctx.fill();
    ctx.beginPath(); ctx.arc(f(p, "x"), f(p, "y"), f(p, "r"), 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255,255,255,${tw.toFixed(3)})`; ctx.fill();
  });
}

const DRAW: Record<string, (ctx: Ctx, parts: Part[], time: number, w: number, h: number, ac: Accent) => void> = {
  fireflies: drawFireflies, rain: drawRain, aurora: drawAurora, stardust: drawStardust,
};

export function ThemeCanvas() {
  const lock = useStore((s) => s.themeLock);
  const userAnim = (useStore((s) => s.settings.themeAnim) as string) || localStorage.getItem("themeAnim") || "none";
  const animKey = lock ? lock.anim : userAnim;
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (animKey === "none") {
      canvas.style.opacity = "0";
      return;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let parts: Part[] = [];
    let time = 0;
    let raf = 0;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      parts = buildParticles(animKey, canvas.width, canvas.height);
    };
    resize();
    const draw = DRAW[animKey];
    if (!draw) { canvas.style.opacity = "0"; return; }
    canvas.style.opacity = "1";
    const tick = () => {
      time++;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      draw(ctx, parts, time, canvas.width, canvas.height, accentRgb());
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [animKey]);

  return (
    <canvas
      ref={canvasRef}
      id="themeCanvas"
      style={{ position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none", opacity: 0, transition: "opacity 0.8s ease" }}
    />
  );
}
