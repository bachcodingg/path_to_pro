// Results and the match centre: every match of a competition, grouped by matchday (or the
// list of finals), and per match both teams' numbers side by side, the goals and a shot map.
import { Link, useParams } from "react-router-dom";
import { Crest } from "../shared/Club";
import { PageHeader } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { Card, ErrorNote, PageSkeleton, SectionTitle, cn, fmtDay } from "../shared/ui";
import { COMP_COLOR, usePro, type Competition } from "./context";

export interface MatchRow {
  id: number;
  date: string | null;
  week: number | null;
  home: string;
  away: string;
  home_goals: number;
  away_goals: number;
  home_shootout?: number;
  away_shootout?: number;
}
export interface MatchList {
  competition: Competition;
  matches: MatchRow[];
}

const day = (d: string | null, long = false) =>
  d ? fmtDay(d, long ? { weekday: "long", day: "numeric", month: "long", year: "numeric" } : { day: "numeric", month: "short", year: "numeric" }) : "";

function shootout(m: MatchRow): string | null {
  if (m.home_shootout == null || m.away_shootout == null) return null;
  const winner = m.home_shootout > m.away_shootout ? m.home : m.away;
  return `${winner} won ${Math.max(m.home_shootout, m.away_shootout)}-${Math.min(m.home_shootout, m.away_shootout)} on penalties`;
}

export function Results({ data }: { data: MatchList }) {
  const { comp } = usePro();
  const finals = data.competition.coverage === "finals";
  const groups = new Map<string, MatchRow[]>();
  for (const m of data.matches) {
    const key = finals ? "Finals" : m.week ? `Matchday ${m.week}` : day(m.date);
    groups.set(key, [...(groups.get(key) ?? []), m]);
  }
  return (
    <div className="max-w-4xl space-y-5">
      {[...groups].map(([title, list]) => (
        <section key={title}>
          <SectionTitle>{title}</SectionTitle>
          <Card className="divide-y divide-[color:var(--line)] p-0">
            {list.map((m) => (
              <Link
                key={m.id}
                to={`/pro/${comp}/matches/${m.id}`}
                aria-label={`${m.home} ${m.home_goals}-${m.away_goals} ${m.away}${m.date ? `, ${day(m.date)}` : ""}`}
                className="hover:bg-surface-2 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 px-4 py-2.5 transition-colors"
              >
                <span className="flex min-w-0 items-center justify-end gap-2 text-right font-semibold">
                  <span className="truncate">{m.home}</span>
                  <Crest name={m.home} size={26} />
                </span>
                <span className="flex flex-col items-center">
                  <span className="font-display num rounded-md bg-[#050f0a] px-2.5 py-0.5 text-lg font-bold text-white">
                    {m.home_goals} - {m.away_goals}
                  </span>
                  <span className="text-ink-2 mt-0.5 text-[11px]">{finals ? m.date?.slice(0, 4) : day(m.date)}</span>
                </span>
                <span className="flex min-w-0 items-center gap-2 font-semibold">
                  <Crest name={m.away} size={26} />
                  <span className="truncate">{m.away}</span>
                </span>
                {shootout(m) && <span className="text-ink-2 col-span-3 text-center text-xs">{shootout(m)}</span>}
              </Link>
            ))}
          </Card>
        </section>
      ))}
    </div>
  );
}

interface Stat {
  key: string;
  label: string;
  unit: string;
  digits: number;
  better: "high" | "low" | null;
  home: number | null;
  away: number | null;
}
interface Report extends MatchRow {
  competition: Competition;
  stats: Stat[];
  shot_columns: string[];
  shots: (string | number | boolean)[][];
}

// One match: counts are whole numbers; xG keeps two decimals
const fmt = (s: Stat, v: number | null) => (v == null ? "–" : s.unit === "%" ? `${v.toFixed(0)}%` : v.toFixed(s.key === "xg" ? 2 : 0));
// StatsBomb counts elapsed minutes (a goal after 50 seconds is minute 0); football says 1'
const clock = (minute: number) => `${minute + 1}'`;

export function MatchCentre() {
  const { matchId = "" } = useParams();
  const { comp, base } = usePro();
  const { data, error, loading, reload } = useApi<Report>(`${base}/matches/${encodeURIComponent(matchId)}`);
  if (loading && !data) return <PageSkeleton label="Loading the match" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const col = Object.fromEntries(data.shot_columns.map((c, i) => [c, i]));
  const shots = data.shots.map((s) => ({
    team: String(s[col.team]),
    x: Number(s[col.x]),
    y: Number(s[col.y]),
    xg: Number(s[col.xg]),
    outcome: String(s[col.outcome]),
    player: String(s[col.player]),
    minute: Number(s[col.minute]),
    type: String(s[col.type]),
  }));
  const goals = shots.filter((s) => s.outcome === "Goal");
  const so = shootout(data);
  return (
    <div className="space-y-5">
      <PageHeader
        accent={COMP_COLOR[comp]}
        eyebrow={
          <Link to={`/pro/${comp}?tab=results`} className="hover:underline">
            ← {data.competition.name} {data.competition.season}
            {data.week && data.competition.coverage !== "finals" ? ` · matchday ${data.week}` : ""}
          </Link>
        }
        title={
          <>
            <span className="sr-only">
              {data.home} {data.home_goals}-{data.away_goals} {data.away}
            </span>
            <span aria-hidden className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 md:gap-6">
              <span className="flex min-w-0 items-center justify-end gap-3 text-right">
                <span className="truncate text-2xl md:text-4xl">{data.home}</span>
                <Crest name={data.home} size={52} />
              </span>
              <span className="num rounded-lg bg-black/40 px-4 py-1 text-4xl md:text-6xl">
                {data.home_goals} - {data.away_goals}
              </span>
              <span className="flex min-w-0 items-center gap-3">
                <Crest name={data.away} size={52} />
                <span className="truncate text-2xl md:text-4xl">{data.away}</span>
              </span>
            </span>
          </>
        }
        subtitle={<span className="block text-center">{[day(data.date, true), so].filter(Boolean).join(" · ")}</span>}
      />

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="space-y-4">
          <section>
            <SectionTitle>Goals</SectionTitle>
            <Card className="p-0">
              {goals.length === 0 && <p className="text-ink-2 p-4 text-sm">No goals in open play or from penalties.</p>}
              <ul className="divide-y divide-[color:var(--line)]">
                {goals.map((g, i) => (
                  <li key={i} className={cn("flex items-center gap-3 px-4 py-2", g.team === data.away && "flex-row-reverse text-right")}>
                    <Crest name={g.team} size={22} />
                    <span className="font-display num w-10 text-lg font-bold">{clock(g.minute)}</span>
                    <span className="flex-1 font-semibold">
                      {g.player}
                      {g.type === "penalty" && <span className="text-ink-2 text-sm font-normal"> (pen.)</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
            <p className="text-ink-2 mt-1 text-xs">Own goals aren't shots, so they are in the score but not in this list.</p>
          </section>
          <section>
            <SectionTitle>Match stats</SectionTitle>
            <Card className="space-y-3">
              <div className="flex justify-between text-sm font-bold">
                <span className="flex items-center gap-2">
                  <Crest name={data.home} size={20} /> {data.home}
                </span>
                <span className="flex items-center gap-2">
                  {data.away} <Crest name={data.away} size={20} />
                </span>
              </div>
              {data.stats.map((s) => (
                <StatBar key={s.key} s={s} />
              ))}
            </Card>
          </section>
        </div>
        <section>
          <SectionTitle>Shot map</SectionTitle>
          <Card className="p-2">
            <MatchShotMap shots={shots} home={data.home} />
            <p className="text-ink-2 px-2 pt-2 text-xs">
              {data.home} attack to the right, {data.away} to the left. Bigger dot = better chance (xG); filled = goal.
            </p>
          </Card>
        </section>
      </div>
      <p className="text-ink-2 text-xs">
        Data: <a className="underline" href="https://github.com/statsbomb/open-data">StatsBomb Open Data</a>. Possession is the
        share of the match's passes.
      </p>
    </div>
  );
}

// Broadcast-style bar: each side's share of the two values, the better side highlighted
function StatBar({ s }: { s: Stat }) {
  const h = s.home ?? 0,
    a = s.away ?? 0;
  const total = h + a || 1;
  const better = s.better === "low" ? (h < a ? "home" : h > a ? "away" : null) : h > a ? "home" : h < a ? "away" : null;
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className={cn("num w-14 font-bold", better === "home" && "text-pitch-700")}>{fmt(s, s.home)}</span>
        <span className="text-ink-2 text-center text-xs font-semibold">{s.label}</span>
        <span className={cn("num w-14 text-right font-bold", better === "away" && "text-pitch-700")}>{fmt(s, s.away)}</span>
      </div>
      <div className="mt-1 flex h-2 gap-1" aria-hidden>
        <span className="bg-surface-2 flex flex-1 justify-end overflow-hidden rounded-full">
          <span className={cn("h-full rounded-full", better === "home" ? "bg-pitch-600" : "bg-draw")} style={{ width: `${(100 * h) / total}%` }} />
        </span>
        <span className="bg-surface-2 flex-1 overflow-hidden rounded-full">
          <span className={cn("block h-full rounded-full", better === "away" ? "bg-pitch-600" : "bg-draw")} style={{ width: `${(100 * a) / total}%` }} />
        </span>
      </div>
    </div>
  );
}

// Whole pitch, 120 x 80: the home team's shots at the right-hand goal, the away team's
// mirrored to the left
function MatchShotMap({ shots, home }: { shots: { team: string; x: number; y: number; xg: number; outcome: string; player: string; minute: number }[]; home: string }) {
  const line = { fill: "none", stroke: "rgb(255 255 255 / 0.7)", strokeWidth: 0.4 };
  return (
    <svg viewBox="-2 -2 124 84" className="w-full rounded-lg" role="img" aria-label={`Shot map: ${shots.length} shots`}>
      <rect x={-2} y={-2} width={124} height={84} fill="#1a6340" />
      <rect x={0} y={0} width={120} height={80} {...line} />
      <line x1={60} y1={0} x2={60} y2={80} {...line} />
      <circle cx={60} cy={40} r={10} {...line} />
      <rect x={0} y={18} width={18} height={44} {...line} />
      <rect x={102} y={18} width={18} height={44} {...line} />
      <rect x={0} y={30} width={6} height={20} {...line} />
      <rect x={114} y={30} width={6} height={20} {...line} />
      <rect x={-1.5} y={36} width={1.5} height={8} fill="#fff" />
      <rect x={120} y={36} width={1.5} height={8} fill="#fff" />
      {shots.map((s, i) => {
        const mine = s.team === home;
        const x = mine ? s.x : 120 - s.x,
          y = mine ? s.y : 80 - s.y;
        const goal = s.outcome === "Goal";
        return (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={1 + 4 * Math.sqrt(s.xg)}
            fill={goal ? (mine ? "#f6c344" : "#ffffff") : "transparent"}
            stroke={mine ? "#f6c344" : "#ffffff"}
            strokeWidth={0.5}
            opacity={goal ? 1 : 0.85}
          >
            <title>{`${s.player}, ${clock(s.minute)}: ${s.outcome} (xG ${s.xg.toFixed(2)})`}</title>
          </circle>
        );
      })}
    </svg>
  );
}
