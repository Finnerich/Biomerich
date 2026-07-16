import { useEffect, useRef, useState } from "react";
import {
  MERCHANT_AUTOBUY_CATALOG, RUNE_GRAD, merchantTierMeta,
  type AutobuyMerchant, type MerchantItem,
} from "../data/merchantItems";
import { BuffBadges } from "./PotionSelect";

function dotStyle(tier: string): React.CSSProperties {
  if (tier === "rune") return { background: RUNE_GRAD };
  return { background: merchantTierMeta(tier)?.color || "transparent" };
}

function headStyle(tier: string): React.CSSProperties {
  if (tier === "rune") {
    return {
      background: RUNE_GRAD,
      WebkitBackgroundClip: "text",
      backgroundClip: "text",
      WebkitTextFillColor: "transparent",
    };
  }
  return { color: merchantTierMeta(tier)?.color || "inherit" };
}

export function MerchantItemSelect({ mid, value, onChange, exclude, disabled, className }: {
  mid: AutobuyMerchant;
  value: string;
  onChange: (name: string) => void;
  exclude?: Set<string>;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 10);
    const onDocMouseDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => { window.clearTimeout(focusTimer); document.removeEventListener("mousedown", onDocMouseDown); };
  }, [open]);

  const normalizedQuery = query.trim().toLowerCase();
  const catalog = MERCHANT_AUTOBUY_CATALOG[mid].filter(
    (item) => (item.name === value || !exclude?.has(item.name)) && (!normalizedQuery || item.name.toLowerCase().includes(normalizedQuery)),
  );

  const groups: Array<{ tier: string; items: MerchantItem[] }> = [];
  for (const item of catalog) {
    const last = groups[groups.length - 1];
    if (last && last.tier === item.tier) last.items.push(item);
    else groups.push({ tier: item.tier, items: [item] });
  }

  const selected = MERCHANT_AUTOBUY_CATALOG[mid].find((item) => item.name === value);

  return (
    <div
      ref={wrapRef}
      className={`cs-wrap potion-select${open ? " open" : ""}${disabled ? " disabled" : ""}${className ? " " + className : ""}`}
    >
      <div
        className="cs-trigger"
        tabIndex={0}
        onMouseDown={(e) => { e.preventDefault(); if (!disabled) setOpen((v) => !v); }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (!disabled) setOpen((v) => !v); }
          if (e.key === "Escape") setOpen(false);
        }}
      >
        {selected ? (
          <span className="ps-val">
            <span className="ps-dot" style={dotStyle(selected.tier)}></span>
            <span className="ps-oname">{selected.name}</span>
            <BuffBadges buffs={selected.buffs} />
          </span>
        ) : (
          <span className="cs-label placeholder">Select an item…</span>
        )}
        <i className="fa-solid fa-chevron-down cs-arrow"></i>
      </div>

      <div className="cs-dropdown ps-dropdown">
        <div className="ps-search">
          <i className="fa-solid fa-magnifying-glass"></i>
          <input
            ref={inputRef}
            value={query}
            placeholder="Search items…"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
          />
        </div>
        <div className="ps-scroll">
          {groups.map((group, i) => (
            <div key={`${group.tier}-${i}`} className="ps-group">
              <div className="ps-group-head" style={headStyle(group.tier)}>
                <span className="ps-dot" style={dotStyle(group.tier)}></span>
                {merchantTierMeta(group.tier)?.label || group.tier}
              </div>
              {group.items.map((item) => (
                <div
                  key={item.name}
                  className={`cs-option ps-option${item.name === value ? " selected" : ""}`}
                  onMouseDown={(e) => { e.preventDefault(); onChange(item.name); setOpen(false); }}
                >
                  <span className="ps-dot" style={dotStyle(item.tier)}></span>
                  <span className="ps-oname">{item.name}</span>
                  <BuffBadges buffs={item.buffs} />
                </div>
              ))}
            </div>
          ))}
          {!catalog.length && <div className="ps-empty">No items match “{query}”.</div>}
        </div>
      </div>
    </div>
  );
}
