import { useEffect } from "react";

export function useBlockBrowserDefaults(): void {
  useEffect(() => {
    const devToolsAvailable = () => {
      let available = false;
      return available;
    };

    const onKeyDown = (e: KeyboardEvent) => {
      const k = (e.key || "").toLowerCase();

      const devtools =
        !devToolsAvailable() &&
        (e.key === "F12" ||
          (e.ctrlKey && e.shiftKey && (k === "i" || k === "j" || k === "c")) ||
          (e.ctrlKey && k === "u"));

      const browserShortcuts =
        e.ctrlKey &&
        (k === "w" || k === "r" || k === "t" || k === "n" || k === "l" || k === "d" ||
          k === "h" || k === "j" || k === "b" || k === "p" || k === "s" || k === "u" ||
          k === "+" || k === "-" || k === "0");

      const fnKeys =
        e.key === "F5" || e.key === "F1" || e.key === "F3" || e.key === "F6" ||
        (e.altKey && e.key === "F4");

      const navKeys =
        (e.altKey && (e.key === "ArrowLeft" || e.key === "ArrowRight")) ||
        (!e.ctrlKey && !e.shiftKey && !e.altKey && e.key === "Backspace" &&
          !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement));

      if (devtools || browserShortcuts || fnKeys || navKeys) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    const onContextMenu = (e: MouseEvent) => {
      if (!devToolsAvailable()) e.preventDefault();
    };
    const onMouseDown = (e: MouseEvent) => {
      if (e.button === 1 || e.button === 3 || e.button === 4) e.preventDefault();
    };
    const onAuxClick = (e: MouseEvent) => {
      if (e.button === 1) e.preventDefault();
    };
    const onWheel = (e: WheelEvent) => {
      if (e.ctrlKey) e.preventDefault();
    };
    const onDragStart = (e: DragEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName !== "INPUT" && t.tagName !== "TEXTAREA") e.preventDefault();
    };

    document.addEventListener("keydown", onKeyDown, true);
    document.addEventListener("contextmenu", onContextMenu);
    document.addEventListener("mousedown", onMouseDown, true);
    document.addEventListener("auxclick", onAuxClick, true);
    document.addEventListener("wheel", onWheel, { passive: false });
    document.addEventListener("dragstart", onDragStart);

    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      document.removeEventListener("contextmenu", onContextMenu);
      document.removeEventListener("mousedown", onMouseDown, true);
      document.removeEventListener("auxclick", onAuxClick, true);
      document.removeEventListener("wheel", onWheel);
      document.removeEventListener("dragstart", onDragStart);
    };
  }, []);
}
