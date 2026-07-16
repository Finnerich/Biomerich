import { useEffect, useRef } from "react";
import { useSearch } from "../search";

export function GlobalSearch() {
  const open = useSearch((s) => s.open);
  const query = useSearch((s) => s.query);
  const results = useSearch((s) => s.results);
  const idx = useSearch((s) => s.idx);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const search = useSearch.getState();
      if (e.ctrlKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        search.open ? search.closeSearch() : search.openSearch();
        return;
      }
      if (!search.open) return;
      if (e.key === "Escape") {
        search.closeSearch();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        search.move(1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        search.move(-1);
      } else if (e.key === "Enter") {
        e.preventDefault();
        search.pick();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <>
      <div className="search-overlay" onClick={() => useSearch.getState().closeSearch()}></div>
      <div className="search-palette glass" role="dialog" aria-label="Search">
        <div className="search-palette-input">
          <i className="fa-solid fa-magnifying-glass"></i>
          <input
            ref={inputRef}
            id="globalSearch"
            type="text"
            placeholder="Search tabs, actions, accounts…"
            value={query}
            onChange={(e) => useSearch.getState().setQuery(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          <kbd>esc</kbd>
        </div>
        {results.length > 0 ? (
          <div className="search-results">
            {results.map((result, i) => (
              <div
                className={`sr-item ${i === idx ? "focused" : ""}`}
                key={i}
                onMouseDown={() => useSearch.getState().pick(i)}
                onMouseOver={() => useSearch.getState().setIdx(i)}
              >
                <span className="sr-ico"><i className={`fa-solid ${result.icon}`}></i></span>
                <span className="sr-body">
                  <span className="sr-label">{result.label}</span>
                  <span className="sr-sub">{result.sub}</span>
                </span>
                <kbd className="sr-enter" style={{ opacity: i === idx ? 1 : 0 }}>↵</kbd>
              </div>
            ))}
          </div>
        ) : (
          <div className="search-empty">
            {query.trim() ? "Nothing found." : "Type to jump to any tab, setting or account."}
          </div>
        )}
      </div>
    </>
  );
}
