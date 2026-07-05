import { Component, type ReactNode } from "react";

interface Props { children: ReactNode }
interface State { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }
  componentDidCatch(error: Error, info: unknown) {
    console.error("[SolRich] tab crashed:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <section className="tab active-tab">
          <header className="page-head">
            <h1>This tab crashed</h1>
            <p>Something went wrong while rendering. The rest of the app keeps running.</p>
          </header>
          <div className="glass card panel" style={{ padding: 20 }}>
            <div className="panel-head"><div className="panel-title"><i className="fa-solid fa-triangle-exclamation"></i> Error</div></div>
            <pre style={{ whiteSpace: "pre-wrap", color: "var(--text-dim)", fontSize: 12, margin: 0 }}>
              {String(this.state.error.stack || this.state.error.message || this.state.error)}
            </pre>
            <button className="btn-add" style={{ marginTop: 14 }} onClick={() => location.reload()}>
              <i className="fa-solid fa-rotate-right"></i> Reload app
            </button>
          </div>
        </section>
      );
    }
    return this.props.children;
  }
}
