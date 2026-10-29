// Sign-up for self-guided players (amateur / non-academy, 13+) and for parents with an invite code.
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError, DEMO } from "./api";
import { useAuth } from "./auth";
import type { User } from "./types";
import { LegalLinks } from "../legal/Legal";
import { Button, Card, cn } from "./ui";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const POSITIONS = [
  ["goalkeeper", "Goalkeeper"],
  ["centre_back", "Centre-back"],
  ["full_back", "Full-back"],
  ["midfielder", "Midfielder"],
  ["winger", "Winger"],
  ["striker", "Striker"],
];
const LEVELS = [
  [1, "Starter: I play for fun or just joined a team"],
  [2, "Grassroots: I train with a club every week"],
  [3, "Competitive amateur: I start in a competitive league"],
  [4, "Elite amateur: regional or select team"],
];
export const input = "bg-surface-2 border-line text-ink mt-1 h-12 w-full rounded-xl border px-3 text-base";

// Also the frame of the password, verification and account pages (AuthPages.tsx)
export function Shell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <main className="dark bg-pitch-950 flex min-h-full items-start justify-center p-4 sm:items-center">
      <div className="w-full max-w-md py-6">
        <div className="mb-5 text-center text-white">
          <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="mx-auto mb-3 h-12 w-12" />
          <h1 className="text-2xl font-extrabold tracking-tight">{title}</h1>
          <p className="text-pitch-200 mt-1">{subtitle}</p>
        </div>
        <Card>{children}</Card>
        {footer ?? (
          <p className="text-pitch-200 mt-4 text-center text-sm">
            Already have an account?{" "}
            <Link to="/login" className="font-semibold text-white underline">
              Sign in
            </Link>
          </p>
        )}
        <LegalLinks className="mt-6 justify-center text-pitch-200/80" />
      </div>
    </main>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="text-ink-2 text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="text-ink-2 mt-1 block text-xs">{hint}</span>}
    </label>
  );
}

function age(birth: string): number | null {
  if (!birth) return null;
  const b = new Date(birth + "T12:00:00");
  return (Date.now() - b.getTime()) / (365.25 * 24 * 3600 * 1000);
}

export function Register() {
  const { adopt } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({
    name: "",
    email: "",
    password: "",
    birth_date: "",
    sex: "male",
    position: "midfielder",
    level: 2,
    equipment: "none",
    team_days: [1, 3] as number[],
    match_day: 5 as number | null,
    guardian_email: "",
    accept_terms: false,
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [invite, setInvite] = useState<string | null>(null);
  const set = (k: keyof typeof f, v: unknown) => setF((x) => ({ ...x, [k]: v }));
  const a = age(f.birth_date);
  const minor = a != null && a < 16;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = { ...f, guardian_email: minor ? f.guardian_email : null };
      const out = await api<{ token: string; user: User; guardian_invite: string | null }>("/api/auth/register", {
        method: "POST",
        json: body,
      });
      adopt(out.token, out.user);
      if (out.guardian_invite) setInvite(out.guardian_invite);
      else nav("/player");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Cannot reach the server");
    } finally {
      setBusy(false);
    }
  }

  if (invite)
    return (
      <Shell title="Almost there" subtitle="One more step for players under 16">
        <p>Give this code to a parent. They sign up at the link below and agree to what we store about you.</p>
        <p className="my-4 text-center font-mono text-3xl font-extrabold tracking-widest" aria-label="Parent invite code">
          {invite}
        </p>
        <p className="text-ink-2 mb-4 text-sm break-all">{window.location.origin + import.meta.env.BASE_URL}register/guardian</p>
        <p className="text-ink-2 mb-4 text-sm">Until then you get your training plan and gym sessions, but no check-ins or test results are saved.</p>
        <Button className="w-full" onClick={() => nav("/player")}>
          Go to my plan
        </Button>
      </Shell>
    );

  return (
    <Shell title="Join PathToPro" subtitle="A plan to reach your next level. Free, for players 13+.">
      {DEMO && (
        <p className="border-caution/50 bg-caution/10 mb-3 rounded-xl border p-3 text-sm">
          This is the offline demo: sign-up needs the live server. Try the demo account "Self-guided player" on the sign-in page.
        </p>
      )}
      <form onSubmit={submit} className="space-y-3">
        <Field label="First name and initial">
          <input className={input} required minLength={2} maxLength={60} value={f.name} onChange={(e) => set("name", e.target.value)} autoComplete="nickname" />
        </Field>
        <Field label="Email">
          <input className={input} type="email" required value={f.email} onChange={(e) => set("email", e.target.value)} autoComplete="email" />
        </Field>
        <Field label="Password" hint="At least 8 characters">
          <input className={input} type="password" required minLength={8} value={f.password} onChange={(e) => set("password", e.target.value)} autoComplete="new-password" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date of birth">
            <input className={input} type="date" required value={f.birth_date} onChange={(e) => set("birth_date", e.target.value)} />
          </Field>
          <Field label="Benchmarks for">
            <select className={input} value={f.sex} onChange={(e) => set("sex", e.target.value)}>
              <option value="male">Boys / men</option>
              <option value="female">Girls / women</option>
              <option value="other">Prefer not to say</option>
            </select>
          </Field>
        </div>
        {minor && (
          <Field label="A parent's email" hint="Under 16, a parent must agree before check-ins and tests are stored.">
            <input className={input} type="email" required value={f.guardian_email} onChange={(e) => set("guardian_email", e.target.value)} />
          </Field>
        )}
        <Field label="Position">
          <select className={input} value={f.position} onChange={(e) => set("position", e.target.value)}>
            {POSITIONS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Where are you now?" hint="Your guess. Tests move you up from here.">
          <select className={input} value={f.level} onChange={(e) => set("level", Number(e.target.value))}>
            {LEVELS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
        <div>
          <span className="text-ink-2 text-sm font-medium">Club training days</span>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {WEEKDAYS.map((d, i) => {
              const on = f.team_days.includes(i);
              return (
                <button
                  type="button"
                  key={d}
                  aria-pressed={on}
                  onClick={() => set("team_days", on ? f.team_days.filter((x) => x !== i) : [...f.team_days, i])}
                  className={cn("tap h-11 w-11 rounded-xl border text-sm font-bold", on ? "bg-pitch-600 border-pitch-600 text-white" : "border-line")}
                >
                  {d}
                </button>
              );
            })}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Match day">
            <select className={input} value={f.match_day ?? -1} onChange={(e) => set("match_day", Number(e.target.value) < 0 ? null : Number(e.target.value))}>
              <option value={-1}>None</option>
              {WEEKDAYS.map((d, i) => (
                <option key={d} value={i}>
                  {d}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Equipment">
            <select className={input} value={f.equipment} onChange={(e) => set("equipment", e.target.value)}>
              <option value="none">None</option>
              <option value="home">Band + dumbbells</option>
              <option value="gym">Full gym</option>
            </select>
          </Field>
        </div>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1 h-5 w-5" checked={f.accept_terms} onChange={(e) => set("accept_terms", e.target.checked)} required />
          <span>
            I agree that PathToPro stores my training data to plan my sessions (see the{" "}
            <Link to="/privacy" target="_blank" className="font-semibold underline">
              privacy notice
            </Link>{" "}
            and{" "}
            <Link to="/terms" target="_blank" className="font-semibold underline">
              terms
            </Link>
            ). It gives training guidance, not medical advice. I can delete my data at any time.
          </span>
        </label>
        {error && (
          <p role="alert" className="text-recover text-sm font-medium">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" loading={busy} disabled={DEMO}>
          Create my plan
        </Button>
      </form>
    </Shell>
  );
}

export function RegisterGuardian() {
  const { adopt } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [code, setCode] = useState(params.get("code") ?? "");  // the emailed link carries it
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const out = await api<{ token: string; user: User }>("/api/auth/register/guardian", {
        method: "POST",
        json: { invite_code: code, name, password },
      });
      adopt(out.token, out.user);
      nav("/guardian");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Cannot reach the server");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell title="Parent sign-up" subtitle="Link to your child's account with their code">
      <form onSubmit={submit} className="space-y-3">
        <Field label="Invite code">
          <input className={cn(input, "font-mono tracking-widest uppercase")} required minLength={6} maxLength={20} value={code} onChange={(e) => setCode(e.target.value)} />
        </Field>
        <Field label="Your name">
          <input className={input} required minLength={2} maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Password" hint="At least 8 characters. Your email is the one your child entered.">
          <input className={input} type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
        </Field>
        {error && (
          <p role="alert" className="text-recover text-sm font-medium">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" loading={busy} disabled={DEMO}>
          Link accounts
        </Button>
        <p className="text-ink-2 text-xs">Next you choose, for each type of data, whether PathToPro may store it. You can change this any time.</p>
      </form>
    </Shell>
  );
}
