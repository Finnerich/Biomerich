import { callPy } from "../bridge";

interface MacroCredit { name: string; icon: string; repo: string }
const MACRO_CREDITS: MacroCredit[] = [
  { name: "Coteab Macro", icon: "fa-cubes-stacked", repo: "https://github.com/xVapure/Noteab-Macro" },
  { name: "Fishsol Macro", icon: "fa-fish", repo: "https://github.com/ivelchampion249/FishSol-Macro" },
  { name: "J.JARAM", icon: "fa-bolt", repo: "https://github.com/Jirach-1/J.JARAM" },
];

const TESTERS = [
  "ghostofdaylight", "thatoneslavic", "mexicanthethird", "huyent20.10",
  "bread_on_crack", "soniccobra95", "jowzyeet", "_reify",
];

export function Creator() {
  return (
    <section className="tab active-tab" id="credits">
      <header className="page-head">
        <h1>Credits</h1>
        <p>Credits idk what to write</p>
      </header>

      {}
      <div className="glass card credits-owner" data-reveal>
        <div className="co-badge"><i className="fa-solid fa-crown"></i></div>
        <div className="co-meta">
          <span className="co-label">Owner &amp; Developer</span>
          <span className="co-name">Finnerich</span>
          <span className="co-sub">Built SolRich: design, code, and everything else.</span>
        </div>
      </div>

      {}
      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-award"></i> Took inspiration from</div>
          <span className="badge badge-soft">huge credit</span>
        </div>
        <div className="credits-macros">
          {MACRO_CREDITS.map((macro) => (
            <div className="credit-macro gold-stroke" key={macro.name}>
              <div className="cm-ico"><i className={`fa-solid ${macro.icon}`}></i></div>
              <div className="cm-meta">
                <span className="cm-name">{macro.name}</span>
              </div>
              <button className="cm-gh" onClick={() => void callPy("open_url", macro.repo)}>
                <i className="fa-brands fa-github"></i> GitHub
              </button>
            </div>
          ))}
        </div>
      </div>

      {}
      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-circle-dot"></i> Special thanks</div>
        </div>
        <div className="credit-special">
          <div className="cs-ico"><i className="fa-solid fa-star"></i></div>
          <div className="cs-meta">
            <span className="cs-name">@thwpluywr</span>
            <span className="cs-role">Sol's RNG Tester. Helped me with the Eden contract prompt.</span>
          </div>
        </div>
      </div>

      {}
      <div className="glass card panel" data-reveal>
        <div className="panel-head">
          <div className="panel-title"><i className="fa-solid fa-flask-vial"></i> Testers</div>
          <span className="badge badge-soft">{TESTERS.length} sigmas</span>
        </div>
        <div className="credits-testers">
          {TESTERS.map((tester) => (
            <div className="credit-tester" key={tester}>
              <i className="fa-brands fa-discord"></i>
              <span>@{tester}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
