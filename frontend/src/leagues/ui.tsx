// The Pro League app's own building blocks, on top of the shared ones: a panel with a titled
// header, the small capital labels the league sites use, segmented switches, a rank badge, and
// the colours that carry meaning here (good / bad, home / away).
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../shared/ui";
import { ordinal } from "./types";

// Meaning, not decoration: good and bad performance, and the two sides of a match
export const TONE = {
  good: "var(--color-good)",
  bad: "var(--color-bad)",
  brand: "var(--color-pitch-500)",
  home: "var(--color-home)",
  away: "var(--color-away)",
} as const;

// Small capitals over a number or a column: "POINTS", "FORM"
export function Label({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("lg-label", className)}>{children}</span>;
}

// A card with a header line: icon, title, a note, and something on the right
export function Panel({
  title,
  icon: Icon,
  note,
  action,
  children,
  className,
  bodyClassName,
  accent,
  level = 2,
  ...rest
}: {
  title: ReactNode;
  icon?: LucideIcon;
  note?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  accent?: string; // a line of colour along the top: the panel's meaning
  level?: 2 | 3;
  "aria-label"?: string;
}) {
  const H = level === 2 ? "h2" : "h3";
  return (
    <section className={cn("lg-panel", className)} style={accent ? { borderTopColor: accent, borderTopWidth: 3 } : undefined} {...rest}>
      <div className="border-line flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 border-b px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          {Icon && <Icon className="h-[18px] w-[18px] shrink-0" style={{ color: accent ?? "var(--color-pitch-600)" }} aria-hidden />}
          <H className="font-display text-ink text-[1.05rem] leading-tight font-extrabold">{title}</H>
          {note && <span className="text-ink-2 hidden text-xs sm:inline">{note}</span>}
        </div>
        {action}
      </div>
      <div className={cn("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

// A row of options where one is on (aria-pressed), drawn as one control
export function Segmented<K extends string>({
  value,
  options,
  onChange,
  label,
  className,
}: {
  value: K;
  options: Record<K, string>;
  onChange: (k: K) => void;
  label: string;
  className?: string;
}) {
  return (
    <div className={cn("lg-seg", className)} role="group" aria-label={label}>
      {(Object.keys(options) as K[]).map((k) => (
        <button key={k} onClick={() => onChange(k)} aria-pressed={value === k}>
          {options[k]}
        </button>
      ))}
    </div>
  );
}

// Where a team stands in the league for one number. Coloured only when there is a better end:
// the top quarter good, the bottom quarter bad.
export function RankBadge({ rank, teams, better, className }: { rank: number | null; teams: number | null; better: "high" | "low" | null; className?: string }) {
  if (rank == null || teams == null) return null;
  const quarter = Math.max(1, Math.round(teams / 4));
  const tone = !better ? "plain" : rank <= quarter ? "good" : rank > teams - quarter ? "bad" : "plain";
  return (
    <span
      className={cn(
        "num inline-flex shrink-0 items-baseline gap-0.5 rounded px-1.5 py-0.5 text-xs leading-none font-bold",
        tone === "good" ? "bg-good/12 text-good" : tone === "bad" ? "bg-bad/10 text-bad" : "bg-surface-2 text-ink-2",
        className,
      )}
      title={`${ordinal(rank)} ${better ? "best" : "highest"} of ${teams}`}
    >
      {ordinal(rank)}
      <span className="text-[10px] font-semibold opacity-75">/{teams}</span>
    </span>
  );
}

// A number under its label, for header bands and summary strips
export function Fact({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <Label className="block text-white/80">{label}</Label>
      <div className="font-display num mt-0.5 text-2xl leading-none font-extrabold text-white md:text-[1.7rem]">{children}</div>
    </div>
  );
}

// The competition's mark: its initials on its colour (no league logos in the app)
const MARK: Record<string, string> = {
  "la-liga": "LL",
  "premier-league": "PL",
  "ligue-1": "L1",
  bundesliga: "BL",
  "ligue-1-psg": "PSG",
  "champions-league": "UCL",
};
export function CompMark({ id, name, color, size = 44 }: { id: string; name: string; color: string; size?: number }) {
  const text =
    MARK[id] ??
    name
      .split(/\s+/)
      .map((w) => w[0])
      .join("")
      .slice(0, 3)
      .toUpperCase();
  return (
    <span
      aria-hidden
      className="font-display inline-flex shrink-0 items-center justify-center rounded-md font-black text-white ring-1 ring-white/25"
      style={{ width: size, height: size, background: color, fontSize: size * (text.length > 2 ? 0.3 : 0.4), textShadow: "0 1px 1px rgb(0 0 0 / 0.45)" }}
    >
      {text}
    </span>
  );
}

// Nothing to show, said plainly
export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-ink-2 border-line bg-surface-2/60 rounded-md border border-dashed px-4 py-6 text-center text-sm">{children}</p>;
}
