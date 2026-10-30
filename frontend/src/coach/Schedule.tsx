// The team's training week and its fixtures: the two inputs every player's plan is built on.
// Changes reach the plans at the next agent run (tonight, or "Run agents now").
import { CalendarPlus, Save, Trash2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../shared/api";
import { useAuth } from "../shared/auth";
import { PageHeader } from "../shared/PageHeader";
import { Button, Card, Chip, ErrorNote, SectionTitle, Spinner, capitalize, cn, fmtDay, intensityClass } from "../shared/ui";
import type { SessionKind } from "../shared/types";
import { useApi } from "../shared/useApi";

interface Slot {
  weekday: number;
  kind: SessionKind;
  minutes: number;
  rpe: number;
}
interface ScheduleData {
  team: string;
  today: string;
  weeks_ahead: number;
  training_week: Slot[];
  saved: boolean; // false: the week is read from the sessions already planned
  kinds: { kind: SessionKind; minutes: number; rpe_min: number; rpe_max: number }[];
  fixtures: { id: string; kickoff: string; opponent: string; competition: string | null; is_evening: boolean }[];
  next_sessions: { day: string; kind: SessionKind; minutes: number | null; rpe: number | null }[];
}

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const field = "bg-surface-2 border-line text-ink h-10 rounded-lg border px-2 text-sm";

function message(err: unknown): string {
  return err instanceof ApiError ? err.message : "Cannot reach the server";
}

export function Schedule() {
  const { user } = useAuth();
  const canEdit = user?.role === "coach";
  const { data, error, loading, reload, setData } = useApi<ScheduleData>("/api/coach/schedule");
  const [week, setWeek] = useState<(Slot | null)[]>(Array(7).fill(null));
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [fx, setFx] = useState({ opponent: "", kickoff: "", competition: "" });

  useEffect(() => {
    if (data) setWeek(WEEKDAYS.map((_, i) => data.training_week.find((s) => s.weekday === i) ?? null));
  }, [data]);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const kinds = data.kinds;
  const range = (k: SessionKind) => kinds.find((x) => x.kind === k)!;

  function setDay(i: number, slot: Slot | null) {
    setWeek((w) => w.map((s, j) => (j === i ? slot : s)));
  }

  function toggle(i: number, on: boolean) {
    const k = kinds.find((x) => x.kind === "technical") ?? kinds[0];
    setDay(i, on ? { weekday: i, kind: k.kind, minutes: k.minutes, rpe: Math.round((k.rpe_min + k.rpe_max) / 2) } : null);
  }

  function changeKind(i: number, kind: SessionKind) {
    const r = range(kind);
    setDay(i, { weekday: i, kind, minutes: r.minutes, rpe: Math.min(Math.max(week[i]!.rpe, r.rpe_min), r.rpe_max) });
  }

  async function saveWeek() {
    setBusy("week");
    setNote(null);
    try {
      const out = await api<ScheduleData & { added: number; removed: number }>("/api/coach/schedule/week", {
        method: "PUT",
        json: { days: week.filter(Boolean) },
      });
      setData(out);
      setNote({ ok: true, text: `Training week saved: ${out.added} sessions planned for the next ${out.weeks_ahead} weeks. Players' plans follow at the next agent run.` });
    } catch (err) {
      setNote({ ok: false, text: message(err) });
    } finally {
      setBusy(null);
    }
  }

  async function addFixture(e: FormEvent) {
    e.preventDefault();
    setBusy("fixture");
    setNote(null);
    try {
      await api("/api/coach/fixtures", { method: "POST", json: { ...fx, competition: fx.competition || null } });
      setFx({ opponent: "", kickoff: "", competition: "" });
      setNote({ ok: true, text: "Fixture added. That day's training makes way for the match." });
      await reload();
    } catch (err) {
      setNote({ ok: false, text: message(err) });
    } finally {
      setBusy(null);
    }
  }

  async function removeFixture(id: string) {
    setBusy(id);
    setNote(null);
    try {
      await api(`/api/coach/fixtures/${id}`, { method: "DELETE" });
      await reload();
    } catch (err) {
      setNote({ ok: false, text: message(err) });
    } finally {
      setBusy(null);
    }
  }

  const trainingDays = week.filter(Boolean).length;
  const upcoming = data.fixtures.filter((f) => f.kickoff.slice(0, 10) >= data.today);
  const recent = data.fixtures.filter((f) => f.kickoff.slice(0, 10) < data.today);
  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow={data.team}
        title="Schedule"
        subtitle="The team's training week and its fixtures. The planner builds each player's week from these, then adapts it to their readiness, growth and load."
      />
      {note && (
        <p role={note.ok ? "status" : "alert"} className={cn("text-sm font-semibold", note.ok ? "text-ready" : "text-recover")}>
          {note.text}
        </p>
      )}
      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <section>
          <SectionTitle
            action={
              canEdit && (
                <Button onClick={saveWeek} loading={busy === "week"} disabled={trainingDays > 6}>
                  <Save className="h-4 w-4" aria-hidden /> Save training week
                </Button>
              )
            }
          >
            Training week
          </SectionTitle>
          <Card className="p-0">
            <ul>
              {WEEKDAYS.map((day, i) => {
                const s = week[i];
                const r = s ? range(s.kind) : null;
                return (
                  <li key={day} className="border-line flex flex-wrap items-center gap-3 border-t px-4 py-2 first:border-t-0">
                    <label className="flex w-32 items-center gap-2 font-semibold">
                      <input type="checkbox" className="h-5 w-5" checked={!!s} disabled={!canEdit} onChange={(e) => toggle(i, e.target.checked)} />
                      {day}
                    </label>
                    {s && r ? (
                      <>
                        <select aria-label={`${day} session`} className={field} value={s.kind} disabled={!canEdit} onChange={(e) => changeKind(i, e.target.value as SessionKind)}>
                          {kinds.map((k) => (
                            <option key={k.kind} value={k.kind}>
                              {capitalize(k.kind)}
                            </option>
                          ))}
                        </select>
                        <label className="flex items-center gap-1 text-sm">
                          <input
                            aria-label={`${day} minutes`}
                            className={cn(field, "w-20")}
                            type="number"
                            min={20}
                            max={150}
                            step={5}
                            value={s.minutes}
                            disabled={!canEdit}
                            onChange={(e) => setDay(i, { ...s, minutes: Number(e.target.value) })}
                          />
                          min
                        </label>
                        <label className="flex items-center gap-1 text-sm">
                          RPE
                          <input
                            aria-label={`${day} RPE`}
                            className={cn(field, "w-16")}
                            type="number"
                            min={r.rpe_min}
                            max={r.rpe_max}
                            value={s.rpe}
                            disabled={!canEdit}
                            onChange={(e) => setDay(i, { ...s, rpe: Number(e.target.value) })}
                          />
                          <span className="text-ink-2 text-xs">
                            ({r.rpe_min}-{r.rpe_max})
                          </span>
                        </label>
                      </>
                    ) : (
                      <span className="text-ink-2 text-sm">Rest</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </Card>
          {!data.saved && data.training_week.length > 0 && (
            <p className="mt-2 text-sm font-semibold">
              Read from the sessions already planned. Check it and save, so the next weeks are planned the same way.
            </p>
          )}
          <p className="text-ink-2 mt-2 text-xs">
            Sessions are planned {data.weeks_ahead} weeks ahead and extended every Sunday. At least one rest day a week; on match days the
            match replaces training. Players in a growth spurt or with a load spike get a safer version automatically.
            {trainingDays > 6 && <strong className="text-recover"> Leave at least one rest day.</strong>}
          </p>
          {data.next_sessions.length > 0 && (
            <div className="mt-6">
              <SectionTitle>Next team sessions</SectionTitle>
              <div className="flex flex-wrap gap-2">
                {data.next_sessions.map((s) => (
                  <span key={s.day} className={cn("rounded-lg px-2 py-1 text-xs font-semibold", intensityClass(s.kind, s.rpe ?? 5))}>
                    {fmtDay(s.day, { weekday: "short", day: "numeric", month: "short" })} · {s.kind}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="space-y-4">
          <div>
            <SectionTitle>Fixtures</SectionTitle>
            <Card className="p-0">
              <ul>
                {upcoming.length === 0 && <li className="text-ink-2 px-4 py-3 text-sm">No upcoming matches.</li>}
                {upcoming.map((f) => (
                  <li key={f.id} className="border-line flex items-center justify-between gap-2 border-t px-4 py-2 first:border-t-0">
                    <span>
                      <span className="block font-semibold">{f.opponent}</span>
                      <span className="text-ink-2 text-xs">
                        {fmtDay(f.kickoff.slice(0, 10), { weekday: "short", day: "numeric", month: "short" })} · {f.kickoff.slice(11, 16)}
                        {f.competition && ` · ${f.competition}`}
                      </span>
                    </span>
                    {canEdit && (
                      <Button size="sm" variant="ghost" onClick={() => removeFixture(f.id)} loading={busy === f.id} aria-label={`Remove the match against ${f.opponent}`}>
                        <Trash2 className="h-4 w-4" aria-hidden />
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
            {recent.length > 0 && (
              <p className="text-ink-2 mt-2 text-xs">
                Last two weeks: {recent.map((f) => f.opponent).join(", ")} <Chip>played</Chip>
              </p>
            )}
          </div>
          {canEdit && (
            <Card>
              <SectionTitle>Add a match</SectionTitle>
              <form onSubmit={addFixture} className="space-y-3">
                <label className="block">
                  <span className="text-ink-2 text-xs font-semibold">Opponent</span>
                  <input className={cn(field, "mt-1 w-full")} required minLength={2} value={fx.opponent} onChange={(e) => setFx({ ...fx, opponent: e.target.value })} />
                </label>
                <label className="block">
                  <span className="text-ink-2 text-xs font-semibold">Kick-off</span>
                  <input
                    className={cn(field, "mt-1 w-full")}
                    type="datetime-local"
                    required
                    min={`${data.today}T00:00`}
                    value={fx.kickoff}
                    onChange={(e) => setFx({ ...fx, kickoff: e.target.value })}
                  />
                </label>
                <label className="block">
                  <span className="text-ink-2 text-xs font-semibold">Competition (optional)</span>
                  <input className={cn(field, "mt-1 w-full")} placeholder="League, Cup, Friendly" value={fx.competition} onChange={(e) => setFx({ ...fx, competition: e.target.value })} />
                </label>
                <Button type="submit" className="w-full" loading={busy === "fixture"}>
                  <CalendarPlus className="h-4 w-4" aria-hidden /> Add match
                </Button>
              </form>
            </Card>
          )}
        </section>
      </div>
    </div>
  );
}
