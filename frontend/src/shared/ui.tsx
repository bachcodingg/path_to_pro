// shadcn/ui-style primitives (cva + tailwind-merge), kept local.
import { cva, type VariantProps } from "class-variance-authority";
import { clsx, type ClassValue } from "clsx";
import { BatteryFull, BatteryLow, BatteryMedium, BatteryWarning, Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type HTMLAttributes, type ReactNode } from "react";
import { twMerge } from "tailwind-merge";
import type { Band, SessionKind } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const button = cva(
  "tap inline-flex items-center justify-center gap-2 rounded-xl px-4 text-[15px] font-semibold transition-colors disabled:opacity-50 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        primary: "bg-pitch-600 text-white hover:bg-pitch-700",
        secondary: "bg-surface border border-line text-ink hover:bg-surface-2",
        ghost: "text-ink-2 hover:bg-surface-2",
        danger: "bg-ready-red text-white hover:brightness-95",
        approve: "bg-ready-green text-white hover:brightness-95",
      },
      size: { md: "h-11", sm: "h-11 px-3 text-sm", lg: "h-14 text-base px-6" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button> & { loading?: boolean }
>(({ className, variant, size, loading, children, ...props }, ref) => (
  <button ref={ref} className={cn(button({ variant, size }), className)} {...props}>
    {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
    {children}
  </button>
));
Button.displayName = "Button";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("bg-surface rounded-2xl border border-line p-4 shadow-sm", className)} {...props} />;
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <h2 className="font-display text-ink flex items-center gap-2 text-lg font-bold tracking-wide uppercase">
        <span className="bg-pitch-500 h-4 w-1 rounded-full" aria-hidden />
        {children}
      </h2>
      {action}
    </div>
  );
}

export function Chip({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | Band }) {
  const tones = {
    neutral: "bg-surface-2 text-ink border-line",
    green: "bg-ready-green/10 text-ready-green border-ready-green/30",
    amber: "bg-ready-amber/10 text-amber-700 dark:text-ready-amber border-ready-amber/40",
    red: "bg-ready-red/10 text-ready-red border-ready-red/40",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold", tones[tone])}>
      {children}
    </span>
  );
}

export const BAND_TEXT: Record<Band, string> = { green: "Ready", amber: "Take care", red: "Recover" };
export const BAND_BG: Record<Band, string> = {
  green: "bg-ready-green",
  amber: "bg-ready-amber",
  red: "bg-ready-red",
};

export function BandIcon({ band, className }: { band: Band | null; className?: string }) {
  const Icon = band === "green" ? BatteryFull : band === "amber" ? BatteryMedium : band === "red" ? BatteryLow : BatteryWarning;
  return <Icon className={className} aria-hidden />;
}

export function BandBadge({ band, score }: { band: Band | null; score?: number | null }) {
  if (!band) return <Chip>No data</Chip>;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold text-white", BAND_BG[band])}>
      <BandIcon band={band} className="h-3.5 w-3.5" />
      {score != null ? Math.round(score) : BAND_TEXT[band]}
    </span>
  );
}

// Session intensity colour scale (lanes on the week pitch, strips in the inbox)
export function intensityClass(kind: SessionKind, rpe: number): string {
  if (kind === "match") return "bg-pitch-900 text-white";
  if (kind === "rest") return "bg-surface-2 text-ink-2";
  if (rpe <= 3) return "bg-pitch-200 text-pitch-900";
  if (rpe <= 5) return "bg-pitch-400 text-pitch-950";
  if (rpe <= 7) return "bg-pitch-600 text-white";
  return "bg-pitch-800 text-white";
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="text-ink-2 flex items-center justify-center gap-2 p-8" role="status">
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
      <span>{label}…</span>
    </div>
  );
}

// Placeholder in the shape of what is loading, so the page does not jump when it arrives
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

export function PageSkeleton({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-4">
      <Skeleton className="h-28 rounded-2xl" />
      <div className="grid gap-4 md:grid-cols-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
      <Skeleton className="h-64 rounded-2xl" />
      <span className="sr-only">{label}…</span>
    </div>
  );
}

// Big-number tile: label, value in the display face, a line of context
export function StatTile({ label, value, sub, accent, className }: { label: ReactNode; value: ReactNode; sub?: ReactNode; accent?: string; className?: string }) {
  return (
    <Card className={cn("relative overflow-hidden p-3", className)}>
      {accent && <span className="absolute inset-y-0 left-0 w-1" style={{ background: accent }} aria-hidden />}
      <p className="text-ink-2 text-xs leading-tight font-semibold">{label}</p>
      <p className="font-display num mt-1 text-[1.9rem] leading-none font-bold">{value}</p>
      {sub && <p className="text-ink-2 mt-1 text-xs">{sub}</p>}
    </Card>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card className="border-ready-red/40">
      <p className="text-ready-red font-semibold">Something went wrong</p>
      <p className="text-ink-2 mt-1 text-sm">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </Card>
  );
}

export function fmtDay(iso: string, opts: Intl.DateTimeFormatOptions = { weekday: "short" }): string {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-GB", opts);
}

export function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"],
    v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

export function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function fmtValue(v: number, unit: string): string {
  return unit === "m" ? String(Math.round(v)) : String(v);
}
