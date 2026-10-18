// Club history: every club in the order the player joined, with years, teams (U12, U15,
// Men...), leagues and numbers. Overlapping clubs (dual registration, loans) sit side by side.
import { useApi } from "../shared/useApi";
import { BONUS_LABEL, eur, PERIOD } from "../shared/money";
import { Card, Chip, SectionTitle, cn } from "../shared/ui";

export interface ClubStint {
  club: string;
  from: string;
  to: string;
  teams: string[];
  competitions: string[];
  apps: number;
  goals: number;
  current: boolean;
  top_level: number;
  seasons: { season: string; team: string; competition_label: string }[];
}

function initials(club: string): string {
  const words = club.replace(/^(FC|FK|IF|SC)\s+/i, "").split(/\s+/);
  return (words.length > 1 ? words[0][0] + words[1][0] : club.replace(/\s/g, "").slice(0, 3)).toUpperCase();
}

const PALETTE = ["#2a6fdb", "#1fa05a", "#d9480f", "#7048e8", "#0c8599", "#c2255c", "#5c940d"];

export function ClubHistory({ clubs }: { clubs: ClubStint[] }) {
  if (!clubs.length) return null;
  return (
    <section>
      <SectionTitle>Club history</SectionTitle>
      <Card className="p-0">
        <ol className="relative">
          {[...clubs].reverse().map((c, i) => (
            <li key={c.club} className={cn("flex gap-3 px-4 py-3", i > 0 && "border-line border-t")}>
              <div className="flex flex-col items-center">
                <span
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-extrabold text-white"
                  style={{ background: PALETTE[clubs.indexOf(c) % PALETTE.length] }}
                  aria-hidden
                >
                  {initials(c.club)}
                </span>
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-bold">{c.club}</p>
                  {c.current && <Chip tone="green">now</Chip>}
                </div>
                <p className="text-ink-2 text-sm">
                  {c.from === c.to ? c.from : `${c.from}–${c.to}`} · {c.teams.join(" → ")}
                </p>
                <p className="text-ink-2 text-xs">{c.competitions.join(" · ")}</p>
              </div>
              <div className="text-right text-sm tabular-nums">
                <p className="font-bold">{c.apps}</p>
                <p className="text-ink-2 text-xs">apps · {c.goals} G</p>
              </div>
            </li>
          ))}
        </ol>
      </Card>
    </section>
  );
}

interface Money {
  contracts: { id: string; kind: string; kind_label: string; title: string; direction: "income" | "expense"; amount_cents: number; period: string; bonus: Record<string, number>; team: string | null; ends_on: string | null }[];
  fees_paid_cents: number;
  fees_due_cents: number;
  salary_cents: number;
  bonus_cents: number;
  bonus_by_type: { type: string; amount_cents: number }[];
  entries: { id: string; date: string; description: string; amount_cents: number; direction: string; status: string }[];
}

export function MoneyCard() {
  const { data } = useApi<Money>("/api/me/finance");
  if (!data || data.contracts.length === 0) return null;
  const earns = data.salary_cents + data.bonus_cents > 0;
  return (
    <section>
      <SectionTitle>Contract and money</SectionTitle>
      <Card className="space-y-3">
        {data.contracts
          .filter((c) => !c.ends_on)
          .map((c) => (
            <div key={c.id} className="flex flex-wrap items-center justify-between gap-2">
              <span>
                <span className="font-semibold">{c.title}</span>
                <span className="text-ink-2 block text-xs">{c.team}</span>
              </span>
              <span className={cn("font-bold tabular-nums", c.direction === "expense" ? "text-ready-green" : "")}>
                {c.direction === "expense" ? "you get " : "you pay "}
                {eur(c.amount_cents)} {PERIOD[c.period]}
              </span>
              {Object.keys(c.bonus).length > 0 && (
                <div className="flex w-full flex-wrap gap-1">
                  {Object.entries(c.bonus).map(([k, v]) => (
                    <Chip key={k}>
                      {BONUS_LABEL[k] ?? k} +{eur(v)}
                    </Chip>
                  ))}
                </div>
              )}
            </div>
          ))}
        <div className="border-line grid grid-cols-2 gap-2 border-t pt-3 text-center text-sm">
          {earns && (
            <>
              <div>
                <p className="text-ready-green text-lg font-extrabold">{eur(data.salary_cents)}</p>
                <p className="text-ink-2 text-xs">salary this season</p>
              </div>
              <div>
                <p className="text-ready-green text-lg font-extrabold">{eur(data.bonus_cents)}</p>
                <p className="text-ink-2 text-xs">bonuses earned</p>
              </div>
            </>
          )}
          <div>
            <p className="text-lg font-extrabold">{eur(data.fees_paid_cents)}</p>
            <p className="text-ink-2 text-xs">fees paid</p>
          </div>
          <div>
            <p className={cn("text-lg font-extrabold", data.fees_due_cents > 0 && "text-ready-amber")}>{eur(data.fees_due_cents)}</p>
            <p className="text-ink-2 text-xs">fees due</p>
          </div>
        </div>
        {data.bonus_by_type.length > 0 && (
          <p className="text-ink-2 text-xs">Bonuses: {data.bonus_by_type.map((b) => `${b.type} ${eur(b.amount_cents)}`).join(" · ")}</p>
        )}
      </Card>
    </section>
  );
}
