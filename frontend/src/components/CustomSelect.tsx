import { useEffect, useId, useRef, useState } from "react";

export interface SelectOption {
  value: string;
  label: string;
}

interface Props {
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
}

export function CustomSelect({
  options,
  value,
  onChange,
  placeholder = "Select…",
  disabled,
  className,
  "aria-label": ariaLabel,
}: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLDivElement>(null);
  const baseId = useId();
  const listId = `${baseId}-list`;
  const optId = (i: number) => `${baseId}-opt-${i}`;

  useEffect(() => {
    if (!open) return;
    const onDocMouseDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [open]);

  const selectedIndex = options.findIndex((o) => o.value === value);
  const selected = selectedIndex >= 0 ? options[selectedIndex] : undefined;
  const label = selected ? selected.label : placeholder;

  useEffect(() => {
    if (!open) return;
    document.getElementById(optId(active))?.scrollIntoView?.({ block: "nearest" });
  }, [open, active]); // eslint-disable-line react-hooks/exhaustive-deps

  function openMenu() {
    if (disabled) return;
    setActive(selectedIndex >= 0 ? selectedIndex : 0);
    setOpen(true);
  }

  function closeMenu(refocus = true) {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  }

  function choose(i: number) {
    const opt = options[i];
    if (!opt) return;
    onChange(opt.value);
    closeMenu();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (disabled) return;
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openMenu();
      }
      return;
    }
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActive((i) => Math.min(options.length - 1, i + 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((i) => Math.max(0, i - 1));
        break;
      case "Home":
        e.preventDefault();
        setActive(0);
        break;
      case "End":
        e.preventDefault();
        setActive(options.length - 1);
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        choose(active);
        break;
      case "Escape":
        e.preventDefault();
        closeMenu();
        break;
      case "Tab":
        setOpen(false);
        break;
    }
  }

  return (
    <div
      ref={wrapRef}
      className={`cs-wrap${open ? " open" : ""}${disabled ? " disabled" : ""}${className ? " " + className : ""}`}
    >
      <div
        ref={triggerRef}
        className="cs-trigger"
        role="combobox"
        tabIndex={disabled ? -1 : 0}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-disabled={disabled || undefined}
        aria-label={ariaLabel}
        aria-activedescendant={open ? optId(active) : undefined}
        onMouseDown={(e) => { e.preventDefault(); open ? closeMenu(false) : openMenu(); }}
        onKeyDown={onKeyDown}
      >
        <span className={`cs-label${selected ? "" : " placeholder"}`}>{label}</span>
        <i className="fa-solid fa-chevron-down cs-arrow" aria-hidden="true"></i>
      </div>
      <div className="cs-dropdown" role="listbox" id={listId} aria-label={ariaLabel}>
        {options.map((opt, i) => (
          <div
            key={opt.value}
            id={optId(i)}
            role="option"
            aria-selected={opt.value === value}
            className={`cs-option${opt.value === value ? " selected" : ""}${i === active && open ? " highlighted" : ""}`}
            onMouseEnter={() => setActive(i)}
            onMouseDown={(e) => {
              e.preventDefault();
              choose(i);
            }}
          >
            {opt.label}
          </div>
        ))}
      </div>
    </div>
  );
}
