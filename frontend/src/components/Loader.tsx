import { useStore } from "../store";

export function Loader() {
  const loading = useStore((s) => s.loading);
  const status = useStore((s) => s.loaderStatus);

  return (
    <div className={`loader${loading ? "" : " hide"}`} id="loadingScreen">
      <div className="loader-inner">
        <div className="loader-mark"><i className="fa-solid fa-satellite-dish"></i></div>
        <div className="loader-name">SolRich</div>
        <div className="loader-bar"><span></span></div>
        <div className="loader-status">{status}</div>
      </div>
    </div>
  );
}
