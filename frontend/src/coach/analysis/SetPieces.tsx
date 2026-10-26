// Team analysis, set pieces tab: corners for and against, penalties and direct free kicks.
import { useState } from "react";
import { useApi } from "../../shared/useApi";
import { Card, Chip, ErrorNote, SectionTitle, Spinner, cn } from "../../shared/ui";

export interface Source {
  source: string;
  source_url: string;
  competition: string;
  season: string;
  matches: number;
}
export interface TeamRow {
  id: string;
  name: string;
  matches: number;
  corners: number;
  penalties: number;
}
interface Share {
  key: string;
  label: string;
  n: number;
  pct: number | null;
  lo: number;
  hi: number;
  league_pct: number | null;
  flag: "more" | "less" | null;
}
interface Rate {
  n: number;
  k: number;
  pct: number | null;
  league_pct: number | null;
  flag: "more" | "less" | null;
}
interface CornerBlock {
  total: number;
  per_match: number;
  league_per_match: number | null;
  sides: Record<Side, number>;
  zones: Share[];
  technique: Share[];
  shot: Rate;
  goals: number;
  xg_per_corner: number;
  league_xg_per_corner: number | null;
}
interface Kick {
  taker: string;
  foot: string;
  y: number;
  z: number | null;
  third: "left" | "centre" | "right";
  outcome: string;
  opp: string;
  minute?: number;
  xg?: number;
}
interface KickBlock {
  total: number;
  scored: number;
  on_target: number;
  conversion: Rate;
  placement: Share[];
  height: Share[];
  kicks: Kick[];
  takers: { name: string; n: number; scored: number; foot: string; left: number; centre: number; right: number }[];
}
type Side = "L" | "R";
interface Profile extends Source {
  id: string;
  team: string;
  team_matches: number;
  min_n: number;
  corners: CornerBlock;
  corners_against: CornerBlock;
  corner_takers: {
    name: string;
    n: number;
    share_pct: number;
    foot: string;
    sides: Record<Side, number>;
    technique: Record<string, number>;
    main_zone: string;
    shots: number;
    goals: number;
  }[];
  corner_points: [number, number, Side, string, "goal" | "shot" | "none"][];
  penalties: KickBlock;
  free_kicks: KickBlock;
  notes: string[];
}

const ZONE_SHORT: Record<string, string> = {
  short: "Short",
  near_post: "Near post",
  six_yard: "Six-yard, central",
  penalty_spot: "Penalty spot",
  far_post: "Far post",
  edge: "Edge of box",
};
const FOOT: Record<string, string> = { R: "Right", L: "Left", other: "Other" };
const RESULT_COLOUR = { goal: "#e3a008", shot: "#2f7fe0", none: "rgba(255,255,255,0.6)" };
export const pct = (x: number | null | undefined) => (x == null ? "–" : `${Math.round(x)}%`);

export function SetPieces({ teamId }: { teamId: string }) {
  const { data, error, loading, reload } = useApi<Profile>(`/api/coach/analysis/teams/${encodeURIComponent(teamId)}`);
  if (loading && !data) return <Spinner label="Reading match events" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  return <TeamView p={data} />;
}

function TeamView({ p }: { p: Profile }) {
  const c = p.corners;
  return (
    <>
      <Card>
        <SectionTitle>Scouting notes</SectionTitle>
        {p.notes.length ? (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {p.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        ) : (
          <p className="text-ink-2 text-sm">No set-piece habit stands out from the rest of the league.</p>
        )}
      </Card>

      <section>
        <SectionTitle>Attacking corners</SectionTitle>
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Card className="self-start">
            <CornerMap points={p.corner_points} />
          </Card>
          <div className="space-y-4">
            <Stats
              items={[
                ["Corners a match", c.per_match.toFixed(1), c.league_per_match?.toFixed(1)],
                ["End in a shot (15 s)", pct(c.shot.pct), pct(c.shot.league_pct)],
                ["xG per corner", c.xg_per_corner.toFixed(3), c.league_xg_per_corner?.toFixed(3)],
                ["Goals", String(c.goals), undefined],
              ]}
              foot={`${c.total} corners in ${p.team_matches} matches · ${c.sides.L} from the left, ${c.sides.R} from the right`}
            />
            <Card>
              <h3 className="mb-2 font-bold">Where the ball goes</h3>
              <ShareBars rows={c.zones} labels={ZONE_SHORT} minN={p.min_n} />
            </Card>
            <Card>
              <h3 className="mb-2 font-bold">Delivery</h3>
              <ShareBars rows={c.technique.filter((t) => t.n > 0)} minN={p.min_n} />
            </Card>
          </div>
        </div>
      </section>

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <caption className="p-3 text-left font-bold">Corner takers</caption>
          <thead className="text-ink-2 text-left">
            <tr>
              <th className="p-3">Player</th>
              <th className="p-3">Corners</th>
              <th className="p-3">Foot</th>
              <th className="p-3">Left / right side</th>
              <th className="p-3">In / out-swinging</th>
              <th className="p-3">Usual target</th>
              <th className="p-3">Shots / goals</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--line)]">
            {p.corner_takers.slice(0, 6).map((t) => (
              <tr key={t.name}>
                <td className="p-3 font-semibold">{t.name}</td>
                <td className="p-3">
                  {t.n} <span className="text-ink-2">({pct(t.share_pct)})</span>
                </td>
                <td className="p-3">{FOOT[t.foot] ?? t.foot}</td>
                <td className="p-3">
                  {t.sides.L} / {t.sides.R}
                </td>
                <td className="p-3">
                  {t.technique.in ?? 0} / {t.technique.out ?? 0}
                </td>
                <td className="p-3">{ZONE_SHORT[t.main_zone]}</td>
                <td className="p-3">
                  {t.shots} / {t.goals}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <section>
        <SectionTitle>Defending corners</SectionTitle>
        <Stats
          items={[
            ["Conceded a match", p.corners_against.per_match.toFixed(1), p.corners_against.league_per_match?.toFixed(1)],
            ["Opponent shot (15 s)", pct(p.corners_against.shot.pct), pct(p.corners_against.shot.league_pct)],
            ["xG conceded per corner", p.corners_against.xg_per_corner.toFixed(3), p.corners_against.league_xg_per_corner?.toFixed(3)],
            ["Goals conceded", String(p.corners_against.goals), undefined],
          ]}
          foot={`${p.corners_against.total} corners against`}
        />
      </section>

      <KickSection title="Penalties" block={p.penalties} minN={p.min_n} showMinute />
      <KickSection title="Direct free kicks" block={p.free_kicks} minN={p.min_n} />
    </>
  );
}

function Stats({ items, foot }: { items: [string, string, string | undefined][]; foot: string }) {
  return (
    <Card>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {items.map(([label, value, league]) => (
          <div key={label}>
            <dt className="text-ink-2 text-xs">{label}</dt>
            <dd className="text-xl font-extrabold">{value}</dd>
            {league !== undefined && <dd className="text-ink-2 text-xs">league {league}</dd>}
          </div>
        ))}
      </dl>
      <p className="text-ink-2 mt-2 text-xs">{foot}</p>
    </Card>
  );
}

function ShareBars({ rows, labels, minN }: { rows: Share[]; labels?: Record<string, string>; minN: number }) {
  const total = rows.reduce((s, r) => s + r.n, 0);
  return (
    <div className="space-y-2.5">
      {rows.map((r) => (
        <div key={r.key}>
          <div className="flex items-baseline justify-between gap-2 text-sm">
            <span className="font-semibold">{labels?.[r.key] ?? r.label}</span>
            <span>
              {pct(r.pct)} <span className="text-ink-2 text-xs">({r.n}) · league {pct(r.league_pct)}</span>
            </span>
          </div>
          <div className="bg-surface-2 relative mt-1 h-2.5 rounded-full" aria-hidden>
            <div className="bg-pitch-500 h-full rounded-full" style={{ width: `${r.pct ?? 0}%` }} />
            {r.league_pct != null && (
              <div className="absolute -top-1 h-[18px] w-0.5" style={{ left: `${r.league_pct}%`, background: "var(--ink)" }} title="Rest of the league" />
            )}
          </div>
          {r.flag && (
            <div className="mt-1">
              <Chip tone={r.flag === "more" ? "amber" : "neutral"}>{r.flag === "more" ? "More than the league" : "Less than the league"}</Chip>
            </div>
          )}
        </div>
      ))}
      <p className="text-ink-2 text-xs">
        Black tick: rest of the league.{" "}
        {total < minN ? `Only ${total} cases: too few to call a tendency.` : "Flagged only when the 95% interval excludes the league."}
      </p>
    </div>
  );
}

// Attacking end, goal at the top. StatsBomb x (towards goal) becomes screen y; y stays screen x.
function CornerMap({ points }: { points: Profile["corner_points"] }) {
  const [side, setSide] = useState<"all" | Side>("all");
  // "All" draws every corner as if taken from the right flag, so near and far post line up.
  const shown = points
    .filter((pt) => side === "all" || pt[2] === side)
    .map(([x, y, s, , result]) => ({ sx: side === "all" && s === "L" ? 80 - y : y, sy: 120 - x, result }));
  const flagX = side === "L" ? 0 : 80;
  const nearX = side === "L" ? 37 : 43; // near/far post dividers, 37 and 43 yards in from the flag
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-bold">Corner deliveries</h3>
        <div className="flex gap-1" role="group" aria-label="Corner side">
          {(["all", "L", "R"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSide(s)}
              aria-pressed={side === s}
              className={cn("tap rounded-lg border border-line px-2.5 py-1 text-xs font-semibold", side === s && "bg-pitch-700 text-white")}
            >
              {s === "all" ? "All" : s === "L" ? "From left" : "From right"}
            </button>
          ))}
        </div>
      </div>
      <svg viewBox="-3 -5 86 52" className="w-full rounded-xl" role="img" aria-label={`${shown.length} corner deliveries on the attacking half`}>
        <rect x={-3} y={-5} width={86} height={52} fill="#1d6b44" />
        <g fill="none" stroke="rgba(255,255,255,0.55)" strokeWidth={0.35}>
          <rect x={0} y={0} width={80} height={60} />
          <rect x={18} y={0} width={44} height={18} />
          <rect x={30} y={0} width={20} height={6} />
          <rect x={36} y={-2.2} width={8} height={2.2} />
          <path d="M 32.7 18 A 10 10 0 0 0 47.3 18" />
        </g>
        <circle cx={40} cy={12} r={0.4} fill="rgba(255,255,255,0.7)" />
        <g stroke="rgba(255,255,255,0.35)" strokeWidth={0.25} strokeDasharray="1 1">
          <line x1={nearX} y1={0} x2={nearX} y2={18} />
          <line x1={80 - nearX} y1={0} x2={80 - nearX} y2={18} />
          <line x1={37} y1={6} x2={43} y2={6} />
        </g>
        <text x={nearX + (side === "L" ? -1 : 1)} y={20.5} fontSize={2} fill="rgba(255,255,255,0.75)" textAnchor={side === "L" ? "end" : "start"}>
          near post
        </text>
        <text x={80 - nearX + (side === "L" ? 1 : -1)} y={20.5} fontSize={2} fill="rgba(255,255,255,0.75)" textAnchor={side === "L" ? "start" : "end"}>
          far post
        </text>
        <circle cx={flagX} cy={0} r={1.2} fill="#e3a008" />
        {shown.map((pt, i) => (
          <circle key={i} cx={pt.sx} cy={pt.sy} r={pt.result === "none" ? 0.7 : 0.9} fill={RESULT_COLOUR[pt.result]} opacity={0.9} />
        ))}
      </svg>
      <Legend
        items={[
          ["Goal within 15 s", RESULT_COLOUR.goal],
          ["Shot", RESULT_COLOUR.shot],
          ["No shot", "#9db3a6"],
        ]}
        extra={side === "all" ? "All corners drawn as if taken from the right flag (orange dot)." : undefined}
      />
    </div>
  );
}

export function Legend({ items, extra }: { items: [string, string][]; extra?: string }) {
  return (
    <div className="text-ink-2 mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
      {items.map(([label, colour]) => (
        <span key={label} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: colour }} /> {label}
        </span>
      ))}
      {extra && <span>{extra}</span>}
    </div>
  );
}

const KICK_COLOUR: Record<string, string> = { Goal: "#e3a008", Saved: "#2f7fe0", "Saved to Post": "#2f7fe0" };

function KickSection({ title, block, minN, showMinute }: { title: string; block: KickBlock; minN: number; showMinute?: boolean }) {
  if (!block.total)
    return (
      <section>
        <SectionTitle>{title}</SectionTitle>
        <Card className="text-ink-2 text-sm">None in this season.</Card>
      </section>
    );
  return (
    <section>
      <SectionTitle>{title}</SectionTitle>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <GoalMouth kicks={block.kicks} />
          <p className="text-ink-2 mt-1 text-xs">
            {block.total} taken, {block.scored} scored ({pct(block.conversion.pct)}; league {pct(block.conversion.league_pct)}). Seen from
            behind the kicker: the kicker's left is the goalkeeper's right.
          </p>
        </Card>
        <Card>
          <h3 className="mb-2 font-bold">Placement of kicks on target ({block.on_target})</h3>
          <ShareBars rows={block.placement} labels={{ left: "Kicker's left", centre: "Centre", right: "Kicker's right" }} minN={minN} />
        </Card>
      </div>
      <Card className="mt-4 overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="text-ink-2 text-left">
            <tr>
              <th className="p-3">Kicker</th>
              <th className="p-3">Taken / scored</th>
              <th className="p-3">Foot</th>
              <th className="p-3">On target: left / centre / right</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--line)]">
            {block.takers.map((t) => (
              <tr key={t.name}>
                <td className="p-3 font-semibold">{t.name}</td>
                <td className="p-3">
                  {t.n} / {t.scored}
                </td>
                <td className="p-3">{FOOT[t.foot] ?? t.foot}</td>
                <td className="p-3">
                  {t.left} / {t.centre} / {t.right}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {showMinute && (
          <details className="border-t border-line p-3 text-sm">
            <summary className="cursor-pointer font-semibold">Every penalty</summary>
            <ul className="mt-2 space-y-1">
              {block.kicks.map((k, i) => (
                <li key={i}>
                  {k.minute}' {k.taker} vs {k.opp}: {k.outcome.toLowerCase()}, kicker's {k.third}
                  {k.foot !== "other" && `, ${FOOT[k.foot].toLowerCase()} foot`}
                </li>
              ))}
            </ul>
          </details>
        )}
      </Card>
    </section>
  );
}

// Front view of the goal: 8 yards wide (StatsBomb y 36-44), 2.67 high.
function GoalMouth({ kicks }: { kicks: Kick[] }) {
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
  return (
    <div>
      <svg viewBox="33 -1.3 14 4.6" className="w-full rounded-xl" role="img" aria-label={`${kicks.length} kicks on the goal mouth`}>
        <rect x={33} y={-1.3} width={14} height={4.6} fill="#1d6b44" />
        <rect x={36} y={0} width={8} height={2.67} fill="rgba(255,255,255,0.08)" stroke="#fff" strokeWidth={0.12} />
        <g stroke="rgba(255,255,255,0.35)" strokeWidth={0.05} strokeDasharray="0.2 0.2">
          <line x1={38.67} y1={0} x2={38.67} y2={2.67} />
          <line x1={41.33} y1={0} x2={41.33} y2={2.67} />
          <line x1={36} y1={0.89} x2={44} y2={0.89} />
          <line x1={36} y1={1.78} x2={44} y2={1.78} />
        </g>
        <line x1={33} y1={2.67} x2={47} y2={2.67} stroke="rgba(255,255,255,0.5)" strokeWidth={0.05} />
        {kicks.map((k, i) => (
          <circle
            key={i}
            cx={clamp(k.y, 33.3, 46.7)}
            cy={clamp(2.67 - (k.z ?? 0.15), -1.1, 3.1)}
            r={0.22}
            fill={KICK_COLOUR[k.outcome] ?? "#ea6a12"}
            stroke="#0b2a20"
            strokeWidth={0.04}
          >
            <title>{`${k.taker} vs ${k.opp}: ${k.outcome}`}</title>
          </circle>
        ))}
      </svg>
      <Legend
        items={[
          ["Goal", KICK_COLOUR.Goal],
          ["Saved", KICK_COLOUR.Saved],
          ["Missed (wide, over, post)", "#ea6a12"],
        ]}
      />
    </div>
  );
}
