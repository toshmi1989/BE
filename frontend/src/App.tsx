import { StudyWorkspace } from "./pages/StudyWorkspace";

export default function App() {
  return (
    <div className="app-shell app-shell-wide">
      <header className="app-header">
        <div className="brand">BE Protocol Platform</div>
        <p className="tagline">
          Writer workspace · Documents · Data · Decisions · Sample Size · Statistics · Protocol · Preflight
        </p>
      </header>
      <main>
        <StudyWorkspace />
      </main>
    </div>
  );
}
