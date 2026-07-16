import { useEffect } from "react";
import { useStore } from "../store";
import { callPy } from "../bridge";
import { renderMarkdown } from "../markdown";
import { isUpdateAvailable, latestUrl } from "../update";
import { useUpdateInstall } from "../updateInstall";

const mb = (bytes: number) => (Math.max(0, bytes) / 1048576).toFixed(1);

export function UpdateModal() {
  const open = useStore((s) => s.updateModalOpen);
  const releases = useStore((s) => s.releases);
  const phase = useUpdateInstall((s) => s.phase);
  const percent = useUpdateInstall((s) => s.percent);
  const downloaded = useUpdateInstall((s) => s.downloaded);
  const total = useUpdateInstall((s) => s.total);
  const error = useUpdateInstall((s) => s.error);
  const busy = phase === "downloading" || phase === "launching";

  const close = () => {
    if (busy) return;
    useStore.getState().setUpdateModalOpen(false);
    useUpdateInstall.getState().reset();
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, busy]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!isUpdateAvailable(releases)) return null;
  const latest = releases!.releases![0];
  const githubUrl = latestUrl(releases);
  const currentVersion = "v" + String(releases!.current || "?").replace(/^v/i, "");
  const latestVersion = "v" + String(releases!.latest || latest.tag || "?").replace(/^v/i, "");
  const body = latest.body;
  const exeUrl = latest.exeUrl;
  const exeName = latest.exeName || `SolRich-${latestVersion}.exe`;

  function openGithub() {
    if (githubUrl) void callPy("open_url", githubUrl);
    close();
  }
  function install() {
    if (exeUrl) void useUpdateInstall.getState().start(exeUrl, exeName);
  }

  const choosing = phase === "idle" || phase === "error";
  const barPct = phase === "launching" || phase === "done" ? 100 : Math.max(0, Math.min(100, percent));

  return (
    <div className={`modal-overlay${open ? " open" : ""}`} onClick={(e) => { if (e.target === e.currentTarget) close(); }}>
      <div className="modal glass update-modal" role="dialog" aria-modal="true" aria-label="New version available">
        <div className="update-icon"><i className="fa-solid fa-rocket"></i></div>
        <div className="update-head">
          <span className="update-title">New version of SolRich available</span>
          <span className="update-sub">{phase === "done" ? "Launching the new version…" : "Wanna upgrade?"}</span>
        </div>
        <div className="update-versions">
          <div className="uv-box">
            <span className="uv-label">Current</span>
            <span className="uv-val">{currentVersion}</span>
          </div>
          <i className="fa-solid fa-arrow-right uv-arrow"></i>
          <div className="uv-box new">
            <span className="uv-label">New</span>
            <span className="uv-val">{latestVersion}</span>
          </div>
        </div>
        {latest.unstable && (
          <div className="update-unstable">
            <i className="fa-solid fa-triangle-exclamation"></i>
            <span>This is an unstable {(latest.channel || "pre-release").toUpperCase()} version. Expect bugs.</span>
          </div>
        )}

        {choosing ? (
          <>
            {body && String(body).trim() && (
              <div className="update-notes-wrap">
                <div className="update-notes-head"><i className="fa-solid fa-list-ul"></i> What's new</div>
                <div className="update-notes">{renderMarkdown(body)}</div>
              </div>
            )}
            {phase === "error" && error && (
              <div className="update-unstable">
                <i className="fa-solid fa-triangle-exclamation"></i>
                <span>{error}</span>
              </div>
            )}
            <div className="modal-foot">
              <button className="btn-cancel" onClick={close}>Later</button>
              <button className="btn-show" onClick={openGithub}>
                <i className="fa-brands fa-github"></i> Open on GitHub
              </button>
              {exeUrl && (
                <button className="btn-save" onClick={install}>
                  <i className="fa-solid fa-download"></i> {phase === "error" ? "Try again" : "Download & install"}
                </button>
              )}
            </div>
            {!exeUrl && (
              <div className="update-no-exe">
                <i className="fa-solid fa-circle-info"></i> This release has no installer to download here. Get it from GitHub.
              </div>
            )}
          </>
        ) : (
          <div className="update-progress">
            <div className={`tess-bar${(!total && phase === "downloading") || phase === "launching" ? " indeterminate" : ""}`}>
              <div className="tess-bar-fill" style={{ width: `${barPct}%` }}></div>
            </div>
            <div className="tess-stats">
              {phase === "downloading" ? (
                total ? (
                  <>
                    <span className="tess-mb">{mb(downloaded)} / {mb(total)} MB</span>
                    <span className="tess-pct">{Math.round(percent)}%</span>
                  </>
                ) : (
                  <span className="tess-mb">{mb(downloaded)} MB downloaded…</span>
                )
              ) : (
                <span className="tess-mb">Starting the new version… this window will close.</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
