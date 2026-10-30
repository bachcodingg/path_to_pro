// Gym: this week's strength sessions. Shared work for every footballer + a position block.
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "../shared/api";
import { useAuth } from "../shared/auth";
import { GymProgrammeView } from "../shared/GymProgramme";
import type { GymWeek, Position } from "../shared/types";
import { useApi } from "../shared/useApi";
import { Button, Card, ErrorNote, SectionTitle, Spinner, fmtDay } from "../shared/ui";
import { TrainingSwitch } from "./Skills";

const EQUIPMENT_LABEL = { gym: "Full gym", home: "Home: band and dumbbells", none: "No equipment" };

export function Gym() {
  const { user } = useAuth();
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useApi<GymWeek>(`/api/me/gym?offset=${offset}`);
  const [msg, setMsg] = useState<string | null>(null);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  async function changePosition(position: Position) {
    setMsg(null);
    try {
      await api("/api/me/position", { method: "PUT", json: { position } });
      await reload();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Could not change position");
    }
  }

  const selfGuided = user?.pathway === "amateur";
  return (
    <div className="space-y-4 pt-2">
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => setOffset(Math.max(-1, offset - 1))} aria-label="Previous week" disabled={offset <= -1}>
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div className="text-center">
          <h1 className="text-xl font-extrabold">Gym</h1>
          <p className="text-ink-2 text-sm">
            {offset === 0 ? "This week" : offset === 1 ? "Next week" : "Last week"} · {EQUIPMENT_LABEL[data.equipment]}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setOffset(Math.min(1, offset + 1))} aria-label="Next week" disabled={offset >= 1}>
          <ChevronRight className="h-5 w-5" />
        </Button>
      </div>
      <TrainingSwitch active="gym" />

      <Card>
        <p className="text-ink-2 text-xs font-semibold uppercase">Your position</p>
        {selfGuided ? (
          <label className="mt-1 block">
            <span className="sr-only">Position</span>
            <select
              className="bg-surface-2 border-line h-11 w-full rounded-xl border px-3 font-bold"
              value={data.position}
              onChange={(e) => changePosition(e.target.value as Position)}
            >
              {data.positions.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <p className="text-lg font-bold">{data.position_label}</p>
        )}
        <p className="text-ink-2 mt-2 text-sm">{data.focus}</p>
        <p className="text-ink-2 mt-2 text-xs">
          Every session has the same warm-up, injury prevention (Nordic curls, Copenhagen planks), core and cool-down for all
          players. The power and position blocks are chosen for your position.
        </p>
        {msg && <p className="text-recover mt-2 text-sm">{msg}</p>}
      </Card>

      {data.sessions.map(({ session, programme }) => (
        <section key={session.date}>
          <SectionTitle>
            {fmtDay(session.date, { weekday: "long", day: "numeric", month: "short" })} · effort {session.rpe}/10
          </SectionTitle>
          <Card>
            <p className="mb-2 text-lg font-bold">{programme.title}</p>
            <GymProgrammeView p={programme} />
          </Card>
        </section>
      ))}

      {data.sessions.length === 0 && data.optional && (
        <section>
          <SectionTitle>No gym day this week</SectionTitle>
          <Card>
            <p className="mb-1 text-lg font-bold">Optional: {data.optional.title}</p>
            <p className="text-ink-2 mb-3 text-sm">A short session you can do on an easy day. Skip it if you feel tired.</p>
            <GymProgrammeView p={data.optional} />
          </Card>
        </section>
      )}
      <p className="text-ink-2 text-center text-xs">Tap an exercise for coaching cues. Stop if anything hurts and tell an adult.</p>
    </div>
  );
}
