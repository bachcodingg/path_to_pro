// Players tab: the opponent's squad with shooting, passing, duel and defending numbers; sortable.
// Every name opens the player's own page (PlayerProfile).
import { useState } from "react";
import { Link } from "react-router-dom";
import { PhotoCredits, PlayerPhoto } from "../shared/PlayerPhoto";
import { useApi } from "../shared/useApi";
import { ErrorNote, Spinner, cn } from "../shared/ui";
import { Label, Segmented } from "./ui";
import type { PlayerRow } from "./types";
import { usePro } from "./context";

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
  const { base, comp } = usePro();
  const profile = (p: PlayerRow) => `/${comp}/teams/${teamId}/players/${p.id}`;
  const { data, error, loading, reload } = useApi<{ team: string; min_minutes: number; players: PlayerRow[] }>(
    `${base}/teams/${encodeURIComponent(teamId)}/players`,
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
    <div className="space-y-4 md:space-y-5">
      <Leaders players={data.players} profile={profile} />
      <section className="lg-panel" aria-label="Squad">
        <div className="border-line flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-display text-[1.05rem] font-extrabold">Squad</h2>
            <Segmented value={cat} options={Object.fromEntries(Object.entries(CATEGORIES).map(([k, c]) => [k, c.label]))} onChange={setCat} label="Category" />
          </div>
          <label className="text-ink-2 flex items-center gap-2 text-sm font-bold">
            Line
            <select className="bg-surface text-ink border-line h-11 rounded-md border px-3 md:h-9" value={lineFilter} onChange={(e) => setLine(e.target.value as keyof typeof LINES)}>
              {Object.entries(LINES).map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="overflow-x-auto">
        <table className="lg-table">
          <thead className="text-left">
            <tr>
              <th>Player</th>
              <th>Position</th>
              <SortHeader k="minutes" label="Minutes" sort={key} onSort={setSort} />
              {cols.map(([k, label]) => (
                <SortHeader key={k} k={k} label={label} sort={key} onSort={setSort} />
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.name}>
                <td className="!py-1.5 font-bold whitespace-nowrap">
                  <span className="flex items-center gap-3">
                    <PlayerPhoto name={p.name} photo={p.photo} size={32} />
                    <Link to={profile(p)} className="hover:underline">
                      {p.name}
                    </Link>
                  </span>
                </td>
                <td className="text-ink-2 whitespace-nowrap">{p.position ?? "–"}</td>
                <td className={cn("text-right", key === "minutes" && "bg-pitch-500/8 font-extrabold")}>{p.minutes}</td>
                {cols.map(([k, , kind]) => (
                  <td key={k} className={cn("text-right", k === key && "bg-pitch-500/8 font-extrabold")}>
                    {fmt(p[k], kind)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </section>
      <p className="text-ink-2 text-xs">
        Per-90 numbers need {data.min_minutes}+ minutes; percentages need enough attempts (100 passes, 30 long passes, 20 aerial
        duels, 15 dribbles, 10 shots). Tap-ins are goals from inside the six-yard box; long shots are from outside the box.
      </p>
      <PhotoCredits people={data.players} />
    </div>
  );
}

// Stats-centre cards: the squad's top five for a few headline numbers
const LEADERS: [string, string, Kind][] = [
  ["goals", "Goals", "int"],
  ["assists", "Assists", "int"],
  ["key_passes90", "Key passes /90", "num"],
  ["aerial_won", "Aerial duels won", "int"],
  ["tackles_int90", "Tackles + interceptions /90", "num"],
];

function Leaders({ players, profile }: { players: PlayerRow[]; profile: (p: PlayerRow) => string }) {
  return (
    <section aria-label="Squad leaders" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {LEADERS.map(([k, label, kind]) => {
        const top = players
          .filter((p) => p[k] != null && Number(p[k]) > 0)
          .sort((a, b) => Number(b[k]) - Number(a[k]))
          .slice(0, 5);
        const [first, ...rest] = top;
        return (
          <div key={k} className="lg-panel">
            <div className="bg-[#0b1230] border-pitch-300 border-b-[3px] px-3 pt-2.5 pb-3 text-white">
              <Label className="text-pitch-300">{label}</Label>
              {first ? (
                <div className="mt-2 flex items-center gap-2.5">
                  <PlayerPhoto name={first.name} photo={first.photo} size={48} />
                  <span className="min-w-0 flex-1">
                    <Link to={profile(first)} className="line-clamp-2 text-[15px] leading-tight font-extrabold hover:underline">
                      {first.name}
                    </Link>
                    <span className="block truncate text-xs text-white/85">{first.position ?? ""}</span>
                  </span>
                  <span className="font-display num text-[2.1rem] leading-none font-extrabold">{fmt(first[k], kind)}</span>
                </div>
              ) : (
                <p className="mt-1 text-sm text-white/95">No one yet</p>
              )}
            </div>
            <ol className="divide-line divide-y text-sm" start={2}>
              {rest.map((p, i) => (
                <li key={p.name} className="flex items-center gap-2 px-3 py-1.5">
                  <span className="text-ink-2 num w-4 text-xs font-bold">{i + 2}</span>
                  <Link to={profile(p)} className="min-w-0 flex-1 truncate font-semibold hover:underline">
                    {p.name}
                  </Link>
                  <span className="num font-extrabold">{fmt(p[k], kind)}</span>
                </li>
              ))}
            </ol>
          </div>
        );
      })}
    </section>
  );
}

function SortHeader({ k, label, sort, onSort }: { k: string; label: string; sort: string; onSort: (k: string) => void }) {
  return (
    <th className={cn("!py-0 text-right", sort === k && "!bg-pitch-500/12")} aria-sort={sort === k ? "descending" : "none"}>
      <button className={cn("tap tracking-[inherit] whitespace-nowrap uppercase hover:underline", sort === k && "text-ink")} onClick={() => onSort(k)}>
        {label}
        {sort === k ? " ↓" : ""}
      </button>
    </th>
  );
}
