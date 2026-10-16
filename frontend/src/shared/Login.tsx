import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ApiError } from "./api";
import { homeFor, useAuth } from "./auth";
import { Button, Card } from "./ui";

const DEMO = [
  { label: "Player (tired, growth zone)", email: "p15@demo.pathtopro" },
  { label: "Player", email: "p03@demo.pathtopro" },
  { label: "Coach", email: "coach@demo.pathtopro" },
  { label: "Physio", email: "physio@demo.pathtopro" },
  { label: "Guardian", email: "guardian02@demo.pathtopro" },
];

export function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homeFor(user.role)} replace />;

  async function submit(e: FormEvent, override?: string) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(override ?? email, override ? "demo1234" : password);
      nav(homeFor(u.role));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Cannot reach the server");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="dark flex min-h-full items-center justify-center bg-pitch-950 p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center text-white">
          <img src="/icon.svg" alt="" className="mx-auto mb-3 h-14 w-14" />
          <h1 className="text-3xl font-extrabold tracking-tight">PathToPro</h1>
          <p className="mt-1 text-pitch-200">Train smart. Grow safe. Get better.</p>
        </div>
        <Card>
          <form onSubmit={submit} className="space-y-3">
            <label className="block">
              <span className="text-ink-2 text-sm font-medium">Email</span>
              <input
                className="bg-surface-2 border-line text-ink mt-1 h-12 w-full rounded-xl border px-3 text-base"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label className="block">
              <span className="text-ink-2 text-sm font-medium">Password</span>
              <input
                className="bg-surface-2 border-line text-ink mt-1 h-12 w-full rounded-xl border px-3 text-base"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            {error && (
              <p role="alert" className="text-ready-red text-sm font-medium">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" loading={busy}>
              Sign in
            </Button>
          </form>
          <div className="border-line mt-4 border-t pt-3">
            <p className="text-ink-2 mb-2 text-xs font-semibold uppercase">Demo accounts (synthetic data)</p>
            <div className="flex flex-wrap gap-2">
              {DEMO.map((d) => (
                <Button key={d.email} variant="secondary" size="sm" disabled={busy} onClick={(e) => submit(e, d.email)}>
                  {d.label}
                </Button>
              ))}
            </div>
          </div>
        </Card>
      </div>
    </main>
  );
}
