// Team analysis: how an opponent plays, from real match events (StatsBomb Open Data).
// Tabs: overview, attack, passing, duels, defending, set pieces, players; optional comparison team.
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useApi } from "../../shared/useApi";
import { ErrorNote, Spinner, cn } from "../../shared/ui";
import { Players } from "./Players";
import { SetPieces, type Source, type TeamRow } from "./SetPieces";
import { ShotMap } from "./ShotMap";
import { MeasureList, Overview } from "./Style";
import type { Standing, StyleProfile } from "./types";

const DEFAULT_TEAM = "real-madrid";
const TABS = [
  ["overview", "Overview"],
  ["attack", "Attack"],
  ["passing", "Passing"],
  ["duels", "Duels & headers"],
  ["defending", "Defending"],
  ["set-pieces", "Set pieces"],
  ["players", "Players"],
] as const;
type Tab = (typeof TABS)[number][0];

export function TeamAnalysis() {
  const { teamId = DEFAULT_TEAM } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const tab = (TABS.find(([k]) => k === params.get("tab"))?.[0] ?? "overview") as Tab;
  const vsId = params.get("vs");
  const list = useApi<Source & { teams: TeamRow[]; table: Standing[] }>("/api/coach/analysis/teams");
  const style = useApi<StyleProfile>(`/api/coach/analysis/teams/${encodeURIComponent(teamId)}/style`);
  const vs = useApi<StyleProfile>(vsId && vsId !== teamId ? `/api/coach/analysis/teams/${encodeURIComponent(vsId)}/style` : null);

  function set(key: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }
  const pickTeam = (id: string) => navigate(`/coach/analysis/${id}${params.size ? `?${params}` : ""}`);

  if (list.error) return <ErrorNote message={list.error} onRetry={list.reload} />;
  const teams = list.data?.teams ?? [];
  const p = style.data;
  const versus = vsId && vsId !== teamId ? vs.data : null;
  return (
    <div className="max-w-6xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-2xl">
          <h1 className="text-2xl font-extrabold">Team analysis</h1>
          <p className="text-ink-2 text-sm">
            How an opponent plays, from every event of real matches
            {list.data && ` (${list.data.competition} ${list.data.season}, ${list.data.matches} matches)`}. Each number is
            compared with the rest of the league and ranked; it is only called a strength, weakness or habit when the gap is
            bigger than match-to-match chance.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <label className="text-sm font-semibold">
            Team{" "}
            <select aria-label="Team" className="bg-surface ml-1 rounded-lg border border-line px-3 py-2" value={teamId} onChange={(e) => pickTeam(e.target.value)}>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-semibold">
            Compare with{" "}
            <select aria-label="Compare with" className="bg-surface ml-1 rounded-lg border border-line px-3 py-2" value={vsId ?? ""} onChange={(e) => set("vs", e.target.value || null)}>
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
        </div>
      </div>

      <div role="tablist" aria-label="Analysis sections" className="flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => set("tab", key === "overview" ? null : key)}
            className={cn(
              "tap -mb-px shrink-0 border-b-2 px-3 py-2 text-sm font-semibold",
              tab === key ? "border-pitch-600 text-ink" : "text-ink-2 border-transparent hover:text-ink",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={TABS.find(([k]) => k === tab)?.[1]}>
        {tab === "set-pieces" ? (
          <SetPieces teamId={teamId} />
        ) : tab === "players" ? (
          <Players teamId={teamId} />
        ) : style.loading && !p ? (
          <Spinner label="Reading match events" />
        ) : style.error || !p ? (
          <ErrorNote message={style.error ?? "No data"} onRetry={style.reload} />
        ) : tab === "overview" ? (
          <Overview p={p} vs={versus} table={list.data?.table ?? []} onPick={pickTeam} />
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
        used under StatsBomb's open-data terms. Definitions: docs/team-analysis.md.
      </p>
    </div>
  );
}
