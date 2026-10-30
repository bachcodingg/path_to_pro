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
  // Premier League 2015/16
  "AFC Bournemouth": { code: "BOU", colors: ["#da291c", "#000000"] },
  Arsenal: { code: "ARS", colors: ["#ef0107", "#ffffff"] },
  "Aston Villa": { code: "AVL", colors: ["#670e36", "#95bfe5"] },
  Chelsea: { code: "CHE", colors: ["#034694", "#ffffff"] },
  "Crystal Palace": { code: "CRY", colors: ["#1b458f", "#c4122e"] },
  Everton: { code: "EVE", colors: ["#003399", "#ffffff"] },
  "Leicester City": { code: "LEI", colors: ["#003090", "#fdbe11"] },
  Liverpool: { code: "LIV", colors: ["#c8102e", "#f6eb61"] },
  "Manchester City": { code: "MCI", colors: ["#6cabdd", "#1c2c5b"] },
  "Manchester United": { code: "MUN", colors: ["#da291c", "#fbe122"] },
  "Newcastle United": { code: "NEW", colors: ["#241f20", "#ffffff"] },
  "Norwich City": { code: "NOR", colors: ["#fff200", "#00a650"] },
  Southampton: { code: "SOU", colors: ["#d71920", "#ffffff"] },
  "Stoke City": { code: "STK", colors: ["#e03a3e", "#ffffff"] },
  Sunderland: { code: "SUN", colors: ["#eb172b", "#ffffff"] },
  "Swansea City": { code: "SWA", colors: ["#ffffff", "#121212"] },
  "Tottenham Hotspur": { code: "TOT", colors: ["#ffffff", "#132257"] },
  Watford: { code: "WAT", colors: ["#fbee23", "#ed2127"] },
  "West Bromwich Albion": { code: "WBA", colors: ["#122f67", "#ffffff"] },
  "West Ham United": { code: "WHU", colors: ["#7a263a", "#1bb1e7"] },
  // Ligue 1 2015/16
  "AS Monaco": { code: "MON", colors: ["#e51b22", "#ffffff"] },
  Angers: { code: "ANG", colors: ["#000000", "#ffffff"] },
  Bastia: { code: "BAS", colors: ["#0050a0", "#ffffff"] },
  Bordeaux: { code: "BOR", colors: ["#1b1f44", "#ffffff"] },
  "Gazélec Ajaccio": { code: "GFC", colors: ["#d4001a", "#0b2e6b"] },
  Guingamp: { code: "GUI", colors: ["#d4001a", "#000000"] },
  Lille: { code: "LIL", colors: ["#e01e13", "#1a2b5f"] },
  Lorient: { code: "LOR", colors: ["#f58113", "#000000"] },
  Lyon: { code: "OL", colors: ["#ffffff", "#1c3f94"] },
  Montpellier: { code: "MTP", colors: ["#002f6c", "#f58113"] },
  Nantes: { code: "NAN", colors: ["#fcdd09", "#0b8c3b"] },
  "OGC Nice": { code: "NIC", colors: ["#c8102e", "#000000"] },
  "Olympique de Marseille": { code: "OM", colors: ["#ffffff", "#2faee0"] },
  "Paris Saint-Germain": { code: "PSG", colors: ["#004170", "#da291c"] },
  Rennes: { code: "REN", colors: ["#e13327", "#000000"] },
  "Saint-Étienne": { code: "ASSE", colors: ["#009639", "#ffffff"] },
  "Stade Malherbe Caen": { code: "CAE", colors: ["#1a3c7b", "#d7111f"] },
  "Stade de Reims": { code: "REI", colors: ["#ee2223", "#ffffff"] },
  Toulouse: { code: "TFC", colors: ["#5a2a82", "#ffffff"] },
  Troyes: { code: "TRO", colors: ["#0055a4", "#ffffff"] },
  // Bundesliga 2023/24 (Leverkusen's season)
  Augsburg: { code: "FCA", colors: ["#ba3733", "#46714d"] },
  "Bayer Leverkusen": { code: "B04", colors: ["#e32221", "#000000"] },
  "Bayern Munich": { code: "FCB", colors: ["#dc052d", "#0066b2"] },
  Bochum: { code: "BOC", colors: ["#005ca9", "#ffffff"] },
  "Borussia Dortmund": { code: "BVB", colors: ["#fde100", "#000000"] },
  "Borussia Mönchengladbach": { code: "BMG", colors: ["#ffffff", "#000000"] },
  "Darmstadt 98": { code: "D98", colors: ["#004e9e", "#ffffff"] },
  "Eintracht Frankfurt": { code: "SGE", colors: ["#e1000f", "#000000"] },
  "FC Heidenheim": { code: "FCH", colors: ["#e2001a", "#003e7e"] },
  "FC Köln": { code: "KOE", colors: ["#ffffff", "#ed1c24"] },
  "FSV Mainz 05": { code: "M05", colors: ["#c3141e", "#ffffff"] },
  Freiburg: { code: "SCF", colors: ["#000000", "#e2001a"] },
  Hoffenheim: { code: "TSG", colors: ["#1961b5", "#ffffff"] },
  "RB Leipzig": { code: "RBL", colors: ["#ffffff", "#dd0741"] },
  "Union Berlin": { code: "FCU", colors: ["#eb1923", "#ffffff"] },
  "VfB Stuttgart": { code: "VFB", colors: ["#ffffff", "#e32219"] },
  "Werder Bremen": { code: "SVW", colors: ["#1d9053", "#ffffff"] },
  Wolfsburg: { code: "WOB", colors: ["#65b32e", "#ffffff"] },
  // Champions League finalists (the rest are above)
  "AC Milan": { code: "MIL", colors: ["#fb090b", "#000000"] },
  "FC Porto": { code: "POR", colors: ["#00428c", "#ffffff"] },
  "Inter Milan": { code: "INT", colors: ["#0068a8", "#000000"] },
  Juventus: { code: "JUV", colors: ["#000000", "#ffffff"] },
};

const FALLBACK: [string, string][] = [
  ["#0b1230", "#6ee7cf"],
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
  if (name.startsWith("PathToPro")) return { code: "PTP", colors: ["#0b1230", "#6ee7cf"] };
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
