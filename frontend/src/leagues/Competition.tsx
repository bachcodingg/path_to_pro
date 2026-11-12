// A competition's page. A full league opens on its overview: the club strip, the table and
// the season at a glance beside the latest matchday; then the table, results and clubs each
// on a tab. One club's season shows the club and its results; the Champions League its finals.
import { ArrowRight, CalendarDays, Shield, Trophy } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Crest, FormGuide } from "../shared/Club";
import { PageHeader, Tabs } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { ErrorNote, PageSkeleton, Skeleton } from "../shared/ui";
import { COMP_COLOR, usePro } from "./context";
import { LeagueTable } from "./LeagueTable";
import { MatchCard, Results, type MatchList } from "./Matches";
import { COVERAGE } from "./ProHome";
import type { TeamList } from "./TeamAnalysis";
import type { Standing } from "./types";
import { CompMark, Fact, Label, Panel } from "./ui";

export function CompetitionPage() {
  const { comp, base } = usePro();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const teams = useApi<TeamList>(`${base}/teams`);
  const matches = useApi<MatchList>(`${base}/matches`);
  if (teams.error) return <ErrorNote message={teams.error} onRetry={teams.reload} />;
  if (!teams.data) return <PageSkeleton label="Loading the competition" />;
  const c = teams.data.competition;
  const table = teams.data.table ?? [];
  const tabs = (
    c.coverage === "league"
      ? [
          ["overview", "Overview"],
          ["table", "Table"],
          ["results", "Results"],
          ["clubs", "Clubs"],
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
  const open = (id: string) => navigate(`/${comp}/teams/${id}`);
  const goals = table.reduce((n, t) => n + t.gf, 0);
  return (
    <div className="space-y-4 md:space-y-5">
      <PageHeader
        accent={COMP_COLOR[comp]}
        leading={<CompMark id={comp} name={c.name} color={COMP_COLOR[comp] ?? "#1597d0"} size={56} />}
        eyebrow={<span className="lg-label !text-white/85">{COVERAGE[c.coverage]}</span>}
        title={
          <>
            {c.name} <span className="text-pitch-300">{c.season}</span>
          </>
        }
        subtitle={c.note}
        bottom={
          <>
            <div className="mb-3 flex flex-wrap gap-x-8 gap-y-3 border-t border-white/20 pt-3 md:gap-x-12">
              <Fact label="Matches">{teams.data.matches}</Fact>
              {c.coverage !== "finals" && <Fact label={teams.data.teams.length === 1 ? "Club" : "Clubs"}>{teams.data.teams.length}</Fact>}
              {goals > 0 && (
                <>
                  <Fact label="Goals">{goals}</Fact>
                  <Fact label="Goals a match">{(goals / teams.data.matches).toFixed(2)}</Fact>
                </>
              )}
              {table[0]?.position === 1 && (
                <Fact label="Top of the table">
                  <span className="flex items-center gap-2">
                    <Crest name={table[0].team} size={24} />
                    <span className="text-xl md:text-2xl">{table[0].team}</span>
                  </span>
                </Fact>
              )}
            </div>
            <Tabs label="Competition sections" items={tabs} value={tab} onChange={set} />
          </>
        }
      />

      {tab === "overview" && (
        <>
          <ClubStrip table={table} comp={comp} />
          <div className="grid items-start gap-4 md:gap-5 xl:grid-cols-[minmax(0,1fr)_24rem]">
            <LeagueTable tables={teams.data} highlight="" onPick={open} />
            <div className="space-y-4 md:space-y-5">
              <SeasonLeaders table={table} comp={comp} />
              <LatestMatchday matches={matches.data} onAll={() => set("results")} />
            </div>
          </div>
        </>
      )}
      {tab === "clubs" && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {teams.data.teams.map((t) => {
            const row = table.find((x) => x.id === t.id);
            return (
              <Link key={t.id} to={`/${comp}/teams/${t.id}`} className="lg-panel group hover:border-pitch-500 flex flex-col items-center gap-2 p-4 text-center transition-[border-color,box-shadow] hover:shadow-md">
                <Crest name={t.name} size={52} />
                <span className="leading-tight font-extrabold">{t.name}</span>
                {row?.position != null ? (
                  <span className="text-ink-2 num flex items-center gap-2 text-xs font-semibold">
                    <span className="bg-[#0b1230] font-display rounded px-1.5 py-0.5 text-[13px] leading-none font-extrabold text-white">{row.position}</span>
                    {row.points} pts
                  </span>
                ) : (
                  <span className="text-ink-2 num text-xs font-semibold">{t.matches} matches</span>
                )}
                {row?.form && <FormGuide form={row.form} />}
              </Link>
            );
          })}
        </div>
      )}
      {tab === "table" && <LeagueTable tables={teams.data} highlight="" onPick={open} />}
      {tab === "results" &&
        (matches.data ? <Results data={matches.data} /> : matches.error ? <ErrorNote message={matches.error} onRetry={matches.reload} /> : <PageSkeleton />)}
    </div>
  );
}

// Every club's badge in table order: one tap to a club
function ClubStrip({ table, comp }: { table: Standing[]; comp: string }) {
  return (
    <nav aria-label="Clubs" className="lg-panel no-scrollbar flex items-center gap-0.5 overflow-x-auto px-2 py-1.5 md:justify-between">
      {table.map((t) => (
        <Link key={t.id} to={`/${comp}/teams/${t.id}`} aria-label={t.team} title={t.team} className="tap hover:bg-surface-2 flex shrink-0 items-center justify-center rounded-md px-1.5 transition-colors">
          <Crest name={t.team} size={30} />
        </Link>
      ))}
    </nav>
  );
}

// The season in three lines: who is top, who scores most, who concedes least
function SeasonLeaders({ table, comp }: { table: Standing[]; comp: string }) {
  if (!table.length) return null;
  const attack = table.slice().sort((a, b) => b.gf - a.gf)[0];
  const defence = table.slice().sort((a, b) => a.ga - b.ga)[0];
  const rows: [string, Standing, string, string][] = [
    ["Top of the table", table[0], String(table[0].points), "pts"],
    ["Most goals", attack, String(attack.gf), "scored"],
    ["Fewest conceded", defence, String(defence.ga), "conceded"],
  ];
  return (
    <Panel title="Season at a glance" icon={Trophy} bodyClassName="p-0">
      <ul className="divide-line divide-y">
        {rows.map(([label, t, value, unit]) => (
          <li key={label}>
            <Link to={`/${comp}/teams/${t.id}`} className="hover:bg-surface-2 flex items-center gap-3 px-4 py-2.5 transition-colors">
              <Crest name={t.team} size={34} />
              <span className="min-w-0 flex-1">
                <Label className="block">{label}</Label>
                <span className="block truncate font-extrabold">{t.team}</span>
              </span>
              <span className="text-right">
                <span className="font-display num block text-2xl leading-none font-extrabold">{value}</span>
                <span className="text-ink-2 text-xs">{unit}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function LatestMatchday({ matches, onAll }: { matches: MatchList | null; onAll: () => void }) {
  const week = matches ? Math.max(0, ...matches.matches.map((m) => m.week ?? 0)) : 0;
  const list = matches?.matches.filter((m) => m.week === week) ?? [];
  return (
    <Panel
      title={week ? `Matchday ${week}` : "Latest results"}
      icon={week ? CalendarDays : Shield}
      bodyClassName="space-y-2.5 bg-surface-2/50 p-3"
      action={
        <button className="tap text-pitch-600 -my-2 flex items-center gap-1 text-sm font-bold hover:underline" onClick={onAll}>
          All results <ArrowRight className="h-4 w-4" aria-hidden />
        </button>
      }
    >
      {!matches ? (
        <>
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </>
      ) : (
        list.map((m) => <MatchCard key={m.id} m={m} />)
      )}
    </Panel>
  );
}
