// The pages behind emailed links: forgot password, set a password (reset or invitation),
// confirm an email address. Tokens come in the URL and are sent back once.
import { CheckCircle2, MailCheck } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError, DEMO } from "./api";
import { homeFor, useAuth } from "./auth";
import { Field, input, Shell } from "./Register";
import type { User } from "./types";
import { Button, Spinner } from "./ui";

function message(err: unknown): string {
  return err instanceof ApiError ? err.message : "Cannot reach the server";
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/api/auth/password/forgot", { method: "POST", json: { email } });
      setSent(true);
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell title="Forgot your password?" subtitle="We'll email you a link to choose a new one">
      {sent ? (
        <div className="space-y-2 text-center" role="status">
          <MailCheck className="text-pitch-500 mx-auto h-10 w-10" aria-hidden />
          <p className="font-semibold">Check your inbox</p>
          <p className="text-ink-2 text-sm">
            If {email} has a PathToPro account, a link is on its way. It works for one hour. Nothing there? Check the spam folder, or ask
            your coach or club administrator.
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <Field label="Email">
            <input className={input} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          {error && (
            <p role="alert" className="text-recover text-sm font-medium">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" loading={busy} disabled={DEMO}>
            Send the link
          </Button>
          {DEMO && <p className="text-ink-2 text-xs">The demo has no email: sign in with a demo account instead.</p>}
        </form>
      )}
    </Shell>
  );
}

// Reset and invitation links both end here: the server says which one it is
export function SetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { adopt } = useAuth();
  const nav = useNavigate();
  const [info, setInfo] = useState<{ purpose: "reset" | "invite"; email: string; name: string } | null>(null);
  const [linkError, setLinkError] = useState<string | null>(token ? null : "This link is incomplete. Open it again from your email.");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    api<{ purpose: "reset" | "invite"; email: string; name: string }>("/api/auth/token", { method: "POST", json: { token } })
      .then(setInfo)
      .catch((err) => setLinkError(message(err)));
  }, [token]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password !== repeat) {
      setError("The two passwords are not the same");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const out = await api<{ token: string; user: User } | { mfa_required: true; mfa_token: string }>("/api/auth/password/set", {
        method: "POST",
        json: { token, password },
      });
      if ("mfa_token" in out) {
        nav("/login", { replace: true, state: { mfaToken: out.mfa_token } }); // the code from the app is still needed
        return;
      }
      adopt(out.token, out.user);
      nav(homeFor(out.user.role), { replace: true });
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  const invite = info?.purpose === "invite";
  return (
    <Shell
      title={invite ? `Welcome, ${info.name.split(" ")[0]}` : "Choose a new password"}
      subtitle={invite ? "Choose a password to finish setting up your account" : "You'll be signed out on your other devices"}
    >
      {linkError ? (
        <div className="space-y-3">
          <p role="alert" className="text-recover font-medium">
            {linkError}
          </p>
          <Link to="/forgot-password" className="text-pitch-600 font-semibold underline">
            Ask for a new link
          </Link>
        </div>
      ) : !info ? (
        <Spinner label="Checking the link" />
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <p className="text-ink-2 text-sm">
            Account: <strong className="text-ink">{info.email}</strong>
          </p>
          {/* Lets password managers save the new password against the right account */}
          <input type="email" autoComplete="username" value={info.email} readOnly hidden />
          <Field label="New password" hint="At least 8 characters">
            <input className={input} type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Field label="Repeat it">
            <input className={input} type="password" autoComplete="new-password" required minLength={8} value={repeat} onChange={(e) => setRepeat(e.target.value)} />
          </Field>
          {error && (
            <p role="alert" className="text-recover text-sm font-medium">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" loading={busy}>
            {invite ? "Set password and sign in" : "Save and sign in"}
          </Button>
          {invite && (
            <p className="text-ink-2 text-xs">
              By continuing you accept the <Link to="/terms" target="_blank" className="underline">terms</Link> and have read the{" "}
              <Link to="/privacy" target="_blank" className="underline">privacy notice</Link>.
            </p>
          )}
        </form>
      )}
    </Shell>
  );
}

export function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { user } = useAuth();
  const [state, setState] = useState<{ ok: boolean; text: string } | null>(token ? null : { ok: false, text: "This link is incomplete." });
  const sent = useRef(false);

  useEffect(() => {
    if (!token || sent.current) return; // the link works once: don't send it twice in StrictMode
    sent.current = true;
    api<{ email: string }>("/api/auth/verify-email", { method: "POST", json: { token } })
      .then((r) => setState({ ok: true, text: `${r.email} is confirmed. Thank you!` }))
      .catch((err) => setState({ ok: false, text: message(err) }));
  }, [token]);

  return (
    <Shell
      title="Confirm your email"
      subtitle="So we can reach you if you forget your password"
      footer={
        <p className="text-pitch-200 mt-4 text-center text-sm">
          <Link to={user ? homeFor(user.role) : "/login"} className="font-semibold text-white underline">
            {user ? "Back to PathToPro" : "Sign in"}
          </Link>
        </p>
      }
    >
      {!state ? (
        <Spinner label="Confirming" />
      ) : (
        <p role={state.ok ? "status" : "alert"} className={state.ok ? "flex items-center gap-2 font-semibold" : "text-recover font-medium"}>
          {state.ok && <CheckCircle2 className="text-ready h-6 w-6" aria-hidden />}
          {state.text}
          {!state.ok && user && " You can send a new link from your account settings."}
        </p>
      )}
    </Shell>
  );
}
