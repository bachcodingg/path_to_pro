// Match diary: after the final whistle, minutes, position, goals, assists, a self-rating
// and how hard it was. Feeds the career stats and the planner's match load.
import { Minus, Plus, Trophy } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "../shared/api";
import { POSITION_LABEL } from "../shared/Rating";
import type { Career, DiaryDue, Position } from "../shared/types";
import { Button, Card, cn, fmtDay } from "../shared/ui";

function Stepper({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm font-semibold">{label}</span>
      <span className="flex items-center gap-2">
        <Button type="button" variant="secondary" size="sm" aria-label={`${label} minus one`} onClick={() => onChange(Math.max(0, value - 1))}>
          <Minus className="h-4 w-4" />
        </Button>
        <span className="w-6 text-center text-lg font-bold tabular-nums" aria-label={`${label}: ${value}`}>
          {value}
        </span>
        <Button type="button" variant="secondary" size="sm" aria-label={`${label} plus one`} onClick={() => onChange(Math.min(10, value + 1))}>
          <Plus className="h-4 w-4" />
        </Button>
      </span>
    </div>
  );
}

export function MatchDiary({ due, position, onSaved }: { due: DiaryDue[]; position?: Position | null; onSaved: (c: Career) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [minutes, setMinutes] = useState(90);
  const [pos, setPos] = useState<Position>(position ?? "midfielder");
  const [goals, setGoals] = useState(0);
  const [assists, setAssists] = useState(0);
  const [rating, setRating] = useState<number | null>(null);
  const [rpe, setRpe] = useState(7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!due.length) return null;
  const match = due.find((d) => d.match_id === open);

  async function save() {
    if (!match || rating == null) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api<Career>(`/api/me/matches/${match.match_id}/diary`, {
        method: "POST",
        json: { minutes, position: pos, goals, assists, self_rating: rating, rpe },
      });
      setOpen(null);
      setRating(null);
      onSaved(out);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Match diary">
      <Card className="border-pitch-500">
        <p className="flex items-center gap-2 font-bold">
          <Trophy className="text-ready-amber h-5 w-5" aria-hidden /> How did the match go?
        </p>
        {!match && (
          <ul className="mt-2 space-y-2">
            {due.map((d) => (
              <li key={d.match_id}>
                <button
                  className="tap border-line hover:bg-surface-2 flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left"
                  onClick={() => {
                    setOpen(d.match_id);
                    setMinutes(d.minutes ?? 90);
                  }}
                >
                  <span>
                    <span className="block font-semibold">vs {d.opponent}</span>
                    <span className="text-ink-2 text-xs">
                      {fmtDay(d.date, { weekday: "short", day: "numeric", month: "short" })} · {d.team}
                    </span>
                  </span>
                  <span className="text-pitch-300 text-sm font-semibold">Fill in</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {match && (
          <div className="mt-3 space-y-4">
            <p className="text-ink-2 text-sm">
              vs {match.opponent} · {match.team}
            </p>
            <label className="block">
              <span className="text-sm font-semibold">Minutes played: {minutes === 0 ? "didn't play" : minutes}</span>
              <input type="range" min={0} max={120} step={5} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} className="accent-pitch-400 h-11 w-full" />
            </label>
            <label className="block">
              <span className="text-sm font-semibold">Position</span>
              <select className="bg-surface-2 border-line mt-1 h-11 w-full rounded-xl border px-3" value={pos} onChange={(e) => setPos(e.target.value as Position)}>
                {Object.entries(POSITION_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <Stepper label="Goals" value={goals} onChange={setGoals} />
            <Stepper label="Assists" value={assists} onChange={setAssists} />
            <fieldset>
              <legend className="text-sm font-semibold">How well did you play?</legend>
              <div className="mt-1 grid grid-cols-10 gap-1">
                {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                  <button
                    key={n}
                    type="button"
                    aria-pressed={rating === n}
                    aria-label={`Self-rating ${n}`}
                    onClick={() => setRating(n)}
                    className={cn("tap h-11 rounded-lg border text-sm font-bold", rating === n ? "bg-pitch-600 border-pitch-600 text-white" : "border-line")}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </fieldset>
            <label className="block">
              <span className="text-sm font-semibold">How hard was it? {rpe}/10</span>
              <input type="range" min={1} max={10} value={rpe} onChange={(e) => setRpe(Number(e.target.value))} className="accent-pitch-400 h-11 w-full" />
            </label>
            {error && (
              <p role="alert" className="text-ready-red text-sm">
                {error}
              </p>
            )}
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setOpen(null)}>
                Back
              </Button>
              <Button className="flex-1" onClick={save} loading={busy} disabled={rating == null}>
                Save match diary
              </Button>
            </div>
          </div>
        )}
      </Card>
    </section>
  );
}
