import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

interface TipState { text: string; rect: DOMRect; }

export function TooltipLayer() {
  const [tip, setTip] = useState<TipState | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const heldRef = useRef<{ el: Element; title: string } | null>(null);

  useEffect(() => {
    function restore() {
      const held = heldRef.current;
      if (held) {
        if (held.el.isConnected && !held.el.getAttribute("title")) {
          held.el.setAttribute("title", held.title);
        }
        heldRef.current = null;
      }
    }
    function clear() { restore(); setTip(null); }

    function onOver(e: MouseEvent) {
      const target = e.target as Element | null;
      const el = target && target.closest ? target.closest("[title]") : null;
      if (!el) return;
      if (el.closest(".sidebar.is-rail")) return;
      const title = el.getAttribute("title");
      if (!title || !title.trim()) return;
      if (heldRef.current?.el === el) return;
      restore();
      heldRef.current = { el, title };
      el.setAttribute("title", "");
      setTip({ text: title, rect: el.getBoundingClientRect() });
    }
    function onOut(e: MouseEvent) {
      const held = heldRef.current;
      if (!held) return;
      const related = e.relatedTarget as Node | null;
      if (related && held.el.contains(related)) return;
      clear();
    }

    document.addEventListener("mouseover", onOver, true);
    document.addEventListener("mouseout", onOut, true);
    window.addEventListener("scroll", clear, true);
    window.addEventListener("mousedown", clear, true);
    window.addEventListener("wheel", clear, true);
    return () => {
      restore();
      document.removeEventListener("mouseover", onOver, true);
      document.removeEventListener("mouseout", onOut, true);
      window.removeEventListener("scroll", clear, true);
      window.removeEventListener("mousedown", clear, true);
      window.removeEventListener("wheel", clear, true);
    };
  }, []);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!tip || !el) return;
    const margin = 8, gap = 9;
    const tw = el.offsetWidth, th = el.offsetHeight;
    const r = tip.rect;
    let top = r.top - th - gap;
    let arrow = "bottom";
    if (top < margin) { top = r.bottom + gap; arrow = "top"; }
    let left = r.left + r.width / 2 - tw / 2;
    left = Math.min(Math.max(margin, left), window.innerWidth - tw - margin);
    el.style.left = `${left}px`;
    el.style.top = `${top}px`;
    el.dataset.arrow = arrow;
    el.style.setProperty("--tip-arrow-x", `${Math.min(Math.max(12, r.left + r.width / 2 - left), tw - 12)}px`);
    el.style.opacity = "1";
  }, [tip]);

  if (!tip) return null;
  return createPortal(
    <div ref={ref} className="tipz" style={{ opacity: 0 }} role="tooltip">{tip.text}</div>,
    document.body,
  );
}
