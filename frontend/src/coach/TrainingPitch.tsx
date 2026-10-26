// Training pitch: the squad's week on one board. Drag a team session onto a day (or pick
// it and press the day): every player is checked against the hard rules, and anyone for
// whom it isn't safe gets the nearest safe version. Preview, then apply to the squad.
import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight } from "lucide-react";
import { useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../shared/api";
import { useAuth } from "../shared/auth";
import type { PlanDay, SessionKind } from "../shared/types";
import { PageHeader } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { BandBadge, Button, Card, Chip, ErrorNote, Spinner, cn, fmtDay, intensityClass } from "../shared/ui";

interface Row {
  id: string;
  name: string;
  position: string;
  phv: boolean;
  band: "green" | "amber" | "red" | null;
  dual: boolean;
  days: (PlanDay & { team_match?: boolean })[];
}
interface SquadWeek {
  start: string;
  today: string;
  dates: string[];
  players: Row[];
}
interface Placement {
  player: { id: string; name: string };
  status: "ok" | "adjusted" | "unchanged" | "match";
  current: PlanDay;
  proposed: PlanDay;
  reasons: string[];
}
interface Preview {
  day: string;
  label: string;
  counts: Record<string, number>;
  players: Placement[];
  applied: boolean;
}

const PALETTE: { kind: SessionKind; label: string; rpe: number; min: number; max: number }[] = [
  { kind: "technical", label: "Technical", rpe: 5, min: 3, max: 6 },
  { kind: "tactical", label: "Tactical", rpe: 6, min: 4, max: 7 },
  { kind: "strength", label: "Gym", rpe: 6, min: 4, max: 8 },
  { kind: "speed", label: "Speed", rpe: 7, min: 5, max: 8 },
  { kind: "recovery", label: "Recovery", rpe: 3, min: 2, max: 3 },
];

export function TrainingPitch() {
  const { user } = useAuth();
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useApi<SquadWeek>(`/api/coach/squad-week?offset=${offset}`);
  const [picked, setPicked] = useState(0);
  const [rpe, setRpe] = useState(PALETTE[0].rpe);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const canPlan = user?.role === "coach";
  const item = PALETTE[picked];

  async function place(day: string, apply = false) {
    setBusy(true);
    setMsg(null);
    try {
      const out = await api<Preview>("/api/coach/squad-week/session", {
        method: "POST",
        json: { day, kind: item.kind, rpe, apply },
      });
      if (apply) {
        setPreview(null);
        setMsg(`Applied: ${out.counts.ok ?? 0} as planned, ${out.counts.adjusted ?? 0} adjusted for safety.`);
        await reload();
      } else setPreview(out);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  function onDrop(e: DragEvent, day: string) {
    e.preventDefault();
    setOver(null);
    const i = Number(e.dataTransfer.getData("text/plain"));
    if (!Number.isNaN(i)) {
      setPicked(i);
      setRpe(PALETTE[i].rpe);
    }
    void place(day);
  }

  const byPlayer = new Map(preview?.players.map((p) => [p.player.id, p]));
  const col = preview ? data.dates.indexOf(preview.day) : -1;
  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Squad"
        title="Training pitch"
        subtitle="Plan a team session; the hard rules are checked for every player."
        actions={
        <div className="flex items-center gap-1 rounded-xl bg-white/10 p-1">
          <Button variant="ghost" size="sm" aria-label="This week" disabled={offset === 0} onClick={() => (setOffset(0), setPreview(null))}>
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <span className="font-display min-w-24 text-center text-lg font-bold uppercase">{offset === 0 ? "This week" : "Next week"}</span>
          <Button variant="ghost" size="sm" aria-label="Next week" disabled={offset === 1} onClick={() => (setOffset(1), setPreview(null))}>
            <ChevronRight className="h-5 w-5" />
          </Button>
        </div>
        }
      />

      {canPlan && (
        <Card className="flex flex-wrap items-center gap-2">
          <span className="text-ink-2 text-sm font-semibold">Session</span>
          {PALETTE.map((p, i) => (
            <button
              key={p.kind}
              draggable
              onDragStart={(e) => e.dataTransfer.setData("text/plain", String(i))}
              onClick={() => {
                setPicked(i);
                setRpe(p.rpe);
                setPreview(null);
              }}
              aria-pressed={picked === i}
              className={cn(
                "tap cursor-grab rounded-xl px-3 py-2 text-sm font-bold active:cursor-grabbing",
                intensityClass(p.kind, p.rpe),
                picked === i && "ring-pitch-500 ring-2 ring-offset-2",
              )}
            >
              {p.label}
            </button>
          ))}
          <label className="ml-auto flex items-center gap-2 text-sm">
            Effort {rpe}
            <input
              type="range"
              min={item.min}
              max={item.max}
              value={rpe}
              onChange={(e) => {
                setRpe(Number(e.target.value));
                setPreview(null);
              }}
              aria-label="Effort"
              className="accent-pitch-500 w-28"
            />
          </label>
          <p className="text-ink-2 w-full text-xs">Drag a session onto a day, or pick one and press "Place" under the day.</p>
        </Card>
      )}

      {preview && (
        <Card className="border-pitch-500 flex flex-wrap items-center gap-3" role="status" aria-label="Team session preview">
          <p className="font-semibold">
            {item.label} (effort {rpe}) on {fmtDay(preview.day, { weekday: "long" })}:
          </p>
          <Chip tone="green">{preview.counts.ok ?? 0} as planned</Chip>
          {(preview.counts.adjusted ?? 0) > 0 && <Chip tone="amber">{preview.counts.adjusted} adjusted for safety</Chip>}
          {(preview.counts.match ?? 0) > 0 && <Chip>{preview.counts.match} match day</Chip>}
          {(preview.counts.unchanged ?? 0) > 0 && <Chip tone="red">{preview.counts.unchanged} unchanged</Chip>}
          <span className="ml-auto flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setPreview(null)}>
              Cancel
            </Button>
            <Button variant="approve" size="sm" loading={busy} onClick={() => place(preview.day, true)}>
              Apply to squad
            </Button>
          </span>
        </Card>
      )}
      {msg && (
        <p role="status" className="text-sm font-semibold">
          {msg}
        </p>
      )}

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[900px] table-fixed border-separate border-spacing-1 text-xs">
          <thead>
            <tr>
              <th className="text-ink-2 w-44 p-2 text-left font-semibold">Player</th>
              {data.dates.map((d) => {
                const past = d < data.today;
                return (
                  <th
                    key={d}
                    onDragOver={(e) => !past && canPlan && (e.preventDefault(), setOver(d))}
                    onDragLeave={() => setOver(null)}
                    onDrop={(e) => !past && canPlan && onDrop(e, d)}
                    className={cn("rounded-lg p-1 text-center align-top", over === d && "bg-pitch-100", d === data.today && "text-pitch-700")}
                  >
                    <div className="font-bold">{fmtDay(d, { weekday: "short", day: "numeric" })}</div>
                    {canPlan &&
                      (past ? (
                        <div className="text-ink-2 flex h-11 items-center justify-center font-normal">Done</div>
                      ) : (
                        <Button variant="ghost" size="sm" className="px-2 text-xs" onClick={() => place(d)} disabled={busy} aria-label={`Place on ${fmtDay(d, { weekday: "long" })}`}>
                          Place
                        </Button>
                      ))}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {data.players.map((p) => {
              const pl = byPlayer.get(p.id);
              return (
                <tr key={p.id}>
                  <td className="p-1">
                    <Link to={`/coach/players/${p.id}`} className="font-semibold hover:underline">
                      {p.name}
                    </Link>
                    <span className="mt-0.5 flex flex-wrap gap-1">
                      <BandBadge band={p.band} />
                      {p.phv && <Chip tone="amber">Growth</Chip>}
                      {p.dual && <Chip>Dual</Chip>}
                    </span>
                  </td>
                  {p.days.map((d, i) => {
                    const show = pl && i === col ? pl.proposed : d;
                    const changed = pl && i === col;
                    return (
                      <td key={d.date} className="p-0">
                        <div
                          className={cn(
                            "rounded-lg p-1.5 text-center",
                            intensityClass(show.kind, show.rpe),
                            changed && pl.status === "ok" && "ring-ready-green ring-2",
                            changed && pl.status === "adjusted" && "ring-ready-amber ring-2",
                            changed && pl.status === "unchanged" && "ring-ready-red ring-2",
                          )}
                          title={changed && pl.reasons.length ? pl.reasons.join("; ") : undefined}
                        >
                          <div className="truncate font-semibold">
                            {show.kind === "match" ? (d.team_match ? "Match (2nd team)" : "Match") : show.label}
                          </div>
                          <div>{show.kind === "rest" ? "–" : show.kind === "match" ? `${show.minutes}'` : show.rpe}</div>
                          {changed && pl.status === "adjusted" && (
                            <div className="mt-0.5 flex items-center justify-center gap-0.5 text-[10px] font-semibold">
                              <AlertTriangle className="h-3 w-3" aria-hidden /> {pl.reasons[0]}
                            </div>
                          )}
                          {changed && pl.status === "ok" && <CheckCircle2 className="mx-auto mt-0.5 h-3 w-3" aria-label="as planned" />}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
