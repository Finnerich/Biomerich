import { labelOfTab } from "../navConfig";

export function Placeholder({ tab }: { tab: string }) {
  return (
    <section className="tab active-tab">
      <header className="page-head">
        <h1>{labelOfTab(tab)}</h1>
        <p>This tab isn't available in this build.</p>
      </header>
      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title">
            <i className="fa-solid fa-circle-info"></i> Not available
          </div>
        </div>
        <p style={{ padding: "16px", opacity: 0.7 }}>
          "{labelOfTab(tab)}" doesn't exist in this version of SolRich.
        </p>
      </div>
    </section>
  );
}
