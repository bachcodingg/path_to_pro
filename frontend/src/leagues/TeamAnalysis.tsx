// A club's page in the pro-league section: how the team plays, from real match events
// (StatsBomb Open Data). Laid out like a league website's club page: a strip of club badges
// to switch team, a header in the club's colours with its record and form, then the
// sections as tabs. For one club's season (Bundesliga: Leverkusen) the club is compared with
// its opponents and there is no table, ranking or second team to compare.
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Crest, FormGuide, clubMeta } from "../shared/Club";
import { PageHeader, Tabs } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { ErrorNote, PageSkeleton, cn } from "../shared/ui";
import { Fact } from "./ui";
import { usePro, type Competition } from "./context";
import { LeagueTable, type Tables } from "./LeagueTable";
import { Players } from "./Players";
import { SetPieces, type Source, type TeamRow } from "./SetPieces";
import { ShotMap } from "./ShotMap";
import { MeasureList, Overview } from "./Style";
import { ordinal, type StyleProfile } from "./types";

const TABS = [
  ["overview", "Overview"],
  ["attack", "Attack"],
  ["passing", "Passing"],
  ["duels", "Duels & headers"],
  ["defending", "Defending"],
  ["set-pieces", "Set pieces"],
  ["players", "Players"],
  ["table", "Table"],
] as const;
type Tab = (typeof TABS)[number][0];

export type TeamList = Source & Tables & { teams: TeamRow[]; competition: Competition };

export function TeamAnalysis() {
  const { teamId = "" } = useParams();
  const { comp, base, label } = usePro();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const list = useApi<TeamList>(`${base}/teams`);
  const style = useApi<StyleProfile>(`${base}/teams/${encodeURIComponent(teamId)}/style`);
  const league = list.data?.competition.coverage !== "club";
  const tabs = TABS.filter(([k]) => league || k !== "table");
  const tab = (tabs.find(([k]) => k === params.get("tab"))?.[0] ?? "overview") as Tab;
  const vsId = league ? params.get("vs") : null;
  const vs = useApi<StyleProfile>(vsId && vsId !== teamId ? `${base}/teams/${encodeURIComponent(vsId)}/style` : null);

  function set(key: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }
  const pickTeam = (id: string) => navigate(`/${comp}/teams/${id}${params.size ? `?${params}` : ""}`);

  if (list.error) return <ErrorNote message={list.error} onRetry={list.reload} />;
  const teams = list.data?.teams ?? [];
  const table = list.data?.table ?? [];
  const p = style.data;
  const versus = vsId && vsId !== teamId ? vs.data : null;
  const name = p?.team ?? teams.find((t) => t.id === teamId)?.name ?? "";
  const standing = table.find((t) => t.id === teamId) ?? p?.standing;
  const [c1, c2] = clubMeta(name).colors;
  const field = "rounded-lg border px-3 py-2 text-sm font-semibold";
  const c = list.data?.competition;
  const goalDiff = standing ? standing.gf - standing.ga : 0;
  return (
    <div className="space-y-4 md:space-y-5">
      <div>
        {/* The league sites' club bar: every club's badge in table order, one tap to switch */}
        {table.length > 1 && (
          <nav aria-label="Clubs" className="bg-surface border-line no-scrollbar -mx-4 -mt-4 flex gap-0.5 overflow-x-auto border-b px-2 md:-mx-6 md:-mt-6 md:justify-center md:px-4">
            {table.map((t) => (
              <button
                key={t.id}
                onClick={() => pickTeam(t.id)}
                aria-label={t.team}
                aria-current={t.id === teamId ? "page" : undefined}
                title={t.team}
                className={cn(
                  "tap relative flex shrink-0 items-center justify-center px-2 py-1.5 transition",
                  t.id === teamId ? "bg-surface-2" : "opacity-75 hover:opacity-100",
                )}
              >
                <Crest name={t.team} size={28} />
                {t.id === teamId && <span className="bg-pitch-500 absolute inset-x-0 bottom-0 h-[3px]" aria-hidden />}
              </button>
            ))}
          </nav>
        )}
        <PageHeader
          className={table.length > 1 ? "mt-0 mb-0 md:mt-0 md:mb-0" : "mb-0 md:mb-0"}
          accent={c1 === "#ffffff" ? c2 : c1}
          eyebrow={
            c && (
              <Link to={`/${comp}`} className="hover:underline">
                ← {c.name} {c.season}
              </Link>
            )
          }
          title={
            <>
              <span className="sr-only">Team analysis: </span>
              {name}
            </>
          }
          leading={name && <Crest name={name} size={72} className="drop-shadow-lg" />}
          actions={
            league && (
              <>
                <label className="flex items-center gap-2 text-sm font-semibold">
                  Team
                  <select aria-label="Team" className={field} value={teamId} onChange={(e) => pickTeam(e.target.value)}>
                    {teams.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex items-center gap-2 text-sm font-semibold">
                  Compare with
                  <select aria-label="Compare with" className={field} value={vsId ?? ""} onChange={(e) => set("vs", e.target.value || null)}>
                    <option value="">No comparison</option>
                    {teams
                      .filter((t) => t.id !== teamId)
                      .map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                  </select>
                </label>
              </>
            )
          }
          bottom={
            <>
              {!league && c && <p className="mb-3 max-w-3xl text-sm text-white/95">{c.note}</p>}
              {standing && (
                <div className="mb-3 flex flex-wrap items-end gap-x-8 gap-y-3 border-t border-white/20 pt-3 md:gap-x-12">
                  {standing.position != null && <Fact label="League position">{ordinal(standing.position)}</Fact>}
                  <Fact label="Points">{standing.points}</Fact>
                  <Fact label="Record">
                    W{standing.won} D{standing.drawn} L{standing.lost}
                  </Fact>
                  <Fact label="Goals">
                    {standing.gf}:{standing.ga}{" "}
                    <span className="text-base font-bold text-white/85">
                      ({goalDiff > 0 ? "+" : ""}
                      {goalDiff})
                    </span>
                  </Fact>
                  {standing.form && (
                    <div>
                      <span className="lg-label mb-1 block !text-white/80">Form</span>
                      <FormGuide form={standing.form} size="md" />
                    </div>
                  )}
                </div>
              )}
              {versus && (
                <p className="mb-3 flex flex-wrap items-center gap-2 text-sm text-white/95">
                  <span className="font-display rounded bg-white px-1.5 py-0.5 text-xs leading-none font-black text-[#0c1a3d]">VS</span>
                  <Crest name={versus.team} size={22} />
                  <span className="font-semibold text-white">{versus.team}</span>
                  {versus.standing.position != null && `${ordinal(versus.standing.position)}, `}
                  {versus.standing.points} pts · shown as gold rings on the bars and "vs" numbers
                  <button className="tap ml-1 underline" onClick={() => set("vs", null)}>
                    Clear
                  </button>
                </p>
              )}
              <Tabs label="Analysis sections" items={tabs} value={tab} onChange={(k) => set("tab", k === "overview" ? null : k)} />
            </>
          }
        />
      </div>

      <div role="tabpanel" aria-label={tabs.find(([k]) => k === tab)?.[1]}>
        {tab === "set-pieces" ? (
          <SetPieces teamId={teamId} />
        ) : tab === "players" ? (
          <Players teamId={teamId} />
        ) : tab === "table" ? (
          list.data && <LeagueTable tables={list.data} highlight={teamId} compare={versus?.id} onPick={pickTeam} />
        ) : style.loading && !p ? (
          <PageSkeleton label="Reading match events" />
        ) : style.error || !p ? (
          <ErrorNote message={style.error ?? "No data"} onRetry={style.reload} />
        ) : tab === "overview" ? (
          <Overview p={p} vs={versus} table={table} onPick={pickTeam} onTable={() => set("tab", "table")} />
        ) : tab === "attack" ? (
          <div className="grid items-start gap-4 md:gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <ShotMap teamId={teamId} />
            <MeasureList p={p} vs={versus} groups={["shooting"]} />
          </div>
        ) : tab === "passing" ? (
          <MeasureList p={p} vs={versus} groups={["passing"]} />
        ) : tab === "duels" ? (
          <MeasureList p={p} vs={versus} groups={["duels"]} />
        ) : (
          <MeasureList p={p} vs={versus} groups={["defending", "discipline"]} />
        )}
      </div>

      <p className="text-ink-2 text-xs">
        Data: <a className="underline" href={list.data?.source_url ?? "https://github.com/statsbomb/open-data"}>StatsBomb Open Data</a>,
        used under StatsBomb's open-data terms. Numbers are compared with the {label}
        {league ? " (the other teams)" : " in the same matches"}. Crests: the free ones kept in the app, the others from Wikipedia (Club crests on the Pro League home page).
        Definitions: docs/team-analysis.md.
      </p>
    </div>
  );
}
