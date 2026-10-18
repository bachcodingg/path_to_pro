// A match the player's team played: line-up on the pitch with everyone's rating, like a
// ratings app. The player is ringed in gold; tap anyone for their stats.
import { Link, useParams } from "react-router-dom";
import { MatchLineup, type LineupRow } from "../coach/MatchLineup";
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
      <div>
        <h1 className="text-xl font-extrabold">
          {data.match.team} vs {data.match.opponent}
        </h1>
        <p className="text-ink-2 text-sm">
          {fmtDay(data.match.date, { weekday: "long", day: "numeric", month: "long" })} · {data.match.competition ?? ""}
        </p>
      </div>
      <MatchLineup rows={data.players} me={data.me} />
    </div>
  );
}
