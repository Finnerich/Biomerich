import { useEffect, useId, useRef, useState } from "react";

export interface SelectOption {
  value: string;
  label: string;
  icon?: string;
  iconClassName?: string;
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
  const [activeIndex, setActiveIndex] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLDivElement>(null);
  const baseId = useId();
  const listId = `${baseId}-list`;
  const optId = (index: number) => `${baseId}-opt-${index}`;

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
    document.getElementById(optId(activeIndex))?.scrollIntoView?.({ block: "nearest" });
  }, [open, activeIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  function openMenu() {
    if (disabled) return;
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0);
    setOpen(true);
  }

  function closeMenu(refocus = true) {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  }

  function choose(index: number) {
    const option = options[index];
    if (!option) return;
    onChange(option.value);
    closeMenu();
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (disabled) return;
    if (!open) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp" || event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openMenu();
      }
      return;
    }
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        setActiveIndex((i) => Math.min(options.length - 1, i + 1));
        break;
      case "ArrowUp":
        event.preventDefault();
        setActiveIndex((i) => Math.max(0, i - 1));
        break;
      case "Home":
        event.preventDefault();
        setActiveIndex(0);
        break;
      case "End":
        event.preventDefault();
        setActiveIndex(options.length - 1);
        break;
      case "Enter":
      case " ":
        event.preventDefault();
        choose(activeIndex);
        break;
      case "Escape":
        event.preventDefault();
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
      data-value={value}
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
        aria-activedescendant={open ? optId(activeIndex) : undefined}
        onMouseDown={(e) => { e.preventDefault(); open ? closeMenu(false) : openMenu(); }}
        onKeyDown={onKeyDown}
      >
        {selected?.icon && (
          <i
            className={`fa-solid ${selected.icon} cs-option-icon${selected.iconClassName ? ` ${selected.iconClassName}` : ""}`}
            aria-hidden="true"
          ></i>
        )}
        <span className={`cs-label${selected ? "" : " placeholder"}`}>{label}</span>
        <i className="fa-solid fa-chevron-down cs-arrow" aria-hidden="true"></i>
      </div>
      <div className="cs-dropdown" role="listbox" id={listId} aria-label={ariaLabel}>
        {options.map((option, i) => (
          <div
            key={option.value}
            id={optId(i)}
            role="option"
            aria-selected={option.value === value}
            className={`cs-option${option.value === value ? " selected" : ""}${i === activeIndex && open ? " highlighted" : ""}`}
            onMouseEnter={() => setActiveIndex(i)}
            onMouseDown={(e) => {
              e.preventDefault();
              choose(i);
            }}
          >
            {option.icon && (
              <i
                className={`fa-solid ${option.icon} cs-option-icon${option.iconClassName ? ` ${option.iconClassName}` : ""}`}
                aria-hidden="true"
              ></i>
            )}
            {option.label}
          </div>
        ))}
      </div>
    </div>
  );
}
