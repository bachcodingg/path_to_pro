// Reusable football pitch SVG (plan risk: build the pitch component once, reuse it).
import type { ReactNode } from "react";

export function PitchLines({ width = 100, height = 150, stroke = "rgba(255,255,255,0.35)" }) {
  const w = width,
    h = height;
  return (
    <g fill="none" stroke={stroke} strokeWidth={0.6}>
      <rect x={2} y={2} width={w - 4} height={h - 4} rx={1} />
      <line x1={2} y1={h / 2} x2={w - 2} y2={h / 2} />
      <circle cx={w / 2} cy={h / 2} r={w * 0.13} />
      <rect x={w * 0.22} y={2} width={w * 0.56} height={h * 0.15} />
      <rect x={w * 0.22} y={h - 2 - h * 0.15} width={w * 0.56} height={h * 0.15} />
      <rect x={w * 0.38} y={2} width={w * 0.24} height={h * 0.06} />
      <rect x={w * 0.38} y={h - 2 - h * 0.06} width={w * 0.24} height={h * 0.06} />
    </g>
  );
}

export function Pitch({
  width = 100,
  height = 150,
  children,
  className,
  label,
}: {
  width?: number;
  height?: number;
  children?: ReactNode;
  className?: string;
  label: string;
}) {
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className={className} role="img" aria-label={label}>
      <defs>
        <pattern id="mow" width={width} height={20} patternUnits="userSpaceOnUse">
          <rect width={width} height={10} fill="#1d6b44" />
          <rect y={10} width={width} height={10} fill="#1a6340" />
        </pattern>
      </defs>
      <rect width={width} height={height} rx={3} fill="url(#mow)" />
      <PitchLines width={width} height={height} />
      {children}
    </svg>
  );
}

export function Ball({ x, y, r = 3 }: { x: number; y: number; r?: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <circle r={r} fill="#fff" stroke="#111" strokeWidth={0.4} />
      <path d={`M0 ${-r * 0.45} L${r * 0.43} ${-r * 0.14} L${r * 0.27} ${r * 0.37} L${-r * 0.27} ${r * 0.37} L${-r * 0.43} ${-r * 0.14}Z`} fill="#111" />
    </g>
  );
}
