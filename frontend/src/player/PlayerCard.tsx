// "Your attribute card": percentiles vs players at the same stage of growth (bio-banded).
import { Map } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Attribute, Card as CardData } from "../shared/types";
import { useApi } from "../shared/useApi";
import { Card, Chip, ErrorNote, SectionTitle, Spinner, capitalize, cn, fmtValue, ordinal } from "../shared/ui";

const STATUS_TEXT: Record<string, string> = {
  pre_phv: "before growth spurt",
  circa_phv: "in growth spurt",
  post_phv: "after growth spurt",
};

export function PlayerCard() {
  const { data, error, loading, reload } = useApi<CardData>("/api/me/card");
  const [open, setOpen] = useState<string | null>(null);
  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  const byAttr = (a: string) => data.attributes.filter((x) => x.attribute === a);
  const overall = Math.round(data.attributes.reduce((s, a) => s + a.bio_percentile, 0) / Math.max(1, data.attributes.length));
  const selected = data.attributes.find((a) => a.kpi === open);

  return (
    <div className="space-y-4 pt-2">
      <Link to="/player/road" className="text-pitch-300 flex items-center justify-end gap-1 text-sm font-semibold">
        <Map className="h-4 w-4" aria-hidden /> Road to Pro
      </Link>
      <div className="rounded-3xl bg-gradient-to-br from-amber-300 via-amber-200 to-amber-500 p-1 shadow-lg">
        <div className="rounded-[20px] bg-gradient-to-br from-pitch-800 to-pitch-950 p-5 text-white">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-5xl font-extrabold">{overall}</p>
              <p className="text-pitch-200 text-xs font-semibold uppercase">avg percentile</p>
            </div>
            <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="h-10 w-10" />
          </div>
          <p className="mt-4 text-2xl font-extrabold">{data.name}</p>
          <p className="text-pitch-200 text-sm">Compared with players {STATUS_TEXT[data.maturity_status] ?? ""}</p>
          <div className="mt-4 grid grid-cols-3 gap-2">
            {(["speed", "power", "endurance"] as const).map((attr) => {
              const items = byAttr(attr);
              const v = items.length ? Math.round(items.reduce((s, a) => s + a.bio_percentile, 0) / items.length) : null;
              return (
                <button
                  key={attr}
                  onClick={() => setOpen(items[0]?.kpi ?? null)}
                  className="tap rounded-xl bg-white/10 py-2 text-center hover:bg-white/20"
                  aria-label={`${attr}: ${v ?? "no data"} percentile`}
                >
                  <p className="text-2xl font-extrabold">{v ?? "–"}</p>
                  <p className="text-xs font-semibold uppercase">{attr.slice(0, 3)}</p>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <section>
        <SectionTitle>Tests</SectionTitle>
        <div className="space-y-2">
          {data.attributes.map((a) => (
            <AttrRow key={a.kpi} a={a} active={open === a.kpi} onClick={() => setOpen(open === a.kpi ? null : a.kpi)} />
          ))}
        </div>
        <p className="text-ink-2 mt-2 text-xs">
          Percentiles use placeholder reference values for this demo, not validated academy norms. Treat them as a rough guide.
        </p>
      </section>

      {selected && (
        <Card>
          <p className="font-bold">{capitalize(selected.label)}: history</p>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={selected.history} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} fontSize={11} stroke="#a9c2b3" />
                <YAxis domain={["auto", "auto"]} reversed={selected.unit === "s"} fontSize={11} stroke="#a9c2b3" />
                <Tooltip contentStyle={{ background: "#0f2219", border: "1px solid #24402f" }} />
                <Line dataKey="value" stroke="#7ee0a8" strokeWidth={3} dot />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {selected.drills.length > 0 ? (
            <>
              <p className="mt-3 font-bold">Your drills</p>
              <ul className="mt-1 space-y-2">
                {selected.drills.map((d) => (
                  <li key={d.id} className="bg-surface-2 rounded-xl p-3">
                    <p className="font-semibold">{d.name}</p>
                    <p className="text-ink-2 text-sm">{d.description}</p>
                    <div className="mt-1 flex gap-2">
                      <Chip>{d.minutes} min</Chip>
                      <Chip>effort {d.rpe}</Chip>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-ink-2 mt-2 text-sm">No drills linked to this test right now.</p>
          )}
        </Card>
      )}
    </div>
  );
}

function AttrRow({ a, active, onClick }: { a: Attribute; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={cn("bg-surface border-line tap w-full rounded-2xl border p-3 text-left", active && "border-pitch-300")} aria-expanded={active}>
      <div className="flex items-center justify-between">
        <span className="font-semibold">{capitalize(a.label)}</span>
        <span className="text-ink-2 text-sm">
          {fmtValue(a.value, a.unit)} {a.unit}
        </span>
      </div>
      <div className="bg-surface-2 mt-2 h-2.5 overflow-hidden rounded-full" aria-hidden>
        <div className="bg-pitch-400 h-full rounded-full" style={{ width: `${a.bio_percentile}%` }} />
      </div>
      <p className="text-ink-2 mt-1 text-xs">
        {ordinal(a.bio_percentile)} percentile at your stage of growth · {ordinal(a.age_percentile)} for your age group
      </p>
    </button>
  );
}
