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
      const titledEl = target && target.closest ? target.closest("[title]") : null;
      if (!titledEl) return;
      if (titledEl.closest(".sidebar.is-rail")) return;
      const title = titledEl.getAttribute("title");
      if (!title || !title.trim()) return;
      if (heldRef.current?.el === titledEl) return;
      restore();
      heldRef.current = { el: titledEl, title };
      titledEl.setAttribute("title", "");
      setTip({ text: title, rect: titledEl.getBoundingClientRect() });
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
    const tipEl = ref.current;
    if (!tip || !tipEl) return;
    const margin = 8, gap = 9;
    const tipWidth = tipEl.offsetWidth, tipHeight = tipEl.offsetHeight;
    const anchor = tip.rect;
    let top = anchor.top - tipHeight - gap;
    let arrow = "bottom";
    if (top < margin) { top = anchor.bottom + gap; arrow = "top"; }
    let left = anchor.left + anchor.width / 2 - tipWidth / 2;
    left = Math.min(Math.max(margin, left), window.innerWidth - tipWidth - margin);
    tipEl.style.left = `${left}px`;
    tipEl.style.top = `${top}px`;
    tipEl.dataset.arrow = arrow;
    tipEl.style.setProperty("--tip-arrow-x", `${Math.min(Math.max(12, anchor.left + anchor.width / 2 - left), tipWidth - 12)}px`);
    tipEl.style.opacity = "1";
  }, [tip]);

  if (!tip) return null;
  return createPortal(
    <div ref={ref} className="tipz" style={{ opacity: 0 }} role="tooltip">{tip.text}</div>,
    document.body,
  );
}
