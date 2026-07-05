export function BetaTag({ className }: { className?: string }) {
  return <span className={`beta-tag${className ? " " + className : ""}`}>BETA</span>;
}

export function BetaWarning({ what = "This feature" }: { what?: string }) {
  return (
    <div className="beta-warning">
      <i className="fa-solid fa-flask"></i>
      <span>
        <b>BETA: still unstable.</b> {what} reads the in-game chat to spot what's happening,
        and it doesn't always get it right: it can miss things, read them wrong, or react late.
        Use it at your own risk.
      </span>
    </div>
  );
}
