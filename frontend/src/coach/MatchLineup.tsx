// Match line-up with ratings: the starting XI in formation on the pitch (formation read
// from the players' positions), substitutes who came on, and the unused bench.
import { Star } from "lucide-react";
import { useState } from "react";
import { Ball, Pitch } from "../shared/Pitch";
import { Breakdown, POSITION_LABEL, RatingBadge, ratingBand } from "../shared/Rating";
import type { BreakdownItem, Position, RatingBand } from "../shared/types";
import { Card, Chip, SectionTitle, cn } from "../shared/ui";

export interface LineupRow {
  player: { id: string; name: string; position: Position };
  minutes: number;
  started: boolean;
  position: Position;
  stats: Record<string, number | string>;
  rating: number | null;
  rating_source: "stats" | "diary" | null;
  breakdown: BreakdownItem[];
  self_rating: number | null;
}

const HEX: Record<RatingBand, string> = { elite: "#2a6fdb", good: "#1fa05a", fair: "#a3c639", average: "#f0a020", poor: "#e5484d" };
const LINE_Y = { gk: 138, def: 112, mid: 80, fwd: 42 };

function line(pos: Position): keyof typeof LINE_Y {
  return pos === "goalkeeper" ? "gk" : pos === "centre_back" || pos === "full_back" ? "def" : pos === "midfielder" ? "mid" : "fwd";
}

/** Order a line left to right: wide players (full-backs, wingers) on the outside. */
function order(rows: LineupRow[]): LineupRow[] {
  const wide = rows.filter((r) => r.position === "full_back" || r.position === "winger");
  const central = rows.filter((r) => !wide.includes(r));
  if (!wide.length) return central;
  return [wide[0], ...central, ...wide.slice(1)];
}

export function lineup(rows: LineupRow[]) {
  const played = rows.filter((r) => r.minutes > 0);
  let starters = played.filter((r) => r.started);
  if (starters.length !== 11) {
    // incomplete data: the 11 with the most minutes
    starters = [...played].sort((a, b) => b.minutes - a.minutes).slice(0, 11);
  }
  const subs = played.filter((r) => !starters.includes(r)).sort((a, b) => b.minutes - a.minutes);
  const unused = rows.filter((r) => r.minutes === 0);
  const lines = { gk: [] as LineupRow[], def: [] as LineupRow[], mid: [] as LineupRow[], fwd: [] as LineupRow[] };
  for (const r of starters) lines[line(r.position)].push(r);
  const placed = (Object.keys(lines) as (keyof typeof lines)[]).flatMap((k) => {
    const ordered = order(lines[k]);
    return ordered.map((r, i) => ({ row: r, x: ((i + 1) * 100) / (ordered.length + 1), y: LINE_Y[k] }));
  });
  const formation = [lines.def.length, lines.mid.length, lines.fwd.length].filter((n) => n > 0).join("-");
  const rated = played.filter((r) => r.rating != null);
  const potm = rated.length ? rated.reduce((a, b) => ((b.rating ?? 0) > (a.rating ?? 0) ? b : a)) : null;
  const teamAvg = rated.length ? rated.reduce((s, r) => s + (r.rating ?? 0), 0) / rated.length : null;
  return { placed, subs, unused, formation, potm, teamAvg };
}

function short(name: string): string {
  const [first, ...rest] = name.split(" ");
  return rest.length ? `${first} ${rest.join(" ")}` : first;
}

export function MatchLineup({ rows }: { rows: LineupRow[] }) {
  const { placed, subs, unused, formation, potm, teamAvg } = lineup(rows);
  const [selected, setSelected] = useState<string | null>(potm?.player.id ?? null);
  const sel = rows.find((r) => r.player.id === selected);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Card className="p-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Chip>{formation || "–"}</Chip>
          <span className="text-ink-2 text-sm">Team rating</span>
          <RatingBadge value={teamAvg == null ? null : Math.round(teamAvg * 10) / 10} />
          {potm && (
            <Chip tone="green">
              <Star className="mr-1 h-3.5 w-3.5" aria-hidden /> {potm.player.name} {potm.rating?.toFixed(1)}
            </Chip>
          )}
        </div>
        <Pitch label={`Starting line-up, ${formation}, with match ratings`} className="mx-auto w-full max-w-xl">
          {placed.map(({ row, x, y }) => {
            const b = ratingBand(row.rating);
            const goals = Number(row.stats.goals ?? 0);
            const assists = Number(row.stats.assists ?? 0);
            const isPotm = potm?.player.id === row.player.id;
            return (
              <g
                key={row.player.id}
                transform={`translate(${x} ${y})`}
                onClick={() => setSelected(row.player.id)}
                style={{ cursor: "pointer" }}
                role="button"
                tabIndex={0}
                aria-label={`${row.player.name}, ${POSITION_LABEL[row.position]}, rating ${row.rating?.toFixed(1) ?? "none"}`}
                onKeyDown={(e) => e.key === "Enter" && setSelected(row.player.id)}
              >
                <circle r={5.2} fill={selected === row.player.id ? "#fff" : "#0f2219"} stroke="#fff" strokeWidth={0.6} />
                <text y={1.8} textAnchor="middle" fontSize={4.6} fontWeight={800} fill={selected === row.player.id ? "#0f2219" : "#fff"}>
                  {row.player.name[0]}
                </text>
                <rect x={2.5} y={-10} width={10} height={5.6} rx={1.4} fill={b ? HEX[b] : "#667"} />
                <text x={7.5} y={-5.8} textAnchor="middle" fontSize={3.8} fontWeight={800} fill="#fff">
                  {row.rating?.toFixed(1) ?? "–"}
                </text>
                {isPotm && (
                  <text x={-10} y={-5} fontSize={5} fill="#f0c020">
                    ★
                  </text>
                )}
                {goals > 0 && <Ball x={-6.5} y={3} r={1.9} />}
                {goals > 1 && (
                  <text x={-11.5} y={4.4} fontSize={3.4} fill="#fff" fontWeight={700}>
                    {goals}
                  </text>
                )}
                {assists > 0 && (
                  <text x={5.5} y={4.5} fontSize={3.6} fill="#7ee0a8" fontWeight={800}>
                    A{assists > 1 ? assists : ""}
                  </text>
                )}
                <text y={10} textAnchor="middle" fontSize={3.6} fill="#fff" fontWeight={600}>
                  {short(row.player.name)}
                </text>
                {row.minutes < 85 && (
                  <text y={14} textAnchor="middle" fontSize={3} fill="rgba(255,255,255,0.75)">
                    off {row.minutes}'
                  </text>
                )}
              </g>
            );
          })}
        </Pitch>
      </Card>

      <div className="space-y-4">
        {sel && (
          <Card aria-label="Selected player rating">
            <div className="mb-2 flex items-center gap-3">
              <RatingBadge value={sel.rating} size="lg" estimate={sel.rating_source === "diary"} />
              <div>
                <p className="font-bold">{sel.player.name}</p>
                <p className="text-ink-2 text-xs">
                  {POSITION_LABEL[sel.position]} · {sel.minutes}' {sel.started ? "· started" : "· substitute"}
                  {sel.self_rating != null && ` · own rating ${sel.self_rating}/10`}
                </p>
              </div>
            </div>
            <Breakdown items={sel.breakdown} />
          </Card>
        )}
        <section>
          <SectionTitle>Substitutes</SectionTitle>
          <Card className="divide-[color:var(--line)] divide-y p-0">
            {subs.length === 0 && <p className="text-ink-2 p-3 text-sm">No substitutes came on.</p>}
            {subs.map((r) => (
              <BenchRow key={r.player.id} r={r} active={selected === r.player.id} onClick={() => setSelected(r.player.id)} />
            ))}
          </Card>
        </section>
        {unused.length > 0 && (
          <section>
            <SectionTitle>Did not play</SectionTitle>
            <Card className="text-ink-2 text-sm">{unused.map((r) => r.player.name).join(", ")}</Card>
          </section>
        )}
      </div>
    </div>
  );
}

function BenchRow({ r, active, onClick }: { r: LineupRow; active: boolean; onClick: () => void }) {
  const goals = Number(r.stats.goals ?? 0),
    assists = Number(r.stats.assists ?? 0);
  return (
    <button className={cn("tap flex w-full items-center gap-3 px-3 py-2 text-left", active && "bg-surface-2")} onClick={onClick}>
      <RatingBadge value={r.rating} size="sm" />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{r.player.name}</span>
        <span className="text-ink-2 text-xs">
          {POSITION_LABEL[r.position]} · on for {r.minutes}'
          {goals > 0 && ` · ${goals}G`}
          {assists > 0 && ` · ${assists}A`}
        </span>
      </span>
    </button>
  );
}
