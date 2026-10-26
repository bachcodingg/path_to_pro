// A competition's page: clubs, table and results for a full league; the one club and its
// results for a club season; the list of finals for the Champions League.
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Crest } from "../shared/Club";
import { PageHeader, Tabs } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { Card, ErrorNote, PageSkeleton } from "../shared/ui";
import { COMP_COLOR, usePro } from "./context";
import { LeagueTable } from "./LeagueTable";
import { Results, type MatchList } from "./Matches";
import { COVERAGE } from "./ProHome";
import type { TeamList } from "./TeamAnalysis";

export function CompetitionPage() {
  const { comp, base } = usePro();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const teams = useApi<TeamList>(`${base}/teams`);
  const matches = useApi<MatchList>(`${base}/matches`);
  if (teams.error) return <ErrorNote message={teams.error} onRetry={teams.reload} />;
  if (!teams.data) return <PageSkeleton label="Loading the competition" />;
  const c = teams.data.competition;
  const tabs = (
    c.coverage === "league"
      ? [
          ["clubs", "Clubs"],
          ["table", "Table"],
          ["results", "Results"],
        ]
      : c.coverage === "club"
        ? [
            ["clubs", "Club"],
            ["results", "Results"],
          ]
        : [["results", "Finals"]]
  ) as [string, string][];
  const tab = tabs.find(([k]) => k === params.get("tab"))?.[0] ?? tabs[0][0];
  const set = (k: string) => setParams(k === tabs[0][0] ? {} : { tab: k }, { replace: true });
  return (
    <div className="space-y-4">
      <PageHeader
        accent={COMP_COLOR[comp]}
        eyebrow={`${COVERAGE[c.coverage]} · ${teams.data.matches} matches`}
        title={`${c.name} ${c.season}`}
        subtitle={c.note}
        bottom={<Tabs label="Competition sections" items={tabs} value={tab} onChange={set} />}
      />
      {tab === "clubs" && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {teams.data.teams.map((t) => {
            const row = teams.data!.table?.find((x) => x.id === t.id);
            return (
              <Link key={t.id} to={`/pro/${comp}/teams/${t.id}`} className="group">
                <Card className="flex h-full flex-col items-center gap-2 p-4 text-center transition-shadow group-hover:shadow-md">
                  <Crest name={t.name} size={48} />
                  <span className="font-bold leading-tight">{t.name}</span>
                  <span className="text-ink-2 num text-xs">
                    {row ? `${row.position}. · ${row.points} pts` : `${t.matches} matches`}
                  </span>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
      {tab === "table" && (
        <LeagueTable tables={teams.data} highlight="" onPick={(id) => navigate(`/pro/${comp}/teams/${id}`)} />
      )}
      {tab === "results" &&
        (matches.data ? <Results data={matches.data} /> : matches.error ? <ErrorNote message={matches.error} onRetry={matches.reload} /> : <PageSkeleton />)}
    </div>
  );
}
