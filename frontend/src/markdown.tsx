import type { ReactNode } from "react";
import { callPy } from "./bridge";

const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(\[[^\]]+\]\(https?:\/\/[^\s)]+\))/;

function parseInline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let rest = text;
  let key = 0;
  while (rest) {
    const match = INLINE.exec(rest);
    if (!match) {
      out.push(rest);
      break;
    }
    if (match.index > 0) out.push(rest.slice(0, match.index));
    const token = match[0];
    if (token.startsWith("`")) {
      out.push(<code key={key++}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith("**")) {
      out.push(<strong key={key++}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("*")) {
      out.push(<em key={key++}>{token.slice(1, -1)}</em>);
    } else {
      const linkMatch = token.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
      if (linkMatch) {
        const url = linkMatch[2];
        out.push(
          <a key={key++} className="patch-link" onClick={() => void callPy("open_url", url)}>
            {linkMatch[1]}
          </a>,
        );
      } else {
        out.push(token);
      }
    }
    rest = rest.slice(match.index + token.length);
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
    let match: RegExpMatchArray | null;
    if ((match = line.match(/^(#{1,4})\s+(.*)$/))) {
      flushList();
      const level = match[1].length;
      blocks.push(
        <div className={`patch-h patch-h${level}`} key={key++}>
          {parseInline(match[2])}
        </div>,
      );
      return;
    }
    if ((match = line.match(/^\s*[-*]\s+(.*)$/))) {
      if (!listItems) listItems = [];
      listItems.push(<li key={listItems.length}>{parseInline(match[1])}</li>);
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
