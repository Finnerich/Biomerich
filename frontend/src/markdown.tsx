import type { ReactNode } from "react";
import { callPy } from "./bridge";

const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(\[[^\]]+\]\(https?:\/\/[^\s)]+\))/;

function parseInline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let rest = text;
  let key = 0;
  while (rest) {
    const m = INLINE.exec(rest);
    if (!m) {
      out.push(rest);
      break;
    }
    if (m.index > 0) out.push(rest.slice(0, m.index));
    const tok = m[0];
    if (tok.startsWith("`")) {
      out.push(<code key={key++}>{tok.slice(1, -1)}</code>);
    } else if (tok.startsWith("**")) {
      out.push(<strong key={key++}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("*")) {
      out.push(<em key={key++}>{tok.slice(1, -1)}</em>);
    } else {
      const lm = tok.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
      if (lm) {
        const url = lm[2];
        out.push(
          <a key={key++} className="patch-link" onClick={() => void callPy("open_url", url)}>
            {lm[1]}
          </a>,
        );
      } else {
        out.push(tok);
      }
    }
    rest = rest.slice(m.index + tok.length);
  }
  return out;
}

export function renderMarkdown(md: string | undefined): ReactNode {
  const lines = String(md || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let listItems: ReactNode[] | null = null;
  let key = 0;

  const flushList = () => {
    if (listItems) {
      blocks.push(
        <ul className="patch-ul" key={key++}>
          {listItems}
        </ul>,
      );
      listItems = null;
    }
  };

  lines.forEach((raw) => {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flushList();
      return;
    }
    let m: RegExpMatchArray | null;
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
      flushList();
      const lvl = m[1].length;
      blocks.push(
        <div className={`patch-h patch-h${lvl}`} key={key++}>
          {parseInline(m[2])}
        </div>,
      );
      return;
    }
    if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {
      if (!listItems) listItems = [];
      listItems.push(<li key={listItems.length}>{parseInline(m[1])}</li>);
      return;
    }
    flushList();
    blocks.push(
      <p className="patch-p" key={key++}>
        {parseInline(line)}
      </p>,
    );
  });
  flushList();

  if (!blocks.length) return <p className="patch-p patch-muted">No notes for this release.</p>;
  return <>{blocks}</>;
}
