// Team analysis: overview (strengths, weaknesses, style, key numbers, league table) and the
// measure lists with each team's place in the league's range.
import { Card, Chip, SectionTitle, StatTile, cn } from "../shared/ui";
import { MiniTable } from "./LeagueTable";
import { fmtMeasure, rankText, type Measure, type Standing, type StyleProfile } from "./types";
import { usePro } from "./context";

const VERDICT: Record<string, { label: string; tone: "green" | "red" | "neutral"; dot: string }> = {
  strength: { label: "Strength", tone: "green", dot: "var(--color-ready-green)" },
  weakness: { label: "Weakness", tone: "red", dot: "var(--color-ready-red)" },
  style: { label: "Habit", tone: "neutral", dot: "var(--color-pitch-500)" },
};
const KEY_NUMBERS = ["goals", "conceded", "xg", "xga", "possession", "pass_acc", "ppda", "aerial_win", "conversion", "shots"];

export function Overview({ p, vs, table, onPick, onTable }: { p: StyleProfile; vs: StyleProfile | null | undefined; table: Standing[]; onPick: (id: string) => void; onTable: () => void }) {
  const { label, rest } = usePro();
  const by = Object.fromEntries(p.measures.map((m) => [m.key, m]));
  const vsBy = vs ? Object.fromEntries(vs.measures.map((m) => [m.key, m])) : {};
  return (
    <div className={cn("grid gap-4", table.length > 0 && "lg:grid-cols-[minmax(0,1fr)_21rem]")}>
      <div className="space-y-5">
        <div className="grid gap-4 md:grid-cols-3">
          <Summary title="Strengths" tone="var(--color-ready-green)" items={p.summary.strength} empty={`Nothing clearly better than ${rest}.`} />
          <Summary title="Weaknesses" tone="var(--color-ready-red)" items={p.summary.weakness} empty={`Nothing clearly worse than ${rest}.`} />
          <Summary title="How they play" tone="var(--color-pitch-500)" items={p.summary.style} empty={`No habit stands out from ${rest}.`} />
        </div>

        <section>
          <SectionTitle>Key numbers</SectionTitle>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
            {KEY_NUMBERS.filter((k) => by[k]).map((k) => {
              const m = by[k];
              return (
                <StatTile
                  key={k}
                  label={m.label}
                  value={fmtMeasure(m, m.value)}
                  accent={m.verdict ? VERDICT[m.verdict].dot : undefined}
                  sub={
                    <>
                      {vsBy[k] && (
                        <span className="text-ink block font-semibold">
                          {vs?.team}: {fmtMeasure(vsBy[k], vsBy[k].value)}
                        </span>
                      )}
                      {label} {fmtMeasure(m, m.league)}
                      {m.rank ? ` · ${rankText(m)}` : ""}
                    </>
                  }
                />
              );
            })}
          </div>
        </section>
      </div>

      {table.length > 0 && (
        <div className="self-start">
          <MiniTable rows={table} highlight={p.id} compare={vs?.id} onPick={onPick} onMore={onTable} />
        </div>
      )}
    </div>
  );
}

function Summary({ title, tone, items, empty }: { title: string; tone: string; items: string[]; empty: string }) {
  return (
    <Card className="border-t-4" style={{ borderTopColor: tone }}>
      <h3 className="font-display mb-2 text-xl font-bold uppercase">{title}</h3>
      {items.length ? (
        <ul className="space-y-1.5 text-sm">
          {items.map((i) => (
            <li key={i} className="flex gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: tone }} aria-hidden />
              <span>{i}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-ink-2 text-sm">{empty}</p>
      )}
    </Card>
  );
}

export function MeasureList({ p, vs, groups }: { p: StyleProfile; vs: StyleProfile | null | undefined; groups: string[] }) {
  const { rest } = usePro();
  const vsBy = vs ? Object.fromEntries(vs.measures.map((m) => [m.key, m])) : {};
  return (
    <div className="space-y-4">
      {groups.map((g) => (
        <section key={g}>
          <SectionTitle>{p.groups.find((x) => x.key === g)?.label ?? g}</SectionTitle>
          <Card className="p-0">
            <ul className="divide-y divide-[color:var(--line)]">
              {p.measures
                .filter((m) => m.group === g)
                .map((m) => (
                  <MeasureRow key={m.key} m={m} vs={vsBy[m.key]} vsName={vs?.team} />
                ))}
            </ul>
          </Card>
        </section>
      ))}
      <p className="text-ink-2 text-xs">
        Each bar runs from the lowest to the highest team in the data; where less is better (goals conceded, PPDA, fouls) the
        best team is on the right. Black tick: {rest}. A label appears only when the 95% interval over the team's matches
        excludes that value.
      </p>
    </div>
  );
}

function MeasureRow({ m, vs, vsName }: { m: Measure; vs?: Measure; vsName?: string }) {
  const { label } = usePro();
  const lo = m.league_min ?? 0,
    hi = m.league_max ?? 1;
  const flip = m.better === "low"; // best on the right
  const at = (v: number | null | undefined) => {
    if (v == null || hi === lo) return 50;
    const t = (v - lo) / (hi - lo);
    return Math.max(0, Math.min(100, 100 * (flip ? 1 - t : t)));
  };
  const v = m.verdict ? VERDICT[m.verdict] : null;
  return (
    <li className="grid gap-x-4 gap-y-2 p-3 md:grid-cols-[minmax(0,1.2fr)_9rem_minmax(0,1fr)] md:items-center">
      <div className="min-w-0">
        <p className="font-semibold">{m.label}</p>
        {m.help && <p className="text-ink-2 text-xs">{m.help}</p>}
      </div>
      <div className="md:text-right">
        <p className="text-lg leading-tight font-extrabold">
          {fmtMeasure(m, m.value)}
          {vs && <span className="text-ink-2 ml-1 text-sm font-semibold">vs {fmtMeasure(vs, vs.value)}</span>}
        </p>
        <p className="text-ink-2 text-xs">
          {label} {fmtMeasure(m, m.league)}
          {m.rank ? ` · ${rankText(m)}` : ""}
        </p>
      </div>
      <div>
        <div className="bg-surface-2 relative h-2.5 rounded-full border border-line" aria-hidden>
          {m.league != null && <span className="absolute -top-1 h-[18px] w-0.5" style={{ left: `${at(m.league)}%`, background: "var(--ink)" }} />}
          {vs && (
            <span
              className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-transparent"
              style={{ left: `${at(vs.value)}%`, borderColor: "var(--ink)" }}
              title={vsName}
            />
          )}
          <span
            className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white"
            style={{ left: `${at(m.value)}%`, background: v?.dot ?? "var(--color-pitch-600)" }}
          />
        </div>
        <div className="text-ink-2 mt-1 flex justify-between text-[11px]">
          <span>{fmtMeasure(m, flip ? hi : lo)}</span>
          {v && <Chip tone={v.tone}>{v.label}</Chip>}
          <span>{fmtMeasure(m, flip ? lo : hi)}</span>
        </div>
      </div>
    </li>
  );
}
