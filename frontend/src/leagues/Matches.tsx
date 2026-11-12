// Results and the match centre: every match of a competition as a match card, a matchday at a
// time (or one club's season, or the list of finals), and per match a scoreboard, the goals in
// order, both teams' numbers side by side and a shot map.
import { BarChart3, ChevronLeft, ChevronRight, Crosshair, Timer } from "lucide-react";
import { useState, type CSSProperties } from "react";
import { Link, useParams } from "react-router-dom";
import { Crest } from "../shared/Club";
import { useApi } from "../shared/useApi";
import { ErrorNote, PageSkeleton, cn, fmtDay } from "../shared/ui";
import { COMP_COLOR, usePro, type Competition } from "./context";
import { FullPitch } from "./pitch";
import { Empty, Label, Panel } from "./ui";

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

// One match as the league sites show it: the two clubs under each other, the score on the right,
// the winner in bold
export function MatchCard({ m, meta }: { m: MatchRow; meta?: string }) {
  const { comp } = usePro();
  const so = shootout(m);
  const homeWon = m.home_goals > m.away_goals || (m.home_shootout ?? 0) > (m.away_shootout ?? 0);
  const awayWon = m.away_goals > m.home_goals || (m.away_shootout ?? 0) > (m.home_shootout ?? 0);
  return (
    <Link
      to={`/${comp}/matches/${m.id}`}
      aria-label={`${m.home} ${m.home_goals}-${m.away_goals} ${m.away}${m.date ? `, ${day(m.date)}` : ""}`}
      className="lg-panel hover:border-pitch-500 block transition-[border-color,box-shadow] hover:shadow-md"
    >
      <div className="flex items-center justify-between gap-2 px-3 pt-2">
        <Label>{meta ?? day(m.date)}</Label>
        <Label className="text-ink-2/80">{so ? "Pens" : "FT"}</Label>
      </div>
      <div className="space-y-1 px-3 pt-1.5 pb-2.5">
        <Side name={m.home} goals={m.home_goals} won={homeWon} lost={awayWon} />
        <Side name={m.away} goals={m.away_goals} won={awayWon} lost={homeWon} />
      </div>
      {so && <p className="text-ink-2 border-line bg-surface-2/60 border-t px-3 py-1.5 text-xs">{so}</p>}
    </Link>
  );
}

function Side({ name, goals, won, lost }: { name: string; goals: number; won: boolean; lost: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <Crest name={name} size={24} />
      <span className={cn("min-w-0 flex-1 truncate", won ? "font-extrabold" : lost ? "text-ink-2 font-semibold" : "font-semibold")}>{name}</span>
      <span className={cn("lg-score h-7 w-7 text-[1.05rem]", !won && "bg-surface-2 text-ink border-line border")}>{goals}</span>
    </div>
  );
}

const GRID = "grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4";

export function Results({ data }: { data: MatchList }) {
  const coverage = data.competition.coverage;
  const weeks = [...new Set(data.matches.map((m) => m.week).filter((w): w is number => w != null))].sort((a, b) => a - b);
  const clubs = [...new Set(data.matches.flatMap((m) => [m.home, m.away]))].sort((a, b) => a.localeCompare(b));
  const [week, setWeek] = useState<number | null>(null);
  const [club, setClub] = useState("");
  // Finals, and one club's season: every match on one page
  if (coverage !== "league" || weeks.length === 0)
    return (
      <div className={GRID}>
        {data.matches.map((m) => (
          <MatchCard key={m.id} m={m} meta={coverage === "finals" ? `Final ${m.date?.slice(0, 4) ?? ""}` : `${m.week ? `Matchday ${m.week} · ` : ""}${day(m.date)}`} />
        ))}
      </div>
    );
  const shownWeek = week ?? weeks[weeks.length - 1];
  const at = weeks.indexOf(shownWeek);
  const byDate = (a: MatchRow, b: MatchRow) => (a.date ?? "").localeCompare(b.date ?? "") || a.id - b.id;
  const list = club
    ? data.matches.filter((m) => m.home === club || m.away === club).sort((a, b) => (a.week ?? 0) - (b.week ?? 0) || byDate(a, b))
    : data.matches.filter((m) => m.week === shownWeek).sort(byDate);
  const field = "bg-surface border-line h-11 rounded-md border px-3 text-sm font-bold md:h-10";
  const step = "tap border-line bg-surface hover:bg-surface-2 flex items-center justify-center rounded-md border disabled:opacity-40 md:!min-h-10 md:!min-w-10";
  return (
    <div className="space-y-4">
      <div className="lg-panel flex flex-wrap items-center justify-between gap-3 px-3 py-2.5">
        <div className={cn("flex items-center gap-2", club && "opacity-50")}>
          <button className={step} aria-label="Previous matchday" disabled={!!club || at <= 0} onClick={() => setWeek(weeks[at - 1])}>
            <ChevronLeft className="h-5 w-5" aria-hidden />
          </button>
          <select aria-label="Matchday" className={field} disabled={!!club} value={shownWeek} onChange={(e) => setWeek(Number(e.target.value))}>
            {weeks.map((w) => (
              <option key={w} value={w}>
                Matchday {w}
              </option>
            ))}
          </select>
          <button className={step} aria-label="Next matchday" disabled={!!club || at >= weeks.length - 1} onClick={() => setWeek(weeks[at + 1])}>
            <ChevronRight className="h-5 w-5" aria-hidden />
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm font-bold">
          <span className="text-ink-2">Club</span>
          <select className={field} value={club} onChange={(e) => setClub(e.target.value)}>
            <option value="">All clubs</option>
            {clubs.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>
      <h2 className="font-display flex items-baseline gap-3 text-xl font-extrabold">
        {club ? `${club}: every match` : `Matchday ${shownWeek}`}
        <span className="lg-label">{list.length} matches</span>
      </h2>
      {list.length ? (
        <div className={GRID}>
          {list.map((m) => (
            <MatchCard key={m.id} m={m} meta={club ? `Matchday ${m.week} · ${day(m.date)}` : undefined} />
          ))}
        </div>
      ) : (
        <Empty>No matches.</Empty>
      )}
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
interface MatchShot {
  team: string;
  x: number;
  y: number;
  xg: number;
  outcome: string;
  player: string;
  minute: number;
  type: string;
}

// One match: counts are whole numbers; xG keeps two decimals
const fmt = (s: Stat, v: number | null) => (v == null ? "–" : s.unit === "%" ? `${v.toFixed(0)}%` : v.toFixed(s.key === "xg" ? 2 : 0));
// StatsBomb counts elapsed minutes (a goal after 50 seconds is minute 0); football says 1'
const clock = (minute: number) => `${minute + 1}'`;

// The numbers in the order a match report reads them
const STAT_GROUPS: [string, string[]][] = [
  ["Attack", ["xg", "shots", "on_target", "box_passes", "final_third", "crosses"]],
  ["Passing", ["passes", "pass_acc"]],
  ["Duels", ["aerial_win", "dribble_success", "tackle_success"]],
  ["Defending", ["interceptions", "pressures"]],
  ["Discipline", ["fouls", "yellow", "red"]],
];

export function MatchCentre() {
  const { matchId = "" } = useParams();
  const { comp, base } = usePro();
  const { data, error, loading, reload } = useApi<Report>(`${base}/matches/${encodeURIComponent(matchId)}`);
  if (loading && !data) return <PageSkeleton label="Loading the match" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const col = Object.fromEntries(data.shot_columns.map((c, i) => [c, i]));
  const shots: MatchShot[] = data.shots.map((s) => ({
    team: String(s[col.team]),
    x: Number(s[col.x]),
    y: Number(s[col.y]),
    xg: Number(s[col.xg]),
    outcome: String(s[col.outcome]),
    player: String(s[col.player]),
    minute: Number(s[col.minute]),
    type: String(s[col.type]),
  }));
  const goals = shots.filter((s) => s.outcome === "Goal").sort((a, b) => a.minute - b.minute);
  const so = shootout(data);
  const by = Object.fromEntries(data.stats.map((s) => [s.key, s]));
  const grouped = new Set(STAT_GROUPS.flatMap(([, keys]) => keys).concat("possession"));
  const groups = [...STAT_GROUPS, ["More", data.stats.filter((s) => !grouped.has(s.key)).map((s) => s.key)] as [string, string[]]]
    .map(([title, keys]) => [title, keys.filter((k) => by[k])] as const)
    .filter(([, keys]) => keys.length);
  const finals = data.competition.coverage === "finals";
  return (
    <div className="space-y-4 md:space-y-5">
      <header
        style={{ "--hero-glow": `${COMP_COLOR[comp] ?? "#1597d0"}66` } as CSSProperties}
        className="hero match-hero dark -mx-4 -mt-4 px-4 pt-4 pb-6 md:-mx-6 md:-mt-6 md:px-6 md:pt-6 md:pb-8"
      >
        <p className="text-sm font-bold">
          <Link to={`/${comp}?tab=results`} className="hover:underline">
            ← {data.competition.name} {data.competition.season}
            {data.week && !finals ? ` · matchday ${data.week}` : ""}
          </Link>
        </p>
        <h1 className="sr-only">
          {data.home} {data.home_goals}-{data.away_goals} {data.away}
        </h1>
        <div className="mx-auto mt-3 grid max-w-4xl grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-start gap-3 md:mt-1 md:gap-8" aria-hidden>
          <Club name={data.home} side="Home" />
          <div className="flex flex-col items-center pt-1 md:pt-3">
            <Label className="text-white/85">{finals ? "Final" : "Full time"}</Label>
            <div className="mt-1.5 flex items-center gap-1.5 md:gap-2">
              <span className="lg-score h-14 w-12 bg-black/45 text-[2.6rem] ring-1 ring-white/20 md:h-20 md:w-[4.25rem] md:text-[4rem]">{data.home_goals}</span>
              <span className="lg-score h-14 w-12 bg-black/45 text-[2.6rem] ring-1 ring-white/20 md:h-20 md:w-[4.25rem] md:text-[4rem]">{data.away_goals}</span>
            </div>
          </div>
          <Club name={data.away} side="Away" />
          <Scorers goals={goals.filter((g) => g.team === data.home)} className="text-right" />
          <span />
          <Scorers goals={goals.filter((g) => g.team === data.away)} />
        </div>
        <p className="mt-4 text-center text-sm font-semibold text-white">{[day(data.date, true), so].filter(Boolean).join(" · ")}</p>
      </header>

      <div className="grid items-start gap-4 md:gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <div className="space-y-4 md:space-y-5">
          <Panel title="Goals" icon={Timer} bodyClassName="p-0">
            {goals.length === 0 ? (
              <p className="text-ink-2 p-4 text-sm">No goals in open play or from penalties.</p>
            ) : (
              <ul className="relative py-1">
                <span className="bg-line absolute inset-y-3 left-1/2 w-px -translate-x-1/2" aria-hidden />
                {goals.map((g, i) => {
                  const home = g.team === data.home;
                  const who = (
                    <span className={cn("flex min-w-0 items-center gap-2", home && "flex-row-reverse text-right")}>
                      <Crest name={g.team} size={20} />
                      <span className="min-w-0 truncate font-bold">
                        {g.player}
                        {g.type === "penalty" && <span className="text-ink-2 text-sm font-normal"> (pen.)</span>}
                      </span>
                    </span>
                  );
                  return (
                    <li key={i} className="relative grid grid-cols-[minmax(0,1fr)_3.25rem_minmax(0,1fr)] items-center gap-2 px-3 py-1.5">
                      {home ? who : <span />}
                      <span className="lg-score num z-[1] h-7 justify-self-center px-1.5 text-sm" style={{ background: home ? "var(--color-home)" : "var(--color-away)" }}>
                        {clock(g.minute)}
                      </span>
                      {home ? <span /> : who}
                    </li>
                  );
                })}
              </ul>
            )}
            <p className="text-ink-2 border-line bg-surface-2/60 border-t px-4 py-2 text-xs">Own goals aren't shots, so they are in the score but not in this list.</p>
          </Panel>

          <Panel title="Match stats" icon={BarChart3} bodyClassName="p-0">
            <div className="border-line flex items-center justify-between gap-3 border-b px-4 py-2.5 text-sm font-extrabold">
              <span className="flex min-w-0 items-center gap-2">
                <Crest name={data.home} size={22} /> <span className="truncate">{data.home}</span>
                <i className="bg-home h-2.5 w-2.5 shrink-0 rounded-full" aria-hidden />
              </span>
              <span className="flex min-w-0 items-center gap-2">
                <i className="bg-away h-2.5 w-2.5 shrink-0 rounded-full" aria-hidden />
                <span className="truncate">{data.away}</span> <Crest name={data.away} size={22} />
              </span>
            </div>
            {by.possession && <Possession s={by.possession} />}
            {groups.map(([title, keys]) => (
              <div key={title} className="border-line border-t px-4 pt-3 pb-4 first:border-t-0">
                <Label className="mb-2 block text-center">{title}</Label>
                <div className="space-y-3">
                  {keys.map((k) => (
                    <StatBar key={k} s={by[k]} />
                  ))}
                </div>
              </div>
            ))}
          </Panel>
        </div>

        <Panel title="Shot map" icon={Crosshair} bodyClassName="p-3" className="lg:sticky lg:top-28">
          <div className="mb-3 grid grid-cols-2 gap-3">
            <ShotTotals name={data.home} shots={shots} tone="var(--color-home)" />
            <ShotTotals name={data.away} shots={shots} tone="var(--color-away)" right />
          </div>
          <MatchShotMap shots={shots} home={data.home} />
          <p className="text-ink-2 px-1 pt-2 text-xs">
            {data.home} attack to the right, {data.away} to the left. Bigger dot = better chance (xG); filled = goal.
          </p>
        </Panel>
      </div>
      <p className="text-ink-2 text-xs">
        Data: <a className="underline" href="https://github.com/statsbomb/open-data">StatsBomb Open Data</a>. Possession is the
        share of the match's passes.
      </p>
    </div>
  );
}

function Club({ name, side }: { name: string; side: string }) {
  return (
    <div className="flex min-w-0 flex-col items-center gap-2 text-center">
      <Crest name={name} size={76} className="hidden drop-shadow-lg md:block" />
      <Crest name={name} size={52} className="drop-shadow-lg md:hidden" />
      <span className="font-display max-w-full text-lg leading-tight font-extrabold break-words md:text-3xl">{name}</span>
      <Label className="text-white/80">{side}</Label>
    </div>
  );
}

// Under each club on the scoreboard: who scored, and when
function Scorers({ goals, className }: { goals: MatchShot[]; className?: string }) {
  const byPlayer = new Map<string, string[]>();
  for (const g of goals) byPlayer.set(g.player, [...(byPlayer.get(g.player) ?? []), `${clock(g.minute)}${g.type === "penalty" ? " (pen.)" : ""}`]);
  return (
    <div className={cn("space-y-0.5 text-xs text-white/95 md:text-sm", className)}>
      {[...byPlayer].map(([player, minutes]) => (
        <p key={player}>
          <span className="font-bold">{player}</span> <span className="num">{minutes.join(", ")}</span>
        </p>
      ))}
    </div>
  );
}

// One bar shared between the two teams
function Possession({ s }: { s: Stat }) {
  const h = s.home ?? 50,
    a = s.away ?? 50;
  const total = h + a || 1;
  return (
    <div className="px-4 pt-3 pb-4">
      <Label className="mb-2 block text-center">{s.label}</Label>
      <div className="flex h-9 overflow-hidden rounded-md text-white" role="img" aria-label={`${s.label}: ${fmt(s, s.home)} to ${fmt(s, s.away)}`}>
        <span className="bg-home font-display num flex items-center pl-3 text-lg font-extrabold" style={{ width: `${(100 * h) / total}%` }}>
          {fmt(s, s.home)}
        </span>
        <span className="bg-away font-display num flex flex-1 items-center justify-end pr-3 text-lg font-extrabold">{fmt(s, s.away)}</span>
      </div>
    </div>
  );
}

// Broadcast-style bar: the two values grow from the middle, the better side at full strength
function StatBar({ s }: { s: Stat }) {
  const h = s.home ?? 0,
    a = s.away ?? 0;
  const total = h + a || 1;
  const better = s.better === "low" ? (h < a ? "home" : h > a ? "away" : null) : s.better === "high" ? (h > a ? "home" : h < a ? "away" : null) : null;
  const dim = (side: "home" | "away") => (s.better && better !== side ? "opacity-40" : undefined);
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className={cn("num w-14", better === "home" ? "text-base font-extrabold" : "font-semibold")}>{fmt(s, s.home)}</span>
        <span className="text-ink-2 text-center text-[13px] font-semibold">{s.label}</span>
        <span className={cn("num w-14 text-right", better === "away" ? "text-base font-extrabold" : "font-semibold")}>{fmt(s, s.away)}</span>
      </div>
      <div className="mt-1 flex h-2 gap-0.5" aria-hidden>
        <span className="bg-surface-2 flex flex-1 justify-end overflow-hidden rounded-l-full">
          <span className={cn("bg-home h-full rounded-l-full", dim("home"))} style={{ width: `${(100 * h) / total}%` }} />
        </span>
        <span className="bg-surface-2 flex-1 overflow-hidden rounded-r-full">
          <span className={cn("bg-away block h-full rounded-r-full", dim("away"))} style={{ width: `${(100 * a) / total}%` }} />
        </span>
      </div>
    </div>
  );
}

function ShotTotals({ name, shots, tone, right }: { name: string; shots: MatchShot[]; tone: string; right?: boolean }) {
  const mine = shots.filter((s) => s.team === name);
  return (
    <div className={cn("border-line rounded-md border px-3 py-2", right && "text-right")} style={{ [right ? "borderRightWidth" : "borderLeftWidth"]: 4, [right ? "borderRightColor" : "borderLeftColor"]: tone }}>
      <p className="truncate text-sm font-bold">{name}</p>
      <p className="num text-ink-2 text-xs">
        <b className="font-display text-ink text-xl font-extrabold">{mine.reduce((a, s) => a + s.xg, 0).toFixed(2)}</b> xG · {mine.length} shots ·{" "}
        {mine.filter((s) => s.outcome === "Goal").length} scored
      </p>
    </div>
  );
}

// Whole pitch, 120 x 80: the home team's shots at the right-hand goal, the away team's
// mirrored to the left
function MatchShotMap({ shots, home }: { shots: MatchShot[]; home: string }) {
  return (
    <FullPitch label={`Shot map: ${shots.length} shots`}>
      {shots
        .slice()
        .sort((a, b) => b.xg - a.xg)
        .map((s, i) => {
          const mine = s.team === home;
          const x = mine ? s.x : 120 - s.x,
            y = mine ? s.y : 80 - s.y;
          const goal = s.outcome === "Goal";
          const colour = mine ? "#5ad1ff" : "#ffc93c";
          return (
            <circle key={i} cx={x} cy={y} r={1 + 4 * Math.sqrt(s.xg)} fill={colour} fillOpacity={goal ? 1 : 0.14} stroke={goal ? "#0c1a3d" : colour} strokeWidth={goal ? 0.35 : 0.5}>
              <title>{`${s.player}, ${clock(s.minute)}: ${s.outcome} (xG ${s.xg.toFixed(2)})`}</title>
            </circle>
          );
        })}
    </FullPitch>
  );
}
