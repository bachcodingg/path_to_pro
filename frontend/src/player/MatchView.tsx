// A match the player's team played: line-up on the pitch with everyone's rating, like a
// ratings app. The player is ringed in gold; tap anyone for their stats.
import { Link, useParams } from "react-router-dom";
import { MatchLineup, type LineupRow } from "../coach/MatchLineup";
import { Crest } from "../shared/Club";
import { useApi } from "../shared/useApi";
import { ErrorNote, Spinner, fmtDay } from "../shared/ui";

interface PlayerMatch {
  match: { id: string; date: string; opponent: string; team: string; competition: string | null };
  players: LineupRow[];
  me: string;
}

export function MatchView() {
  const { id } = useParams();
  const { data, error, loading, reload } = useApi<PlayerMatch>(`/api/me/matches/${id}`);
  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  return (
    <div className="space-y-3 pt-2">
      <Link to="/player/career" className="text-pitch-300 text-sm font-semibold">
        ← My career
      </Link>
      {/* Match-centre header: both badges either side of the date */}
      <div className="bg-surface border-line rounded-2xl border p-4">
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 text-center">
          <span className="flex flex-col items-center gap-1.5">
            <Crest name={data.match.team} size={44} />
            <span className="text-sm leading-tight font-semibold">{data.match.team}</span>
          </span>
          <span className="font-display text-2xl font-bold text-ink-2 uppercase">vs</span>
          <span className="flex flex-col items-center gap-1.5">
            <Crest name={data.match.opponent} size={44} />
            <span className="text-sm leading-tight font-semibold">{data.match.opponent}</span>
          </span>
        </div>
        <h1 className="sr-only">
          {data.match.team} vs {data.match.opponent}
        </h1>
        <p className="text-ink-2 mt-3 text-center text-sm">
          {fmtDay(data.match.date, { weekday: "long", day: "numeric", month: "long" })} · {data.match.competition ?? ""}
        </p>
      </div>
      <MatchLineup rows={data.players} me={data.me} />
    </div>
  );
}
