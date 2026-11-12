// Shot map: every shot a team took (or conceded), or one player's shots, filtered by body part
// and situation, with tap-in / box / long-shot totals computed from what is shown.
import { useState, type ReactNode } from "react";
import { useApi } from "../shared/useApi";
import { Crosshair } from "lucide-react";
import { ErrorNote, Spinner } from "../shared/ui";
import { HalfPitch } from "./pitch";
import { Legend } from "./SetPieces";
import { Label, Panel, Segmented } from "./ui";
import type { Shots } from "./types";
import { usePro } from "./context";

type Side = "for" | "against";
const BODY = { all: "Any", foot: "Foot", head: "Header" } as const;
const SITUATION = { all: "All", open: "Open play", counter: "Counter", set: "Set play", penalty: "Penalty" } as const;
const ZONES = [
  ["six", "Tap-in range (six-yard box)"],
  ["box", "Rest of the box"],
  ["out", "Outside the box"],
] as const;
const COLOUR = { goal: "#ffc93c", target: "#5ad1ff", other: "rgba(255,255,255,0.6)" };

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

function rowsToShots(columns: string[], rows: (string | number | boolean)[][], player = ""): Shot[] {
  return rows.map((r) => ({ player, ...Object.fromEntries(columns.map((c, i) => [c, r[i]])) }) as unknown as Shot);
}

export function ShotMap({ teamId }: { teamId: string }) {
  const { base } = usePro();
  const { data, error, loading, reload } = useApi<Shots>(`${base}/teams/${encodeURIComponent(teamId)}/shots`);
  const [side, setSide] = useState<Side>("for");
  if (loading && !data) return <Spinner label="Loading shots" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  return (
    <ShotView
      all={rowsToShots(data.columns, data[side])}
      toggle={<Segmented value={side} options={{ for: `${data.team} shots`, against: "Shots conceded" }} onChange={setSide} label="Whose shots" />}
    />
  );
}

// One player's shots (rows in the API's column order), on the same pitch
export function PlayerShotMap({ name, columns, rows }: { name: string; columns: string[]; rows: (string | number | boolean)[][] }) {
  return <ShotView all={rowsToShots(columns, rows, name)} title={`${name}'s shots`} />;
}

function ShotView({ all, toggle, title = "Shot map" }: { all: Shot[]; toggle?: ReactNode; title?: string }) {
  const [body, setBody] = useState<keyof typeof BODY>("all");
  const [sit, setSit] = useState<keyof typeof SITUATION>("all");
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
    <Panel title={title} icon={Crosshair} level={3} action={toggle} bodyClassName="p-0">
      <dl className="divide-line border-line grid grid-cols-4 divide-x border-b text-center">
        {(
          [
            ["Shots", shots.length],
            ["Goals", goals],
            ["xG", xg.toFixed(1)],
            ["Scored", shots.length ? `${Math.round((100 * goals) / shots.length)}%` : "–"],
          ] as const
        ).map(([k, v]) => (
          <div key={k} className="px-2 py-2.5">
            <dt>
              <Label>{k}</Label>
            </dt>
            <dd className="font-display num text-2xl leading-tight font-extrabold">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-x-4 gap-y-2 px-3 pt-3">
        <Segmented value={body} options={BODY} onChange={setBody} label="Body part" />
        <Segmented value={sit} options={SITUATION} onChange={setSit} label="Situation" />
      </div>
      <div className="p-3">
      <HalfPitch label={`${shots.length} shots on the attacking half`}>
        {shots
          .slice()
          .sort((a, b) => b.xg - a.xg)
          .map((s, i) => {
            const fill = s.outcome === "Goal" ? COLOUR.goal : s.outcome === "Saved" || s.outcome === "Saved to Post" ? COLOUR.target : COLOUR.other;
            return (
              <circle key={i} cx={s.y} cy={Math.min(49, 120 - s.x)} r={0.5 + 2.6 * Math.sqrt(s.xg)} fill={fill} fillOpacity={0.85} stroke="#0c1a3d" strokeWidth={0.14}>
                <title>{`${s.minute}' ${s.player}: ${s.outcome.toLowerCase()}, xG ${s.xg.toFixed(2)}`}</title>
              </circle>
            );
          })}
      </HalfPitch>
      <Legend
        items={[
          ["Goal", COLOUR.goal],
          ["Saved", COLOUR.target],
          ["Missed or blocked", "#a9b6c9"],
        ]}
        extra="Bigger dot = better chance (xG)."
      />
      </div>
      <table className="lg-table border-line border-t">
        <thead className="text-left">
          <tr>
            <th>Where</th>
            <th className="text-right">Shots</th>
            <th className="text-right">Goals</th>
            <th className="text-right">Scored</th>
            <th className="text-right">xG</th>
          </tr>
        </thead>
        <tbody>
          {ZONES.map(([key, label]) => {
            const z = shots.filter((s) => zone(s.x, s.y) === key);
            const g = z.filter((s) => s.outcome === "Goal").length;
            return (
              <tr key={key}>
                <td>{label}</td>
                <td className="text-right">{z.length}</td>
                <td className="text-right">{g}</td>
                <td className="text-right">{z.length ? `${Math.round((100 * g) / z.length)}%` : "–"}</td>
                <td className="text-right">{z.reduce((a, s) => a + s.xg, 0).toFixed(1)}</td>
              </tr>
            );
          })}
          <tr className="bg-surface-2 font-extrabold">
            <td>All shown</td>
            <td className="text-right">{shots.length}</td>
            <td className="text-right">{goals}</td>
            <td className="text-right">{shots.length ? `${Math.round((100 * goals) / shots.length)}%` : "–"}</td>
            <td className="text-right">{xg.toFixed(1)}</td>
          </tr>
        </tbody>
      </table>
    </Panel>
  );
}
