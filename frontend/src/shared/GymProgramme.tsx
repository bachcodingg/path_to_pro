// One gym session: shared blocks every footballer does + the position block, with the
// safety adjustments (growth zone, readiness, match tomorrow) shown on top.
import { ChevronDown, Dumbbell, ShieldCheck, Target } from "lucide-react";
import { useState } from "react";
import type { GymItem, GymProgramme } from "./types";
import { Card, Chip, cn } from "./ui";

const EQUIPMENT: Record<string, string> = {
  bodyweight: "Bodyweight",
  band: "Band",
  dumbbell: "Dumbbell",
  barbell: "Barbell",
  box: "Box or step",
  med_ball: "Med ball",
  partner: "Partner",
  bench: "Bench",
  bar: "Pull-up bar",
};

export function GymProgrammeView({ p, compact = false }: { p: GymProgramme; compact?: boolean }) {
  return (
    <div className="space-y-3" aria-label={`Gym programme: ${p.title}`}>
      <div className="flex flex-wrap items-center gap-2">
        <Chip>{p.minutes} min</Chip>
        <Chip>{p.stage_label}</Chip>
        <Chip tone="green">{p.position_label}</Chip>
      </div>
      {!compact && <p className="text-ink-2 text-sm">Intensity: {p.intensity}.</p>}
      {p.adjustments.length > 0 && (
        <ul className="space-y-1">
          {p.adjustments.map((a) => (
            <li key={a} className="border-caution/40 bg-caution/10 flex gap-2 rounded-xl border p-2 text-sm">
              <ShieldCheck className="text-caution h-4 w-4 shrink-0" aria-hidden />
              {a}
            </li>
          ))}
        </ul>
      )}
      {/* Wide screens: blocks side by side, in session order row by row */}
      <div className={cn("space-y-3", !compact && "lg:grid lg:grid-cols-2 lg:items-start lg:gap-4 lg:space-y-0")}>
        {p.blocks.map((b) => (
          <section key={b.title}>
            <h3 className="mb-1 flex items-center gap-2 text-sm font-bold">
              {b.tag === "position" ? <Target className="text-pitch-400 h-4 w-4" aria-hidden /> : <Dumbbell className="h-4 w-4" aria-hidden />}
              {b.title}
              <span className="text-ink-2 text-xs font-medium">{b.tag === "position" ? `· ${p.position_label}` : "· everyone"}</span>
            </h3>
            <div className="border-line divide-[color:var(--line)] divide-y rounded-xl border">
              {b.items.map((it) => (
                <ExerciseRow key={it.id} it={it} compact={compact} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function ExerciseRow({ it, compact }: { it: GymItem; compact: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        className="tap flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        disabled={compact}
      >
        <span className="min-w-0">
          <span className="block font-semibold">{it.name}</span>
          <span className="text-ink-2 text-xs">
            {EQUIPMENT[it.equipment] ?? it.equipment}
            {it.rest_s > 0 && ` · rest ${it.rest_s} s`}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-1 font-bold tabular-nums">
          {it.sets} × {it.amount}
          {!compact && <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} aria-hidden />}
        </span>
      </button>
      {open && <p className="text-ink-2 px-3 pb-2 text-sm">{it.cue}</p>}
    </div>
  );
}

export function GymCard({ p }: { p: GymProgramme }) {
  return (
    <Card>
      <p className="mb-2 text-lg font-bold">{p.title}</p>
      <GymProgrammeView p={p} />
    </Card>
  );
}
