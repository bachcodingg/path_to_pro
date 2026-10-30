// "My career": football CV across teams and leagues, season stats with match ratings,
// the pathway chart through the league ladder, and the match diary.
import { ChevronDown } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError } from "../shared/api";
import { useAuth } from "../shared/auth";
import { Breakdown, POSITION_LABEL, RatingBadge } from "../shared/Rating";
import { RatingHistory } from "../shared/RatingHistory";
import type { AppearanceRow, Career as CareerData } from "../shared/types";
import { Crest } from "../shared/Club";
import { useApi } from "../shared/useApi";
import { Button, Card, Chip, ErrorNote, SectionTitle, Spinner, cn, fmtDay } from "../shared/ui";
import { ClubHistory, MoneyCard } from "./ClubHistory";
import { MatchDiary } from "./MatchDiary";

export function Career() {
  const { user } = useAuth();
  const { data, setData, error, loading, reload } = useApi<CareerData>("/api/me/career");
  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const s = data.summary;

  return (
    <div className="space-y-5 pt-2">
      <div>
        <h1 className="text-2xl font-extrabold">My career</h1>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {data.registrations.map((r) => (
            <Chip key={r.team_id} tone={r.primary ? "green" : "neutral"}>
              {r.team} · {r.competition_label}
              {data.registrations.length > 1 && (r.primary ? " · main team" : " · dual registration")}
            </Chip>
          ))}
        </div>
      </div>

      {/* Wide screens: this season on the left, matches and history on the right */}
      <div className="space-y-5 lg:grid lg:grid-cols-2 lg:items-start lg:gap-6 lg:space-y-0">
        <div className="space-y-5">
          <MatchDiary due={data.diary_due} position={user?.position} onSaved={setData} />

          <section>
            <SectionTitle>Season {data.season}</SectionTitle>
            <Card>
              <div className="flex items-center gap-4">
                <RatingBadge value={s.avg_rating} size="lg" />
                <div className="grid flex-1 grid-cols-4 gap-2 text-center">
                  {[
                    ["Apps", s.apps],
                    ["Min", s.minutes],
                    ["Goals", s.goals],
                    ["Assists", s.assists],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <p className="text-xl font-extrabold tabular-nums">{v}</p>
                      <p className="text-ink-2 text-xs">{k}</p>
                    </div>
                  ))}
                </div>
              </div>
              <p className="text-ink-2 mt-3 text-sm">
                Average rating · <span className="text-ink font-semibold">{s.exposure}</span> full matches at top level (minutes
                weighted by league level)
              </p>
              {data.current.length > 1 && (
                <ul className="border-line mt-3 space-y-1 border-t pt-2 text-sm">
                  {data.current.map((c) => (
                    <li key={c.competition} className="flex justify-between">
                      <span>{c.competition_label}</span>
                      <span className="text-ink-2 tabular-nums">
                        {c.apps} apps · {c.minutes} min · {c.goals}G {c.assists}A
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </section>

          <section>
            <SectionTitle>Rating progress</SectionTitle>
            <RatingHistory data={data.history} />
          </section>

          {data.ladder.length > 0 && (
            <section>
              <SectionTitle>My pathway</SectionTitle>
              <Card className="h-48 p-2" aria-label="Pathway chart: highest league level per season">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.ladder} margin={{ top: 12, right: 16, left: -16, bottom: 0 }}>
                    <CartesianGrid stroke="rgba(255,255,255,0.08)" />
                    <XAxis dataKey="season" fontSize={11} stroke="#a8b4c8" />
                    <YAxis domain={[0, 100]} fontSize={11} stroke="#a8b4c8" />
                    <Tooltip
                      contentStyle={{ background: "#111b30", border: "1px solid #24324d" }}
                      formatter={(v: number, _n, p) => [`${p.payload.competition_label} (level ${v})`, "Highest league"]}
                    />
                    <Line type="stepAfter" dataKey="level" stroke="#f0a020" strokeWidth={3} dot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            </section>
          )}
        </div>

        <div className="space-y-5">
          <section>
            <SectionTitle>Recent matches</SectionTitle>
            <Card className="divide-[color:var(--line)] divide-y p-0">
              {data.recent.length === 0 && <p className="text-ink-2 p-4 text-sm">No matches yet this season.</p>}
              {data.recent.map((a) => (
                <MatchRow key={a.match_id} a={a} />
              ))}
            </Card>
          </section>

          <ClubHistory clubs={data.clubs} />

          <MoneyCard />

          <section>
            <SectionTitle>Past seasons</SectionTitle>
            <Card className="overflow-x-auto p-0">
              <table className="w-full text-sm">
                <thead className="text-ink-2 text-left text-xs">
                  <tr>
                    <th className="p-2">Season</th>
                    <th className="p-2">Team · league</th>
                    <th className="p-2 text-right">Apps</th>
                    <th className="p-2 text-right">G</th>
                    <th className="p-2 text-right">A</th>
                    <th className="p-2 text-right">Avg</th>
                  </tr>
                </thead>
                <tbody className="divide-[color:var(--line)] divide-y">
                  {[...data.past].reverse().map((r) => (
                    <tr key={r.id ?? r.season + r.competition}>
                      <td className="p-2 font-semibold">{r.season}</td>
                      <td className="p-2">
                        {r.team}
                        <span className="text-ink-2 block text-xs">{r.competition_label}</span>
                      </td>
                      <td className="p-2 text-right tabular-nums">{r.apps}</td>
                      <td className="p-2 text-right tabular-nums">{r.goals}</td>
                      <td className="p-2 text-right tabular-nums">{r.assists}</td>
                      <td className="p-2 text-right">
                        <RatingBadge value={r.avg_rating} size="sm" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
            <AddSeason data={data} onSaved={setData} />
          </section>
        </div>
      </div>

      <p className="text-ink-2 text-center text-xs">{data.note}</p>
    </div>
  );
}

function MatchRow({ a }: { a: AppearanceRow }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button className="tap flex w-full items-center gap-3 px-4 py-3 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <RatingBadge value={a.rating} estimate={a.rating_source === "diary"} />
        <Crest name={a.opponent} size={28} />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-semibold">vs {a.opponent}</span>
          <span className="text-ink-2 text-xs">
            {fmtDay(a.date, { day: "numeric", month: "short" })} · {a.team} · {a.minutes}'
            {a.goals > 0 && ` · ${a.goals}G`}
            {a.assists > 0 && ` · ${a.assists}A`}
          </span>
        </span>
        <ChevronDown className={cn("text-ink-2 h-4 w-4 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div className="space-y-2 px-4 pb-3">
          <p className="text-ink-2 text-xs">
            {a.competition_label}
            {a.position && ` · ${POSITION_LABEL[a.position]}`}
            {a.self_rating != null && ` · your own rating ${a.self_rating}/10`}
          </p>
          <Breakdown items={a.breakdown} />
          <Link to={`/player/matches/${a.match_id}`} className="text-pitch-300 inline-block text-sm font-semibold underline">
            See the line-up and everyone's ratings
          </Link>
        </div>
      )}
    </div>
  );
}

function AddSeason({ data, onSaved }: { data: CareerData; onSaved: (c: CareerData) => void }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ season: String(Number(data.season) - 1), club: "", team: "", competition: data.competitions[0]?.id ?? "", apps: 0, starts: 0, minutes: 0, goals: 0, assists: 0 });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f, v: string | number) => setF((x) => ({ ...x, [k]: v }));
  const input = "bg-surface-2 border-line mt-1 h-11 w-full rounded-xl border px-3";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      onSaved(await api<CareerData>("/api/me/career/seasons", { method: "POST", json: f }));
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save");
    }
  }

  if (!open)
    return (
      <Button variant="secondary" size="sm" className="mt-2" onClick={() => setOpen(true)}>
        Add a past season
      </Button>
    );
  return (
    <Card className="mt-2">
      <form onSubmit={submit} className="grid grid-cols-2 gap-2">
        <label>
          <span className="text-xs font-semibold">Season</span>
          <input className={input} inputMode="numeric" pattern="(19|20)\d\d" required value={f.season} onChange={(e) => set("season", e.target.value)} />
        </label>
        <label>
          <span className="text-xs font-semibold">Club</span>
          <input className={input} required maxLength={100} value={f.club} onChange={(e) => set("club", e.target.value)} />
        </label>
        <label>
          <span className="text-xs font-semibold">Team</span>
          <input className={input} required maxLength={100} value={f.team} onChange={(e) => set("team", e.target.value)} placeholder="e.g. U17" />
        </label>
        <label>
          <span className="text-xs font-semibold">League</span>
          <select className={input} value={f.competition} onChange={(e) => set("competition", e.target.value)}>
            {data.competitions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        {(["apps", "starts", "minutes", "goals", "assists"] as const).map((k) => (
          <label key={k}>
            <span className="text-xs font-semibold capitalize">{k}</span>
            <input className={input} type="number" min={0} value={f[k]} onChange={(e) => set(k, Number(e.target.value))} />
          </label>
        ))}
        {error && (
          <p role="alert" className="text-recover col-span-2 text-sm">
            {error}
          </p>
        )}
        <Button type="submit" className="col-span-2">
          Save season
        </Button>
      </form>
    </Card>
  );
}
