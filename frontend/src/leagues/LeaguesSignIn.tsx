// The Pro League app's sign-in. One account for every app on the platform: a PathToPro account
// signs in here, and having signed in to either app in this browser, the other one is open too.
import { ArrowUpRight } from "lucide-react";
import { useState, type FormEvent } from "react";
import { ApiError } from "../shared/api";
import { APPS } from "../shared/apps";
import { useAuth } from "../shared/auth";
import { Button, cn } from "../shared/ui";

// Fields on the light sheet
const INPUT = "h-12 w-full rounded-xl border border-line bg-white px-3 text-ink outline-none transition focus:border-pitch-500 focus:ring-2 focus:ring-pitch-300/40";

const DEMO_ACCOUNT = "coach@demo.pathtopro";

export function LeaguesSignIn() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"form" | "demo" | null>(null);

  async function signIn(e: FormEvent | null, demo = false) {
    e?.preventDefault();
    setBusy(demo ? "demo" : "form");
    setError(null);
    try {
      const u = await login(demo ? DEMO_ACCOUNT : email, demo ? "demo1234" : password);
      // Two-step sign-in lives on PathToPro's sign-in page; the session it starts is shared
      if ("mfaToken" in u) window.location.assign(`${APPS.pathtopro.url}login`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Cannot reach the server");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="app-bg text-ink flex min-h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <img src={APPS.leagues.icon} alt="" className="h-14 w-14" />
          <div>
            <h1 className="font-display text-2xl leading-none font-extrabold tracking-wide uppercase">{APPS.leagues.name}</h1>
            <p className="text-ink-2 mt-1 text-sm">{APPS.leagues.tagline}</p>
          </div>
        </div>
        <div className="border-line bg-surface rounded-2xl border p-5 shadow-sm">
          <h2 className="font-display text-[1.6rem] leading-none font-extrabold uppercase">Sign in</h2>
          <p className="text-ink-2 mt-2 text-[15px]">Use your PathToPro account. One account works in every app.</p>
          <form onSubmit={(e) => signIn(e)} className="mt-4 space-y-3">
            <label className="block">
              <span className="text-[15px] font-semibold">Email</span>
              <input className={cn(INPUT, "mt-1 text-base")} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="block">
              <span className="text-[15px] font-semibold">Password</span>
              <input
                className={cn(INPUT, "mt-1 text-base")}
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {error && (
              <p role="alert" className="text-[15px] font-semibold text-red-700">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" loading={busy === "form"} disabled={!!busy}>
              Sign in
            </Button>
          </form>
          <div className="mt-4 border-t border-line pt-4">
            <Button variant="secondary" className="w-full" loading={busy === "demo"} disabled={!!busy} onClick={() => signIn(null, true)}>
              Look around with a demo account
            </Button>
          </div>
        </div>
        <p className="text-ink-2 mt-5 text-center text-sm">
          No account?{" "}
          <a className="text-ink font-semibold underline underline-offset-4" href={`${APPS.pathtopro.url}register`}>
            Create one in PathToPro
          </a>
        </p>
        <p className="mt-2 text-center text-sm">
          <a className="text-ink-2 inline-flex items-center gap-1 hover:underline" href={APPS.pathtopro.url}>
            <img src={APPS.pathtopro.icon} alt="" className="h-4 w-4" /> Open PathToPro <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
          </a>
        </p>
      </div>
    </main>
  );
}
