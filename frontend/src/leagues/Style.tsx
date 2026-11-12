// Team analysis: the overview (head to head with a second club, strengths, weaknesses and
// habits, where the team ranks area by area, key numbers, league table) and the measure lists
// with each team's place in the league's range. What stands out from the league is drawn
// stronger than what does not.
import { Compass, Crosshair, Gauge, Hash, RectangleVertical, Shield, Swords, TrendingDown, TrendingUp, Waypoints, type LucideIcon } from "lucide-react";
import { Crest } from "../shared/Club";
import { cn } from "../shared/ui";
import { usePro } from "./context";
import { MiniTable } from "./LeagueTable";
import { fmtMeasure, ordinal, rankText, type Measure, type Standing, type StyleProfile } from "./types";
import { Panel, RankBadge, TONE } from "./ui";

const VERDICT: Record<string, { label: string; colour: string; chip: string }> = {
  strength: { label: "Strength", colour: TONE.good, chip: "bg-good/12 text-good" },
  weakness: { label: "Weakness", colour: TONE.bad, chip: "bg-bad/10 text-bad" },
  style: { label: "Habit", colour: TONE.brand, chip: "bg-pitch-500/12 text-pitch-700" },
};
const KEY_NUMBERS = ["goals", "conceded", "xg", "xga", "possession", "pass_acc", "ppda", "aerial_win", "conversion", "shots"];
const GROUP_ICON: Record<string, LucideIcon> = {
  results: Hash,
  passing: Waypoints,
  shooting: Crosshair,
  duels: Swords,
  defending: Shield,
  discipline: RectangleVertical,
};

type By = Record<string, Measure>;
const index = (p: StyleProfile | null | undefined): By => (p ? Object.fromEntries(p.measures.map((m) => [m.key, m])) : {});

export function Overview({ p, vs, table, onPick, onTable }: { p: StyleProfile; vs: StyleProfile | null | undefined; table: Standing[]; onPick: (id: string) => void; onTable: () => void }) {
  const { label, rest } = usePro();
  const by = index(p);
  return (
    <div className={cn("grid items-start gap-4 md:gap-5", table.length > 0 && "xl:grid-cols-[minmax(0,1fr)_21rem]")}>
      <div className="space-y-4 md:space-y-5">
        {vs && <HeadToHead a={p} b={vs} />}
        <div className="grid gap-4 md:grid-cols-3 md:gap-5">
          <Summary title="Strengths" icon={TrendingUp} tone={TONE.good} items={p.summary.strength} empty={`Nothing clearly better than ${rest}.`} />
          <Summary title="Weaknesses" icon={TrendingDown} tone={TONE.bad} items={p.summary.weakness} empty={`Nothing clearly worse than ${rest}.`} />
          <Summary title="How they play" icon={Compass} tone={TONE.brand} items={p.summary.style} empty={`No habit stands out from ${rest}.`} />
        </div>

        <RankProfile p={p} vs={vs} />

        <section aria-label="Key numbers">
          <h2 className="font-display mb-2 text-xl font-extrabold">Key numbers</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {KEY_NUMBERS.filter((k) => by[k]).map((k) => {
              const m = by[k];
              const v = m.verdict ? VERDICT[m.verdict] : null;
              return (
                <div key={k} className="lg-panel relative flex flex-col p-3">
                  {v && <span className="absolute inset-y-0 left-0 w-1" style={{ background: v.colour }} aria-hidden />}
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-ink-2 text-xs leading-tight font-bold">{m.label}</p>
                    <RankBadge rank={m.rank} teams={m.teams} better={m.better} />
                  </div>
                  <p className="font-display num mt-1.5 text-[2rem] leading-none font-extrabold">{fmtMeasure(m, m.value)}</p>
                  <div className="mt-auto pt-3">
                    <Scale m={m} />
                    <p className="text-ink-2 num mt-1.5 text-xs">
                      {label} {fmtMeasure(m, m.league)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {table.length > 0 && <MiniTable rows={table} highlight={p.id} compare={vs?.id} onPick={onPick} onMore={onTable} />}
    </div>
  );
}

// "Pass accuracy: 85% (2nd best of 20; league 76%)" as name, number and context
function split(item: string): [string, string, string] | null {
  const m = item.match(/^(.+?): (.+?) \((.+)\)$/);
  return m ? [m[1], m[2], m[3]] : null;
}

function Summary({ title, icon, tone, items, empty }: { title: string; icon: LucideIcon; tone: string; items: string[]; empty: string }) {
  return (
    <Panel title={title} icon={icon} accent={tone} level={3} bodyClassName="p-0" note={items.length ? String(items.length) : undefined}>
      {items.length ? (
        <ul className="divide-line divide-y text-sm">
          {items.map((i) => {
            const parts = split(i);
            return (
              <li key={i} className="px-4 py-2">
                {parts ? (
                  <>
                    <span className="flex items-baseline justify-between gap-3">
                      <span className="font-semibold">{parts[0]}</span>
                      <b className="num font-display shrink-0 text-base font-extrabold" style={{ color: tone }}>
                        {parts[1]}
                      </b>
                    </span>
                    <span className="text-ink-2 block text-xs">{parts[2]}</span>
                  </>
                ) : (
                  i
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-ink-2 p-4 text-sm">{empty}</p>
      )}
    </Panel>
  );
}

// Area by area: the team's average league rank over the numbers that have a better end
function areas(p: StyleProfile) {
  return p.groups
    .map((g) => {
      const ranked = p.measures.filter((m) => m.group === g.key && m.better && m.rank != null && m.teams);
      if (!ranked.length) return null;
      const rank = ranked.reduce((s, m) => s + m.rank!, 0) / ranked.length;
      const teams = ranked[0].teams!;
      return { ...g, rank, teams, n: ranked.length, score: teams > 1 ? (teams - rank) / (teams - 1) : 0.5 };
    })
    .filter((a): a is NonNullable<typeof a> => a != null);
}

function RankProfile({ p, vs }: { p: StyleProfile; vs: StyleProfile | null | undefined }) {
  const rows = areas(p);
  if (!rows.length) return null;
  const other = vs ? Object.fromEntries(areas(vs).map((a) => [a.key, a])) : {};
  return (
    <Panel title="Where they rank" icon={Gauge} note="average league rank, area by area">
      <ul className="grid gap-x-8 gap-y-3 md:grid-cols-2">
        {rows.map((a) => {
          const Icon = GROUP_ICON[a.key] ?? Hash;
          const tone = a.score >= 0.75 ? TONE.good : a.score <= 0.25 ? TONE.bad : TONE.brand;
          const o = other[a.key];
          return (
            <li key={a.key}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="flex items-center gap-2 font-bold">
                  <Icon className="text-ink-2 h-4 w-4 self-center" aria-hidden />
                  {a.label}
                </span>
                <span className="num text-ink-2 text-xs">
                  <b className="font-display text-ink text-base font-extrabold">{a.rank.toFixed(1)}</b> of {a.teams}
                  {o && <span style={{ color: "var(--color-away)" }} className="font-bold"> · {vs?.team} {o.rank.toFixed(1)}</span>}
                </span>
              </div>
              <div className="bg-surface-2 border-line relative mt-1 h-2.5 rounded-full border" role="img" aria-label={`${a.label}: average rank ${a.rank.toFixed(1)} of ${a.teams}`}>
                <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${Math.max(4, 100 * a.score)}%`, background: tone }} />
                {o && <span className="bg-surface absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px]" style={{ left: `${100 * o.score}%`, borderColor: "var(--color-away)" }} title={vs?.team} />}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="text-ink-2 mt-3 text-xs">
        The mean of the team's league rank over each area's numbers that have a better end (1 is best). Habits, such as how
        often they cross, are left out. A longer bar is a better rank.
      </p>
    </Panel>
  );
}

// Two clubs face to face: the key numbers grow from the middle, the better side at full strength
function HeadToHead({ a, b }: { a: StyleProfile; b: StyleProfile }) {
  const A = index(a),
    B = index(b);
  const side = (p: StyleProfile, right?: boolean) => (
    <div className={cn("flex min-w-0 items-center gap-3", right && "flex-row-reverse text-right")}>
      <Crest name={p.team} size={48} />
      <div className="min-w-0">
        <p className="font-display truncate text-xl leading-tight font-extrabold">{p.team}</p>
        <p className="text-ink-2 num text-xs font-semibold">
          {p.standing.position != null && `${ordinal(p.standing.position)} · `}
          {p.standing.points} pts · W{p.standing.won} D{p.standing.drawn} L{p.standing.lost}
        </p>
      </div>
    </div>
  );
  return (
    <section className="lg-panel" aria-label={`${a.team} compared with ${b.team}`}>
      <div className="border-line bg-surface-2/60 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 border-b px-4 py-3">
        {side(a)}
        <span className="font-display bg-[#0b1230] rounded px-2 py-1 text-sm leading-none font-black text-white">VS</span>
        {side(b, true)}
      </div>
      <div className="grid gap-x-10 gap-y-3 p-4 md:grid-cols-2">
        {KEY_NUMBERS.filter((k) => A[k] && B[k]).map((k) => {
          const m = A[k],
            o = B[k];
          const x = m.value ?? 0,
            y = o.value ?? 0;
          const total = Math.abs(x) + Math.abs(y) || 1;
          const better = m.better == null || x === y ? null : (m.better === "high") === x > y ? "a" : "b";
          const dim = (s: "a" | "b") => (m.better && better !== s ? "opacity-40" : undefined);
          return (
            <div key={k}>
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className={cn("num w-16", better === "a" ? "text-base font-extrabold" : "font-semibold")}>{fmtMeasure(m, m.value)}</span>
                <span className="text-ink-2 text-center text-[13px] font-semibold">{m.label}</span>
                <span className={cn("num w-16 text-right", better === "b" ? "text-base font-extrabold" : "font-semibold")}>{fmtMeasure(o, o.value)}</span>
              </div>
              <div className="mt-1 flex h-2 gap-0.5" aria-hidden>
                <span className="bg-surface-2 flex flex-1 justify-end overflow-hidden rounded-l-full">
                  <span className={cn("bg-home h-full rounded-l-full", dim("a"))} style={{ width: `${(100 * Math.abs(x)) / total}%` }} />
                </span>
                <span className="bg-surface-2 flex-1 overflow-hidden rounded-r-full">
                  <span className={cn("bg-away block h-full rounded-r-full", dim("b"))} style={{ width: `${(100 * Math.abs(y)) / total}%` }} />
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-ink-2 border-line border-t px-4 py-2 text-xs">
        Per match. The stronger bar is the better number; where neither end is better (share of passes) both are shown alike.
        On the other tabs {b.team} is the gold ring on each bar.
      </p>
    </section>
  );
}

// The league's range for one number: the lowest team on the left, the highest on the right
// (the other way round where less is better), a tick at the league's value, the team as a dot
// and the compared club as a ring
function Scale({ m, vs, vsName, ends }: { m: Measure; vs?: Measure; vsName?: string; ends?: boolean }) {
  const lo = m.league_min ?? 0,
    hi = m.league_max ?? 1;
  const flip = m.better === "low"; // best on the right
  const at = (v: number | null | undefined) => {
    if (v == null || hi === lo) return 50;
    const t = (v - lo) / (hi - lo);
    return Math.max(0, Math.min(100, 100 * (flip ? 1 - t : t)));
  };
  const colour = m.verdict ? VERDICT[m.verdict].colour : "var(--ink)";
  return (
    <div>
      <div className="relative h-4" aria-hidden>
        <span className="bg-line absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full" />
        {m.league != null && <span className="bg-ink-2 absolute top-0.5 bottom-0.5 w-0.5 -translate-x-1/2 rounded-full" style={{ left: `${at(m.league)}%` }} />}
        {vs && (
          <span
            className="bg-surface absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px]"
            style={{ left: `${at(vs.value)}%`, borderColor: "var(--color-away)" }}
            title={vsName}
          />
        )}
        <span
          className="border-surface absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 shadow-sm"
          style={{ left: `${at(m.value)}%`, background: colour }}
        />
      </div>
      {ends && (
        <div className="text-ink-2 num flex justify-between text-[11px] leading-none">
          <span>{fmtMeasure(m, flip ? hi : lo)}</span>
          <span>{fmtMeasure(m, flip ? lo : hi)}</span>
        </div>
      )}
    </div>
  );
}

export function MeasureList({ p, vs, groups }: { p: StyleProfile; vs: StyleProfile | null | undefined; groups: string[] }) {
  const { rest } = usePro();
  const vsBy = index(vs);
  return (
    <div className="space-y-4 md:space-y-5">
      {groups.map((g) => {
        const rows = p.measures.filter((m) => m.group === g);
        const count = (v: string) => rows.filter((m) => m.verdict === v).length;
        return (
          <Panel
            key={g}
            title={p.groups.find((x) => x.key === g)?.label ?? g}
            icon={GROUP_ICON[g]}
            bodyClassName="@container p-0"
            action={
              <span className="flex flex-wrap gap-1.5 text-xs font-bold">
                {(["strength", "weakness", "style"] as const).map(
                  (v) =>
                    count(v) > 0 && (
                      <span key={v} className={cn("rounded px-1.5 py-0.5", VERDICT[v].chip)}>
                        {count(v)} {VERDICT[v].label.toLowerCase()}
                        {count(v) > 1 ? "s" : ""}
                      </span>
                    ),
                )}
              </span>
            }
          >
            <ul className="divide-line divide-y">
              {rows.map((m) => (
                <MeasureRow key={m.key} m={m} vs={vsBy[m.key]} vsName={vs?.team} />
              ))}
            </ul>
          </Panel>
        );
      })}
      <p className="text-ink-2 text-xs">
        Each line runs from the lowest to the highest team in the data; where less is better (goals conceded, PPDA, fouls) the
        best team is on the right. Grey tick: {rest}.{vs ? ` Gold ring: ${vs.team}.` : ""} A label appears only when the 95% interval over the
        team's matches excludes that value.
      </p>
    </div>
  );
}

function MeasureRow({ m, vs, vsName }: { m: Measure; vs?: Measure; vsName?: string }) {
  const { label } = usePro();
  const v = m.verdict ? VERDICT[m.verdict] : null;
  return (
    <li className={cn("relative grid gap-x-5 gap-y-2 px-4 py-3 @2xl:grid-cols-[minmax(0,1.15fr)_8.5rem_minmax(0,1fr)] @2xl:items-center", v && "bg-surface-2/40")}>
      {v && <span className="absolute inset-y-0 left-0 w-1" style={{ background: v.colour }} aria-hidden />}
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className={v ? "font-extrabold" : "font-semibold"}>{m.label}</span>
          {v && <span className={cn("rounded px-1.5 py-0.5 text-[11px] leading-none font-bold tracking-wide uppercase", v.chip)}>{v.label}</span>}
        </p>
        {m.help && <p className="text-ink-2 text-xs">{m.help}</p>}
      </div>
      <div className="flex items-baseline justify-between gap-3 @2xl:block @2xl:text-right">
        <p className="num leading-tight">
          <span className={cn("font-display font-extrabold", v ? "text-2xl" : "text-xl")}>{fmtMeasure(m, m.value)}</span>
          {vs && (
            <span className="ml-1.5 text-sm font-bold" style={{ color: "var(--color-away)" }}>
              vs {fmtMeasure(vs, vs.value)}
            </span>
          )}
        </p>
        <p className="text-ink-2 num text-xs">
          {label} {fmtMeasure(m, m.league)}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <Scale m={m} vs={vs} vsName={vsName} ends />
        </div>
        <span className="flex w-14 shrink-0 justify-end" title={m.rank ? rankText(m) : undefined}>
          <RankBadge rank={m.rank} teams={m.teams} better={m.better} />
          {m.rank && <span className="sr-only">{rankText(m)}</span>}
        </span>
      </div>
    </li>
  );
}
