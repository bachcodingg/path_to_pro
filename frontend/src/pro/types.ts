// Shapes of /api/pro/{comp}/teams/{id}/style, /players and /shots (backend/scouting/style.py).

export interface Measure {
  key: string;
  group: string;
  label: string;
  unit: "" | "%";
  digits: number;
  better: "high" | "low" | null;
  help: string;
  value: number | null;
  lo: number | null;
  hi: number | null;
  league: number | null;
  league_min: number | null;
  league_max: number | null;
  rank: number | null;
  teams: number | null;
  flag: "high" | "low" | null;
  verdict: "strength" | "weakness" | "style" | null;
}

export interface Standing {
  team: string;
  id: string;
  position: number | null; // null when the data has one club's season, not the league's
  played: number;
  won: number;
  drawn: number;
  lost: number;
  gf: number;
  ga: number;
  points: number;
  form?: ("W" | "D" | "L")[];
}

export interface StyleProfile {
  id: string;
  team: string;
  matches: number;
  standing: Standing;
  groups: { key: string; label: string }[];
  measures: Measure[];
  summary: { strength: string[]; weakness: string[]; style: string[] };
}

export type PlayerRow = Record<string, number | string | null> & { name: string; position: string | null; minutes: number };

export interface Shots {
  team: string;
  columns: string[];
  for: (string | number)[][];
  against: (string | number)[][];
}

export function fmtMeasure(m: Pick<Measure, "unit" | "digits">, v: number | null | undefined): string {
  if (v == null) return "–";
  return m.unit === "%" ? `${v.toFixed(1)}%` : v.toFixed(m.digits);
}

export function ordinal(n: number): string {
  const s = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${s}`;
}

// Same wording as rank_text in backend/scouting/style.py.
export function rankText(m: Measure): string {
  const { rank, teams: n } = m;
  if (rank == null || n == null) return "";
  const [top, bottom] = m.better ? ["best", "worst"] : ["highest", "lowest"];
  if (rank === 1) return `${top} in the league`;
  if (rank === n) return `${bottom} in the league`;
  return rank <= Math.floor((n + 1) / 2) ? `${ordinal(rank)} ${top} of ${n}` : `${ordinal(n - rank + 1)} ${bottom} of ${n}`;
}
