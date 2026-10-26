// "Scouting report": timeline of load, readiness, ACWR, growth, tests, approved changes and notes.
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, Brush, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError } from "../shared/api";
import { useAuth } from "../shared/auth";
import { GymProgrammeView } from "../shared/GymProgramme";
import { RatingHistory, type RatingHistoryData } from "../shared/RatingHistory";
import type { Card as CardData, GymProgramme, PlanDay, Position, Roadmap, Status } from "../shared/types";
import { useApi } from "../shared/useApi";
import { PageHeader } from "../shared/PageHeader";
import { BAND_TEXT, BandIcon, Button, Card, Chip, ErrorNote, SectionTitle, Spinner, cn, fmtDay, intensityClass } from "../shared/ui";

const BAND_RING = { green: "ring-ready-green", amber: "ring-ready-amber", red: "ring-ready-red" } as const;
const initials = (name: string) =>
  name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

interface Profile {
  player: { id: string; name: string; age: number; position: Position };
  positions: { id: Position; label: string; focus: string }[];
  gym: GymProgramme | null;
  ratings: RatingHistoryData;
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
      {/* Player-profile header, as on the league sites: portrait (initials), name, key facts */}
      <PageHeader
        eyebrow={
          <Link to="/coach" className="hover:underline">
            ← Dressing room
          </Link>
        }
        title={data.player.name}
        subtitle={`${data.player.age} years · ${data.positions.find((p) => p.id === data.player.position)?.label ?? data.player.position}`}
        leading={
          <span
            className={cn(
              "font-display flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-white/10 text-2xl font-bold ring-4 md:h-20 md:w-20 md:text-3xl",
              s?.band ? BAND_RING[s.band] : "ring-white/20",
            )}
            aria-hidden
          >
            {initials(data.player.name)}
          </span>
        }
        actions={
          <>
            <span className="text-right">
              <span className="font-display block text-5xl leading-none font-bold">{s?.score != null ? Math.round(s.score) : "–"}</span>
              <span className="flex items-center justify-end gap-1 text-xs font-bold tracking-wider text-white/75 uppercase">
                <BandIcon band={s?.band ?? null} className="h-3.5 w-3.5" /> {s?.band ? BAND_TEXT[s.band] : "No reading"}
              </span>
            </span>
            <label className="flex items-center gap-2 text-sm">
              <span className="text-white/75">Position</span>
              <select
                aria-label="Position"
                className="h-9 rounded-lg border px-2 font-semibold"
                value={data.player.position}
                onChange={async (e) => {
                  await api(`/api/coach/players/${id}/position`, { method: "PUT", json: { position: e.target.value } });
                  void reload();
                }}
              >
                {data.positions.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
          </>
        }
        bottom={
          (s?.in_phv_window || s?.acwr != null) && (
            <div className="flex flex-wrap gap-2 pb-5">
              {s?.in_phv_window && <Chip tone="amber">Growth zone ({s.maturity_offset?.toFixed(1)} y)</Chip>}
              {s?.acwr != null && <Chip tone={s.acwr > 1.5 ? "red" : "neutral"}>ACWR {s.acwr.toFixed(2)}</Chip>}
            </div>
          )
        }
      />

      <InstructionBox playerId={id!} name={data.player.name.split(" ")[0]} onApplied={reload} />

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

      <section>
        <SectionTitle>Match ratings over time</SectionTitle>
        <RatingHistory data={data.ratings} dark={false} />
      </section>

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
        {data.gym && (
          <section>
            <SectionTitle>Gym this week: {data.gym.title}</SectionTitle>
            <Card className="max-h-96 overflow-y-auto">
              <p className="text-ink-2 mb-2 text-sm">{data.gym.focus}</p>
              <GymProgrammeView p={data.gym} compact />
            </Card>
          </section>
        )}
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

interface InstructionResult {
  constraints: string[];
  source: string;
  status: string;
  dropped: string[];
  current: PlanDay[];
  proposed: PlanDay[];
  applied: boolean;
}

// Plain-words coach instruction -> planner constraints, previewed before it is applied.
function InstructionBox({ playerId, name, onApplied }: { playerId: string; name: string; onApplied: () => void }) {
  const { user } = useAuth();
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<InstructionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (user?.role !== "coach") return null;

  async function send(apply: boolean, e?: FormEvent) {
    e?.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api<InstructionResult>(`/api/coach/players/${playerId}/instruction`, { method: "POST", json: { text, apply } });
      setPreview(out);
      if (out.applied) {
        setText("");
        onApplied();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed");
      setPreview(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <form onSubmit={(e) => send(false, e)} className="flex flex-wrap gap-2">
        <label className="min-w-0 flex-1">
          <span className="text-sm font-semibold">Tell the planner in your own words</span>
          <input
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setPreview(null);
            }}
            placeholder={`e.g. "Keep ${name} light until Thursday, no gym this week"`}
            aria-label="Coach instruction"
            maxLength={300}
            className="bg-surface-2 border-line mt-1 h-11 w-full rounded-xl border px-3"
          />
        </label>
        <Button type="submit" variant="secondary" className="self-end" loading={busy && !preview}>
          Preview
        </Button>
      </form>
      {error && (
        <p role="alert" className="text-ready-red mt-2 text-sm font-medium">
          {error}
        </p>
      )}
      {preview && (
        <div className="mt-3 space-y-2" aria-label="Instruction preview">
          <div className="flex flex-wrap gap-1.5">
            {preview.constraints.map((c) => (
              <Chip key={c}>{c}</Chip>
            ))}
            <Chip tone="green">{preview.source === "rules" ? "rule parser" : "Claude"}</Chip>
          </div>
          {(["current", "proposed"] as const).map((k) => (
            <div key={k} className="grid grid-cols-[5rem_1fr] items-center gap-2">
              <span className="text-ink-2 text-xs font-semibold uppercase">{k === "current" ? "Now" : "New"}</span>
              <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${preview[k].length}, minmax(0, 1fr))` }}>
                {preview[k].map((d) => (
                  <div key={d.date} className={cn("rounded-lg p-1 text-center text-[11px]", intensityClass(d.kind, d.rpe))}>
                    <div className="font-bold">{fmtDay(d.date)}</div>
                    <div className="truncate">{d.label}</div>
                    <div>{d.kind === "rest" ? "–" : d.rpe}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {preview.dropped.length > 0 && (
            <p className="text-ink-2 text-xs">Not possible within the safety rules: {preview.dropped.join("; ")}</p>
          )}
          {preview.applied ? (
            <p role="status" className="text-ready-green text-sm font-semibold">
              Applied. {name} sees the new week with your note.
            </p>
          ) : (
            <Button variant="approve" onClick={() => send(true)} loading={busy}>
              Apply to {name}'s week
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}
