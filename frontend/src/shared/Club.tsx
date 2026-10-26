// Club identity for tables, match cards and headers: a badge in the club's colours with its
// three-letter code (LaLiga's abbreviations), and the W / D / L form guide.
// The badges are drawn from colours, not the clubs' crests, which are their trademarks.
import { cn } from "./ui";

interface ClubMeta {
  code: string;
  colors: [string, string];
}

// La Liga 2015/16, keyed by the names in the StatsBomb data
const CLUBS: Record<string, ClubMeta> = {
  "Athletic Club": { code: "ATH", colors: ["#ee2523", "#ffffff"] },
  "Atlético Madrid": { code: "ATM", colors: ["#cb3524", "#272e61"] },
  Barcelona: { code: "BAR", colors: ["#a50044", "#004d98"] },
  "Celta Vigo": { code: "CEL", colors: ["#8ac3ee", "#ffffff"] },
  Eibar: { code: "EIB", colors: ["#0a3a82", "#a6192e"] },
  Espanyol: { code: "ESP", colors: ["#007fc8", "#ffffff"] },
  Getafe: { code: "GET", colors: ["#005999", "#ffffff"] },
  Granada: { code: "GRA", colors: ["#c8102e", "#ffffff"] },
  "Las Palmas": { code: "LPA", colors: ["#ffe400", "#0055a5"] },
  "Levante UD": { code: "LEV", colors: ["#b4053f", "#004c9a"] },
  Málaga: { code: "MAL", colors: ["#00a0e1", "#ffffff"] },
  "RC Deportivo La Coruña": { code: "DEP", colors: ["#0067b1", "#ffffff"] },
  "Rayo Vallecano": { code: "RAY", colors: ["#ffffff", "#e53027"] },
  "Real Betis": { code: "BET", colors: ["#0bb363", "#ffffff"] },
  "Real Madrid": { code: "RMA", colors: ["#ffffff", "#febe10"] },
  "Real Sociedad": { code: "RSO", colors: ["#0067b1", "#ffffff"] },
  Sevilla: { code: "SEV", colors: ["#ffffff", "#d81e05"] },
  "Sporting Gijón": { code: "SPO", colors: ["#e4002b", "#ffffff"] },
  Valencia: { code: "VAL", colors: ["#ffffff", "#f18e00"] },
  Villarreal: { code: "VIL", colors: ["#ffe667", "#005187"] },
};

const FALLBACK: [string, string][] = [
  ["#0f3d2e", "#7ee0a8"],
  ["#1e3a8a", "#ffffff"],
  ["#7f1d1d", "#fbbf24"],
  ["#111827", "#f97316"],
  ["#5b21b6", "#ffffff"],
  ["#0e7490", "#fde68a"],
];

export function clubMeta(name: string): ClubMeta {
  const known = CLUBS[name];
  if (known) return known;
  // The academy's own team and its opponents: stable colours from the name
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const words = name.replace(/[^\p{L}\p{N} ]/gu, "").split(/\s+/).filter(Boolean);
  const num = name.match(/\d+/)?.[0];
  if (name.startsWith("PathToPro")) return { code: "PTP", colors: ["#0f3d2e", "#7ee0a8"] };
  const code = (num && words.length <= 2 ? words[0][0] + num : words.map((w) => w[0]).join("").slice(0, 3)).toUpperCase();
  return { code: code || "?", colors: FALLBACK[h % FALLBACK.length] };
}

function luminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

// Shield split diagonally in the club's two colours; the code is printed from 28 px up.
export function Crest({ name, size = 28, className }: { name: string; size?: number; className?: string }) {
  const { code, colors } = clubMeta(name);
  const [a, b] = colors;
  const ink = luminance(a) > 0.45 ? "#111" : "#fff";
  const id = `c${code}${size}`;
  return (
    <svg viewBox="0 0 40 46" width={size} height={size * 1.15} className={cn("shrink-0", className)} aria-hidden>
      <defs>
        <clipPath id={id}>
          <path d="M20 1.5 L37.5 7 V21 C37.5 32.5 30 40.5 20 44.5 C10 40.5 2.5 32.5 2.5 21 V7 Z" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${id})`}>
        <rect width={40} height={46} fill={a} />
        <path d="M40 18 L40 46 L8 46 Z" fill={b} />
      </g>
      <path
        d="M20 1.5 L37.5 7 V21 C37.5 32.5 30 40.5 20 44.5 C10 40.5 2.5 32.5 2.5 21 V7 Z"
        fill="none"
        stroke="rgb(0 0 0 / 0.25)"
        strokeWidth={1.2}
      />
      {size >= 28 && (
        <text
          x={20}
          y={24}
          textAnchor="middle"
          fontFamily="Barlow Condensed, Arial Narrow, sans-serif"
          fontWeight={800}
          fontSize={code.length > 3 ? 10.5 : 12.5}
          fill={ink}
          stroke={ink === "#fff" ? "rgb(0 0 0 / 0.35)" : "rgb(255 255 255 / 0.5)"}
          strokeWidth={0.6}
          paintOrder="stroke"
        >
          {code}
        </text>
      )}
    </svg>
  );
}

export type Result = "W" | "D" | "L";
const RESULT_BG: Record<Result, string> = { W: "bg-win", D: "bg-draw", L: "bg-loss" };
const RESULT_TEXT: Record<Result, string> = { W: "won", D: "drawn", L: "lost" };

// Last results, oldest first (the newest on the right, as on the league sites).
export function FormGuide({ form, size = "sm" }: { form: Result[]; size?: "sm" | "md" }) {
  return (
    <span className="inline-flex items-center gap-1" aria-label={`Form, oldest first: ${form.map((r) => RESULT_TEXT[r]).join(", ")}`}>
      {form.map((r, i) => (
        <span
          key={i}
          aria-hidden
          className={cn(
            "font-display inline-flex items-center justify-center rounded-full font-bold text-white",
            size === "sm" ? "h-5 w-5 text-[11px]" : "h-7 w-7 text-sm",
            RESULT_BG[r],
          )}
        >
          {r}
        </span>
      ))}
    </span>
  );
}

export function resultOf(gf: number, ga: number): Result {
  return gf > ga ? "W" : gf === ga ? "D" : "L";
}
