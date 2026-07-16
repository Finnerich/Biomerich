import { useEffect, useState } from "react";
import { callPy } from "../bridge";
import { renderMarkdown } from "../markdown";
import { useStore, type Release, type Releases } from "../store";
import { loadReleases } from "../update";
import { useUpdateInstall } from "../updateInstall";

function fmtDate(iso?: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}


const mb = (bytes: number) => (Math.max(0, bytes) / 1048576).toFixed(1);

export function Patchlog() {
  const releases = useStore((s) => s.releases);
  const [expanded, setExpanded] = useState(true);

  const phase = useUpdateInstall((s) => s.phase);
  const percent = useUpdateInstall((s) => s.percent);
  const downloaded = useUpdateInstall((s) => s.downloaded);
  const total = useUpdateInstall((s) => s.total);
  const instError = useUpdateInstall((s) => s.error);

  useEffect(() => {
    void loadReleases();
  }, []);

  const hasUpdate = !!(releases?.available && releases.releases && releases.releases.length);
  const latest = releases?.releases?.[0];
  const exeUrl = latest?.exeUrl;
  const exeName = latest?.exeName || `SolRich-${String(releases?.latest || latest?.tag || "").replace(/^v/i, "")}.exe`;
  const choosing = phase === "idle" || phase === "error";
  const barPct = phase === "launching" || phase === "done" ? 100 : Math.max(0, Math.min(100, percent));

  function installUpdate() {
    if (exeUrl) void useUpdateInstall.getState().start(exeUrl, exeName);
  }

  return (
    <section className="tab active-tab" id="patchlog">
      <header className="page-head">
        <h1>Patchlog</h1>
        <p>Every SolRich release and what's new in each version.</p>
      </header>

      <div>
        {hasUpdate && latest && (
          <div className="glass card patch-banner" data-reveal>
            <div className="patch-banner-head">
              <div className="patch-banner-left">
                <span className="patch-banner-icon"><i className="fa-solid fa-rocket"></i></span>
                <div className="patch-banner-text">
                  <span className="patch-banner-title">New version available</span>
                  <span className="patch-banner-sub">
                    v{String(releases?.current || "?").replace(/^v/i, "")} →{" "}
                    <b>v{String(releases?.latest || latest.tag || "?").replace(/^v/i, "")}</b>
                  </span>
                </div>
              </div>
              <div className="patch-banner-btns">
                <button className="btn-cancel patch-toggle" onClick={() => setExpanded((v) => !v)}>
                  <i className={`fa-solid fa-chevron-${expanded ? "up" : "down"}`}></i>
                  {expanded ? "Hide patchlog" : "Show patchlog"}
                </button>
                {choosing ? (
                  <>
                    <button className="btn-show" onClick={() => void callPy("open_url", latest.url)}>
                      <i className="fa-brands fa-github"></i> Open on GitHub
                    </button>
                    {exeUrl && (
                      <button className="btn-save patch-upgrade" onClick={installUpdate}>
                        <i className="fa-solid fa-download"></i> {phase === "error" ? "Try again" : "Download & install"}
                      </button>
                    )}
                  </>
                ) : (
                  <span className="patch-inst-busy">
                    {phase === "downloading" ? (total ? `Downloading… ${Math.round(percent)}%` : "Downloading…") : "Launching…"}
                  </span>
                )}
              </div>
            </div>
            {!choosing && (
              <div className="patch-inst-progress">
                <div className={`tess-bar${(!total && phase === "downloading") || phase === "launching" ? " indeterminate" : ""}`}>
                  <div className="tess-bar-fill" style={{ width: `${barPct}%` }}></div>
                </div>
                <div className="tess-stats">
                  {phase === "downloading" ? (
                    total ? (
                      <><span className="tess-mb">{mb(downloaded)} / {mb(total)} MB</span><span className="tess-pct">{Math.round(percent)}%</span></>
                    ) : (
                      <span className="tess-mb">{mb(downloaded)} MB downloaded…</span>
                    )
                  ) : (
                    <span className="tess-mb">Starting the new version… this window will close.</span>
                  )}
                </div>
              </div>
            )}
            {phase === "error" && instError && (
              <div className="patch-inst-error"><i className="fa-solid fa-triangle-exclamation"></i> {instError}</div>
            )}
            <div className={`patch-banner-body ${expanded ? "open" : ""}`}>
              <div className="pbb-inner">{renderMarkdown(latest.body)}</div>
            </div>
          </div>
        )}
      </div>

      <div className="patchlog-list">
        <PatchlogBody releases={releases} />
      </div>
    </section>
  );
}

function PatchlogBody({ releases }: { releases: Releases | null }) {
  if (!releases) {
    return (
      <div className="patch-loading">
        <i className="fa-solid fa-spinner fa-spin"></i> Loading releases…
      </div>
    );
  }
  if (releases.error || !releases.releases || !releases.releases.length) {
    const msg =
      releases.error === "no_releases"
        ? "No releases published yet."
        : "Couldn't reach GitHub. Check your connection and try again.";
    return (
      <div className="patch-loading">
        <i className="fa-solid fa-circle-exclamation"></i> {msg}
      </div>
    );
  }
  return (
    <>
      {releases.releases.map((rel, i) => (
        <ReleaseCard key={rel.tag || i} rel={rel} highlight={i === 0 && !!releases.available} />
      ))}
    </>
  );
}

function ReleaseCard({ rel, highlight }: { rel: Release; highlight: boolean }) {
  const date = fmtDate(rel.publishedAt);
  return (
    <div className={`glass card patch-card ${highlight ? "highlight" : ""}`} data-reveal>
      <div className="patch-card-head">
        <div className="patch-titles">
          <span className="patch-tag">{rel.tag}</span>
          <span className="patch-name">{rel.name}</span>
          {rel.prerelease && <span className="patch-badge pre">Pre-release</span>}
        </div>
        <div className="patch-actions">
          {date && (
            <span className="patch-date">
              <i className="fa-regular fa-calendar"></i> {date}
            </span>
          )}
          <button className="btn-show patch-view" onClick={() => void callPy("open_url", rel.url)}>
            <i className="fa-solid fa-arrow-up-right-from-square"></i> View release
          </button>
        </div>
      </div>
      <div className="patch-body">{renderMarkdown(rel.body)}</div>
    </div>
  );
}
