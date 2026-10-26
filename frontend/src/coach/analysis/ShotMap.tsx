// Shot map: every shot a team took (or conceded), filtered by body part and situation,
// with tap-in / box / long-shot totals computed from what is shown.
import { useState } from "react";
import { useApi } from "../../shared/useApi";
import { Card, ErrorNote, Spinner, cn } from "../../shared/ui";
import { Legend } from "./SetPieces";
import type { Shots } from "./types";

type Side = "for" | "against";
const BODY = { all: "Any", foot: "Foot", head: "Header" } as const;
const SITUATION = { all: "All", open: "Open play", counter: "Counter", set: "Set play", penalty: "Penalty" } as const;
const ZONES = [
  ["six", "Tap-in range (six-yard box)"],
  ["box", "Rest of the box"],
  ["out", "Outside the box"],
] as const;
const COLOUR = { goal: "#e3a008", target: "#2f7fe0", other: "rgba(255,255,255,0.55)" };

function zone(x: number, y: number): "six" | "box" | "out" {
  if (x >= 114 && y >= 30 && y <= 50) return "six";
  return x >= 102 && y >= 18 && y <= 62 ? "box" : "out";
}

interface Shot {
  x: number;
  y: number;
  xg: number;
  outcome: string;
  body: string;
  pattern: string;
  type: string;
  player: string;
  minute: number;
}

export function ShotMap({ teamId }: { teamId: string }) {
  const { data, error, loading, reload } = useApi<Shots>(`/api/coach/analysis/teams/${encodeURIComponent(teamId)}/shots`);
  const [side, setSide] = useState<Side>("for");
  const [body, setBody] = useState<keyof typeof BODY>("all");
  const [sit, setSit] = useState<keyof typeof SITUATION>("all");
  if (loading && !data) return <Spinner label="Loading shots" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  const idx = Object.fromEntries(data.columns.map((c, i) => [c, i]));
  const all: Shot[] = data[side].map((r) => Object.fromEntries(data.columns.map((c) => [c, r[idx[c]]])) as unknown as Shot);
  const shots = all.filter(
    (s) =>
      (body === "all" || (body === "head" ? s.body === "H" : s.body === "R" || s.body === "L")) &&
      (sit === "all" ||
        (sit === "penalty"
          ? s.type === "penalty"
          : s.type !== "penalty" &&
            (sit === "open" ? s.pattern === "regular" : sit === "counter" ? s.pattern === "counter" : ["corner", "free_kick", "throw_in"].includes(s.pattern)))),
  );
  const goals = shots.filter((s) => s.outcome === "Goal").length;
  const xg = shots.reduce((a, s) => a + s.xg, 0);
  return (
    <Card>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-bold">Shot map</h3>
        <Toggle value={side} options={{ for: `${data.team} shots`, against: "Shots conceded" }} onChange={setSide} label="Whose shots" />
      </div>
      <div className="mb-2 flex flex-wrap gap-2">
        <Toggle value={body} options={BODY} onChange={setBody} label="Body part" />
        <Toggle value={sit} options={SITUATION} onChange={setSit} label="Situation" />
      </div>
      <svg viewBox="-3 -5 86 55" className="w-full rounded-xl" role="img" aria-label={`${shots.length} shots on the attacking half`}>
        <rect x={-3} y={-5} width={86} height={55} fill="#1d6b44" />
        <g fill="none" stroke="rgba(255,255,255,0.55)" strokeWidth={0.35}>
          <rect x={0} y={0} width={80} height={60} />
          <rect x={18} y={0} width={44} height={18} />
          <rect x={30} y={0} width={20} height={6} />
          <rect x={36} y={-2.2} width={8} height={2.2} />
          <path d="M 32.7 18 A 10 10 0 0 0 47.3 18" />
        </g>
        <circle cx={40} cy={12} r={0.4} fill="rgba(255,255,255,0.7)" />
        {shots
          .slice()
          .sort((a, b) => b.xg - a.xg)
          .map((s, i) => {
            const fill = s.outcome === "Goal" ? COLOUR.goal : s.outcome === "Saved" || s.outcome === "Saved to Post" ? COLOUR.target : COLOUR.other;
            return (
              <circle key={i} cx={s.y} cy={Math.min(49, 120 - s.x)} r={0.5 + 2.6 * Math.sqrt(s.xg)} fill={fill} fillOpacity={0.8} stroke="#0b2a20" strokeWidth={0.12}>
                <title>{`${s.minute}' ${s.player}: ${s.outcome.toLowerCase()}, xG ${s.xg.toFixed(2)}`}</title>
              </circle>
            );
          })}
      </svg>
      <Legend
        items={[
          ["Goal", COLOUR.goal],
          ["Saved", COLOUR.target],
          ["Missed or blocked", "#9db3a6"],
        ]}
        extra="Bigger dot = better chance (xG)."
      />
      <table className="mt-3 w-full text-sm">
        <thead className="text-ink-2 text-left text-xs">
          <tr>
            <th className="py-1">Where</th>
            <th className="py-1 text-right">Shots</th>
            <th className="py-1 text-right">Goals</th>
            <th className="py-1 text-right">Scored</th>
            <th className="py-1 text-right">xG</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[color:var(--line)]">
          {ZONES.map(([key, label]) => {
            const z = shots.filter((s) => zone(s.x, s.y) === key);
            const g = z.filter((s) => s.outcome === "Goal").length;
            return (
              <tr key={key}>
                <td className="py-1.5">{label}</td>
                <td className="py-1.5 text-right">{z.length}</td>
                <td className="py-1.5 text-right">{g}</td>
                <td className="py-1.5 text-right">{z.length ? `${Math.round((100 * g) / z.length)}%` : "–"}</td>
                <td className="py-1.5 text-right">{z.reduce((a, s) => a + s.xg, 0).toFixed(1)}</td>
              </tr>
            );
          })}
          <tr className="font-bold">
            <td className="py-1.5">All shown</td>
            <td className="py-1.5 text-right">{shots.length}</td>
            <td className="py-1.5 text-right">{goals}</td>
            <td className="py-1.5 text-right">{shots.length ? `${Math.round((100 * goals) / shots.length)}%` : "–"}</td>
            <td className="py-1.5 text-right">{xg.toFixed(1)}</td>
          </tr>
        </tbody>
      </table>
    </Card>
  );
}

function Toggle<K extends string>({ value, options, onChange, label }: { value: K; options: Record<K, string>; onChange: (k: K) => void; label: string }) {
  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label={label}>
      {(Object.keys(options) as K[]).map((k) => (
        <button
          key={k}
          onClick={() => onChange(k)}
          aria-pressed={value === k}
          className={cn("tap rounded-lg border border-line px-2.5 py-1 text-xs font-semibold", value === k && "bg-pitch-700 text-white")}
        >
          {options[k]}
        </button>
      ))}
    </div>
  );
}
