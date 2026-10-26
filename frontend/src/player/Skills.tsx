// Ball skills: today's personal technical session for the player's position (next to the
// gym), and the drill library for every position. Drills open to show how to do them.
import { ChevronDown, Footprints, ShieldCheck, User, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useApi } from "../shared/useApi";
import { Card, Chip, ErrorNote, SectionTitle, Spinner, cn } from "../shared/ui";

export interface Drill {
  id: string;
  name: string;
  positions: string[];
  focus: string;
  partner: "none" | "optional" | "needed";
  minutes: number;
  reps: string;
  steps: string[];
  cues: string[];
  harder: string;
  tags: string[];
  block?: string;
  variant?: string;
}
interface SkillsData {
  date: string;
  position: string;
  session: { title: string; minutes: number; mode: string; position_label: string; focus: string; blocks: Drill[]; adjustments: string[] };
  positions: { id: string; label: string; focus: string }[];
  drills: Drill[];
}

const PARTNER = {
  none: { text: "Alone or a wall", icon: User },
  optional: { text: "Better with a friend", icon: Users },
  needed: { text: "With a friend", icon: Users },
};

// Gym session and ball skills sit side by side: the switch between the two pages
export function TrainingSwitch({ active }: { active: "gym" | "skills" }) {
  const item = (to: string, key: string, label: string) => (
    <Link
      to={to}
      aria-current={active === key ? "page" : undefined}
      className={cn("tap flex flex-1 items-center justify-center rounded-lg px-3 text-sm font-bold", active === key ? "bg-pitch-600 text-white" : "text-ink-2 hover:text-ink")}
    >
      {label}
    </Link>
  );
  return (
    <nav aria-label="Training" className="bg-surface border-line flex gap-1 rounded-xl border p-1">
      {item("/player/gym", "gym", "Gym session")}
      {item("/player/skills", "skills", "Ball skills")}
    </nav>
  );
}

export function Skills() {
  const { data, error, loading, reload } = useApi<SkillsData>("/api/me/skills");
  const [params] = useSearchParams();
  const wanted = params.get("drill");
  const [pos, setPos] = useState<string | null>(null);

  useEffect(() => {
    if (wanted) document.getElementById(`drill-${wanted}`)?.scrollIntoView({ block: "center" });
  }, [wanted, data]);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const s = data.session;
  const wantedDrill = data.drills.find((d) => d.id === wanted);
  const shown = pos ?? (wantedDrill && !wantedDrill.positions.includes("all") ? wantedDrill.positions[0] : data.position);
  const own = data.drills.filter((d) => d.positions.includes(shown));
  const everyone = data.drills.filter((d) => d.positions.includes("all"));
  return (
    <div className="space-y-5 pt-2">
      <div>
        <h1>Ball skills</h1>
        <p className="text-ink-2 text-sm">
          {s.position_label}: {s.focus}
        </p>
      </div>
      <TrainingSwitch active="skills" />

      {/* Wide screens: today's session on the left, the library on the right */}
      <div className="space-y-5 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start lg:gap-6 lg:space-y-0">
        <section aria-label="Today's session" className="space-y-3">
          <SectionTitle>Today</SectionTitle>
          <Card>
            <div className="flex items-start gap-3">
              <Footprints className="text-pitch-300 mt-1 h-6 w-6 shrink-0" aria-hidden />
              <div className="flex-1">
                <p className="text-lg font-bold">{s.title}</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  <Chip>{s.minutes} min</Chip>
                  <Chip tone="green">{s.position_label}</Chip>
                  <Chip>{s.blocks.length} drills</Chip>
                </div>
              </div>
            </div>
            {s.adjustments.length > 0 && (
              <ul className="mt-3 space-y-1">
                {s.adjustments.map((a) => (
                  <li key={a} className="border-ready-amber/40 bg-ready-amber/10 flex gap-2 rounded-xl border p-2 text-sm">
                    <ShieldCheck className="text-ready-amber h-4 w-4 shrink-0" aria-hidden />
                    {a}
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <ol className="space-y-2">
            {s.blocks.map((d, i) => (
              <li key={d.id}>
                <DrillCard d={d} index={i + 1} />
              </li>
            ))}
          </ol>
        </section>

        <section aria-label="Drill library" className="space-y-3">
          <SectionTitle
            action={
              <label className="text-sm font-semibold">
                <span className="sr-only">Position</span>
                <select className="bg-surface border-line h-11 rounded-xl border px-3" value={shown} onChange={(e) => setPos(e.target.value)} aria-label="Drills for position">
                  {data.positions.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
            }
          >
            All drills
          </SectionTitle>
          <p className="text-ink-2 text-sm">{data.positions.find((p) => p.id === shown)?.focus}</p>
          <ul className="space-y-2">
            {own.map((d) => (
              <li key={d.id}>
                <DrillCard d={d} open={d.id === wanted} />
              </li>
            ))}
          </ul>
          <p className="text-ink-2 pt-2 text-xs font-bold tracking-wider uppercase">For every position</p>
          <ul className="space-y-2">
            {everyone.map((d) => (
              <li key={d.id}>
                <DrillCard d={d} open={d.id === wanted} />
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

function DrillCard({ d, index, open: initial = false }: { d: Drill; index?: number; open?: boolean }) {
  const [open, setOpen] = useState(initial);
  const partner = PARTNER[d.partner];
  return (
    <Card id={`drill-${d.id}`} className={cn("p-0", initial && "ring-pitch-400 ring-2")}>
      <button className="tap flex w-full items-start gap-3 p-4 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        {index != null && (
          <span className="bg-pitch-600 font-display flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-lg font-bold text-white">
            {index}
          </span>
        )}
        <span className="min-w-0 flex-1">
          {d.block && <span className="text-pitch-300 block text-xs font-bold tracking-wider uppercase">{d.block}</span>}
          <span className="block font-bold">{d.name}</span>
          <span className="text-ink-2 flex flex-wrap items-center gap-x-2 text-sm">
            <span>{d.reps}</span>
            <span>· {d.minutes} min</span>
            <span className="flex items-center gap-1">
              · <partner.icon className="h-3.5 w-3.5" aria-hidden /> {partner.text}
            </span>
          </span>
        </span>
        <ChevronDown className={cn("text-ink-2 mt-1 h-5 w-5 shrink-0 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div className="space-y-3 px-4 pb-4 text-sm">
          {d.variant && (
            <p className="border-ready-amber/40 bg-ready-amber/10 flex gap-2 rounded-xl border p-2">
              <ShieldCheck className="text-ready-amber h-4 w-4 shrink-0" aria-hidden />
              {d.variant}
            </p>
          )}
          <ol className="list-decimal space-y-1 pl-5">
            {d.steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
          <div>
            <p className="font-bold">Focus on</p>
            <ul className="text-ink-2 mt-1 space-y-0.5">
              {d.cues.map((c) => (
                <li key={c}>✓ {c}</li>
              ))}
            </ul>
          </div>
          {d.harder && (
            <p>
              <span className="font-bold">Harder: </span>
              <span className="text-ink-2">{d.harder}</span>
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
