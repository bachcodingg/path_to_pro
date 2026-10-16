// "Season map": the 4-week goal cycle as a level map. Checkpoints = test days, badges = goals met.
import { Award, Lock } from "lucide-react";
import { useState } from "react";
import type { Roadmap } from "../shared/types";
import { useApi } from "../shared/useApi";
import { Card, ErrorNote, SectionTitle, Spinner, capitalize, cn, fmtDay } from "../shared/ui";

export function RoadToPro() {
  const { data, error, loading, reload } = useApi<Roadmap>("/api/me/roadmap");
  const [sel, setSel] = useState<number | null>(null);
  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  const cps = data.checkpoints;
  const n = cps.length;
  // Winding path: points alternate left/right going up the map.
  const pts = cps.map((_, i) => ({ x: i % 2 === 0 ? 30 : 90, y: 30 + (n - 1 - i) * 42 }));
  const height = 60 + (n - 1) * 42;
  const path = pts.map((p, i) => `${i ? "L" : "M"}${p.x} ${p.y}`).join(" ");
  const active = data.goals.filter((g) => g.status === "active");
  const picked = sel != null ? cps[sel] : null;

  return (
    <div className="space-y-4 pt-2">
      <h1 className="text-2xl font-extrabold">Road to Pro</h1>
      <Card className="p-2">
        <svg viewBox={`0 0 120 ${height}`} className="mx-auto max-h-[420px] w-full" role="img" aria-label="Season map">
          <path d={path} fill="none" stroke="#24402f" strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" />
          <path d={path} fill="none" stroke="#7ee0a8" strokeWidth={2} strokeDasharray="3 4" />
          {pts.map((p, i) => (
            <g
              key={i}
              transform={`translate(${p.x} ${p.y})`}
              onClick={() => setSel(i)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && setSel(i)}
              aria-label={`Test day ${fmtDay(cps[i].date, { day: "numeric", month: "short" })}${cps[i].done ? ", done" : ", next"}`}
              style={{ cursor: "pointer" }}
            >
              <circle r={11} fill={cps[i].done ? "#22a061" : "#0f2219"} stroke={sel === i ? "#fff" : "#7ee0a8"} strokeWidth={2} />
              <text y={3.5} textAnchor="middle" fontSize={9} fontWeight={800} fill="#fff">
                {cps[i].done ? "✓" : i + 1}
              </text>
              <text x={p.x < 60 ? 16 : -16} y={3} textAnchor={p.x < 60 ? "start" : "end"} fontSize={7} fill="#a9c2b3">
                {fmtDay(cps[i].date, { day: "numeric", month: "short" })}
              </text>
            </g>
          ))}
        </svg>
      </Card>

      {picked && (
        <Card className="border-pitch-400">
          <p className="font-bold">
            {picked.done ? "Test day completed" : "Next test day"} · {fmtDay(picked.date, { weekday: "long", day: "numeric", month: "long" })}
          </p>
          <p className="text-ink-2 text-sm">Sprint, jump and endurance tests. Your goals update after each test day.</p>
        </Card>
      )}

      <section>
        <SectionTitle>4-week goals</SectionTitle>
        {active.length === 0 && <Card className="text-ink-2">Your coach is setting your next goals.</Card>}
        <div className="space-y-2">
          {active.map((g) => (
            <Card key={g.id}>
              <div className="flex justify-between">
                <p className="font-bold">{capitalize(g.label)}</p>
                <p className="text-ink-2 text-sm">until {fmtDay(g.ends_on, { day: "numeric", month: "short" })}</p>
              </div>
              <p className="text-ink-2 text-sm">
                {g.baseline} → target {g.target} {g.unit} · {g.sessions_per_week} focused sessions a week
              </p>
              <div className="bg-surface-2 mt-2 h-3 overflow-hidden rounded-full" role="progressbar" aria-valuenow={Math.round(g.progress * 100)} aria-valuemin={0} aria-valuemax={100}>
                <div className="bg-pitch-400 h-full rounded-full" style={{ width: `${Math.max(4, g.progress * 100)}%` }} />
              </div>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle>Badges</SectionTitle>
        <div className="grid grid-cols-3 gap-2">
          {data.badges.map((b) => (
            <Card key={b.id} className={cn("flex flex-col items-center p-3 text-center", !b.earned && "opacity-50")}>
              {b.earned ? <Award className="text-ready-amber h-8 w-8" aria-hidden /> : <Lock className="text-ink-2 h-8 w-8" aria-hidden />}
              <p className="mt-1 text-sm font-bold">{b.name}</p>
              <p className="text-ink-2 text-xs">{b.rule}</p>
            </Card>
          ))}
        </div>
        <p className="text-ink-2 mt-2 text-xs">Badges are yours to keep. Missing a day never takes anything away.</p>
      </section>
    </div>
  );
}
