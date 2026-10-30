// Guardian: weekly summary card, the child's training and match schedule, consent switches per data type, data export and delete.
import { CalendarDays, Download, LogOut, Settings, ShieldAlert, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, download } from "../shared/api";
import { useAuth } from "../shared/auth";
import { eur } from "../shared/money";
import { useApi } from "../shared/useApi";
import type { SessionKind } from "../shared/types";
import { Button, Card, ErrorNote, SectionTitle, Spinner, cn, fmtDay } from "../shared/ui";

interface Child {
  id: string;
  name: string;
  age: number;
}
interface Summary {
  name: string;
  week_start: string;
  sessions_done: number;
  avg_sleep_h: number | null;
  goals: { label: string; progress: number }[];
  streak: number;
  alerts?: { id: string; kind: string; text: string; created_at: string }[];
}
interface ScheduleDay {
  date: string;
  kind: SessionKind;
  label: string;
  minutes: number;
  match?: { opponent: string; team: string; primary: boolean; time: string };
}
interface Schedule {
  today: string;
  weeks: { start: string; days: ScheduleDay[] }[];
}
interface Consent {
  age: number;
  items: { data_type: string; text: string; granted: boolean }[];
}

export function GuardianHome() {
  const { user, logout } = useAuth();
  const kids = useApi<Child[]>("/api/guardian/children");
  return (
    <div className="display-headings app-bg min-h-full">
      <header className="hero flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="h-8 w-8" />
          <span className="font-display text-xl font-extrabold tracking-wide uppercase">
            PathToPro <span className="text-pitch-300">· Family</span>
          </span>
        </div>
        <span className="flex items-center gap-1">
          <Link to="/account" className="tap flex h-11 w-11 items-center justify-center" aria-label="Account">
            <Settings className="h-4 w-4" aria-hidden />
          </Link>
          <button onClick={logout} className="tap flex items-center gap-1 text-sm">
            {user?.name} <LogOut className="h-4 w-4" aria-hidden />
          </button>
        </span>
      </header>
      <main className="mx-auto max-w-2xl space-y-6 p-4 lg:max-w-5xl lg:p-6">
        {kids.loading && <Spinner />}
        {kids.error && <ErrorNote message={kids.error} onRetry={kids.reload} />}
        {kids.data?.map((k) => <ChildPanel key={k.id} child={k} />)}
      </main>
    </div>
  );
}

function ChildPanel({ child }: { child: Child }) {
  const summary = useApi<Summary>(`/api/guardian/children/${child.id}/summary`);
  const consent = useApi<Consent>(`/api/guardian/children/${child.id}/consent`);
  const money = useApi<{ contracts: { id: string; title: string; amount_cents: number; direction: string; ends_on: string | null }[]; fees_paid_cents: number; fees_due_cents: number }>(
    `/api/guardian/children/${child.id}/finance`,
  );
  const [confirm, setConfirm] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function toggle(dataType: string, granted: boolean) {
    consent.setData(await api<Consent>(`/api/guardian/children/${child.id}/consent`, { method: "PUT", json: { data_type: dataType, granted } }));
  }
  async function seen(id: string) {
    await api(`/api/guardian/children/${child.id}/alerts/${id}/seen`, { method: "POST" });
    void summary.reload();
  }
  async function del() {
    try {
      await api(`/api/guardian/children/${child.id}/data`, { method: "DELETE" });
      setMsg("All health data was deleted.");
      void summary.reload();
    } catch {
      setMsg("Nothing to delete.");
    }
    setConfirm(false);
  }

  const s = summary.data;
  return (
    <section className="space-y-3">
      <h1 className="text-2xl font-extrabold">
        {child.name} <span className="text-ink-2 text-base font-medium">{child.age} y</span>
      </h1>
      {s?.alerts?.map((a) => (
        <Card key={a.id} className="border-recover/50 flex gap-3" role="alert">
          <ShieldAlert className="text-recover h-6 w-6 shrink-0" aria-hidden />
          <div className="flex-1">
            <p>
              <span className="font-bold">{child.name.split(" ")[0]}</span> {a.text}
            </p>
            <p className="text-ink-2 mt-1 text-xs">{new Date(a.created_at).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" })}</p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => seen(a.id)}>
            Seen
          </Button>
        </Card>
      ))}
      <ScheduleCard childId={child.id} />
      {/* Wide screens: the week and fees on the left, consent and data on the right */}
      <div className="space-y-5 lg:grid lg:grid-cols-2 lg:items-start lg:gap-6 lg:space-y-0">
        <div className="space-y-5">
          {s && (
            <Card>
              <SectionTitle>This week</SectionTitle>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="text-3xl font-extrabold">{s.sessions_done}</p>
                  <p className="text-ink-2 text-sm">sessions done</p>
                </div>
                <div>
                  <p className="text-3xl font-extrabold">{s.avg_sleep_h ?? "–"}</p>
                  <p className="text-ink-2 text-sm">avg sleep (h)</p>
                </div>
                <div>
                  <p className="text-3xl font-extrabold">{s.streak}</p>
                  <p className="text-ink-2 text-sm">check-in streak</p>
                </div>
              </div>
              {s.goals.map((g) => (
                <div key={g.label} className="mt-3">
                  <p className="text-sm font-semibold">Goal: {g.label}</p>
                  <div className="bg-surface-2 mt-1 h-2.5 rounded-full">
                    <div className="bg-pitch-500 h-full rounded-full" style={{ width: `${Math.max(4, g.progress * 100)}%` }} />
                  </div>
                </div>
              ))}
            </Card>
          )}
          {money.data && money.data.contracts.some((c) => c.direction === "income" && !c.ends_on) && (
            <Card>
              <p className="font-bold">Fees</p>
              {money.data.contracts
                .filter((c) => c.direction === "income" && !c.ends_on)
                .map((c) => (
                  <p key={c.id} className="text-sm">
                    {c.title}: {eur(c.amount_cents)} / month
                  </p>
                ))}
              <p className="text-ink-2 mt-1 text-sm">
                Paid this season {eur(money.data.fees_paid_cents)} ·{" "}
                <span className={money.data.fees_due_cents > 0 ? "text-caution font-semibold" : ""}>due {eur(money.data.fees_due_cents)}</span>
              </p>
            </Card>
          )}
        </div>

        <div className="space-y-5">
          {consent.data && (
            <Card>
              <SectionTitle>Consent</SectionTitle>
              <p className="text-ink-2 mb-2 text-sm">
                {consent.data.age < 16
                  ? "Your child is under the age of digital consent, so these switches are yours. You can change them any time."
                  : "Your child is old enough to consent themselves. Switches here still apply."}
              </p>
              <ul className="divide-[color:var(--line)] divide-y">
                {consent.data.items.map((i) => (
                  <li key={i.data_type} className="flex items-center justify-between gap-3 py-2">
                    <span className="text-sm">{i.text}</span>
                    <label className="relative inline-flex cursor-pointer items-center">
                      <input type="checkbox" className="peer sr-only" checked={i.granted} onChange={(e) => toggle(i.data_type, e.target.checked)} aria-label={i.text} />
                      <span className="peer-checked:bg-pitch-500 peer-focus-visible:ring-pitch-300 bg-ink-2/40 h-7 w-12 rounded-full transition peer-focus-visible:ring-4" />
                      <span className="absolute left-1 h-5 w-5 rounded-full bg-white transition peer-checked:translate-x-5" />
                    </label>
                  </li>
                ))}
              </ul>
              <p className="text-ink-2 mt-2 text-xs">We store no location and no free-text diary. Demo data is synthetic.</p>
            </Card>
          )}
          <Card className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => download(`/api/guardian/children/${child.id}/export`, `pathtopro-${child.name}.json`)}>
              <Download className="h-4 w-4" aria-hidden /> Export data
            </Button>
            {!confirm ? (
              <Button variant="danger" onClick={() => setConfirm(true)}>
                <Trash2 className="h-4 w-4" aria-hidden /> Delete health data
              </Button>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">This cannot be undone.</span>
                <Button variant="danger" size="sm" onClick={del}>
                  Yes, delete
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setConfirm(false)}>
                  Cancel
                </Button>
              </div>
            )}
            {msg && (
              <p role="status" className="w-full text-sm">
                {msg}
              </p>
            )}
          </Card>
        </div>
      </div>
    </section>
  );
}

const SHORT: Record<SessionKind, string> = {
  rest: "Rest",
  recovery: "Recovery",
  technical: "Technique",
  tactical: "Tactics",
  strength: "Gym",
  speed: "Speed",
  match: "Match",
};

// This week or next as a strip of seven days, so the family can plan lifts and evenings around training and matches
function ScheduleCard({ childId }: { childId: string }) {
  const { data } = useApi<Schedule>(`/api/guardian/children/${childId}/schedule`);
  const [week, setWeek] = useState(0);
  if (!data) return null;
  const days = data.weeks[week]?.days ?? [];
  const matches = days.filter((d) => d.match);
  return (
    <Card>
      <SectionTitle
        action={
          <div className="bg-surface-2 flex rounded-xl p-1 text-sm font-semibold" role="group" aria-label="Week">
            {["This week", "Next week"].map((label, i) => (
              <button
                key={label}
                onClick={() => setWeek(i)}
                aria-pressed={week === i}
                className={cn("rounded-lg px-3 py-1.5 transition", week === i ? "bg-pitch-600 text-white" : "text-ink-2 hover:text-ink")}
              >
                {label}
              </button>
            ))}
          </div>
        }
      >
        Schedule
      </SectionTitle>
      <ol className="grid grid-cols-7 gap-1.5">
        {days.map((d) => {
          const today = d.date === data.today;
          const past = d.date < data.today;
          return (
            <li
              key={d.date}
              title={d.match ? `Match vs ${d.match.opponent}, ${d.match.time}` : d.kind === "rest" ? "Rest day" : `${d.label}, ${d.minutes} min`}
              className={cn(
                "flex min-h-24 flex-col items-center rounded-xl border px-0.5 py-2 text-center",
                d.match
                  ? "border-pitch-400/60 bg-pitch-500/20"
                  : d.kind === "rest"
                    ? "border-line border-dashed"
                    : "border-line bg-surface-2",
                today && "ring-pitch-300 ring-2",
                past && "opacity-55",
              )}
            >
              <span className="text-ink-2 text-[11px] font-bold uppercase">{fmtDay(d.date)}</span>
              <span className="text-lg leading-tight font-extrabold">{fmtDay(d.date, { day: "numeric" })}</span>
              <span className={cn("mt-auto text-[11px] leading-tight font-semibold sm:text-xs", d.kind === "rest" ? "text-ink-2" : "text-ink")}>
                {SHORT[d.kind] ?? d.label}
              </span>
              {d.match ? (
                <span className="text-pitch-300 text-[11px] font-bold sm:text-xs">{d.match.time}</span>
              ) : (
                d.kind !== "rest" && <span className="text-ink-2 text-[11px] sm:text-xs">{d.minutes}′</span>
              )}
            </li>
          );
        })}
      </ol>
      {matches.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {matches.map((d) => (
            <li key={d.date} className="flex items-center gap-2 text-sm">
              <CalendarDays className="text-pitch-300 h-4 w-4 shrink-0" aria-hidden />
              <span>
                <span className="font-semibold">
                  {fmtDay(d.date, { weekday: "long", day: "numeric", month: "short" })}, {d.match!.time}
                </span>{" "}
                · Match vs {d.match!.opponent}
                {!d.match!.primary && <span className="text-ink-2"> ({d.match!.team})</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
