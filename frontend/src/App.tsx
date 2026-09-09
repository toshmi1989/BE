import { useState } from "react";
import { StudyWorkspace } from "./pages/StudyWorkspace";
import { ControlledBetaDashboard } from "./pages/ControlledBetaDashboard";

export default function App() {
  const [tab, setTab] = useState<"workspace" | "beta">("workspace");
  return (
    <div className="app-shell app-shell-wide">
      <header className="app-header">
        <div className="brand">BE Protocol Platform</div>
        <p className="tagline">
          Study workspace · Evidence · Decisions · Sample Size · Statistics · Protocol · Preflight
        </p>
        <nav className="beta-nav">
          <button type="button" className={tab === "workspace" ? "active" : ""} onClick={() => setTab("workspace")}>
            Study workspace
          </button>
          <button type="button" className={tab === "beta" ? "active" : ""} onClick={() => setTab("beta")}>
            Controlled beta
          </button>
        </nav>
      </header>
      <main>{tab === "workspace" ? <StudyWorkspace /> : <ControlledBetaDashboard />}</main>
    </div>
  );
}
