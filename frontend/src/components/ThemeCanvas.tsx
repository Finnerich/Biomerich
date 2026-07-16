

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
  NAV_ANIMS.forEach((anim) => anim.cls && document.body.classList.remove(anim.cls));
  const entry = NAV_ANIMS.find((anim) => anim.key === key);
  if (entry?.cls) document.body.classList.add(entry.cls);
}

type Particle = Record<string, number | boolean | string>;
interface Accent { r: number; g: number; b: number }

function accentRgb(): Accent {
  const style = getComputedStyle(document.documentElement);
  return {
    r: parseInt(style.getPropertyValue("--ar").trim()) || 68,
    g: parseInt(style.getPropertyValue("--ag").trim()) || 85,
    b: parseInt(style.getPropertyValue("--ab").trim()) || 255,
  };
}

function buildParticles(key: string, w: number, h: number): Particle[] {
  const particles: Particle[] = [];
  if (key === "fireflies") {
    const count = Math.min(55, Math.floor((w * h) / 22000));
    for (let i = 0; i < count; i++) particles.push({ x: Math.random() * w, y: Math.random() * h, r: 1.2 + Math.random() * 2.2, speed: 0.18 + Math.random() * 0.28, angle: Math.random() * Math.PI * 2, drift: (Math.random() - 0.5) * 0.012, phase: Math.random() * Math.PI * 2, pulseSpeed: 0.008 + Math.random() * 0.012, glowR: 6 + Math.random() * 10 });
  }
  if (key === "rain") {
    const count = Math.min(90, Math.floor(w / 8));
    for (let i = 0; i < count; i++) particles.push({ x: Math.random() * w, y: Math.random() * h - h, len: 18 + Math.random() * 40, speed: 4 + Math.random() * 6, opacity: 0.04 + Math.random() * 0.12, width: 0.5 + Math.random() * 0.8 });
  }
  if (key === "stardust") {
    const count = Math.min(120, Math.floor((w * h) / 12000));
    for (let i = 0; i < count; i++) particles.push({ x: Math.random() * w, y: Math.random() * h, r: 0.4 + Math.random() * 1.4, vx: (Math.random() - 0.5) * 0.15, vy: (Math.random() - 0.5) * 0.12, phase: Math.random() * Math.PI * 2, twinkleSpeed: 0.015 + Math.random() * 0.025, baseOpacity: 0.1 + Math.random() * 0.55 });
  }
  return particles;
}

type Ctx = CanvasRenderingContext2D;

const num = (particle: Particle, field: string) => particle[field] as number;

function drawFireflies(ctx: Ctx, particles: Particle[], time: number, w: number, h: number, accent: Accent) {
  particles.forEach((p) => {
    p.angle = num(p, "angle") + num(p, "drift");
    p.x = num(p, "x") + Math.cos(num(p, "angle")) * num(p, "speed");
    p.y = num(p, "y") + Math.sin(num(p, "angle")) * num(p, "speed");
    if (num(p, "x") < -20) p.x = w + 10;
    if (num(p, "x") > w + 20) p.x = -10;
    if (num(p, "y") < -20) p.y = h + 10;
    if (num(p, "y") > h + 20) p.y = -10;
    const pulse = 0.45 + 0.55 * Math.sin(num(p, "phase") + time * num(p, "pulseSpeed"));
    const alpha = pulse * 0.85;
    const glowRadius = num(p, "glowR") * (0.7 + 0.3 * pulse);
    const glow = ctx.createRadialGradient(num(p, "x"), num(p, "y"), 0, num(p, "x"), num(p, "y"), glowRadius);
    glow.addColorStop(0, `rgba(${accent.r},${accent.g},${accent.b},${(alpha * 0.35).toFixed(3)})`);
    glow.addColorStop(1, `rgba(${accent.r},${accent.g},${accent.b},0)`);
    ctx.beginPath(); ctx.arc(num(p, "x"), num(p, "y"), glowRadius, 0, Math.PI * 2); ctx.fillStyle = glow; ctx.fill();
    ctx.beginPath(); ctx.arc(num(p, "x"), num(p, "y"), num(p, "r") * pulse, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${accent.r},${accent.g},${accent.b},${alpha.toFixed(3)})`; ctx.fill();
  });
}

function drawRain(ctx: Ctx, particles: Particle[], _t: number, w: number, h: number, accent: Accent) {
  ctx.lineCap = "round";
  particles.forEach((p) => {
    p.y = num(p, "y") + num(p, "speed");
    if (num(p, "y") - num(p, "len") > h) { p.y = -num(p, "len"); p.x = Math.random() * w; }
    const grad = ctx.createLinearGradient(num(p, "x"), num(p, "y") - num(p, "len"), num(p, "x"), num(p, "y"));
    grad.addColorStop(0, `rgba(${accent.r},${accent.g},${accent.b},0)`);
    grad.addColorStop(0.6, `rgba(${accent.r},${accent.g},${accent.b},${num(p, "opacity").toFixed(3)})`);
    grad.addColorStop(1, `rgba(${accent.r},${accent.g},${accent.b},0)`);
    ctx.beginPath(); ctx.moveTo(num(p, "x"), num(p, "y") - num(p, "len")); ctx.lineTo(num(p, "x"), num(p, "y"));
    ctx.strokeStyle = grad; ctx.lineWidth = num(p, "width"); ctx.stroke();
  });
}

function drawAurora(ctx: Ctx, _p: Particle[], time: number, w: number, h: number, accent: Accent) {
  const phase = time * 0.003;
  for (let band = 0; band < 4; band++) {
    const yBase = h * (0.08 + band * 0.22);
    const amp = h * (0.04 + band * 0.012);
    const freq = 0.0018 + band * 0.0006;
    const speed = phase * (0.4 + band * 0.15);
    const thick = h * (0.055 + band * 0.018);
    const alpha = 0.028 - band * 0.004;
    const bandR = Math.min(255, accent.r + band * 18), bandG = Math.min(255, accent.g + band * 7), bandB = Math.min(255, accent.b - band * 5);
    ctx.beginPath();
    for (let x = 0; x <= w; x += 3) {
      const y = yBase + Math.sin(x * freq + speed) * amp + Math.sin(x * freq * 1.7 + speed * 1.3 + band) * amp * 0.4;
      x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = `rgba(${bandR},${bandG},${bandB},${(alpha * 3).toFixed(3)})`; ctx.lineWidth = 1; ctx.stroke();
    for (let layer = 0; layer < 6; layer++) {
      const layerAlpha = alpha * (1 - layer / 6);
      const layerOffset = (layer / 6) * thick;
      ctx.beginPath();
      for (let x = 0; x <= w; x += 4) {
        const y = yBase + Math.sin(x * freq + speed) * amp + Math.sin(x * freq * 1.7 + speed * 1.3 + band) * amp * 0.4;
        x === 0 ? ctx.moveTo(x, y - layerOffset) : ctx.lineTo(x, y - layerOffset);
      }
      for (let x = w; x >= 0; x -= 4) {
        const y = yBase + Math.sin(x * freq + speed) * amp + Math.sin(x * freq * 1.7 + speed * 1.3 + band) * amp * 0.4;
        ctx.lineTo(x, y + layerOffset);
      }
      ctx.closePath(); ctx.fillStyle = `rgba(${bandR},${bandG},${bandB},${layerAlpha.toFixed(4)})`; ctx.fill();
    }
  }
}

function drawStardust(ctx: Ctx, particles: Particle[], time: number, w: number, h: number, accent: Accent) {
  particles.forEach((p) => {
    p.x = num(p, "x") + num(p, "vx"); p.y = num(p, "y") + num(p, "vy");
    if (num(p, "x") < 0) p.x = w; if (num(p, "x") > w) p.x = 0;
    if (num(p, "y") < 0) p.y = h; if (num(p, "y") > h) p.y = 0;
    const twinkle = num(p, "baseOpacity") * (0.3 + 0.7 * Math.abs(Math.sin(num(p, "phase") + time * num(p, "twinkleSpeed"))));
    const glow = ctx.createRadialGradient(num(p, "x"), num(p, "y"), 0, num(p, "x"), num(p, "y"), num(p, "r") * 4);
    glow.addColorStop(0, `rgba(${accent.r},${accent.g},${accent.b},${(twinkle * 0.4).toFixed(3)})`);
    glow.addColorStop(1, `rgba(${accent.r},${accent.g},${accent.b},0)`);
    ctx.beginPath(); ctx.arc(num(p, "x"), num(p, "y"), num(p, "r") * 4, 0, Math.PI * 2); ctx.fillStyle = glow; ctx.fill();
    ctx.beginPath(); ctx.arc(num(p, "x"), num(p, "y"), num(p, "r"), 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255,255,255,${twinkle.toFixed(3)})`; ctx.fill();
  });
}

const DRAW: Record<string, (ctx: Ctx, particles: Particle[], time: number, w: number, h: number, accent: Accent) => void> = {
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
    let particles: Particle[] = [];
    let time = 0;
    let raf = 0;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      particles = buildParticles(animKey, canvas.width, canvas.height);
    };
    resize();
    const draw = DRAW[animKey];
    if (!draw) { canvas.style.opacity = "0"; return; }
    canvas.style.opacity = "1";
    const tick = () => {
      time++;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      draw(ctx, particles, time, canvas.width, canvas.height, accentRgb());
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
