// Pro player analysis, the Pro League app's player section. Two sources, as tabs:
// - 2024/25 season (API-Football season totals): the featured clubs' squads as they are now,
//   Bayern included, and the best player of every other club in the five leagues.
// - Match events (StatsBomb Open Data): the featured clubs' squads in the seasons the free
//   event data has (2015/16, and PSG 2021-23), with shot maps; the best player of every other club.
// "Best" is the same plain rule in both: the most goals plus assists among players with 900+
// minutes, more minutes breaking a tie.
import { ArrowRight } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Crest } from "../shared/Club";
import { PageHeader, Tabs } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { Card, ErrorNote, PageSkeleton } from "../shared/ui";
import { PlayerLine, type PlayerSummary } from "./PlayerParts";
import { SeasonSource, seasonPlayerUrl, soFar, type SeasonHub } from "./Season";

interface EventsHub {
  regular_minutes: number;
  featured: { comp: string; competition: string; season: string; coverage: string; team: string; team_id: string; players: PlayerSummary[] }[];
  best: { comp: string; competition: string; season: string; team: string; team_id: string; player: PlayerSummary }[];
  not_in_open_data: { team: string; why: string }[];
}

const VIEWS = [
  ["season", "2024/25 season"],
  ["events", "Match events"],
] as const;
type View = (typeof VIEWS)[number][0];

export function PlayersHub() {
  const [params, setParams] = useSearchParams();
  const season = useApi<SeasonHub>("/api/pro/season");
  const view: View = (params.get("view") as View) ?? (season.data && !season.data.available ? "events" : "season");
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Pro player analysis"
        title="Players"
        subtitle="Full squads of Real Madrid, Barcelona, PSG, Manchester City, Manchester United, Chelsea, Liverpool, Arsenal and Bayern, and the best player of every other club."
        bottom={<Tabs items={VIEWS} value={view} onChange={(v) => setParams({ view: v }, { replace: true })} label="Data" />}
      />
      {view === "season" ? <SeasonView hub={season} /> : <EventsView />}
    </div>
  );
}

function SquadCard({ team, label, players, to, playerTo }: { team: string; label: string; players: PlayerSummary[]; to: string; playerTo: (p: PlayerSummary) => string }) {
  return (
    <Card className="flex flex-col p-0">
      <Link to={to} className="hover:bg-surface-2 flex items-center gap-3 rounded-t-lg p-4">
        <Crest name={team} size={44} />
        <span className="min-w-0 flex-1">
          <span className="font-display block truncate text-xl leading-tight font-bold">{team}</span>
          <span className="text-ink-2 block text-sm">{label}</span>
        </span>
        <span className="text-pitch-600 flex shrink-0 items-center gap-1 text-sm font-semibold">
          {players.length} players <ArrowRight className="h-4 w-4" aria-hidden />
        </span>
      </Link>
      <ul className="border-line divide-y divide-[color:var(--line)] border-t">
        {players.slice(0, 4).map((p) => (
          <li key={p.id}>
            <PlayerLine to={playerTo(p)} team={team} p={p} sub={`${p.position ?? ""} · ${p.minutes.toLocaleString("en")} min`} />
          </li>
        ))}
      </ul>
    </Card>
  );
}

function BestOfTheRest({ groups }: { groups: [string, { key: string; team: string; to: string; p: PlayerSummary }[]][] }) {
  return (
    <section aria-labelledby="best-title" className="space-y-3">
      <div>
        <h2 id="best-title" className="font-display text-2xl font-bold">
          Best of the rest
        </h2>
        <p className="text-ink-2 text-sm">One player per club: the most goals plus assists among players with 900+ minutes.</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {groups.map(([title, rows]) => (
          <Card key={title} className="p-0">
            <h3 className="border-line border-b px-3 py-2 font-bold">{title}</h3>
            <ul className="divide-y divide-[color:var(--line)]">
              {rows.map((r) => (
                <li key={r.key}>
                  <PlayerLine to={r.to} team={r.team} p={r.p} />
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </section>
  );
}

function group<T>(rows: T[], key: (r: T) => string): [string, T[]][] {
  const out = new Map<string, T[]>();
  for (const r of rows) out.set(key(r), [...(out.get(key(r)) ?? []), r]);
  return [...out.entries()];
}

function SeasonView({ hub }: { hub: { data: SeasonHub | null; error: string | null; loading: boolean; reload: () => void } }) {
  const { data, error, loading, reload } = hub;
  if (loading && !data) return <PageSkeleton label="Loading the 2024/25 season" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  if (!data.available)
    return (
      <Card className="space-y-2">
        <h2 className="font-display text-xl font-bold">The 2024/25 numbers are not imported on this server yet</h2>
        <p className="text-ink-2 text-sm">
          They come from API-Football, which needs a key. Whoever runs this server imports them once with{" "}
          <code className="bg-surface-2 rounded px-1">python -m scouting.apifootball</code> (backend/scouting/apifootball.py explains how). Until then, the match-event
          analysis has full squads from the seasons in the free event data.
        </p>
        <Link to="/players?view=events" className="text-pitch-600 inline-flex items-center gap-1 font-semibold hover:underline">
          Open the match-event analysis <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      </Card>
    );
  return (
    <>
      {soFar(data) && (
        <p className="text-ink-2 text-sm">
          {soFar(data)}: the free API plan allows about 30 clubs a day, so the rest of the clubs and their best players
          follow. Percentiles compare with the players imported so far.
        </p>
      )}
      <section aria-label="Featured squads" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.featured?.map((f) => (
          <SquadCard
            key={f.team_id}
            team={f.team}
            label={`${f.league} ${data.season}`}
            players={f.players}
            to={`/season/teams/${f.team_id}`}
            playerTo={(p) => seasonPlayerUrl(f.team_id, p.id)}
          />
        ))}
      </section>
      <BestOfTheRest
        groups={group(data.best ?? [], (b) => b.league).map(([league, rows]) => [
          `${league} ${data.season}`,
          rows.map((b) => ({ key: String(b.team_id), team: b.team, to: seasonPlayerUrl(b.team_id, b.player.id), p: b.player })),
        ])}
      />
      <SeasonSource hub={data} />
    </>
  );
}

function EventsView() {
  const { data, error, loading, reload } = useApi<EventsHub>("/api/pro/players");
  if (loading && !data) return <PageSkeleton label="Loading the players" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const profile = (comp: string, teamId: string, p: PlayerSummary) => `/${comp}/teams/${teamId}/players/${p.id}`;
  return (
    <>
      <section aria-label="Featured squads" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.featured.map((f) => (
          <SquadCard
            key={`${f.comp}-${f.team_id}`}
            team={f.team}
            label={`${f.competition} ${f.season}`}
            players={f.players}
            to={`/${f.comp}/teams/${f.team_id}?tab=players`}
            playerTo={(p) => profile(f.comp, f.team_id, p)}
          />
        ))}
        {data.not_in_open_data.map((n) => (
          <Card key={n.team} className="flex items-start gap-3">
            <Crest name={n.team} size={44} />
            <div>
              <p className="font-display text-xl font-bold">{n.team}</p>
              <p className="text-ink-2 text-sm">{n.why}</p>
              <Link to="/players?view=season" className="text-pitch-600 mt-1 inline-flex items-center gap-1 text-sm font-semibold hover:underline">
                2024/25 season <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
            </div>
          </Card>
        ))}
      </section>
      <BestOfTheRest
        groups={group(data.best, (b) => `${b.competition} ${b.season}`).map(([title, rows]) => [
          title,
          rows.map((b) => ({ key: `${b.comp}-${b.team_id}`, team: b.team, to: profile(b.comp, b.team_id, b.player), p: b.player })),
        ])}
      />
      <p className="text-ink-2 text-xs">
        Data: <a className="underline" href="https://github.com/statsbomb/open-data">StatsBomb Open Data</a>. Every event of the matches in the free data: La Liga,
        Premier League and Ligue 1 2015/16, PSG's league matches 2021-23, Leverkusen's 2023/24.
      </p>
    </>
  );
}
