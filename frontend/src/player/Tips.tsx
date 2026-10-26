// Match tips: the tip for today, mindset (after a mistake, nerves, confidence...) and how to
// play each position, with a link to the ball-skills drill that practises it.
import { Brain, ChevronDown, Lightbulb, Map } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Tabs } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { Card, Chip, ErrorNote, Spinner, cn } from "../shared/ui";

export interface Tip {
  id: string;
  title: string;
  why: string;
  steps: string[];
  try?: string;
  drill?: string;
  when?: string;
  reason?: string;
}
export interface TipsData {
  position: string;
  today: Tip;
  mindset: Tip[];
  positions: { id: string; label: string; tips: Tip[] }[];
}

export function Tips() {
  const { data, error, loading, reload } = useApi<TipsData>("/api/me/tips");
  const [tab, setTab] = useState<"mindset" | "position">("mindset");
  const [pos, setPos] = useState<string | null>(null);
  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const shown = pos ?? data.position;
  const group = data.positions.find((p) => p.id === shown) ?? data.positions[0];
  return (
    <div className="space-y-5 pt-2">
      <div>
        <h1>Match tips</h1>
        <p className="text-ink-2 text-sm">How to stay confident in a game, and how to play your position.</p>
      </div>

      <div className="space-y-5 lg:grid lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-start lg:gap-6 lg:space-y-0">
        <section aria-label="Tip for today">
          <Card className="border-pitch-400 bg-pitch-900/40">
            <p className="text-pitch-300 flex items-center gap-2 text-xs font-bold tracking-wider uppercase">
              <Lightbulb className="h-4 w-4" aria-hidden /> Tip for today · {data.today.reason}
            </p>
            <TipBody t={data.today} />
          </Card>
        </section>

        <section className="space-y-3">
          <Tabs
            tone="plain"
            label="Tips"
            value={tab}
            onChange={setTab}
            items={[
              ["mindset", "Mindset"],
              ["position", "Positions"],
            ]}
          />
          {tab === "position" && (
            <label className="flex items-center gap-2 text-sm font-semibold">
              Position
              <select className="bg-surface border-line h-11 flex-1 rounded-xl border px-3" value={shown} onChange={(e) => setPos(e.target.value)}>
                {data.positions.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                    {p.id === data.position ? " (yours)" : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
          <ul className="space-y-2">
            {(tab === "mindset" ? data.mindset : group.tips).map((t) => (
              <li key={t.id}>
                <TipCard t={t} icon={tab === "mindset" ? Brain : Map} />
              </li>
            ))}
          </ul>
          <p className="text-ink-2 text-xs">
            Feeling anxious or low for more than a few days, not only around games? Talk to someone you trust: a parent, your coach or
            the club's welfare officer.
          </p>
        </section>
      </div>
    </div>
  );
}

function TipCard({ t, icon: Icon }: { t: Tip; icon: typeof Brain }) {
  const [open, setOpen] = useState(false);
  return (
    <Card className="p-0">
      <button className="tap flex w-full items-center gap-3 p-4 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <Icon className="text-pitch-300 h-5 w-5 shrink-0" aria-hidden />
        <span className="flex-1 font-bold">{t.title}</span>
        <ChevronDown className={cn("text-ink-2 h-5 w-5 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div className="px-4 pb-4">
          <TipBody t={t} hideTitle />
        </div>
      )}
    </Card>
  );
}

export function TipBody({ t, hideTitle = false }: { t: Tip; hideTitle?: boolean }) {
  return (
    <div className="space-y-2 text-sm">
      {!hideTitle && <p className="mt-1 text-lg font-bold">{t.title}</p>}
      <p className="text-ink-2">{t.why}</p>
      <ol className="space-y-1.5">
        {t.steps.map((s, i) => (
          <li key={s} className="flex gap-2">
            <span className="bg-pitch-600 font-display flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white">
              {i + 1}
            </span>
            <span>{s}</span>
          </li>
        ))}
      </ol>
      {t.try && <p className="text-ink-2 italic">{t.try}</p>}
      {t.drill && (
        <Link to={`/player/skills?drill=${t.drill}`} className="inline-block">
          <Chip tone="green">Practise it: open the drill →</Chip>
        </Link>
      )}
    </div>
  );
}
