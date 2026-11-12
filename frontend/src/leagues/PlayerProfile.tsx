// One player's season from real match events (StatsBomb Open Data): headline numbers, how his
// per-90 numbers rank among the league's regulars in his position, every shot he took, and
// the season totals. In a club season (one club's matches only) there is no fair comparison
// group, so the page says so instead of ranking him.
import { Link, useParams } from "react-router-dom";
import { Crest, clubMeta } from "../shared/Club";
import { PageHeader } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { ErrorNote, PageSkeleton, StatTile } from "../shared/ui";
import { PercentileBars, TotalsTable, type PlayerMeasure, type PlayerSummary } from "./PlayerParts";
import { PlayerShotMap } from "./ShotMap";

interface Profile extends PlayerSummary {
  comp: string;
  competition: string;
  season: string;
  coverage: string;
  team: string;
  team_id: string;
  totals: Record<string, number | null>;
  compared_with: string | null;
  no_percentiles: string | null;
  measures: PlayerMeasure[];
  shot_columns: string[];
  shots: (string | number | boolean)[][];
}

export function PlayerProfile() {
  const { comp = "", teamId = "", playerId = "" } = useParams();
  const { data: p, error, loading, reload } = useApi<Profile>(
    `/api/pro/${encodeURIComponent(comp)}/teams/${encodeURIComponent(teamId)}/players/${encodeURIComponent(playerId)}`,
  );
  if (loading && !p) return <PageSkeleton label="Loading the player" />;
  if (error || !p) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const [c1, c2] = clubMeta(p.team).colors;
  const t = p.totals;
  const per = (n: number | null | undefined) => (n == null || p.minutes < 1 ? "–" : ((90 * n) / p.minutes).toFixed(2));
  return (
    <div className="space-y-4">
      <PageHeader
        accent={c1 === "#ffffff" ? c2 : c1}
        eyebrow={
          <Link to={`/${p.comp}/teams/${p.team_id}?tab=players`} className="hover:underline">
            ← {p.team} squad, {p.competition} {p.season}
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
            {p.position ?? "Position not recorded"} · {p.matches} matches · {p.minutes.toLocaleString("en")} minutes
          </span>
        }
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Goals" value={t.goals} sub={t.pen_goals ? `${t.pen_goals} from penalties` : "no penalties"} />
        <StatTile label="Assists" value={t.assists} sub={`${per(t.assists)} per 90`} />
        <StatTile label="xG" value={t.xg?.toFixed(1)} sub={`${t.np_xg?.toFixed(1)} without penalties`} />
        <StatTile label="Shots" value={t.shots} sub={`${t.shots_on_target} on target`} />
        <StatTile label="Key passes" value={t.key_passes} sub={`${per(t.key_passes)} per 90`} />
        <StatTile label="Pass accuracy" value={t.pass_acc == null ? "–" : `${t.pass_acc}%`} sub={`${t.passes} passes`} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <PercentileBars measures={p.measures} comparedWith={p.compared_with} none={p.no_percentiles} />
        {p.shots.length > 0 ? (
          <PlayerShotMap name={p.name} columns={p.shot_columns} rows={p.shots} />
        ) : (
          <TotalsTable rows={totalRows(t)} />
        )}
      </div>
      {p.shots.length > 0 && <TotalsTable rows={totalRows(t)} />}
      <p className="text-ink-2 text-xs">
        Data: <a className="underline" href="https://github.com/statsbomb/open-data">StatsBomb Open Data</a>, every event of the matches in the data.
        Per-90 numbers from 450 minutes; percentiles from 900.
      </p>
    </div>
  );
}

function totalRows(t: Record<string, number | null>): [string, string | number | null][] {
  return [
    ["Goals", t.goals],
    ["Penalties scored", t.pen_goals],
    ["Headed goals", t.head_goals],
    ["Goals from outside the box", t.out_goals],
    ["xG", t.xg],
    ["Shots (on target)", `${t.shots} (${t.shots_on_target})`],
    ["Assists", t.assists],
    ["Key passes", t.key_passes],
    ["Passes", t.passes],
    ["Pass accuracy", t.pass_acc == null ? null : `${t.pass_acc}%`],
    ["Dribbles completed", t.dribbles],
    ["Tackles", t.tackles],
    ["Interceptions", t.interceptions],
    ["Aerial duels won", t.aerial_won],
    ["Yellow cards", t.yellow],
    ["Red cards", t.red],
  ];
}
