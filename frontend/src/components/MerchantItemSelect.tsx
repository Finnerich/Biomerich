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
    const t = window.setTimeout(() => inputRef.current?.focus(), 10);
    const onDocMouseDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => { window.clearTimeout(t); document.removeEventListener("mousedown", onDocMouseDown); };
  }, [open]);

  const q = query.trim().toLowerCase();
  const catalog = MERCHANT_AUTOBUY_CATALOG[mid].filter(
    (i) => (i.name === value || !exclude?.has(i.name)) && (!q || i.name.toLowerCase().includes(q)),
  );

  const groups: Array<{ tier: string; items: MerchantItem[] }> = [];
  for (const it of catalog) {
    const last = groups[groups.length - 1];
    if (last && last.tier === it.tier) last.items.push(it);
    else groups.push({ tier: it.tier, items: [it] });
  }

  const selected = MERCHANT_AUTOBUY_CATALOG[mid].find((i) => i.name === value);

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
          {groups.map((g, gi) => (
            <div key={`${g.tier}-${gi}`} className="ps-group">
              <div className="ps-group-head" style={headStyle(g.tier)}>
                <span className="ps-dot" style={dotStyle(g.tier)}></span>
                {merchantTierMeta(g.tier)?.label || g.tier}
              </div>
              {g.items.map((it) => (
                <div
                  key={it.name}
                  className={`cs-option ps-option${it.name === value ? " selected" : ""}`}
                  onMouseDown={(e) => { e.preventDefault(); onChange(it.name); setOpen(false); }}
                >
                  <span className="ps-dot" style={dotStyle(it.tier)}></span>
                  <span className="ps-oname">{it.name}</span>
                  <BuffBadges buffs={it.buffs} />
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
