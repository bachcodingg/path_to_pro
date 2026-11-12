// Pieces the player pages share: the hub's types, and percentile bars (how a player's per-90
// numbers compare with the regulars in his position group).
import { Link } from "react-router-dom";
import { LICENCE_TEXT, REAL_CRESTS, WIKI_CRESTS } from "../shared/crests";
import { PlayerPhoto, type Photo } from "../shared/PlayerPhoto";
import { Card, cn } from "../shared/ui";
import { ordinal } from "./types";

export interface PlayerMeasure {
  key: string;
  label: string;
  unit: string;
  help?: string;
  value: number | null;
  percentile: number | null;
  peers: number | null;
  peer_median: number | null;
  lower_is_better?: boolean;
}

export interface PlayerSummary {
  id: string | number;
  name: string;
  slug?: string;
  position: string | null;
  group?: string | null;
  minutes: number;
  goals: number;
  assists: number;
  matches?: number;
  apps?: number;
  xg?: number;
  rating?: number | null;
  age?: number | null;
  nationality?: string | null;
  photo?: Photo | null;
}

function fmt(m: PlayerMeasure, v: number | null): string {
  if (v == null) return "–";
  if (m.unit === "%") return `${v.toFixed(1)}%`;
  if (m.unit === "/10") return v.toFixed(2);
  return v.toFixed(2);
}

// The bar's colour says how high: top fifth, above the middle, below it
function tier(p: number): string {
  return p >= 80 ? "bg-pitch-600" : p >= 50 ? "bg-pitch-400" : "bg-ink-2/40";
}

export function PercentileBars({ measures, comparedWith, none }: { measures: PlayerMeasure[]; comparedWith: string | null; none: string | null }) {
  return (
    <Card>
      <h2 className="font-display text-xl font-bold">How he compares</h2>
      <p className="text-ink-2 mt-0.5 text-sm">
        {none ?? (comparedWith ? `Percentile against ${comparedWith}. 50 is the middle of the group; per 90 minutes unless it is a share.` : "")}
      </p>
      <ul className="mt-3 space-y-3" aria-label="Percentiles">
        {measures.map((m) => (
          <li key={m.key}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="font-semibold" title={m.help}>
                {m.label}
                {m.lower_is_better && <span className="text-ink-2 font-normal"> (fewer is better)</span>}
              </span>
              <span className="num shrink-0">
                <b>{fmt(m, m.value)}</b>
                {m.unit === "" && m.value != null && <span className="text-ink-2"> /90</span>}
                {m.percentile != null && <span className="text-ink-2"> · {ordinal(m.percentile)} pct</span>}
              </span>
            </div>
            {m.percentile != null && (
              <div
                className="bg-surface-2 border-line relative mt-1 h-2.5 overflow-hidden rounded-full border"
                role="img"
                aria-label={`${m.label}: ${ordinal(m.percentile)} percentile of ${m.peers}; the group's median is ${fmt(m, m.peer_median)}`}
              >
                <span className={cn("absolute inset-y-0 left-0 rounded-full", tier(m.percentile))} style={{ width: `${Math.max(3, m.percentile)}%` }} />
                <span className="bg-ink absolute inset-y-0 left-1/2 w-px opacity-40" aria-hidden />
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function TotalsTable({ rows }: { rows: [string, string | number | null][] }) {
  return (
    <Card>
      <h2 className="font-display text-xl font-bold">Season totals</h2>
      <dl className="mt-2 grid grid-cols-1 gap-x-8 text-sm sm:grid-cols-2">
        {rows.map(([label, v]) => (
          <div key={label} className="border-line flex justify-between gap-3 border-b py-1.5">
            <dt className="text-ink-2">{label}</dt>
            <dd className="num font-semibold">{v ?? "–"}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

// One row in a list of players: photo with the club's crest, name, position, goals and assists
export function PlayerLine({ to, team, logo, p, sub }: { to: string; team: string; logo?: string | null; p: PlayerSummary; sub?: string }) {
  return (
    <Link to={to} className="hover:bg-surface-2 flex items-center gap-3 px-3 py-2">
      <PlayerPhoto name={p.name} photo={p.photo} team={team} logo={logo} size={40} />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{p.name}</span>
        <span className="text-ink-2 block truncate text-xs">{sub ?? `${team} · ${p.position ?? ""}`}</span>
      </span>
      <span className="num text-right text-sm">
        <b>{p.goals}</b> <span className="text-ink-2">G</span> <b>{p.assists}</b> <span className="text-ink-2">A</span>
      </span>
    </Link>
  );
}

// Which real crests are shown, under which licence, and where they come from
export function CrestCredits() {
  const others = Object.entries(WIKI_CRESTS).filter(([team]) => !REAL_CRESTS[team]);
  return (
    <details className="text-ink-2 text-xs">
      <summary className="cursor-pointer font-semibold">Club crests</summary>
      <p className="mt-1 max-w-3xl">
        Crests are trademarks of their clubs, and the clubs have no connection with this app. The ones kept in the app are free to reuse: public domain (most
        are simple text logos), public domain in the US where this site is hosted, or under a Creative Commons licence:
      </p>
      <ul className="mt-1 grid gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(REAL_CRESTS).map(([team, c]) => (
          <li key={team}>
            <a className="underline" href={c.source}>
              {team}
            </a>
            : {LICENCE_TEXT[c.licence]}
            {c.author ? `, ${c.author}` : ""}
          </li>
        ))}
      </ul>
      <p className="mt-2 max-w-3xl">
        The others are shown from Wikipedia, which uses most of them under fair use to identify the club, as this app does. The 2024/25 and 2025/26 squads
        show the logos that come with API-Football's data.
      </p>
      <ul className="mt-1 grid gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
        {others.map(([team, c]) => (
          <li key={team}>
            <a className="underline" href={c.file}>
              {team}
            </a>
          </li>
        ))}
      </ul>
    </details>
  );
}
