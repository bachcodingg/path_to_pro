// "Scouting report": timeline of load, readiness, ACWR, growth, tests, approved changes and notes.
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, Brush, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../shared/api";
import type { Card as CardData, PlanDay, Roadmap, Status } from "../shared/types";
import { useApi } from "../shared/useApi";
import { BandBadge, Button, Card, Chip, ErrorNote, SectionTitle, Spinner, cn, fmtDay, intensityClass } from "../shared/ui";

interface Profile {
  player: { id: string; name: string; age: number };
  status: Status | null;
  series: { date: string; load: number; readiness: number | null; acwr: number | null }[];
  growth: { date: string; height_cm: number }[];
  card: CardData;
  roadmap: Roadmap;
  changes: { date: string; kind: string; status: string; reason: string; approver: string | null }[];
  escalations: { date: string; kind: string; acknowledged: boolean }[];
  notes: { date: string; text: string; author: string }[];
  week: PlanDay[];
}

export function PlayerProfile() {
  const { id } = useParams();
  const { data, error, loading, reload } = useApi<Profile>(`/api/coach/players/${id}`);
  const [note, setNote] = useState("");

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  async function addNote(e: FormEvent) {
    e.preventDefault();
    if (!note.trim()) return;
    await api(`/api/coach/players/${id}/notes`, { method: "POST", json: { text: note } });
    setNote("");
    void reload();
  }

  const s = data.status;
  return (
    <div className="space-y-4">
      <Link to="/coach" className="text-pitch-600 text-sm font-semibold hover:underline">
        ← Dressing room
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-extrabold">{data.player.name}</h1>
        <span className="text-ink-2">{data.player.age} y</span>
        <BandBadge band={s?.band ?? null} score={s?.score} />
        {s?.in_phv_window && <Chip tone="amber">Growth zone ({s.maturity_offset?.toFixed(1)} y)</Chip>}
        {s?.acwr != null && <Chip tone={s.acwr > 1.5 ? "red" : "neutral"}>ACWR {s.acwr.toFixed(2)}</Chip>}
      </div>

      <Card className="h-80 p-2">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data.series} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#e5ece8" />
            <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} fontSize={11} />
            <YAxis yAxisId="load" fontSize={11} label={{ value: "AU", angle: -90, position: "insideLeft", fontSize: 11 }} />
            <YAxis yAxisId="r" orientation="right" domain={[0, 100]} fontSize={11} />
            <Tooltip />
            <Legend />
            <Bar yAxisId="load" dataKey="load" name="Load (AU)" fill="#46c17e" />
            <Line yAxisId="r" dataKey="readiness" name="Readiness" stroke="#2f7fe0" strokeWidth={2} dot={false} connectNulls />
            <ReferenceLine yAxisId="r" y={50} stroke="#ea6a12" strokeDasharray="4 4" />
            <Brush dataKey="date" height={20} travellerWidth={8} tickFormatter={(d) => d.slice(5)} />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <section>
          <SectionTitle>This week</SectionTitle>
          <Card className="grid grid-cols-7 gap-1">
            {data.week.map((d) => (
              <div key={d.date} className={cn("rounded-lg p-1.5 text-center text-xs", intensityClass(d.kind, d.rpe))}>
                <div className="font-bold">{fmtDay(d.date)}</div>
                <div className="truncate">{d.label}</div>
                <div>{d.kind === "rest" ? "–" : d.rpe}</div>
              </div>
            ))}
          </Card>
        </section>
        <section>
          <SectionTitle>Tests (bio-banded percentile)</SectionTitle>
          <Card className="space-y-2">
            {data.card.attributes.map((a) => (
              <div key={a.kpi} className="flex items-center gap-3">
                <span className="w-28 text-sm font-semibold">{a.label}</span>
                <div className="bg-surface-2 h-2.5 flex-1 rounded-full">
                  <div className="bg-pitch-500 h-full rounded-full" style={{ width: `${a.bio_percentile}%` }} />
                </div>
                <span className="w-24 text-right text-sm">
                  {a.value} {a.unit} · {a.bio_percentile}
                </span>
              </div>
            ))}
          </Card>
        </section>
        <section>
          <SectionTitle>Agent changes</SectionTitle>
          <Card className="divide-[color:var(--line)] max-h-72 divide-y overflow-y-auto p-0">
            {data.changes.length === 0 && <p className="text-ink-2 p-3 text-sm">No changes yet.</p>}
            {data.changes.map((c, i) => (
              <div key={i} className="p-3 text-sm">
                <div className="flex justify-between">
                  <span className="font-semibold">{c.kind.replaceAll("_", " ")}</span>
                  <span className="text-ink-2">
                    {c.status}
                    {c.approver && ` by ${c.approver}`}
                  </span>
                </div>
                <p className="text-ink-2">{c.reason}</p>
              </div>
            ))}
          </Card>
        </section>
        <section>
          <SectionTitle>Notes</SectionTitle>
          <Card className="space-y-2">
            <form onSubmit={addNote} className="flex gap-2">
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Add a note"
                aria-label="New note"
                className="bg-surface-2 border-line h-11 flex-1 rounded-xl border px-3"
              />
              <Button type="submit" size="sm">
                Add
              </Button>
            </form>
            {data.notes.map((n, i) => (
              <p key={i} className="text-sm">
                <span className="text-ink-2">
                  {n.date} · {n.author}:
                </span>{" "}
                {n.text}
              </p>
            ))}
            {data.escalations.length > 0 && (
              <p className="text-ink-2 text-xs">
                Escalations: {data.escalations.map((e) => `${e.date} ${e.kind.replace("_", " ")}${e.acknowledged ? " ✓" : ""}`).join(", ")}
              </p>
            )}
          </Card>
        </section>
      </div>
    </div>
  );
}
