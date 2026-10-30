import { ArrowRight, Battery, CalendarDays, ClipboardList, Compass, Heart, ShieldCheck, Sparkles, Star, Stethoscope, Users } from "lucide-react";
import { useState, type CSSProperties, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "./api";
import { homeFor, useAuth } from "./auth";
import { LegalLinks } from "../legal/Legal";
import { Button, Card, cn } from "./ui";

// The demo story's accounts, grouped by who uses the app, each with what it shows.
// Each group has its own colour so the three kinds of account read apart at a glance.
const DEMO = [
  {
    group: "Players",
    tone: { tile: "from-emerald-300 to-cyan-400", hover: "hover:border-cyan-300/50 hover:shadow-cyan-400/15", dot: "bg-cyan-300" },
    accounts: [
      { label: "Leon, U15", note: "Tired, in the growth zone", email: "p15@demo.pathtopro", icon: Battery },
      { label: "Academy player", note: "A normal week", email: "p03@demo.pathtopro", icon: CalendarDays },
      { label: "Dual-squad player", note: "U19 + men's team", email: "dual@demo.pathtopro", icon: Users },
      { label: "Self-guided player", note: "No club, own plan", email: "amateur@demo.pathtopro", icon: Compass },
    ],
  },
  {
    group: "Staff",
    tone: { tile: "from-violet-300 to-indigo-400", hover: "hover:border-violet-300/50 hover:shadow-violet-400/15", dot: "bg-violet-300" },
    accounts: [
      { label: "Coach", note: "Squad, matches, analysis", email: "coach@demo.pathtopro", icon: ClipboardList },
      { label: "Men's team coach", note: "Senior squad", email: "mencoach@demo.pathtopro", icon: Star },
      { label: "Physio", note: "Escalation queue", email: "physio@demo.pathtopro", icon: Stethoscope },
    ],
  },
  {
    group: "Family",
    tone: { tile: "from-pink-200 to-pink-500", hover: "hover:border-pink-300/50 hover:shadow-pink-400/15", dot: "bg-pink-300" },
    accounts: [{ label: "Guardian", note: "A parent's view", email: "guardian02@demo.pathtopro", icon: Heart }],
  },
];

const PITCH = [
  { icon: Battery, tile: "bg-cyan-400/15 text-cyan-300", title: "Readiness every morning", text: "Sleep, heart-rate variability and a 30-second check-in become one battery score." },
  { icon: ShieldCheck, tile: "bg-amber-400/15 text-amber-300", title: "Safe through growth spurts", text: "Hard limits for the growth zone and load spikes, checked on every plan change." },
  { icon: ClipboardList, tile: "bg-violet-400/15 text-violet-300", title: "Coaches stay in charge", text: "Every plan change comes with its reason. Small ones apply and the coach is told; bigger ones wait for approval." },
];

const INPUT =
  "mt-1 h-12 w-full rounded-xl border border-white/15 bg-white/[0.06] px-3 text-white outline-none transition focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-300/25";
const SUBMIT =
  "btn-gloss w-full bg-linear-to-r from-emerald-300 via-teal-300 to-cyan-300 font-bold text-pitch-950 shadow-lg shadow-cyan-500/25 transition hover:shadow-cyan-400/40 hover:brightness-110 active:scale-[0.99]";

// Floodlights, pitch markings and a chalked set piece behind the sign-in page; decoration only
function NightPitch() {
  return (
    <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden>
      <div className="login-beam left-[-35vmax]" style={{ "--r": "-30deg" } as CSSProperties} />
      <div className="login-beam right-[-35vmax]" style={{ "--r": "30deg" } as CSSProperties} />
      <svg viewBox="0 0 1000 640" className="login-pitch" fill="none" stroke="currentColor" strokeWidth="3">
        <rect x="20" y="20" width="960" height="600" rx="4" />
        <line x1="500" y1="20" x2="500" y2="620" />
        <circle cx="500" cy="320" r="90" />
        <circle cx="500" cy="320" r="5" fill="currentColor" />
        <rect x="20" y="170" width="160" height="300" />
        <rect x="20" y="245" width="55" height="150" />
        <rect x="820" y="170" width="160" height="300" />
        <rect x="925" y="245" width="55" height="150" />
        <path d="M180 260 a70 70 0 0 1 0 120 M820 260 a70 70 0 0 0 0 120" />
      </svg>
      <svg viewBox="0 0 340 220" className="login-tactics hidden md:block" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
        <defs>
          <marker id="chalk-arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto">
            <path d="M0 0 10 5 0 10z" fill="currentColor" stroke="none" />
          </marker>
        </defs>
        {/* our players (O), the pass and the run in behind */}
        <circle cx="40" cy="180" r="10" />
        <circle cx="110" cy="120" r="10" />
        <circle cx="70" cy="55" r="10" />
        <path d="M52 172 Q 80 160 98 130" strokeDasharray="7 8" markerEnd="url(#chalk-arrow)" />
        <path d="M82 52 Q 190 10 285 48" strokeDasharray="7 8" markerEnd="url(#chalk-arrow)" />
        <path d="M122 118 Q 200 110 275 62" markerEnd="url(#chalk-arrow)" />
        {/* their defenders (X) */}
        <path d="M205 85 l16 16 m0 -16 l-16 16 M240 140 l16 16 m0 -16 l-16 16 M180 175 l16 16 m0 -16 l-16 16" />
      </svg>
    </div>
  );
}

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
    <main className="dark login-bg relative isolate min-h-full lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <NightPitch />
      <section className="login-band flex flex-col justify-between gap-8 px-6 py-8 lg:px-14 lg:py-12">
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
          <p className="inline-flex rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-bold tracking-[0.16em] text-cyan-200 uppercase">
            For academy players aged 13 to 18
          </p>
          <h1 className="font-display mt-4 text-5xl leading-[0.95] font-extrabold uppercase lg:text-7xl">
            Train smart.
            <br />
            Grow safe.
            <br />
            <span className="bg-linear-to-r from-emerald-300 via-cyan-300 to-violet-300 bg-clip-text text-transparent">Get better.</span>
          </h1>
          <ul className="mt-8 hidden max-w-lg space-y-4 lg:block">
            {PITCH.map(({ icon: Icon, tile, title, text }) => (
              <li key={title} className="flex gap-3">
                <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ring-1 ring-white/10", tile)}>
                  <Icon className="h-5 w-5" aria-hidden />
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
          <Card className="border-white/10 bg-white/[0.06] p-5 shadow-2xl shadow-black/40 backdrop-blur-xl">
            {mfaToken ? (
              <form onSubmit={submitCode} className="space-y-3">
                <p className="text-ink-2 text-sm">Enter the 6-digit code from your authenticator app, or one of your recovery codes.</p>
                <label className="block">
                  <span className="text-ink-2 text-sm font-medium">Code</span>
                  <input
                    className={cn(INPUT, "text-center font-mono text-xl tracking-[0.3em]")}
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
                  <p role="alert" className="text-recover text-sm font-medium">
                    {error}
                  </p>
                )}
                <Button type="submit" size="lg" className={SUBMIT} loading={busy}>
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
                  className={cn(INPUT, "text-base")}
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
                  className={cn(INPUT, "text-base")}
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </label>
              {error && (
                <p role="alert" className="text-recover text-sm font-medium">
                  {error}
                </p>
              )}
              <Button type="submit" size="lg" className={SUBMIT} loading={busy}>
                Sign in <ArrowRight className="h-4 w-4" aria-hidden />
              </Button>
              <p className="text-center text-sm">
                <Link to="/forgot-password" className="text-ink-2 hover:text-ink underline">
                  Forgot your password?
                </Link>
              </p>
            </form>
            )}
          </Card>

          <div className="mt-7">
            <p className="mb-3 flex items-center gap-2 text-xs font-bold tracking-[0.14em] text-white/80 uppercase">
              <Sparkles className="h-4 w-4 text-amber-300" aria-hidden /> Or try the demo as (synthetic data)
            </p>
            <div className="space-y-4">
              {DEMO.map(({ group, tone, accounts }) => (
                <div key={group}>
                  <p className="mb-2 flex items-center gap-2 text-xs font-semibold text-white/60">
                    <span className={cn("h-2 w-2 rounded-full", tone.dot)} aria-hidden />
                    {group}
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {accounts.map(({ label, note, email: demoEmail, icon: Icon }) => (
                      <button
                        key={demoEmail}
                        disabled={busy}
                        onClick={(e) => submit(e, demoEmail)}
                        className={cn(
                          "tap glass-btn flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-2.5 text-left backdrop-blur transition duration-200 hover:-translate-y-0.5 hover:bg-white/[0.09] hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300 disabled:opacity-50 motion-reduce:hover:translate-y-0",
                          tone.hover,
                        )}
                      >
                        <span className={cn("text-pitch-950 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-linear-to-br shadow-md", tone.tile)}>
                          <Icon className="h-5 w-5" aria-hidden />
                        </span>
                        <span className="min-w-0">
                          <span className="block text-sm font-bold text-white">{label}</span>
                          <span className="block truncate text-xs text-white/60">{note}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <p className="mt-7 text-center text-sm text-white/70">
            Not in an academy?{" "}
            <Link to="/register" className="font-semibold text-white underline decoration-cyan-300 decoration-2 underline-offset-4">
              Create a free plan
            </Link>
          </p>
          <LegalLinks className="mt-6 justify-center text-white/50" />
        </div>
      </section>
    </main>
  );
}
