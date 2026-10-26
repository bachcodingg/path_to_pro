// Players tab: the opponent's squad with shooting, passing, duel and defending numbers; sortable.
import { useState } from "react";
import { useApi } from "../../shared/useApi";
import { Card, ErrorNote, Spinner, cn } from "../../shared/ui";
import type { PlayerRow } from "./types";

type Kind = "int" | "num" | "pct";
const CATEGORIES: Record<string, { label: string; cols: [string, string, Kind][] }> = {
  shooting: {
    label: "Shooting",
    cols: [
      ["goals", "Goals", "int"],
      ["pen_goals", "Penalties", "int"],
      ["six_goals", "Tap-ins", "int"],
      ["head_goals", "Headers", "int"],
      ["out_goals", "Long shots", "int"],
      ["xg", "xG", "num"],
      ["shots90", "Shots /90", "num"],
      ["conversion", "Conversion", "pct"],
    ],
  },
  passing: {
    label: "Passing",
    cols: [
      ["passes90", "Passes /90", "num"],
      ["pass_acc", "Pass %", "pct"],
      ["short_acc", "Short %", "pct"],
      ["long_acc", "Long %", "pct"],
      ["key_passes90", "Key passes /90", "num"],
      ["assists", "Assists", "int"],
      ["crosses_cmp", "Crosses", "int"],
      ["final_third90", "Into final third /90", "num"],
    ],
  },
  duels: {
    label: "Duels & headers",
    cols: [
      ["aerial_won", "Aerials won", "int"],
      ["aerial_pct", "Aerial %", "pct"],
      ["dribbles90", "Dribbles /90", "num"],
      ["dribble_pct", "Dribble %", "pct"],
    ],
  },
  defending: {
    label: "Defending",
    cols: [
      ["tackles_int90", "Tackles + int. /90", "num"],
      ["pressures90", "Pressures /90", "num"],
      ["recoveries90", "Recoveries /90", "num"],
      ["yellow", "Yellow", "int"],
      ["red", "Red", "int"],
    ],
  },
};
const LINES = { all: "All", GK: "Goalkeepers", DF: "Defenders", MF: "Midfielders", FW: "Forwards" } as const;

function line(position: string | null): keyof typeof LINES {
  if (!position) return "all";
  if (position === "Goalkeeper") return "GK";
  if (position.includes("Back")) return "DF";
  if (position.includes("Midfield")) return "MF";
  return "FW";
}

function fmt(v: unknown, kind: Kind): string {
  if (v == null) return "–";
  const n = Number(v);
  return kind === "pct" ? `${n.toFixed(0)}%` : kind === "num" ? n.toFixed(2) : String(n);
}

export function Players({ teamId }: { teamId: string }) {
  const { data, error, loading, reload } = useApi<{ team: string; min_minutes: number; players: PlayerRow[] }>(
    `/api/coach/analysis/teams/${encodeURIComponent(teamId)}/players`,
  );
  const [cat, setCat] = useState("shooting");
  const [lineFilter, setLine] = useState<keyof typeof LINES>("all");
  const [sort, setSort] = useState<string>("goals");
  if (loading && !data) return <Spinner label="Loading players" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  const cols = CATEGORIES[cat].cols;
  const key = cols.some(([k]) => k === sort) || sort === "minutes" ? sort : cols[0][0];
  const rows = data.players
    .filter((p) => lineFilter === "all" || line(p.position) === lineFilter)
    .slice()
    .sort((a, b) => (b[key] == null ? -1 : a[key] == null ? 1 : Number(b[key]) - Number(a[key])));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1" role="group" aria-label="Category">
          {Object.entries(CATEGORIES).map(([k, c]) => (
            <button
              key={k}
              aria-pressed={cat === k}
              onClick={() => setCat(k)}
              className={cn("tap rounded-lg border border-line px-3 py-1.5 text-sm font-semibold", cat === k && "bg-pitch-700 text-white")}
            >
              {c.label}
            </button>
          ))}
        </div>
        <label className="text-sm font-semibold">
          Line{" "}
          <select className="bg-surface ml-1 rounded-lg border border-line px-2 py-1.5" value={lineFilter} onChange={(e) => setLine(e.target.value as keyof typeof LINES)}>
            {Object.entries(LINES).map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="text-ink-2 text-left text-xs">
            <tr>
              <th className="p-3">Player</th>
              <th className="p-3">Position</th>
              <SortHeader k="minutes" label="Minutes" sort={key} onSort={setSort} />
              {cols.map(([k, label]) => (
                <SortHeader key={k} k={k} label={label} sort={key} onSort={setSort} />
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--line)]">
            {rows.map((p) => (
              <tr key={p.name}>
                <td className="p-3 font-semibold whitespace-nowrap">{p.name}</td>
                <td className="text-ink-2 p-3 whitespace-nowrap">{p.position ?? "–"}</td>
                <td className="p-3 text-right">{p.minutes}</td>
                {cols.map(([k, , kind]) => (
                  <td key={k} className={cn("p-3 text-right", k === key && "font-bold")}>
                    {fmt(p[k], kind)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="text-ink-2 text-xs">
        Per-90 numbers need {data.min_minutes}+ minutes; percentages need enough attempts (100 passes, 30 long passes, 20 aerial
        duels, 15 dribbles, 10 shots). Tap-ins are goals from inside the six-yard box; long shots are from outside the box.
      </p>
    </div>
  );
}

function SortHeader({ k, label, sort, onSort }: { k: string; label: string; sort: string; onSort: (k: string) => void }) {
  return (
    <th className="p-3 text-right" aria-sort={sort === k ? "descending" : "none"}>
      <button className={cn("tap whitespace-nowrap hover:underline", sort === k && "text-ink font-bold")} onClick={() => onSort(k)}>
        {label}
        {sort === k ? " ↓" : ""}
      </button>
    </th>
  );
}
