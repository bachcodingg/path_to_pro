// Pro player analysis, the Pro League app's player section. Two sources, as tabs:
// - 2025/26 and 2024/25 seasons (API-Football season totals): the featured clubs' squads,
//   Bayern included, and the best player of every other club in the five leagues.
// - Match events (StatsBomb Open Data): the featured clubs' squads in the seasons the free
//   event data has (2015/16, and PSG 2021-23), with shot maps; the best player of every other club.
// "Best" is the same plain rule in both: the most goals plus assists among players with 900+
// minutes, more minutes breaking a tie. Every player has his photo where there is one.
import { ArrowRight } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Crest } from "../shared/Club";
import { PageHeader, Tabs } from "../shared/PageHeader";
import { PhotoCredits } from "../shared/PlayerPhoto";
import { useApi } from "../shared/useApi";
import { Card, ErrorNote, PageSkeleton } from "../shared/ui";
import { PlayerLine, type PlayerSummary } from "./PlayerParts";
import { DEFAULT_YEAR, SeasonSource, seasonApi, seasonPlayerUrl, seasonSquadUrl, soFar, type SeasonHub } from "./Season";

interface EventsHub {
  regular_minutes: number;
  featured: { comp: string; competition: string; season: string; coverage: string; team: string; team_id: string; players: PlayerSummary[] }[];
  best: { comp: string; competition: string; season: string; team: string; team_id: string; player: PlayerSummary }[];
  not_in_open_data: { team: string; why: string }[];
}

// The API-Football seasons the app knows, latest first, then the match events
const FALLBACK_SEASONS = [
  { year: 2025, season: "2025/26", available: false },
  { year: DEFAULT_YEAR, season: "2024/25", available: false },
];

export function PlayersHub() {
  const [params, setParams] = useSearchParams();
  const index = useApi<SeasonHub>(seasonApi(DEFAULT_YEAR));
  const seasons = index.data?.seasons ?? FALLBACK_SEASONS;
  const views = [...seasons.map((x) => [String(x.year), `${x.season} season`] as [string, string]), ["events", "Match events"] as [string, string]];
  const asked = params.get("view") === "season" ? String(DEFAULT_YEAR) : params.get("view"); // ?view=season: the older address
  const view = asked ?? (index.data ? String(seasons.find((x) => x.available)?.year ?? "events") : String(DEFAULT_YEAR));
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Pro player analysis"
        title="Players"
        subtitle="Full squads of Real Madrid, Barcelona, PSG, Manchester City, Manchester United, Chelsea, Liverpool, Arsenal and Bayern, and the best player of every other club."
        bottom={<Tabs items={views} value={view} onChange={(v) => setParams({ view: v }, { replace: true })} label="Data" />}
      />
      {view === "events" ? <EventsView /> : <SeasonView year={Number(view)} />}
    </div>
  );
}

function SquadCard({
  team,
  logo,
  label,
  players,
  to,
  playerTo,
}: {
  team: string;
  logo?: string | null;
  label: string;
  players: PlayerSummary[];
  to: string;
  playerTo: (p: PlayerSummary) => string;
}) {
  return (
    <Card className="flex flex-col p-0">
      <Link to={to} className="hover:bg-surface-2 flex items-center gap-3 rounded-t-lg p-4">
        <Crest name={team} src={logo} size={44} />
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
            <PlayerLine to={playerTo(p)} team={team} logo={logo} p={p} sub={`${p.position ?? ""} · ${p.minutes.toLocaleString("en")} min`} />
          </li>
        ))}
      </ul>
    </Card>
  );
}

function BestOfTheRest({ groups }: { groups: [string, { key: string; team: string; logo?: string | null; to: string; p: PlayerSummary }[]][] }) {
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
                  <PlayerLine to={r.to} team={r.team} logo={r.logo} p={r.p} />
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

function SeasonView({ year }: { year: number }) {
  const { data, error, loading, reload } = useApi<SeasonHub>(seasonApi(year));
  if (loading && !data) return <PageSkeleton label="Loading the season" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  if (!data.available)
    return (
      <Card className="space-y-2">
        <h2 className="font-display text-xl font-bold">The {data.season} numbers are not imported on this server yet</h2>
        <p className="text-ink-2 text-sm">
          They come from API-Football, which needs a key. Whoever runs this server imports them with{" "}
          <code className="bg-surface-2 rounded px-1">python -m scouting.apifootball{year === DEFAULT_YEAR ? "" : ` --season ${year}`}</code>{" "}
          (backend/scouting/apifootball.py explains how).
          {year > DEFAULT_YEAR &&
            ` API-Football's free plan does not include ${data.season} (in 2026 it covers 2022 to 2024), so this season needs a paid plan.`}{" "}
          Until then, the match-event analysis has full squads from the seasons in the free event data.
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
            logo={f.logo}
            label={`${f.league} ${data.season}`}
            players={f.players}
            to={seasonSquadUrl(f.team_id, year)}
            playerTo={(p) => seasonPlayerUrl(f.team_id, p.id, year)}
          />
        ))}
      </section>
      <BestOfTheRest
        groups={group(data.best ?? [], (b) => b.league).map(([league, rows]) => [
          `${league} ${data.season}`,
          rows.map((b) => ({ key: String(b.team_id), team: b.team, logo: b.logo, to: seasonPlayerUrl(b.team_id, b.player.id, year), p: b.player })),
        ])}
      />
      <PhotoCredits people={[...(data.featured ?? []).flatMap((f) => f.players.slice(0, 4)), ...(data.best ?? []).map((b) => b.player)]} />
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
              <Link to={`/players?view=${DEFAULT_YEAR}`} className="text-pitch-600 mt-1 inline-flex items-center gap-1 text-sm font-semibold hover:underline">
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
      <PhotoCredits people={[...data.featured.flatMap((f) => f.players.slice(0, 4)), ...data.best.map((b) => b.player)]} />
      <p className="text-ink-2 text-xs">
        Data: <a className="underline" href="https://github.com/statsbomb/open-data">StatsBomb Open Data</a>. Every event of the matches in the free data: La Liga,
        Premier League and Ligue 1 2015/16, PSG's league matches 2021-23, Leverkusen's 2023/24.
      </p>
    </>
  );
}
