import { MiscSettings } from "./moduleBuilder/parts";

export function Safety() {
  return (
    <section className="tab active-tab" id="safety">
      <header className="page-head">
        <h1>Safety</h1>
        <p>Configure the failsafes that protect your macro session.</p>
      </header>

      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-shield-halved"></i> Failsafes</div>
        </div>
        <MiscSettings />
      </div>
    </section>
  );
}
