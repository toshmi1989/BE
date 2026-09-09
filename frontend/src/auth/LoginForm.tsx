import { useState, type FormEvent } from "react";
import { useAuth } from "./AuthContext";

export function LoginForm() {
  const { login, register, error: authError } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLocalError(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await register({
          email: email.trim(),
          password,
          display_name: displayName.trim() || email.trim(),
          organization_name: organizationName.trim() || "Local Org",
        });
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel auth-panel" style={{ maxWidth: 420, margin: "2rem auto" }}>
      <h1 style={{ marginTop: 0 }}>{mode === "login" ? "Sign in" : "Create account"}</h1>
      <p className="muted">Authentication is required for this deployment.</p>
      <form onSubmit={onSubmit} className="auth-form">
        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </label>
        {mode === "register" && (
          <>
            <label>
              Display name
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your name"
              />
            </label>
            <label>
              Organization
              <input
                type="text"
                value={organizationName}
                onChange={(e) => setOrganizationName(e.target.value)}
                placeholder="Organization name"
                required
              />
            </label>
          </>
        )}
        {(localError || authError) && (
          <p className="error" role="alert">
            {localError || authError}
          </p>
        )}
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginTop: "0.75rem" }}>
          <button type="submit" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Register"}
          </button>
          <button
            type="button"
            className="linkish"
            disabled={busy}
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setLocalError(null);
            }}
          >
            {mode === "login" ? "Need an account?" : "Have an account?"}
          </button>
        </div>
      </form>
    </section>
  );
}
