// Page header band (the league websites' pattern): eyebrow, big condensed title, one line of
// context, actions on the right and the page's tabs (or a summary strip) along the bottom edge.
import type { CSSProperties, ReactNode } from "react";
import { cn } from "./ui";

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  bottom,
  leading,
  accent,
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  bottom?: ReactNode;
  leading?: ReactNode;
  accent?: string; // a club colour glowing in from the right
  className?: string;
}) {
  // Bleeds to the edges of the staff layout's padded <main>
  return (
    <header
      style={accent ? ({ "--hero-glow": `${accent}80` } as CSSProperties) : undefined}
      // dark: chips, buttons and fields on the band take their dark-theme colours
      className={cn("hero dark -mx-4 -mt-4 mb-4 px-4 pt-4 md:-mx-6 md:-mt-6 md:mb-6 md:px-6 md:pt-7", !bottom && "pb-4 md:pb-6", className)}
    >
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="flex min-w-0 items-center gap-4">
          {leading}
          <div className="min-w-0">
            {eyebrow && <p className="text-pitch-300 text-xs font-bold tracking-[0.14em] uppercase">{eyebrow}</p>}
            <h1 className="font-display text-[1.75rem] leading-none font-extrabold tracking-tight uppercase md:text-[2.6rem]">{title}</h1>
            {subtitle && <div className="mt-1.5 max-w-3xl text-[13px] text-white/75 md:text-sm">{subtitle}</div>}
          </div>
        </div>
        {actions && <div className="hero-actions flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {bottom && <div className="mt-3 md:mt-4">{bottom}</div>}
    </header>
  );
}

export function Tabs<K extends string>({
  items,
  value,
  onChange,
  label,
  tone = "hero",
}: {
  items: readonly (readonly [K, string])[];
  value: K;
  onChange: (k: K) => void;
  label: string;
  tone?: "hero" | "plain";
}) {
  return (
    <div role="tablist" aria-label={label} className={cn("no-scrollbar flex gap-1 overflow-x-auto", tone === "plain" && "border-line border-b")}>
      {items.map(([key, text]) => (
        <button
          key={key}
          role="tab"
          aria-selected={value === key}
          onClick={() => onChange(key)}
          className={cn(
            "tap -mb-px shrink-0 border-b-[3px] px-3 py-2 text-sm font-bold transition-colors",
            tone === "hero"
              ? value === key
                ? "border-pitch-300 text-white"
                : "border-transparent text-white/65 hover:text-white"
              : value === key
                ? "border-pitch-600 text-ink"
                : "text-ink-2 hover:text-ink border-transparent",
          )}
        >
          {text}
        </button>
      ))}
    </div>
  );
}
