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
  const pickTeam = (id: string) => navigate(`/pro/${comp}/teams/${id}${params.size ? `?${params}` : ""}`);

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
  return (
    <div className="space-y-4">
      <PageHeader
        accent={c1 === "#ffffff" ? c2 : c1}
        eyebrow={
          c && (
            <Link to={`/pro/${comp}`} className="hover:underline">
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
        leading={name && <Crest name={name} size={64} className="drop-shadow-lg" />}
        subtitle={
          standing && (
            <span className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
              {standing.position != null && (
                <span>
                  <span className="font-display text-2xl font-bold text-white">{ordinal(standing.position)}</span> in the league
                </span>
              )}
              <span>
                <span className="font-display text-2xl font-bold text-white">{standing.points}</span> pts
              </span>
              <span className="num">
                W{standing.won} D{standing.drawn} L{standing.lost} · goals {standing.gf}-{standing.ga}
              </span>
              {standing.form && <FormGuide form={standing.form} />}
            </span>
          )
        }
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
            {!league && c && <p className="mb-3 max-w-3xl text-sm text-white/80">{c.note}</p>}
            {versus && (
              <p className="mb-3 flex flex-wrap items-center gap-2 text-sm text-white/80">
                <span className="font-display text-base font-bold tracking-wide text-white uppercase">vs</span>
                <Crest name={versus.team} size={22} />
                <span className="font-semibold text-white">{versus.team}</span>
                {versus.standing.position != null && `${ordinal(versus.standing.position)}, `}
                {versus.standing.points} pts · shown as rings on the bars and "vs" numbers
                <button className="tap ml-1 underline" onClick={() => set("vs", null)}>
                  Clear
                </button>
              </p>
            )}
            <Tabs label="Analysis sections" items={tabs} value={tab} onChange={(k) => set("tab", k === "overview" ? null : k)} />
          </>
        }
      />

      {/* The league sites' club strip: every club's badge, one click to switch */}
      {table.length > 1 && (
        <nav aria-label="Clubs" className="no-scrollbar -mt-1 flex gap-1 overflow-x-auto pb-1">
          {table.map((t) => (
            <button
              key={t.id}
              onClick={() => pickTeam(t.id)}
              aria-label={t.team}
              aria-current={t.id === teamId ? "page" : undefined}
              title={t.team}
              className={cn(
                "tap flex shrink-0 flex-col items-center justify-center rounded-lg px-1.5 py-1 transition",
                t.id === teamId ? "bg-surface border-line border shadow-sm" : "opacity-70 hover:opacity-100",
              )}
            >
              <Crest name={t.team} size={28} />
            </button>
          ))}
        </nav>
      )}

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
          <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
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
        {league ? " (the other teams)" : " in the same matches"}. Club badges are drawn from club colours, not the clubs' crests.
        Definitions: docs/team-analysis.md.
      </p>
    </div>
  );
}
