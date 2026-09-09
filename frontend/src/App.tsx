import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginForm } from "./auth/LoginForm";
import { AiSettingsModal } from "./components/AiSettingsModal";
import { StudyWorkspace } from "./pages/StudyWorkspace";
import { useEffect, useState } from "react";
import { getAiSettings, type AiSettingsView } from "./api/client";

function AppShell() {
  const { loading, authRequired, user, logout, version } = useAuth();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [aiView, setAiView] = useState<AiSettingsView | null>(null);

  useEffect(() => {
    if (loading) return;
    let cancelled = false;
    (async () => {
      try {
        const view = await getAiSettings();
        if (!cancelled) setAiView(view);
      } catch {
        /* optional */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loading]);

  if (loading) {
    return (
      <div className="app-shell app-shell-wide">
        <header className="app-header">
          <div className="brand">BE Protocol Platform</div>
          <p className="tagline">Loading…</p>
        </header>
      </div>
    );
  }

  if (authRequired && !user) {
    return (
      <div className="app-shell app-shell-wide">
        <header className="app-header">
          <div className="brand">BE Protocol Platform</div>
          <p className="tagline">Sign in to continue</p>
        </header>
        <main>
          <LoginForm />
        </main>
      </div>
    );
  }

  const aiOn = Boolean(aiView?.enabled ?? version?.ai_enabled);

  return (
    <div className="app-shell app-shell-wide">
      <header className="app-header">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: "1rem",
            flexWrap: "wrap",
          }}
        >
          <div>
            <div className="brand">BE Protocol Platform</div>
            <p className="tagline">
              Writer workspace · Documents · Data · Decisions · Sample Size · Statistics · Protocol ·
              Preflight
            </p>
          </div>
          <div className="auth-user-bar" style={{ textAlign: "right" }}>
            <div className="muted" style={{ fontSize: "0.85rem" }}>
              ИИ: {aiOn ? "вкл" : "выкл"}
              {aiView?.model ? ` · ${aiView.model}` : ""}
              {!authRequired && !user ? " · local-dev" : ""}
            </div>
            {user ? (
              <div className="muted" style={{ fontSize: "0.9rem" }}>
                {user.email}
                {user.role ? ` · ${user.role}` : ""}
              </div>
            ) : null}
            <div className="header-actions" style={{ justifyContent: "flex-end", marginTop: "0.35rem" }}>
              <button type="button" className="secondary" onClick={() => setSettingsOpen(true)}>
                Настройки
              </button>
              {user ? (
                <button type="button" onClick={() => void logout()}>
                  Logout
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </header>
      <main>
        <StudyWorkspace aiEnabledOverride={aiOn} />
      </main>
      <AiSettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={(view) => setAiView(view)}
      />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
