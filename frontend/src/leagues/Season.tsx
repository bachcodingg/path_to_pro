// The 2024/25 season from API-Football's season totals: a featured club's full squad, and one
// player's page. Season totals, not match events, so there are no shot maps; but these are the
// squads as they are now (Mbappé at Real Madrid), and Bayern Munich, whom the free event data
// does not have.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Crest, clubMeta } from "../shared/Club";
import { PageHeader } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { Card, ErrorNote, PageSkeleton, StatTile, cn } from "../shared/ui";
import { PercentileBars, TotalsTable, type PlayerMeasure, type PlayerSummary } from "./PlayerParts";

export interface SeasonPlayer extends PlayerSummary {
  id: number;
}

export interface SeasonHub {
  available: boolean;
  season: string;
  source: string;
  source_url: string;
  fetched?: string;
  /** Clubs imported so far: the free API plan brings in about 30 a day */
  clubs?: number | null;
  clubs_total?: number | null;
  regular_minutes?: number;
  featured?: { team_id: number; team: string; league: string; players: SeasonPlayer[] }[];
  best?: { league: string; team_id: number; team: string; player: SeasonPlayer }[];
}

export const seasonPlayerUrl = (teamId: number, playerId: number | string) => `/season/teams/${teamId}/players/${playerId}`;

/** "38 of 96 clubs imported so far", while the import is still under way; otherwise nothing */
export function soFar(hub: Pick<SeasonHub, "clubs" | "clubs_total">) {
  return hub.clubs != null && hub.clubs_total && hub.clubs < hub.clubs_total
    ? `${hub.clubs} of ${hub.clubs_total} clubs imported so far`
    : null;
}

export function SeasonSource({ hub }: { hub: Pick<SeasonHub, "source" | "source_url" | "fetched" | "season" | "clubs" | "clubs_total"> }) {
  const partial = soFar(hub);
  return (
    <p className="text-ink-2 text-xs">
      {hub.season} league numbers: <a className="underline" href={hub.source_url}>{hub.source}</a>
      {hub.fetched ? `, imported ${hub.fetched}` : ""}
      {partial ? ` (${partial})` : ""}. Season totals in league matches only. Per 90 from the minutes played; percentiles from 900 minutes.
    </p>
  );
}

const COLS: [keyof SeasonPlayer, string][] = [
  ["position", "Position"],
  ["age", "Age"],
  ["apps", "Apps"],
  ["minutes", "Minutes"],
  ["goals", "Goals"],
  ["assists", "Assists"],
  ["rating", "Rating"],
];

export function SeasonSquad() {
  const teamId = Number(useParams().teamId);
  const { data, error, loading, reload } = useApi<SeasonHub>("/api/pro/season");
  const [sort, setSort] = useState<keyof SeasonPlayer>("minutes");
  if (loading && !data) return <PageSkeleton label="Loading the squad" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const club = data.featured?.find((f) => f.team_id === teamId);
  if (!club) return <ErrorNote message="This club's 2024/25 squad is not in the data." />;
  const [c1, c2] = clubMeta(club.team).colors;
  const rows = [...club.players].sort((a, b) => {
    const x = a[sort] ?? -1;
    const y = b[sort] ?? -1;
    return typeof x === "string" || typeof y === "string" ? String(x).localeCompare(String(y)) : Number(y) - Number(x);
  });
  return (
    <div className="space-y-4">
      <PageHeader
        accent={c1 === "#ffffff" ? c2 : c1}
        eyebrow={
          <Link to="/players" className="hover:underline">
            ← Players, {data.season}
          </Link>
        }
        title={
          <>
            <span className="sr-only">Squad: </span>
            {club.team}
          </>
        }
        leading={<Crest name={club.team} size={64} className="drop-shadow-lg" />}
        subtitle={`${club.league} ${data.season} · ${club.players.length} players who played`}
      />
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-sm" aria-label={`${club.team} squad ${data.season}`}>
          <thead className="text-ink-2 text-left text-xs">
            <tr>
              <th className="p-3">Player</th>
              {COLS.map(([k, label]) => (
                <th key={k} className={cn("p-3", k !== "position" && "text-right")}>
                  <button className="font-semibold hover:underline" onClick={() => setSort(k)} aria-pressed={sort === k}>
                    {label}
                    {sort === k ? " ↓" : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--line)]">
            {rows.map((p) => (
              <tr key={p.id}>
                <td className="p-3 font-semibold whitespace-nowrap">
                  <Link to={seasonPlayerUrl(club.team_id, p.id)} className="hover:underline">
                    {p.name}
                  </Link>
                  {p.nationality && <span className="text-ink-2 block text-xs font-normal">{p.nationality}</span>}
                </td>
                <td className="p-3">{p.position}</td>
                <td className="num p-3 text-right">{p.age ?? "–"}</td>
                <td className="num p-3 text-right">{p.apps}</td>
                <td className="num p-3 text-right">{p.minutes.toLocaleString("en")}</td>
                <td className="num p-3 text-right font-bold">{p.goals}</td>
                <td className="num p-3 text-right">{p.assists}</td>
                <td className="num p-3 text-right">{p.rating?.toFixed(2) ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <SeasonSource hub={data} />
    </div>
  );
}

interface SeasonProfile extends SeasonPlayer {
  available: boolean;
  season: string;
  source: string;
  source_url: string;
  fetched?: string;
  team_id: number;
  team: string;
  league: string;
  totals: Record<string, number>;
  compared_with: string;
  no_percentiles: string | null;
  measures: PlayerMeasure[];
}

export function SeasonPlayerPage() {
  const { teamId = "", playerId = "" } = useParams();
  const { data: p, error, loading, reload } = useApi<SeasonProfile>(`/api/pro/season/teams/${encodeURIComponent(teamId)}/players/${encodeURIComponent(playerId)}`);
  if (loading && !p) return <PageSkeleton label="Loading the player" />;
  if (error || !p) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const [c1, c2] = clubMeta(p.team).colors;
  const t = p.totals;
  const per = (n: number) => (p.minutes ? ((90 * n) / p.minutes).toFixed(2) : "–");
  const keeper = p.position === "Goalkeeper";
  return (
    <div className="space-y-4">
      <PageHeader
        accent={c1 === "#ffffff" ? c2 : c1}
        eyebrow={
          <Link to="/players" className="hover:underline">
            ← Players, {p.season}
          </Link>
        }
        title={
          <>
            <span className="sr-only">Player analysis: </span>
            {p.name}
          </>
        }
        leading={<Crest name={p.team} size={64} className="drop-shadow-lg" />}
        subtitle={
          <span className="num">
            {p.team} · {p.position} · {p.league} {p.season}
            {p.age ? ` · age ${p.age}` : ""}
            {p.nationality ? ` · ${p.nationality}` : ""}
          </span>
        }
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Appearances" value={t.apps} sub={`${t.starts} starts, ${t.minutes.toLocaleString("en")} min`} />
        {keeper ? (
          <>
            <StatTile label="Saves" value={t.saves} sub={`${per(t.saves)} per 90`} />
            <StatTile label="Conceded" value={t.conceded} sub={`${per(t.conceded)} per 90`} />
          </>
        ) : (
          <>
            <StatTile label="Goals" value={t.goals} sub={t.pen_scored ? `${t.pen_scored} from penalties` : "no penalties"} />
            <StatTile label="Assists" value={t.assists} sub={`${per(t.assists)} per 90`} />
          </>
        )}
        <StatTile label="Shots" value={t.shots} sub={`${t.shots_on} on target`} />
        <StatTile label="Key passes" value={t.key_passes} sub={`${per(t.key_passes)} per 90`} />
        <StatTile label="Rating" value={p.rating?.toFixed(2) ?? "–"} sub="average per match" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <PercentileBars measures={p.measures} comparedWith={p.compared_with} none={p.no_percentiles} />
        <TotalsTable
          rows={[
            ["Appearances (starts)", `${t.apps} (${t.starts})`],
            ["Minutes", t.minutes.toLocaleString("en")],
            ["Goals", t.goals],
            ["Penalties scored / missed", `${t.pen_scored} / ${t.pen_missed}`],
            ["Assists", t.assists],
            ["Shots (on target)", `${t.shots} (${t.shots_on})`],
            ["Passes", t.passes],
            ["Key passes", t.key_passes],
            ["Dribbles (completed)", `${t.dribbles} (${t.dribbles_won})`],
            ["Duels (won)", `${t.duels} (${t.duels_won})`],
            ["Tackles", t.tackles],
            ["Interceptions", t.interceptions],
            ["Blocks", t.blocks],
            ["Fouls won / committed", `${t.fouls_drawn} / ${t.fouls}`],
            ["Yellow / red cards", `${t.yellow} / ${t.red}`],
            ...(keeper ? ([["Saves", t.saves], ["Goals conceded", t.conceded]] as [string, number][]) : []),
          ]}
        />
      </div>
      <SeasonSource hub={p} />
    </div>
  );
}
