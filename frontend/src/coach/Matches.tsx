// Match ratings: recent matches, and per match a stat sheet. Ratings (3-10) are computed
// from the stats with a breakdown, and shown next to the player's own diary rating.
import { ChevronDown } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../shared/api";
import { useAuth } from "../shared/auth";
import { Crest } from "../shared/Club";
import { PageHeader, Tabs } from "../shared/PageHeader";
import { Breakdown, POSITION_LABEL, RatingBadge } from "../shared/Rating";
import { MatchLineup } from "./MatchLineup";
import type { BreakdownItem, Position } from "../shared/types";
import { useApi } from "../shared/useApi";
import {
  Button,
  Card,
  ErrorNote,
  SectionTitle,
  Spinner,
  cn,
  fmtDay,
} from "../shared/ui";

interface MatchListItem {
  id: string;
  date: string;
  opponent: string;
  team: string;
  competition: string | null;
  players: number;
  rated: number;
  avg_rating: number | null;
  best: { name: string; rating: number } | null;
}

export function Matches() {
  const { data, error, loading, reload } =
    useApi<MatchListItem[]>("/api/coach/matches");
  if (loading && !data) return <Spinner />;
  if (error || !data)
    return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  // Results list as on the league sites: grouped by month, team - badge - badge - team
  const months = new Map<string, MatchListItem[]>();
  for (const m of data) {
    const key = fmtDay(m.date, { month: "long", year: "numeric" });
    months.set(key, [...(months.get(key) ?? []), m]);
  }
  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Matchday"
        title="Match ratings"
        subtitle="Every player gets a 3-10 rating from the match stats, with the reasons. Players see it in their career next to their own diary rating."
      />
      <div className="space-y-5">
        {data.length === 0 && (
          <Card className="text-ink-2">No matches in the last six weeks.</Card>
        )}
        {[...months].map(([month, list]) => (
          <section key={month}>
            <SectionTitle>{month}</SectionTitle>
            <Card className="divide-[color:var(--line)] divide-y p-0">
              {list.map((m) => (
                <Link
                  key={m.id}
                  to={`/coach/matches/${m.id}`}
                  aria-label={`${m.team} vs ${m.opponent}, ${fmtDay(m.date, { weekday: "long", day: "numeric", month: "long" })}`}
                  className="hover:bg-surface-2 grid grid-cols-[3.5rem_minmax(0,1fr)] items-center gap-3 px-4 py-3 transition-colors md:grid-cols-[4rem_minmax(0,1fr)_13rem]"
                >
                  <span className="text-center leading-none">
                    <span className="text-ink-2 block text-[11px] font-bold uppercase">
                      {fmtDay(m.date)}
                    </span>
                    <span className="font-display block text-3xl font-bold">
                      {m.date.slice(8)}
                    </span>
                  </span>
                  <span className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-x-3 gap-y-1">
                    <span className="text-ink-2 flex min-w-0 items-center justify-end gap-2 text-right text-sm font-medium">
                      <span className="truncate">{m.team}</span>
                      <Crest name={m.team} size={30} />
                    </span>
                    <span className="flex flex-col items-center">
                      <RatingBadge value={m.avg_rating} />
                      <span className="text-ink-2 mt-0.5 text-[10px] font-semibold uppercase">
                        avg
                      </span>
                    </span>
                    <span className="flex min-w-0 items-center gap-2 font-semibold">
                      <Crest name={m.opponent} size={30} />
                      <span className="truncate">{m.opponent}</span>
                    </span>
                    <span className="text-ink-2 col-span-3 text-center text-xs">
                      {m.competition ?? "Match"} · {m.rated}/{m.players} rated
                    </span>
                  </span>
                  {m.best && (
                    <span className="hidden text-right text-xs md:block">
                      <span className="text-ink-2 block font-semibold uppercase">
                        Player of the match
                      </span>
                      <span className="font-semibold">
                        {m.best.name}{" "}
                        <RatingBadge value={m.best.rating} size="sm" />
                      </span>
                    </span>
                  )}
                </Link>
              ))}
            </Card>
          </section>
        ))}
      </div>
    </div>
  );
}

interface ReportRow {
  player: { id: string; name: string; position: Position };
  minutes: number;
  started: boolean;
  position: Position;
  stats: Record<string, number | string>;
  rating: number | null;
  rating_source: "stats" | "diary" | null;
  breakdown: BreakdownItem[];
  self_rating: number | null;
}
interface Report {
  match: {
    id: string;
    date: string;
    opponent: string;
    team: string;
    competition: string | null;
  };
  players: ReportRow[];
}

const POSITION_SHORT: Record<string, string> = {
  goalkeeper: "GK",
  centre_back: "CB",
  full_back: "FB",
  midfielder: "CM",
  winger: "W",
  striker: "ST",
};

const COLS: [string, string][] = [
  ["goals", "G"],
  ["assists", "A"],
  ["shots_on_target", "SoT"],
  ["key_passes", "KP"],
  ["passes", "Pass"],
  ["passes_accurate", "Acc"],
  ["dribbles_won", "Drb"],
  ["tackles_won", "Tkl"],
  ["interceptions", "Int"],
  ["duels_won", "DW"],
  ["duels_lost", "DL"],
  ["saves", "Sav"],
  ["goals_conceded", "GC"],
  ["errors_to_goal", "Err"],
  ["yellow", "YC"],
  ["red", "RC"],
];
const HELP: Record<string, string> = {
  SoT: "Shots on target",
  KP: "Key passes",
  Acc: "Accurate passes",
  Drb: "Dribbles won",
  Tkl: "Tackles won",
  Int: "Interceptions",
  DW: "Duels won",
  DL: "Duels lost",
  Sav: "Saves",
  GC: "Goals conceded while on the pitch",
  Err: "Errors leading to a goal",
};

export function MatchReport() {
  const { id } = useParams();
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi<Report>(
    `/api/coach/matches/${id}`,
  );
  const [rows, setRows] = useState<ReportRow[]>([]);
  const [result, setResult] = useState<string>("");
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [tab, setTab] = useState<"lineup" | "sheet">("lineup");

  useEffect(() => {
    if (!data) return;
    setRows(data.players);
    setResult(
      String(data.players.find((r) => r.stats.result)?.stats.result ?? ""),
    );
  }, [data]);

  if (loading && !data) return <Spinner />;
  if (error || !data)
    return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const canEdit = user?.role === "coach";

  const setStat = (pid: string, key: string, v: string) =>
    setRows((rs) =>
      rs.map((r) =>
        r.player.id === pid
          ? { ...r, stats: { ...r.stats, [key]: v === "" ? "" : Number(v) } }
          : r,
      ),
    );
  const setField = (pid: string, patch: Partial<ReportRow>) =>
    setRows((rs) =>
      rs.map((r) => (r.player.id === pid ? { ...r, ...patch } : r)),
    );

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      const out = await api<Report>(`/api/coach/matches/${id}/ratings`, {
        method: "PUT",
        json: {
          players: rows
            .filter((r) => r.minutes > 0 || r.rating != null)
            .map((r) => ({
              player_id: r.player.id,
              minutes: r.minutes,
              started: r.started,
              position: r.position,
              stats: Object.fromEntries(
                Object.entries({
                  ...r.stats,
                  result: result || undefined,
                }).filter(([, v]) => v !== "" && v !== undefined),
              ),
            })),
        },
      });
      setRows(out.players);
      setMsg("Saved. Ratings updated.");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  const played = rows.filter((r) => r.minutes > 0);
  const top = [...played]
    .filter((r) => r.rating != null)
    .sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0))[0];
  const input =
    "bg-surface-2 border-line h-8 w-12 rounded-md border px-1 text-center tabular-nums";
  return (
    <div className="space-y-4">
      {/* Match-centre header: both badges, the date, the views as tabs */}
      <PageHeader
        eyebrow={
          <Link to="/coach/matches" className="hover:underline">
            ← Match ratings
          </Link>
        }
        title={`${data.match.team} vs ${data.match.opponent}`}
        subtitle={[
          fmtDay(data.match.date, {
            weekday: "long",
            day: "numeric",
            month: "long",
          }),
          data.match.competition,
        ]
          .filter(Boolean)
          .join(" · ")}
        leading={
          <span className="hidden items-center gap-1 sm:flex">
            <Crest name={data.match.team} size={44} />
            <Crest name={data.match.opponent} size={44} />
          </span>
        }
        actions={
          top && (
            <span className="rounded-xl bg-white/10 px-3 py-2 text-sm">
              <span className="block text-xs font-bold tracking-wider text-white/70 uppercase">
                Player of the match
              </span>
              <span className="font-semibold">
                {top.player.name}{" "}
                <span className="font-display text-xl font-bold">
                  {top.rating?.toFixed(1)}
                </span>
              </span>
            </span>
          )
        }
        bottom={
          <Tabs
            label="Match view"
            value={tab}
            onChange={setTab}
            items={[
              ["lineup", "Line-up"],
              ["sheet", "Stat sheet"],
            ]}
          />
        }
      />

      {tab === "lineup" && <MatchLineup rows={rows} linkFor={(id) => `/coach/players/${id}`} />}
      {tab === "sheet" && (
        <>
          {canEdit && (
            <Card className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm font-semibold">
                Result
                <select
                  className="bg-surface-2 border-line h-9 rounded-lg border px-2"
                  value={result}
                  onChange={(e) => setResult(e.target.value)}
                >
                  <option value="">–</option>
                  <option value="win">Win</option>
                  <option value="draw">Draw</option>
                  <option value="loss">Loss</option>
                </select>
              </label>
              <Button onClick={save} loading={busy}>
                Save and rate
              </Button>
              {msg && (
                <p role="status" className="text-sm font-semibold">
                  {msg}
                </p>
              )}
              <p className="text-ink-2 w-full text-xs">
                {Object.entries(HELP)
                  .map(([k, v]) => `${k} = ${v}`)
                  .join(" · ")}
              </p>
            </Card>
          )}

          <SectionTitle>Players</SectionTitle>
          <Card className="overflow-x-auto p-0">
            <table className="w-full min-w-[1100px] text-xs">
              <thead className="text-ink-2 text-left">
                <tr>
                  <th className="p-2">Rating</th>
                  <th className="p-2">Player</th>
                  <th className="p-2">Min</th>
                  <th className="p-2">Start</th>
                  <th className="p-2">Pos</th>
                  {COLS.map(([, h]) => (
                    <th key={h} className="p-1 text-center" title={HELP[h]}>
                      {h}
                    </th>
                  ))}
                  <th className="p-2">Self</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <Fragment key={r.player.id}>
                    <tr className="border-line border-t">
                      <td className="p-2">
                        <button
                          onClick={() =>
                            setOpen(open === r.player.id ? null : r.player.id)
                          }
                          className="flex items-center gap-1"
                          aria-expanded={open === r.player.id}
                          aria-label={`Rating breakdown for ${r.player.name}`}
                        >
                          <RatingBadge
                            value={r.rating}
                            size="sm"
                            estimate={r.rating_source === "diary"}
                          />
                          <ChevronDown
                            className={cn(
                              "h-3 w-3",
                              open === r.player.id && "rotate-180",
                            )}
                            aria-hidden
                          />
                        </button>
                      </td>
                      <td className="p-2 font-semibold whitespace-nowrap">
                        {r.player.name}
                      </td>
                      <td className="p-1">
                        <input
                          className={input}
                          type="number"
                          min={0}
                          max={130}
                          disabled={!canEdit}
                          aria-label={`${r.player.name} minutes`}
                          value={r.minutes}
                          onChange={(e) =>
                            setField(r.player.id, {
                              minutes: Number(e.target.value),
                            })
                          }
                        />
                      </td>
                      <td className="p-1 text-center">
                        <input
                          type="checkbox"
                          disabled={!canEdit}
                          checked={r.started}
                          aria-label={`${r.player.name} started`}
                          onChange={(e) =>
                            setField(r.player.id, { started: e.target.checked })
                          }
                        />
                      </td>
                      <td className="p-1">
                        <select
                          className="bg-surface-2 border-line h-8 rounded-md border"
                          disabled={!canEdit}
                          value={r.position}
                          aria-label={`${r.player.name} position`}
                          onChange={(e) =>
                            setField(r.player.id, {
                              position: e.target.value as Position,
                            })
                          }
                        >
                          {Object.keys(POSITION_LABEL).map((k) => (
                            <option key={k} value={k}>
                              {POSITION_SHORT[k]}
                            </option>
                          ))}
                        </select>
                      </td>
                      {COLS.map(([k, h]) => (
                        <td key={k} className="p-1">
                          <input
                            className={input}
                            type="number"
                            min={0}
                            disabled={!canEdit}
                            aria-label={`${r.player.name} ${HELP[h] ?? h}`}
                            value={r.stats[k] ?? ""}
                            onChange={(e) =>
                              setStat(r.player.id, k, e.target.value)
                            }
                          />
                        </td>
                      ))}
                      <td className="p-2 text-center">
                        {r.self_rating ?? "–"}
                      </td>
                    </tr>
                    {open === r.player.id && (
                      <tr>
                        <td
                          colSpan={COLS.length + 6}
                          className="bg-surface-2 p-3"
                        >
                          <div className="max-w-md">
                            <Breakdown items={r.breakdown} />
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
      <p className="text-ink-2 text-xs">
        Ratings use our own transparent formula (base 6.3, position-weighted
        stats), not a third-party algorithm. Tune the weights in
        backend/performance/rating.py with your staff.
      </p>
    </div>
  );
}
