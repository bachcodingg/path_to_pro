// Levels (self-guided pathway): where you are, the next level's checklist, tests, settings.
import { CheckCircle2, Circle, PartyPopper, Trophy } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../shared/api";
import type { PathwayView } from "../shared/types";
import { useApi } from "../shared/useApi";
import { Button, Card, Chip, ErrorNote, SectionTitle, Spinner, cn } from "../shared/ui";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function fmt(v: number | null, unit: string): string {
  if (v == null) return "–";
  return unit === "s" ? `${v.toFixed(2)} s` : `${Math.round(v)} ${unit}`;
}

export function Pathway() {
  const { data, setData, error, loading, reload } = useApi<PathwayView>("/api/me/pathway");
  const [test, setTest] = useState("");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [levelled, setLevelled] = useState(false);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  const a = data.assessment;
  const current = test || a.focus[0] || a.tests[0].test;
  const row = a.tests.find((r) => r.test === current)!;

  async function logTest(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const out = await api<PathwayView>("/api/me/pathway/tests", { method: "POST", json: { test: current, value: Number(value) } });
      setData(out);
      setValue("");
      setLevelled(!!out.levelled_up);
      setMsg(out.levelled_up ? null : "Result saved.");
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  async function save(patch: Record<string, unknown>) {
    setMsg(null);
    try {
      setData(await api<PathwayView>("/api/me/pathway/profile", { method: "PUT", json: patch }));
      setMsg("Saved. Your plan was rebuilt around your club week.");
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Could not save");
    }
  }

  const met = a.next ? a.next.tests_met : a.tests.filter((t) => t.met).length;
  const need = a.next?.tests_needed ?? 4;
  const cons = a.consistency;
  return (
    <div className="space-y-5 pt-2">
      {levelled && (
        <Card className="border-pitch-400 bg-pitch-700 flex items-center gap-3 text-white" role="status">
          <PartyPopper className="h-8 w-8 shrink-0" aria-hidden />
          <div>
            <p className="text-lg font-extrabold">Level up! You're now {a.name}.</p>
            <p className="text-pitch-100 text-sm">Your training week was updated for your new level.</p>
          </div>
        </Card>
      )}

      {/* Wide screens: level and benchmarks on the left, sessions and history on the right */}
      <div className="space-y-5 lg:grid lg:grid-cols-2 lg:items-start lg:gap-6 lg:space-y-0">
        <div className="space-y-5">
          <Card>
            <div className="flex items-center gap-3">
              <div className="bg-pitch-600 flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl text-2xl font-extrabold text-white">
                {a.level}
              </div>
              <div>
                <p className="text-ink-2 text-xs font-semibold uppercase">Level {a.level} of 5</p>
                <h1 className="text-xl font-extrabold">{a.name}</h1>
                <p className="text-ink-2 text-sm">Goal: {data.profile.goal_label}</p>
              </div>
            </div>
            <p className="mt-3 text-sm">{a.who}</p>
            <p className="text-ink-2 mt-1 text-sm">This level: {a.targets}</p>
          </Card>

          {a.next ? (
            <section>
              <SectionTitle>Road to level {a.next.level}: {a.next.name}</SectionTitle>
              <Card className="space-y-3">
                <Progress label={`Benchmarks met: ${met} of ${need} needed`} value={met / need} done={met >= need} />
                <Progress
                  label={`Training logged in the last 4 weeks: ${cons.logged} of ${cons.needed}`}
                  value={cons.logged / Math.max(1, cons.needed)}
                  done={cons.ok}
                />
                <p className="text-ink-2 text-sm">
                  {met >= need && cons.ok
                    ? "Everything's done: log your next test to move up."
                    : `You move up when you meet ${need} benchmarks and keep training regularly. Levels never go down.`}
                </p>
              </Card>
            </section>
          ) : (
            <Card className="flex items-center gap-3">
              <Trophy className="text-caution h-8 w-8" aria-hidden />
              <p>Top level. Keep your benchmarks up and ask your club coach about trials and showcases.</p>
            </Card>
          )}

          {data.guardian_invite && (
            <Card className="border-caution/50">
              <p className="font-bold">Ask a parent to join</p>
              <p className="text-ink-2 text-sm">
                You're under 16, so a parent has to agree before we store your check-ins and test results. They sign up at{" "}
                <span className="font-semibold">{window.location.origin + import.meta.env.BASE_URL}register/guardian</span> with this
                code:
              </p>
              <p className="mt-2 font-mono text-2xl font-extrabold tracking-widest" aria-label="Parent invite code">
                {data.guardian_invite}
              </p>
            </Card>
          )}

          <section>
            <SectionTitle>Benchmarks for level {a.next?.level ?? a.level}</SectionTitle>
            <Card className="divide-[color:var(--line)] divide-y p-0">
              {a.tests.map((r) => (
                <button
                  key={r.test}
                  className={cn("tap flex w-full items-center gap-3 px-4 py-3 text-left", r.test === current && "bg-surface-2")}
                  onClick={() => setTest(r.test)}
                  aria-pressed={r.test === current}
                >
                  {r.met ? <CheckCircle2 className="text-ready h-5 w-5 shrink-0" aria-label="met" /> : <Circle className="text-ink-2 h-5 w-5 shrink-0" aria-label="not met" />}
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold">{r.label}</span>
                    <span className="text-ink-2 text-xs">{r.kind === "technical" ? "Ball skill" : "Athletic"}</span>
                  </span>
                  <span className="text-right text-sm tabular-nums">
                    <span className="block font-bold">{fmt(r.value, r.unit)}</span>
                    <span className="text-ink-2 text-xs">target {r.lower_is_better ? "≤" : "≥"} {fmt(r.target, r.unit)}</span>
                  </span>
                </button>
              ))}
            </Card>
            {a.focus.length > 0 && (
              <p className="text-ink-2 mt-2 text-sm">
                Focus: {a.focus.map((f) => a.tests.find((t) => t.test === f)?.label).join(" and ")}. Your plan adds sessions for these.
              </p>
            )}
          </section>
        </div>

        <div className="space-y-5">
          <section>
            <SectionTitle>Log a test result</SectionTitle>
            <Card>
              <p className="font-semibold">{row.label}</p>
              <p className="text-ink-2 mb-3 text-sm">{row.how}</p>
              {data.can_store_tests ? (
                <form onSubmit={logTest} className="flex gap-2">
                  <label className="flex-1">
                    <span className="sr-only">Result in {row.unit}</span>
                    <input
                      type="number"
                      inputMode="decimal"
                      step={row.unit === "s" ? "0.01" : "1"}
                      min={0}
                      required
                      value={value}
                      onChange={(e) => setValue(e.target.value)}
                      placeholder={`Result (${row.unit})`}
                      className="bg-surface-2 border-line h-11 w-full rounded-xl border px-3"
                    />
                  </label>
                  <Button type="submit" loading={busy}>
                    Save
                  </Button>
                </form>
              ) : (
                <p className="text-caution text-sm font-semibold">Test results are saved once a parent has agreed.</p>
              )}
              {msg && (
                <p role="status" className="mt-2 text-sm font-semibold">
                  {msg}
                </p>
              )}
            </Card>
          </section>

          <section>
            <SectionTitle>The five levels</SectionTitle>
            <ol className="space-y-2">
              {data.ladder.map((l) => (
                <li key={l.level}>
                  <Card className={cn(l.level === a.level && "border-pitch-500", l.level < a.level && "opacity-70")}>
                    <div className="flex items-center justify-between">
                      <p className="font-bold">
                        {l.level}. {l.name}
                      </p>
                      {l.level === a.level && <Chip tone="green">You</Chip>}
                      {l.level < a.level && <CheckCircle2 className="text-ready h-5 w-5" aria-label="done" />}
                    </div>
                    <p className="text-ink-2 text-sm">{l.who}</p>
                    <p className="text-ink-2 mt-1 text-xs">
                      {l.sessions_per_week} sessions + match a week · {l.gym_per_week} gym
                    </p>
                  </Card>
                </li>
              ))}
            </ol>
          </section>

          <section>
            <SectionTitle>My club week</SectionTitle>
            <Card className="space-y-3">
              <div>
                <p className="mb-1 text-sm font-semibold">Club training days</p>
                <div className="flex flex-wrap gap-1.5">
                  {WEEKDAYS.map((d, i) => {
                    const on = data.profile.team_days.includes(i);
                    return (
                      <button
                        key={d}
                        aria-pressed={on}
                        className={cn("tap h-11 w-11 rounded-xl border text-sm font-bold", on ? "bg-pitch-600 border-pitch-600 text-white" : "border-line")}
                        onClick={() =>
                          save({ team_days: on ? data.profile.team_days.filter((x) => x !== i) : [...data.profile.team_days, i] })
                        }
                      >
                        {d}
                      </button>
                    );
                  })}
                </div>
              </div>
              <label className="block">
                <span className="text-sm font-semibold">Match day</span>
                <select
                  className="bg-surface-2 border-line mt-1 h-11 w-full rounded-xl border px-3"
                  value={data.profile.match_day ?? -1}
                  onChange={(e) => save({ match_day: Number(e.target.value) })}
                >
                  <option value={-1}>No regular match</option>
                  {WEEKDAYS.map((d, i) => (
                    <option key={d} value={i}>
                      {d}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-sm font-semibold">Equipment</span>
                <select
                  className="bg-surface-2 border-line mt-1 h-11 w-full rounded-xl border px-3"
                  value={data.profile.equipment}
                  onChange={(e) => save({ equipment: e.target.value })}
                >
                  <option value="none">No equipment</option>
                  <option value="home">Home: band and dumbbells</option>
                  <option value="gym">Full gym</option>
                </select>
              </label>
              <label className="block">
                <span className="text-sm font-semibold">My goal</span>
                <select
                  className="bg-surface-2 border-line mt-1 h-11 w-full rounded-xl border px-3"
                  value={data.profile.goal}
                  onChange={(e) => save({ goal: e.target.value })}
                >
                  {Object.entries(data.goals).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
            </Card>
          </section>
        </div>
      </div>

      <p className="text-ink-2 text-center text-xs">{data.note}</p>
    </div>
  );
}

function Progress({ label, value, done }: { label: string; value: number; done: boolean }) {
  return (
    <div>
      <p className="mb-1 text-sm font-semibold">{label}</p>
      <div className="bg-surface-2 h-3 rounded-full" role="progressbar" aria-valuenow={Math.round(Math.min(1, value) * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className={cn("h-full rounded-full", done ? "bg-ready" : "bg-pitch-500")} style={{ width: `${Math.min(1, value) * 100}%` }} />
      </div>
    </div>
  );
}
