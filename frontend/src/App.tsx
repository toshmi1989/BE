import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginForm } from "./auth/LoginForm";
import { StudyWorkspace } from "./pages/StudyWorkspace";

function AppShell() {
  const { loading, authRequired, user, logout, version } = useAuth();

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
          {user && (
            <div className="auth-user-bar" style={{ textAlign: "right" }}>
              <div className="muted" style={{ fontSize: "0.9rem" }}>
                {user.email}
                {user.role ? ` · ${user.role}` : ""}
              </div>
              <button type="button" onClick={() => void logout()} style={{ marginTop: "0.35rem" }}>
                Logout
              </button>
            </div>
          )}
          {!authRequired && !user && version && (
            <div className="muted" style={{ fontSize: "0.85rem" }}>
              Local dev · auth off
            </div>
          )}
        </div>
      </header>
      <main>
        <StudyWorkspace />
      </main>
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
