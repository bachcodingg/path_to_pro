// "The pitch": 7 days as 7 vertical lanes on a pitch; lane colour = intensity, ball = match.
// Toggle (or drag the handle) to compare with last week; long-press a day for details.
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { PitchLines } from "../shared/Pitch";
import type { PlanDay, Week } from "../shared/types";
import { useApi } from "../shared/useApi";
import { Button, Card, ErrorNote, Spinner, cn, fmtDay } from "../shared/ui";

const SHORT: Record<string, string> = {
  rest: "Rest",
  recovery: "Recov.",
  technical: "Tech",
  tactical: "Tactic",
  strength: "Gym",
  speed: "Speed",
  match: "Match",
};

function laneFill(d: PlanDay): string {
  if (d.kind === "match") return "#0b2a20";
  if (d.kind === "rest") return "rgba(255,255,255,0.06)";
  const alpha = 0.18 + (d.rpe / 10) * 0.8;
  return `rgba(126, 224, 168, ${alpha.toFixed(2)})`;
}

export function MyWeek() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useApi<Week>(`/api/me/week?offset=${offset}`);
  const [compare, setCompare] = useState(0); // 0 = this week, 1 = last week
  const [detail, setDetail] = useState<PlanDay | null>(null);
  const pressTimer = useRef<number | null>(null);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  const days = compare > 0.5 ? data.last_week : data.days;
  const total = (w: PlanDay[]) => w.reduce((s, d) => s + d.load, 0);

  function startPress(d: PlanDay) {
    pressTimer.current = window.setTimeout(() => setDetail(d), 450);
  }
  function endPress() {
    if (pressTimer.current) window.clearTimeout(pressTimer.current);
  }

  return (
    <div className="space-y-4 pt-2">
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => setOffset(offset - 1)} aria-label="Previous week">
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div className="text-center">
          <h1 className="text-xl font-extrabold">{offset === 0 ? "This week" : offset === 1 ? "Next week" : `Week of ${fmtDay(data.start, { day: "numeric", month: "short" })}`}</h1>
          <p className="text-ink-2 text-sm">{compare > 0.5 ? "Showing last week" : `Planned load ${total(data.days)} AU`}</p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setOffset(offset + 1)} aria-label="Next week">
          <ChevronRight className="h-5 w-5" />
        </Button>
      </div>

      {/* Wide screens: the pitch on the left, the comparison and day details on the right */}
      <div className="space-y-4 lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:items-start lg:gap-6 lg:space-y-0">
        <div className="space-y-5">
          <svg viewBox="0 0 140 150" className="w-full" role="img" aria-label="Week plan on a pitch">
            <rect width={140} height={150} rx={4} fill="#1a6340" />
            <PitchLines width={140} height={150} />
            {days.map((d, i) => {
              const x = 4 + i * 19,
                today = d.date === data.today;
              return (
                <g
                  key={d.date}
                  onPointerDown={() => startPress(d)}
                  onPointerUp={endPress}
                  onPointerLeave={endPress}
                  onClick={() => setDetail(d)}
                  style={{ cursor: "pointer" }}
                  role="button"
                  tabIndex={0}
                  aria-label={`${fmtDay(d.date, { weekday: "long" })}: ${d.label}${d.kind !== "rest" ? `, effort ${d.rpe}` : ""}`}
                  onKeyDown={(e) => e.key === "Enter" && setDetail(d)}
                >
                  <rect x={x} y={14} width={17} height={122} rx={3} fill={laneFill(d)} stroke={today ? "#fff" : "none"} strokeWidth={0.8} />
                  <text x={x + 8.5} y={10} textAnchor="middle" fontSize={6} fill="#fff" fontWeight={700}>
                    {fmtDay(d.date)}
                  </text>
                  {d.kind === "match" ? (
                    <g transform={`translate(${x + 8.5} 75)`}>
                      <circle r={5} fill="#fff" />
                      <path d="M0 -2.2 L2.1 -0.7 L1.3 1.8 L-1.3 1.8 L-2.1 -0.7Z" fill="#111" />
                    </g>
                  ) : (
                    d.kind !== "rest" && (
                      <text x={x + 8.5} y={78} textAnchor="middle" fontSize={7} fill="#fff" fontWeight={800}>
                        {d.rpe}
                      </text>
                    )
                  )}
                  <text x={x + 8.5} y={146} textAnchor="middle" fontSize={4.6} fill="rgba(255,255,255,0.85)">
                    {d.kind === "match" && d.minutes < 90
                      ? `Match ${d.minutes}'`
                      : d.team_day && (d.kind === "technical" || d.kind === "tactical")
                        ? "Club"
                        : SHORT[d.kind]}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        <div className="space-y-5">
          <Card>
            <label className="block">
              <span className="text-sm font-semibold">Drag to compare: this week ↔ last week</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={compare}
                onChange={(e) => setCompare(Number(e.target.value))}
                className="accent-pitch-400 h-11 w-full"
                aria-valuetext={compare > 0.5 ? "last week" : "this week"}
              />
            </label>
            <div className="text-ink-2 flex justify-between text-sm">
              <span>This week {total(data.days)} AU</span>
              <span>Last week {total(data.last_week)} AU</span>
            </div>
          </Card>

          {/* A laptop has room to list the week, so no day needs a click to be read */}
          <Card className="hidden p-0 lg:block">
            <ul className="divide-[color:var(--line)] divide-y" aria-label="Week at a glance">
              {days.map((d) => (
                <li key={d.date}>
                  <button
                    onClick={() => setDetail(d)}
                    className={cn("tap flex w-full items-center gap-3 px-4 py-2.5 text-left", detail?.date === d.date && "bg-white/5")}
                  >
                    <span className={cn("w-10 text-sm font-bold", d.date === data.today && "text-pitch-300")}>{fmtDay(d.date)}</span>
                    <span className="flex-1">
                      {d.label}
                      {d.match && <span className="text-ink-2 text-sm"> · vs {d.match.opponent}</span>}
                    </span>
                    <span className="text-ink-2 text-sm tabular-nums">
                      {d.kind === "rest" ? "–" : `${d.minutes} min · ${d.rpe}/10`}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>

          {detail && (
            <Card className="border-pitch-400" role="dialog" aria-label="Day details">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-ink-2 text-sm">{fmtDay(detail.date, { weekday: "long", day: "numeric", month: "long" })}</p>
                  <p className="text-lg font-bold">{detail.label}</p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setDetail(null)}>
                  Close
                </Button>
              </div>
              {detail.match && (
                <p className="mt-2 text-sm">
                  <span className="font-semibold">{detail.match.team}</span> vs {detail.match.opponent}
                  {detail.minutes === 0 && (
                    <span className="text-caution block">
                      In the squad, but planned not to play: two matches on back-to-back days are too much for under-18s.
                    </span>
                  )}
                </p>
              )}
              {detail.kind !== "rest" && (
                <ul className="mt-2 space-y-1 text-sm">
                  <li>Effort: {detail.rpe} / 10</li>
                  <li>{detail.kind === "match" ? "Planned minutes" : "Duration"}: {detail.minutes} min</li>
                  <li>Planned load: {detail.load} AU</li>
                  {detail.actual_load != null && <li className={cn(detail.actual_load > detail.load * 1.2 && "text-caution")}>Actual load: {Math.round(detail.actual_load)} AU</li>}
                </ul>
              )}
              {detail.content && (
                <div className="mt-3">
                  <p className="font-semibold">{detail.content.title}</p>
                  <ul className="text-ink-2 mt-1 space-y-1 text-sm">
                    {detail.content.items.map((it) => (
                      <li key={it.name}>
                        <span className="text-ink font-semibold">{it.name}</span>
                        {it.minutes != null && ` · ${it.minutes} min`}: {it.how}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {detail.kind === "strength" && (
                <Link to="/player/gym" className="text-pitch-300 mt-3 inline-block text-sm font-semibold underline">
                  See the gym exercises
                </Link>
              )}
            </Card>
          )}
        </div>
      </div>

      <p className="text-ink-2 text-center text-xs">Numbers show effort, from 1 (easy) to 10 (flat out). Tap or long-press a day for details.</p>
    </div>
  );
}
