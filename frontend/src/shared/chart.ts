// One look for every Recharts chart: quiet axes and grid in the theme's ink and line colours,
// and a tooltip that is a small card. Colours are CSS variables, so charts follow dark mode.
import type { CSSProperties } from "react";

export const AXIS = { tick: { fill: "var(--ink-2)", fontSize: 11 }, tickLine: false, axisLine: false } as const;

export const GRID = { stroke: "var(--line)", vertical: false } as const;

export const TOOLTIP = {
  contentStyle: {
    background: "var(--surface)",
    border: "1px solid var(--line)",
    borderRadius: 12,
    boxShadow: "0 4px 16px rgb(0 0 0 / 0.08)",
    fontSize: 12,
    color: "var(--ink)",
  } satisfies CSSProperties,
  labelStyle: { fontWeight: 700, marginBottom: 2 } satisfies CSSProperties,
  cursor: { fill: "var(--surface-2)" },
} as const;
