// Match rating badge (3-10 scale) and its breakdown ("why this rating").
import type { BreakdownItem, RatingBand } from "./types";
import { cn } from "./ui";

export const RATING_COLOUR: Record<RatingBand, string> = {
  elite: "bg-[#2a6fdb] text-white",
  good: "bg-[#1fa05a] text-white",
  fair: "bg-[#a3c639] text-[#13240a]",
  average: "bg-[#f0a020] text-[#2a1800]",
  poor: "bg-[#e5484d] text-white",
};

export function ratingBand(v: number | null | undefined): RatingBand | null {
  if (v == null) return null;
  return v >= 8 ? "elite" : v >= 7 ? "good" : v >= 6.5 ? "fair" : v >= 6 ? "average" : "poor";
}

export function RatingBadge({ value, size = "md", estimate }: { value: number | null | undefined; size?: "sm" | "md" | "lg"; estimate?: boolean }) {
  const b = ratingBand(value);
  const sizes = { sm: "h-6 min-w-9 text-xs", md: "h-8 min-w-11 text-sm", lg: "h-12 min-w-16 text-xl" };
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-lg px-1.5 font-extrabold tabular-nums",
        sizes[size],
        b ? RATING_COLOUR[b] : "bg-surface-2 text-ink-2",
        estimate && "ring-2 ring-current/30 ring-offset-1 italic",
      )}
      aria-label={value == null ? "No rating" : `Rating ${value.toFixed(1)}${estimate ? " (estimate)" : ""}`}
      title={estimate ? "Estimate from the match diary" : undefined}
    >
      {value == null ? "–" : value.toFixed(1)}
    </span>
  );
}

export function Breakdown({ items }: { items: BreakdownItem[] }) {
  if (!items.length) return null;
  return (
    <ul className="space-y-1 text-sm">
      {items.map((b) => (
        <li key={b.label} className="flex justify-between gap-3">
          <span className="text-ink-2">{b.label}</span>
          {b.value !== 0 && (
            <span className={cn("font-semibold tabular-nums", b.value > 0 ? "text-ready-green" : "text-ready-red")}>
              {b.value > 0 ? "+" : ""}
              {b.value.toFixed(2)}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

export const POSITION_LABEL: Record<string, string> = {
  goalkeeper: "Goalkeeper",
  centre_back: "Centre-back",
  full_back: "Full-back",
  midfielder: "Midfielder",
  winger: "Winger",
  striker: "Striker",
};
