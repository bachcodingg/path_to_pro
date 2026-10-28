import { Battery, CalendarDays, ClipboardList, Compass, Heart, ShieldCheck, Star, Stethoscope, Users } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "./api";
import { homeFor, useAuth } from "./auth";
import { LegalLinks } from "../legal/Legal";
import { Button, Card } from "./ui";

// The demo story's accounts, grouped by who uses the app, each with what it shows
const DEMO = [
  {
    group: "Players",
    accounts: [
      { label: "Leon, U15", note: "Tired, in the growth zone", email: "p15@demo.pathtopro", icon: Battery },
      { label: "Academy player", note: "A normal week", email: "p03@demo.pathtopro", icon: CalendarDays },
      { label: "Dual-squad player", note: "U19 + men's team", email: "dual@demo.pathtopro", icon: Users },
      { label: "Self-guided player", note: "No club, own plan", email: "amateur@demo.pathtopro", icon: Compass },
    ],
  },
  {
    group: "Staff",
    accounts: [
      { label: "Coach", note: "Squad, matches, analysis", email: "coach@demo.pathtopro", icon: ClipboardList },
      { label: "Men's team coach", note: "Senior squad", email: "mencoach@demo.pathtopro", icon: Star },
      { label: "Physio", note: "Escalation queue", email: "physio@demo.pathtopro", icon: Stethoscope },
    ],
  },
  {
    group: "Family",
    accounts: [{ label: "Guardian", note: "A parent's view", email: "guardian02@demo.pathtopro", icon: Heart }],
  },
];

const PITCH = [
  { icon: Battery, title: "Readiness every morning", text: "Sleep, heart-rate variability and a 30-second check-in become one battery score." },
  { icon: ShieldCheck, title: "Safe through growth spurts", text: "Hard limits for the growth zone and load spikes, checked on every plan change." },
  { icon: ClipboardList, title: "Coaches stay in charge", text: "Every plan change comes with its reason. Small ones apply and the coach is told; bigger ones wait for approval." },
];

export function Login() {
  const { user, login, finishMfa } = useAuth();
  const nav = useNavigate();
  // After a password reset on an account with two-step sign-in, the code step comes here
  const location = useLocation();
  const [mfaToken, setMfaToken] = useState<string | null>((location.state as { mfaToken?: string } | null)?.mfaToken ?? null);
  const [code, setCode] = useState("");
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
      if ("mfaToken" in u) setMfaToken(u.mfaToken);
      else nav(homeFor(u.role));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Cannot reach the server");
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await finishMfa(mfaToken!, code);
      nav(homeFor(u.role));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Cannot reach the server");
      if (err instanceof ApiError && err.message.startsWith("Sign in again")) setMfaToken(null);
    } finally {
      setBusy(false);
    }
  }

  // Laptop: what the app does on the left, sign-in and the demo accounts on the right. Phone: stacked.
  return (
    <main className="dark bg-pitch-950 min-h-full lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <section className="hero flex flex-col justify-between gap-8 px-6 py-8 lg:px-14 lg:py-12">
        <div className="flex items-center justify-between gap-3">
          <Link to="/" className="flex items-center gap-3">
            <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="h-11 w-11" />
            <span className="font-display text-2xl font-extrabold tracking-wide uppercase">PathToPro</span>
          </Link>
          <Link to="/" className="text-sm font-semibold text-white/70 hover:text-white">
            ← Overview
          </Link>
        </div>
        <div>
          <p className="text-pitch-300 text-xs font-bold tracking-[0.16em] uppercase">For academy players aged 13 to 18</p>
          <h1 className="font-display mt-2 text-5xl leading-[0.95] font-extrabold uppercase lg:text-7xl">
            Train smart.
            <br />
            Grow safe.
            <br />
            <span className="text-pitch-300">Get better.</span>
          </h1>
          <ul className="mt-8 hidden max-w-lg space-y-4 lg:block">
            {PITCH.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10">
                  <Icon className="text-pitch-300 h-5 w-5" aria-hidden />
                </span>
                <span>
                  <span className="block font-bold">{title}</span>
                  <span className="text-sm text-white/70">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <p className="hidden text-xs text-white/50 lg:block">Demo with synthetic players. Team analysis uses StatsBomb Open Data.</p>
      </section>

      <section className="flex items-center justify-center px-4 py-8 lg:px-10">
        <div className="w-full max-w-md">
          <h2 className="font-display mb-3 text-3xl font-bold text-white uppercase">Sign in</h2>
          <Card>
            {mfaToken ? (
              <form onSubmit={submitCode} className="space-y-3">
                <p className="text-ink-2 text-sm">Enter the 6-digit code from your authenticator app, or one of your recovery codes.</p>
                <label className="block">
                  <span className="text-ink-2 text-sm font-medium">Code</span>
                  <input
                    className="bg-surface-2 border-line text-ink mt-1 h-12 w-full rounded-xl border px-3 text-center font-mono text-xl tracking-[0.3em]"
                    inputMode="text"
                    autoComplete="one-time-code"
                    autoFocus
                    required
                    minLength={6}
                    maxLength={20}
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                  />
                </label>
                {error && (
                  <p role="alert" className="text-ready-red text-sm font-medium">
                    {error}
                  </p>
                )}
                <Button type="submit" className="w-full" loading={busy}>
                  Verify
                </Button>
                <button type="button" className="text-ink-2 w-full text-center text-sm underline" onClick={() => setMfaToken(null)}>
                  Back
                </button>
              </form>
            ) : (
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
              <p className="text-center text-sm">
                <Link to="/forgot-password" className="text-ink-2 hover:text-ink underline">
                  Forgot your password?
                </Link>
              </p>
            </form>
            )}
          </Card>

          <div className="mt-6">
            <p className="text-pitch-200 mb-2 text-xs font-bold tracking-[0.14em] uppercase">Or try the demo as (synthetic data)</p>
            <div className="space-y-3">
              {DEMO.map(({ group, accounts }) => (
                <div key={group}>
                  <p className="mb-1.5 text-xs font-semibold text-white/50">{group}</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {accounts.map(({ label, note, email: demoEmail, icon: Icon }) => (
                      <button
                        key={demoEmail}
                        disabled={busy}
                        onClick={(e) => submit(e, demoEmail)}
                        className="tap bg-surface border-line hover:border-pitch-400 flex items-center gap-3 rounded-xl border px-3 py-2 text-left transition-colors disabled:opacity-50"
                      >
                        <Icon className="text-pitch-300 h-5 w-5 shrink-0" aria-hidden />
                        <span className="min-w-0">
                          <span className="text-ink block text-sm font-bold">{label}</span>
                          <span className="text-ink-2 block truncate text-xs">{note}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <p className="text-pitch-200 mt-6 text-center text-sm">
            Not in an academy?{" "}
            <Link to="/register" className="font-semibold text-white underline">
              Create a free plan
            </Link>
          </p>
          <LegalLinks className="mt-6 justify-center text-white/50" />
        </div>
      </section>
    </main>
  );
}
