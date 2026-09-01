import { Suspense, useEffect, useRef } from "react";
import { Background } from "./components/Background";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { renderTab } from "./tabs/registry";
import { useStore } from "./store";
import { useEngine } from "./hooks/useEngine";
import { useBlockBrowserDefaults } from "./hooks/useBlockBrowserDefaults";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Loader } from "./components/Loader";
import { ThemeCanvas } from "./components/ThemeCanvas";
import { GlobalSearch } from "./components/GlobalSearch";
import { Tutorial } from "./components/Tutorial";
import { UpdateModal } from "./components/UpdateModal";
import { TesseractModal } from "./components/TesseractModal";
import { UserAgreement } from "./components/UserAgreement";
import { Dialog } from "./components/Dialog";
import { TooltipLayer } from "./components/Tooltip";
import { ToastLayer } from "./components/Toast";
import { RarePingWarning } from "./components/RarePingWarning";
import { BiomeHealthAlert } from "./components/BiomeHealthAlert";

export function App() {
  const currentTab = useStore((s) => s.currentTab);
  const mainRef = useRef<HTMLElement>(null);
  useEngine();
  useBlockBrowserDefaults();

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 });
  }, [currentTab]);

  let tabContent = renderTab(currentTab);

  return (
    <>
      <ThemeCanvas />
      <TooltipLayer />
      <ToastLayer />
      <Tutorial />
      <UpdateModal />
      <TesseractModal />
      <UserAgreement />
      <Dialog />
      <Loader />
      <Background />
      <div className="app-shell">
        <Sidebar />
        <div className="right-col">
          {}
          {currentTab !== "monitor" && <Topbar />}
          <BiomeHealthAlert />
          <GlobalSearch />
          <main className="main" ref={mainRef}>
            <ErrorBoundary key={currentTab}>
              <Suspense fallback={<div className="tab-loading" />}>
                {tabContent}
              </Suspense>
            </ErrorBoundary>
          </main>
        </div>
      </div>
      <RarePingWarning />
    </>
  );
}
