// The pitches the Pro League app draws on, in StatsBomb's yards (120 long, 80 wide): the
// attacking half seen from behind the attack (goal at the top) for shots and corners, and the
// whole pitch for a match. Mown in bands, lines in chalk, nothing else.
import { useId, type ReactNode } from "react";

const CHALK = "rgb(255 255 255 / 0.62)";

function Mow({ id, vertical, size }: { id: string; vertical?: boolean; size: number }) {
  return (
    <pattern id={id} width={vertical ? size * 2 : 1} height={vertical ? 1 : size * 2} patternUnits="userSpaceOnUse">
      <rect width={vertical ? size : 1} height={vertical ? 1 : size} fill="var(--turf-a, #1c6a45)" />
      <rect x={vertical ? size : 0} y={vertical ? 0 : size} width={vertical ? size : 1} height={vertical ? 1 : size} fill="var(--turf-b, #19613f)" />
    </pattern>
  );
}

// Attacking half, goal at the top: screen x is the pitch's width (0-80), screen y the distance
// from the goal line. `depth` is how far from the goal the picture runs.
export function HalfPitch({ depth = 50, label, children, className }: { depth?: number; label: string; children?: ReactNode; className?: string }) {
  const id = useId();
  return (
    <svg viewBox={`-3 -5 86 ${depth + 5}`} className={className ?? "w-full rounded-md"} role="img" aria-label={label}>
      <defs>
        <Mow id={id} size={6} />
      </defs>
      <rect x={-3} y={-5} width={86} height={depth + 5} fill="var(--turf-b, #19613f)" />
      <rect x={0} y={0} width={80} height={depth} fill={`url(#${id})`} />
      <g fill="none" stroke={CHALK} strokeWidth={0.35}>
        <rect x={0} y={0} width={80} height={60} />
        <rect x={18} y={0} width={44} height={18} />
        <rect x={30} y={0} width={20} height={6} />
        <rect x={36} y={-2.2} width={8} height={2.2} strokeWidth={0.5} stroke="#fff" />
        <path d="M 32.7 18 A 10 10 0 0 0 47.3 18" />
      </g>
      <circle cx={40} cy={12} r={0.45} fill={CHALK} />
      {children}
    </svg>
  );
}

// The whole pitch, left to right
export function FullPitch({ label, children, className }: { label: string; children?: ReactNode; className?: string }) {
  const id = useId();
  return (
    <svg viewBox="-3 -3 126 86" className={className ?? "w-full rounded-md"} role="img" aria-label={label}>
      <defs>
        <Mow id={id} size={10} vertical />
      </defs>
      <rect x={-3} y={-3} width={126} height={86} fill="var(--turf-b, #19613f)" />
      <rect x={0} y={0} width={120} height={80} fill={`url(#${id})`} />
      <g fill="none" stroke={CHALK} strokeWidth={0.4}>
        <rect x={0} y={0} width={120} height={80} />
        <line x1={60} y1={0} x2={60} y2={80} />
        <circle cx={60} cy={40} r={10} />
        <rect x={0} y={18} width={18} height={44} />
        <rect x={102} y={18} width={18} height={44} />
        <rect x={0} y={30} width={6} height={20} />
        <rect x={114} y={30} width={6} height={20} />
        <path d="M 18 32.7 A 10 10 0 0 1 18 47.3" />
        <path d="M 102 32.7 A 10 10 0 0 0 102 47.3" />
      </g>
      <g fill={CHALK}>
        <circle cx={60} cy={40} r={0.6} />
        <circle cx={12} cy={40} r={0.5} />
        <circle cx={108} cy={40} r={0.5} />
      </g>
      <rect x={-1.6} y={36} width={1.6} height={8} fill="#fff" />
      <rect x={120} y={36} width={1.6} height={8} fill="#fff" />
      {children}
    </svg>
  );
}
