// "Line-up readiness": next match formation, each dot coloured by readiness.
// Drag a bench player onto a position (or select + click) to compare/swap.
import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { Crest } from "../shared/Club";
import { PageHeader } from "../shared/PageHeader";
import { Pitch } from "../shared/Pitch";
import type { Band } from "../shared/types";
import { useApi } from "../shared/useApi";
import { BandBadge, Card, Chip, ErrorNote, Spinner, cn, fmtDay } from "../shared/ui";

interface LineupPlayer {
  id: string;
  name: string;
  readiness: number | null;
  band: Band | null;
  flags: string[];
  phv: boolean;
}
interface Lineup {
  match: { date: string; opponent: string; competition: string | null } | null;
  players: LineupPlayer[];
}

// 4-3-3 on a 100 x 150 pitch, own goal at the bottom
const SLOTS = [
  { x: 50, y: 134, pos: "GK" },
  { x: 15, y: 108, pos: "LB" },
  { x: 36, y: 113, pos: "CB" },
  { x: 64, y: 113, pos: "CB" },
  { x: 85, y: 108, pos: "RB" },
  { x: 28, y: 85, pos: "CM" },
  { x: 50, y: 92, pos: "DM" },
  { x: 72, y: 85, pos: "CM" },
  { x: 18, y: 45, pos: "LW" },
  { x: 50, y: 38, pos: "ST" },
  { x: 82, y: 45, pos: "RW" },
];
// Pain and red readiness are for staff, not for the line-up: shown as an alert
const isAlarm = (flag: string) => /pain|red/i.test(flag);
const FILL: Record<Band, string> = { green: "#2f7fe0", amber: "#e3a008", red: "#ea6a12" };

export function TacticsBoard() {
  const { data, error, loading, reload } = useApi<Lineup>("/api/coach/lineup");
  const [xi, setXi] = useState<string[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [hover, setHover] = useState<LineupPlayer | null>(null);

  useEffect(() => {
    if (data && !xi.length) setXi(data.players.slice(0, 11).map((p) => p.id));
  }, [data, xi.length]);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  const byId = Object.fromEntries(data.players.map((p) => [p.id, p]));
  const bench = data.players.filter((p) => !xi.includes(p.id));
  const avg = (ids: string[]) => {
    const v = ids.map((i) => byId[i]?.readiness).filter((x): x is number => x != null);
    return v.length ? Math.round(v.reduce((a, b) => a + b, 0) / v.length) : null;
  };

  function place(slot: number, playerId: string) {
    setXi((cur) => {
      const next = [...cur];
      const from = next.indexOf(playerId);
      if (from >= 0) [next[from], next[slot]] = [next[slot], next[from]];
      else next[slot] = playerId;
      return next;
    });
    setPicked(null);
  }

  return (
    <div className="space-y-4">
      {/* Next-fixture header, as on a match preview: opponent badge, date, the XI's readiness */}
      <PageHeader
        eyebrow="Squad"
        title="Tactics board"
        subtitle="Line-up readiness: drag a bench player onto a position (or select, then click) to see how ready the starting XI is."
        bottom={
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 pb-5">
            {data.match ? (
              <span className="flex items-center gap-3">
                <Crest name="PathToPro Academy" size={36} />
                <span className="font-display text-xl font-bold uppercase">vs</span>
                <Crest name={data.match.opponent} size={36} />
                <span>
                  <span className="block font-bold">Next: {data.match.opponent}</span>
                  <span className="text-sm text-white/75">
                    {data.match.competition ?? "Match"} · {fmtDay(data.match.date, { weekday: "long", day: "numeric", month: "short" })}
                  </span>
                </span>
              </span>
            ) : (
              <span className="text-white/75">No upcoming match</span>
            )}
            <span className="md:ml-auto">
              <span className="font-display text-4xl leading-none font-bold">{avg(xi) ?? "–"}</span>
              <span className="ml-2 text-sm text-white/75">starting XI average readiness</span>
            </span>
          </div>
        }
      />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_1fr]">
        <Card className="p-2">
          <Pitch label="Formation" className="w-full">
            {SLOTS.map((s, i) => {
              const p = byId[xi[i]];
              return (
                <g
                  key={i}
                  transform={`translate(${s.x} ${s.y})`}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => place(i, e.dataTransfer.getData("text/plain"))}
                  onClick={() => (picked ? place(i, picked) : setHover(p ?? null))}
                  onMouseEnter={() => setHover(p ?? null)}
                  style={{ cursor: "pointer" }}
                  role="button"
                  tabIndex={0}
                  aria-label={`${s.pos}: ${p?.name ?? "empty"}, readiness ${p?.readiness ?? "unknown"}`}
                  onKeyDown={(e) => e.key === "Enter" && picked && place(i, picked)}
                >
                  <circle r={6.5} fill={p?.band ? FILL[p.band] : "#6b7f74"} stroke={p?.phv ? "#e3a008" : "#fff"} strokeWidth={p?.phv ? 1.6 : 0.8} />
                  <text y={2} textAnchor="middle" fontSize={4.5} fontWeight={800} fill="#fff">
                    {p?.readiness != null ? Math.round(p.readiness) : "–"}
                  </text>
                  <text y={11} textAnchor="middle" fontSize={3.8} fill="#fff" fontWeight={600}>
                    {p?.name.split(" ")[0] ?? s.pos}
                  </text>
                </g>
              );
            })}
          </Pitch>
        </Card>
        <div className="space-y-3">
          {hover && (
            <Card className={cn(hover.flags.some(isAlarm) && "border-l-ready-red border-l-4")}>
              <div className="flex items-center justify-between">
                <p className="flex items-center gap-2 font-bold">
                  {hover.flags.some(isAlarm) && <AlertTriangle className="text-ready-red h-4 w-4" aria-label="Needs attention" />}
                  {hover.name}
                </p>
                <BandBadge band={hover.band} score={hover.readiness} />
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {hover.flags.length ? (
                  hover.flags.map((f) => (
                    <Chip key={f} tone={isAlarm(f) ? "red" : "amber"}>
                      {f}
                    </Chip>
                  ))
                ) : (
                  <span className="text-ink-2 text-sm">No flags</span>
                )}
              </div>
            </Card>
          )}
          <Card>
            <p className="mb-2 font-bold">Bench</p>
            <p className="text-ink-2 mb-2 text-xs">Drag a player onto a position, or select one and click a position.</p>
            <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
              {bench.map((p) => (
                <li key={p.id}>
                  <button
                    draggable
                    onDragStart={(e) => e.dataTransfer.setData("text/plain", p.id)}
                    onClick={() => setPicked(picked === p.id ? null : p.id)}
                    onMouseEnter={() => setHover(p)}
                    className={cn("tap border-line flex w-full items-center justify-between rounded-xl border px-3", picked === p.id && "ring-pitch-400 ring-2")}
                    aria-pressed={picked === p.id}
                  >
                    <span className="font-medium">
                      {p.name}
                      {p.phv && <span className="text-ready-amber ml-1 text-xs">growth</span>}
                    </span>
                    <BandBadge band={p.band} score={p.readiness} />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
