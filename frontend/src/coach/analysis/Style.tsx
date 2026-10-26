// Team analysis: overview (standing, strengths, weaknesses, style, league table) and the
// measure lists with each team's place in the league's range.
import { Card, Chip, SectionTitle, cn } from "../../shared/ui";
import { fmtMeasure, ordinal, rankText, type Measure, type Standing, type StyleProfile } from "./types";

const VERDICT: Record<string, { label: string; tone: "green" | "red" | "neutral"; dot: string }> = {
  strength: { label: "Strength", tone: "green", dot: "var(--color-ready-green)" },
  weakness: { label: "Weakness", tone: "red", dot: "var(--color-ready-red)" },
  style: { label: "Habit", tone: "neutral", dot: "var(--color-pitch-500)" },
};
const KEY_NUMBERS = ["goals", "conceded", "xg", "xga", "possession", "pass_acc", "ppda", "aerial_win", "conversion", "shots"];

export function Overview({ p, vs, table, onPick }: { p: StyleProfile; vs: StyleProfile | null | undefined; table: Standing[]; onPick: (id: string) => void }) {
  const by = Object.fromEntries(p.measures.map((m) => [m.key, m]));
  const vsBy = vs ? Object.fromEntries(vs.measures.map((m) => [m.key, m])) : {};
  const s = p.standing;
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="space-y-4">
        <Card className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <div>
            <p className="text-ink-2 text-xs font-semibold uppercase">League position</p>
            <p className="text-3xl font-extrabold">{ordinal(s.position)}</p>
          </div>
          <Fact label="Points" value={String(s.points)} />
          <Fact label="Won / drawn / lost" value={`${s.won} / ${s.drawn} / ${s.lost}`} />
          <Fact label="Goals" value={`${s.gf} – ${s.ga}`} />
          {vs && <p className="text-ink-2 text-sm">Compared with {vs.team} ({ordinal(vs.standing.position)}, {vs.standing.points} pts)</p>}
        </Card>

        <div className="grid gap-4 md:grid-cols-3">
          <Summary title="Strengths" items={p.summary.strength} empty="Nothing clearly better than the league." />
          <Summary title="Weaknesses" items={p.summary.weakness} empty="Nothing clearly worse than the league." />
          <Summary title="How they play" items={p.summary.style} empty="No habit stands out from the league." />
        </div>

        <section>
          <SectionTitle>Key numbers</SectionTitle>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
            {KEY_NUMBERS.filter((k) => by[k]).map((k) => (
              <Card key={k} className="p-3">
                <p className="text-ink-2 text-xs leading-tight">{by[k].label}</p>
                <p className="mt-1 text-xl font-extrabold">{fmtMeasure(by[k], by[k].value)}</p>
                {vsBy[k] && <p className="text-ink-2 text-xs">{vs?.team}: {fmtMeasure(vsBy[k], vsBy[k].value)}</p>}
                <p className="text-ink-2 text-xs">
                  league {fmtMeasure(by[k], by[k].league)} · {rankText(by[k])}
                </p>
              </Card>
            ))}
          </div>
        </section>
      </div>

      <Card className="self-start overflow-hidden p-0">
        <table className="w-full text-sm">
          <caption className="p-3 text-left font-bold">League table</caption>
          <thead className="text-ink-2 text-left text-xs">
            <tr>
              <th className="px-3 py-1">#</th>
              <th className="py-1">Team</th>
              <th className="px-1 py-1 text-right">GD</th>
              <th className="px-3 py-1 text-right">Pts</th>
            </tr>
          </thead>
          <tbody>
            {table.map((t) => (
              <tr key={t.id} className={cn(t.id === p.id && "bg-pitch-500/15 font-bold", t.id === vs?.id && "bg-ready-green/10")}>
                <td className="px-3 py-1">{t.position}</td>
                <td className="py-1">
                  <button className="tap text-left hover:underline" onClick={() => onPick(t.id)}>
                    {t.team}
                  </button>
                </td>
                <td className="px-1 py-1 text-right">{t.gf - t.ga > 0 ? `+${t.gf - t.ga}` : t.gf - t.ga}</td>
                <td className="px-3 py-1 text-right">{t.points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-ink-2 text-xs">{label}</p>
      <p className="text-lg font-bold">{value}</p>
    </div>
  );
}

function Summary({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <Card>
      <h3 className="mb-2 font-bold">{title}</h3>
      {items.length ? (
        <ul className="list-disc space-y-1.5 pl-4 text-sm">
          {items.map((i) => (
            <li key={i}>{i}</li>
          ))}
        </ul>
      ) : (
        <p className="text-ink-2 text-sm">{empty}</p>
      )}
    </Card>
  );
}

export function MeasureList({ p, vs, groups }: { p: StyleProfile; vs: StyleProfile | null | undefined; groups: string[] }) {
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
        Each bar runs from the league's lowest to highest team; where less is better (goals conceded, PPDA, fouls) the best team
        is on the right. Black tick: rest of the league. A label appears only when the 95% interval over the team's matches
        excludes the league value.
      </p>
    </div>
  );
}

function MeasureRow({ m, vs, vsName }: { m: Measure; vs?: Measure; vsName?: string }) {
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
          league {fmtMeasure(m, m.league)} · {rankText(m)}
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
