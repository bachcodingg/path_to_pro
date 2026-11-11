// League table in the layout of the LaLiga and Premier League standings pages: all / home /
// away, a coloured bar for the European and relegation places, badges and the form guide.
import { useState } from "react";
import { Crest, FormGuide, clubMeta } from "../shared/Club";
import { Tabs } from "../shared/PageHeader";
import { Card, cn } from "../shared/ui";
import type { Standing } from "./types";

// 2015/16 rules: top four to the Champions League, fifth and sixth to the Europa League,
// bottom three relegated (cup winners can move the Europa League places; not shown here)
const ZONES = [
  { label: "Champions League", color: "#1d4ed8", has: (p: number) => p <= 4 },
  { label: "Europa League", color: "#ea580c", has: (p: number) => p === 5 || p === 6 },
  { label: "Relegation", color: "#dc2626", has: (p: number, n: number) => p > n - 3 },
];
const zoneOf = (p: number, n: number) => ZONES.find((z) => z.has(p, n));

type Venue = "all" | "home" | "away";
export interface Tables {
  table: Standing[];
  table_home?: Standing[];
  table_away?: Standing[];
}

const gd = (t: Standing) => {
  const d = t.gf - t.ga;
  return d > 0 ? `+${d}` : String(d);
};

export function LeagueTable({ tables, highlight, compare, onPick }: { tables: Tables; highlight: string; compare?: string | null; onPick: (id: string) => void }) {
  const [venue, setVenue] = useState<Venue>("all");
  const rows = (venue === "home" ? tables.table_home : venue === "away" ? tables.table_away : tables.table) ?? tables.table;
  const n = rows.length;
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-3">
        <h2 className="font-display text-xl font-bold uppercase">League table</h2>
        <Tabs
          tone="plain"
          label="Matches counted"
          value={venue}
          onChange={setVenue}
          items={[
            ["all", "All matches"],
            ["home", "Home"],
            ["away", "Away"],
          ]}
        />
      </div>
      <div className="overflow-x-auto">
        <table aria-label="League table" className="num w-full min-w-[640px] text-sm">
          <thead className="text-ink-2 border-line border-b text-xs font-bold uppercase">
            <tr>
              <th className="w-12 py-2 pl-4 text-left">Pos</th>
              <th className="py-2 text-left">Club</th>
              <Th title="Played">Pl</Th>
              <Th title="Won">W</Th>
              <Th title="Drawn">D</Th>
              <Th title="Lost">L</Th>
              <Th title="Goals for" wide>
                GF
              </Th>
              <Th title="Goals against" wide>
                GA
              </Th>
              <Th title="Goal difference">GD</Th>
              <Th title="Points">Pts</Th>
              <th className="py-2 pr-4 pl-3 text-left">Form</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => {
              const zone = venue === "all" ? zoneOf(t.position ?? 0, n) : undefined;
              const mine = t.id === highlight,
                theirs = t.id === compare;
              return (
                <tr
                  key={t.id}
                  className={cn(
                    "border-line hover:bg-surface-2 border-b transition-colors last:border-0",
                    mine && "bg-pitch-500/12 hover:bg-pitch-500/15",
                    theirs && "bg-ready/8",
                  )}
                >
                  <td className="relative py-2 pl-4 font-bold">
                    {zone && <span className="absolute inset-y-0 left-0 w-1" style={{ background: zone.color }} title={zone.label} />}
                    {t.position}
                  </td>
                  <td className="py-1.5">
                    <button className="tap flex items-center gap-2.5 text-left font-semibold hover:underline" onClick={() => onPick(t.id)}>
                      <Crest name={t.team} size={24} />
                      <span className="hidden sm:inline">{t.team}</span>
                      <span className="sm:hidden">{clubMeta(t.team).code}</span>
                    </button>
                  </td>
                  <Td>{t.played}</Td>
                  <Td>{t.won}</Td>
                  <Td>{t.drawn}</Td>
                  <Td>{t.lost}</Td>
                  <Td wide>{t.gf}</Td>
                  <Td wide>{t.ga}</Td>
                  <Td>{gd(t)}</Td>
                  <td className="px-2 py-2 text-center text-base font-extrabold">{t.points}</td>
                  <td className="py-2 pr-4 pl-3">{t.form && <FormGuide form={t.form} />}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {venue === "all" && (
        <ul className="text-ink-2 border-line flex flex-wrap gap-x-5 gap-y-1 border-t px-4 py-2.5 text-xs" aria-label="Key">
          {ZONES.map((z) => (
            <li key={z.label} className="flex items-center gap-1.5">
              <span className="h-3 w-1 rounded-full" style={{ background: z.color }} aria-hidden />
              {z.label}
            </li>
          ))}
          <li>Form: last five matches, newest on the right</li>
        </ul>
      )}
    </Card>
  );
}

function Th({ children, title, wide }: { children: string; title: string; wide?: boolean }) {
  return (
    <th className={cn("px-2 py-2 text-center", wide && "hidden md:table-cell")}>
      <abbr title={title} className="no-underline">
        {children}
      </abbr>
    </th>
  );
}

function Td({ children, wide }: { children: number | string; wide?: boolean }) {
  return <td className={cn("px-2 py-2 text-center", wide && "hidden md:table-cell")}>{children}</td>;
}

// Narrow version for the overview's side column: position, badge, points, form
export function MiniTable({ rows, highlight, compare, onPick, onMore }: { rows: Standing[]; highlight: string; compare?: string | null; onPick: (id: string) => void; onMore: () => void }) {
  const n = rows.length;
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between px-4 pt-3 pb-1">
        <h2 className="font-display text-xl font-bold uppercase">League table</h2>
        <button className="tap text-pitch-600 text-sm font-semibold hover:underline" onClick={onMore}>
          Full table →
        </button>
      </div>
      <table aria-label="League table" className="num w-full text-sm">
        <thead className="text-ink-2 text-xs font-bold uppercase">
          <tr>
            <th className="w-10 py-1 pl-4 text-left">#</th>
            <th className="py-1 text-left">Club</th>
            <th className="px-1 py-1 text-right">GD</th>
            <th className="px-2 py-1 text-right">Pts</th>
            <th className="py-1 pr-4 pl-2 text-left">Form</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => {
            const zone = zoneOf(t.position ?? 0, n);
            return (
              <tr key={t.id} className={cn("border-line border-t", t.id === highlight && "bg-pitch-500/12 font-bold", t.id === compare && "bg-ready/8")}>
                <td className="relative py-1 pl-4">
                  {zone && <span className="absolute inset-y-0 left-0 w-1" style={{ background: zone.color }} title={zone.label} />}
                  {t.position}
                </td>
                <td className="py-0.5">
                  <button className="tap flex items-center gap-2 text-left hover:underline" onClick={() => onPick(t.id)} aria-label={t.team}>
                    <Crest name={t.team} size={18} />
                    {clubMeta(t.team).code}
                  </button>
                </td>
                <td className="px-1 py-1 text-right">{gd(t)}</td>
                <td className="px-2 py-1 text-right font-bold">{t.points}</td>
                <td className="py-1 pr-4 pl-2">{t.form && <FormGuide form={t.form.slice(-3)} />}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
