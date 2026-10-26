// "Dressing room": players x last 14 days, cell = readiness. Ring = PHV window, triangle = load flag.
import { useState } from "react";
import { api } from "../shared/api";
import { Link } from "react-router-dom";
import type { Heatmap as HeatmapData, HeatmapRow } from "../shared/types";
import { useApi } from "../shared/useApi";
import { PageHeader } from "../shared/PageHeader";
import type { Band } from "../shared/types";
import { BAND_BG, BAND_TEXT, BandBadge, BandIcon, Card, ErrorNote, PageSkeleton, cn, fmtDay } from "../shared/ui";

// Cells: ready and take-care days are tints, only recover days are solid, so the eye lands on them
const CELL: Record<Band, string> = {
  green: "bg-ready-green/15 text-ready-green dark:bg-ready-green/25",
  amber: "bg-ready-amber/25 text-amber-800 dark:text-ready-amber",
  red: "bg-ready-red text-white",
};

export function Heatmap() {
  const [group, setGroup] = useState("");
  const [flag, setFlag] = useState("");
  const qs = new URLSearchParams({ ...(group && { age_group: group }), ...(flag && { flag }) }).toString();
  const { data, error, loading, reload } = useApi<HeatmapData>(`/api/coach/heatmap${qs ? `?${qs}` : ""}`);
  const [sel, setSel] = useState<{ row: HeatmapRow; i: number } | null>(null);

  if (loading && !data) return <PageSkeleton label="Loading the dressing room" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  const groups = ["U14", "U15", "U16", "U17", "U18", "U19"];
  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Squad"
        title="Dressing room"
        subtitle={`Readiness over the last 14 days · today ${fmtDay(data.today, { weekday: "long", day: "numeric", month: "short" })}`}
        bottom={<SquadPulse rows={data.players} today={data.today} />}
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Legend />
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
                        "tap flex h-11 w-full min-w-11 items-center justify-center rounded-md text-xs font-bold transition-shadow hover:ring-2 hover:ring-line",
                        c.band ? CELL[c.band] : "bg-surface-2 text-ink-2",
                        sel?.row.id === row.id && sel.i === i && "ring-ink ring-2 hover:ring-ink",
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
          <RateButtons playerId={sel.row.id} day={sel.row.cells[sel.i].date} />
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

// The squad at a glance, like the match-stats bar on a broadcast: each player's latest
// reading, one segment per band, and how many have checked in today
function SquadPulse({ rows, today }: { rows: HeatmapRow[]; today: string }) {
  const count: Record<Band | "none", number> = { green: 0, amber: 0, red: 0, none: 0 };
  let checkedIn = 0;
  for (const r of rows) {
    const latest = [...r.cells].reverse().find((c) => c.band);
    count[latest?.band ?? "none"]++;
    if (r.cells.some((c) => c.date === today && c.band)) checkedIn++;
  }
  const parts = (["green", "amber", "red"] as const).map((b) => [b, BAND_TEXT[b], count[b]] as const);
  const total = rows.length || 1;
  return (
    <div className="pb-5">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <span className="text-xs font-bold tracking-[0.14em] text-white/60 uppercase">Latest reading</span>
        {parts.map(([k, label, n]) => (
          <span key={k} className="flex items-center gap-1.5">
            <span className={cn("h-2.5 w-2.5 self-center rounded-full", BAND_BG[k])} aria-hidden />
            <span className="font-display text-2xl font-bold">{n}</span>
            <span className="text-sm text-white/75">{label}</span>
          </span>
        ))}
        <span className="text-sm text-white/75 md:ml-auto">
          <span className="font-display text-2xl font-bold text-white">{checkedIn}</span> of {rows.length} checked in today
        </span>
      </div>
      <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-white/10" aria-hidden>
        {parts.map(([k, , n]) => (
          <span key={k} className={BAND_BG[k]} style={{ width: `${(100 * n) / total}%` }} />
        ))}
      </div>
    </div>
  );
}

function Legend() {
  return (
    <div className="text-ink-2 flex flex-wrap gap-4 text-sm">
      {(["green", "amber", "red"] as const).map((b) => (
        <span key={b} className="flex items-center gap-1">
          <span className={cn("inline-flex h-5 w-5 items-center justify-center rounded", CELL[b])}>
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

function RateButtons({ playerId, day }: { playerId: string; day: string }) {
  const [saved, setSaved] = useState<string | null>(null);
  async function rate(band: "green" | "amber" | "red") {
    await api(`/api/coach/players/${playerId}/rating`, { method: "POST", json: { band, day } });
    setSaved(band);
  }
  return (
    <div className="flex flex-wrap items-center gap-2" key={playerId + day}>
      <span className="text-ink-2 text-sm">How ready did he look?</span>
      {(["green", "amber", "red"] as const).map((b) => (
        <button
          key={b}
          onClick={() => rate(b)}
          aria-pressed={saved === b}
          className={cn("tap inline-flex items-center gap-1 rounded-xl px-3 text-sm font-semibold text-white", BAND_BG[b], saved && saved !== b && "opacity-40")}
        >
          <BandIcon band={b} className="h-4 w-4" /> {b === "green" ? "Ready" : b === "amber" ? "Take care" : "Recover"}
        </button>
      ))}
      {saved && <span className="text-ink-2 text-xs" role="status">Saved. Used to calibrate the score.</span>}
    </div>
  );
}
