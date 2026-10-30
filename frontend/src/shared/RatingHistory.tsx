// Rating over time: every rated match ("Jan M1", "Jan M2", ...), a 5-match rolling average
// and a straight trend line showing whether the player is improving.
import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import { CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { ratingBand } from "./Rating";
import type { RatingBand } from "./types";
import { Card, Chip } from "./ui";

export interface HistoryPoint {
  match_id: string;
  date: string;
  label: string;
  opponent: string;
  team: string;
  minutes: number;
  goals: number;
  assists: number;
  rating: number;
  rating_band: RatingBand | null;
  source: string | null;
  rolling: number;
  trend?: number;
}
export interface RatingHistoryData {
  points: HistoryPoint[];
  progress: {
    matches: number;
    average: number | null;
    slope_per_match: number | null;
    change_10: number | null;
    first_vs_last: number | null;
    verdict: "improving" | "steady" | "dipping" | "not enough matches";
  };
}

const HEX: Record<RatingBand, string> = { elite: "#2a6fdb", good: "#1fa05a", fair: "#a3c639", average: "#f0a020", poor: "#e5484d" };

function Dot(props: { cx?: number; cy?: number; payload?: HistoryPoint }) {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null || !payload) return null;
  const b = ratingBand(payload.rating);
  return <circle cx={cx} cy={cy} r={5} fill={b ? HEX[b] : "#888"} stroke="#fff" strokeWidth={1.5} />;
}

function Tip({ active, payload }: { active?: boolean; payload?: { payload: HistoryPoint }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border border-[#24324d] bg-[#111b30] p-2 text-xs text-white">
      <p className="font-bold">
        {p.label}: {p.rating.toFixed(1)}
      </p>
      <p>
        vs {p.opponent} · {p.team}
      </p>
      <p>
        {new Date(p.date + "T12:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })} · {p.minutes}'
        {p.goals > 0 && ` · ${p.goals}G`}
        {p.assists > 0 && ` · ${p.assists}A`}
      </p>
      <p className="text-[#a8b4c8]">
        5-match average {p.rolling.toFixed(2)}
        {p.trend != null && ` · trend ${p.trend.toFixed(2)}`}
      </p>
    </div>
  );
}

export function RatingHistory({ data, dark = true }: { data: RatingHistoryData; dark?: boolean }) {
  const { points, progress } = data;
  if (points.length === 0) return <Card className="text-ink-2 text-sm">No rated matches yet.</Card>;
  const axis = dark ? "#a8b4c8" : "#5b6780";
  const grid = dark ? "rgba(255,255,255,0.08)" : "#e3e8f1";
  const Icon = progress.verdict === "improving" ? TrendingUp : progress.verdict === "dipping" ? TrendingDown : Minus;
  const tone = progress.verdict === "improving" ? "green" : progress.verdict === "dipping" ? "red" : "neutral";
  const sign = (x: number | null) => (x == null ? "–" : `${x > 0 ? "+" : ""}${x.toFixed(2)}`);
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone={tone}>
          <Icon className="mr-1 h-3.5 w-3.5" aria-hidden />
          {progress.verdict === "not enough matches" ? "Not enough matches for a trend" : `${progress.verdict[0].toUpperCase()}${progress.verdict.slice(1)}`}
        </Chip>
        <Chip>Average {progress.average?.toFixed(2) ?? "–"}</Chip>
        {progress.change_10 != null && <Chip>Trend {sign(progress.change_10)} per 10 matches</Chip>}
        {progress.first_vs_last != null && <Chip>Last 5 vs first 5: {sign(progress.first_vs_last)}</Chip>}
      </div>
      <div className="h-64" role="img" aria-label={`Match ratings over ${points.length} matches, ${progress.verdict}`}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
            <CartesianGrid stroke={grid} />
            <XAxis dataKey="label" fontSize={10} stroke={axis} interval="preserveStartEnd" minTickGap={8} />
            <YAxis domain={[5, 9]} ticks={[5, 6, 6.5, 7, 8, 9]} fontSize={11} stroke={axis} />
            <ReferenceLine y={7} stroke="#1fa05a" strokeDasharray="2 4" />
            <Tooltip content={<Tip />} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line name="Match rating" dataKey="rating" stroke={dark ? "rgba(255,255,255,0.35)" : "#9aa5b8"} strokeWidth={1.5} dot={<Dot />} isAnimationActive={false} />
            <Line name="5-match average" dataKey="rolling" stroke="var(--brand-300)" strokeWidth={3} dot={false} isAnimationActive={false} />
            {progress.slope_per_match != null && (
              <Line name="Trend" dataKey="trend" stroke="#f0a020" strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
            )}
            <Scatter dataKey="rating" fill="transparent" legendType="none" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="text-ink-2 text-xs">
        Each dot is one match (coloured by rating). The green line is the average of the last 5 matches; the dashed orange line is the
        straight-line trend over all {points.length} matches.
      </p>
    </Card>
  );
}
