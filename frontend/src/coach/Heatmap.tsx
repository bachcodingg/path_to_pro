// "Dressing room": players x last 14 days, cell = readiness. Ring = PHV window, triangle = load flag.
import { useState } from "react";
import { Link } from "react-router-dom";
import type { Heatmap as HeatmapData, HeatmapRow } from "../shared/types";
import { useApi } from "../shared/useApi";
import { BAND_BG, BandBadge, BandIcon, Card, ErrorNote, Spinner, cn, fmtDay } from "../shared/ui";

export function Heatmap() {
  const [group, setGroup] = useState("");
  const [flag, setFlag] = useState("");
  const qs = new URLSearchParams({ ...(group && { age_group: group }), ...(flag && { flag }) }).toString();
  const { data, error, loading, reload } = useApi<HeatmapData>(`/api/coach/heatmap${qs ? `?${qs}` : ""}`);
  const [sel, setSel] = useState<{ row: HeatmapRow; i: number } | null>(null);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  const groups = ["U14", "U15", "U16", "U17", "U18", "U19"];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold">Dressing room</h1>
          <p className="text-ink-2 text-sm">Readiness over the last 14 days · today {fmtDay(data.today, { day: "numeric", month: "short" })}</p>
        </div>
        <div className="flex gap-2">
          <select className="bg-surface border-line tap rounded-xl border px-3" value={group} onChange={(e) => setGroup(e.target.value)} aria-label="Age group">
            <option value="">All ages</option>
            {groups.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
          <select className="bg-surface border-line tap rounded-xl border px-3" value={flag} onChange={(e) => setFlag(e.target.value)} aria-label="Flag">
            <option value="">All players</option>
            <option value="phv_window">Growth zone</option>
            <option value="load_spike">Load spike</option>
            <option value="readiness_red">Red readiness</option>
            <option value="short_sleep">Short sleep</option>
          </select>
        </div>
      </div>
      <Legend />
      <Card className="overflow-x-auto p-0">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="bg-surface sticky left-0 p-2 text-left">Player</th>
              {data.dates.map((d) => (
                <th key={d} className={cn("p-1 text-center font-medium", d === data.today && "text-pitch-600 font-bold")}>
                  <div>{fmtDay(d)}</div>
                  <div className="text-ink-2 text-xs">{d.slice(8)}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.players.map((row) => (
              <tr key={row.id} className="border-line border-t">
                <th scope="row" className="bg-surface sticky left-0 p-2 text-left font-semibold whitespace-nowrap">
                  <Link to={`/coach/players/${row.id}`} className="hover:underline">
                    {row.name}
                  </Link>
                  <span className="text-ink-2 ml-1 text-xs font-normal">{row.age_group}</span>
                  {row.phv && <span title="Growth zone (PHV window)" aria-label="Growth zone" className="border-ready-amber ml-2 inline-block h-3.5 w-3.5 rounded-full border-2 align-middle" />}
                  {row.load_flag && (
                    <span title="Load spike" aria-label="Load spike" className="text-ready-red ml-1 align-middle">
                      ▲
                    </span>
                  )}
                </th>
                {row.cells.map((c, i) => (
                  <td key={c.date} className="p-0.5">
                    <button
                      onClick={() => setSel({ row, i })}
                      className={cn(
                        "tap flex h-11 w-full min-w-11 items-center justify-center rounded-md text-xs font-bold text-white",
                        c.band ? BAND_BG[c.band] : "bg-surface-2 text-ink-2",
                        sel?.row.id === row.id && sel.i === i && "ring-ink ring-2",
                      )}
                      aria-label={`${row.name} ${c.date}: ${c.score == null ? "no data" : Math.round(c.score)}`}
                    >
                      {c.score == null ? "·" : Math.round(c.score)}
                    </button>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {sel && (
        <Card className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-bold">
              {sel.row.name} · {fmtDay(sel.row.cells[sel.i].date, { weekday: "long", day: "numeric", month: "short" })}
            </p>
            <p className="text-ink-2 text-sm">Current flags: {sel.row.flags.length ? sel.row.flags.join(", ").replaceAll("_", " ") : "none"}</p>
          </div>
          <div className="flex items-center gap-3">
            <BandBadge band={sel.row.cells[sel.i].band} score={sel.row.cells[sel.i].score} />
            <Link to={`/coach/players/${sel.row.id}`} className="text-pitch-600 font-semibold hover:underline">
              Open scouting report →
            </Link>
          </div>
        </Card>
      )}
    </div>
  );
}

function Legend() {
  return (
    <div className="text-ink-2 flex flex-wrap gap-4 text-sm">
      {(["green", "amber", "red"] as const).map((b) => (
        <span key={b} className="flex items-center gap-1">
          <span className={cn("inline-flex h-5 w-5 items-center justify-center rounded text-white", BAND_BG[b])}>
            <BandIcon band={b} className="h-3.5 w-3.5" />
          </span>
          {b === "green" ? "Ready ≥ 70" : b === "amber" ? "Take care 50-69" : "Recover < 50"}
        </span>
      ))}
      <span className="flex items-center gap-1">
        <span className="border-ready-amber inline-block h-3.5 w-3.5 rounded-full border-2" /> Growth zone
      </span>
      <span className="flex items-center gap-1">
        <span className="text-ready-red">▲</span> Load spike
      </span>
    </div>
  );
}
