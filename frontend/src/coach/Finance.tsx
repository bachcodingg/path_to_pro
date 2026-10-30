// Club finances: income and costs by month, contracts (fees, salaries, staff), running
// costs, bonuses from match stats and titles, and the ledger.
import { Trophy } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError } from "../shared/api";
import { BONUS_LABEL, eur, PERIOD } from "../shared/money";
import { AXIS, GRID, TOOLTIP } from "../shared/chart";
import { PageHeader, Tabs } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { Button, Card, Chip, ErrorNote, SectionTitle, Spinner, cn, fmtDay } from "../shared/ui";

interface ContractRow {
  id: string;
  party: string;
  player_id: string | null;
  staff_id: string | null;
  team: string | null;
  kind: string;
  kind_label: string;
  title: string;
  direction: "income" | "expense";
  amount_cents: number;
  period: string;
  bonus: Record<string, number>;
  starts_on: string;
  ends_on: string | null;
}
interface LedgerRow {
  id: string;
  date: string;
  category: string;
  category_label: string;
  direction: "income" | "expense";
  amount_cents: number;
  description: string;
  status: "due" | "paid";
}
interface FinanceView {
  season: string;
  today: string;
  totals: { income_cents: number; expense_cents: number; net_cents: number; fees_due_cents: number; fees_overdue_cents: number; overdue_count: number };
  months: { month: string; income: number; expense: number }[];
  categories: { category: string; label: string; direction: string; amount_cents: number }[];
  contracts: ContractRow[];
  recurring: { id: string; name: string; category: string; direction: string; amount_cents: number; period: string }[];
  bonuses: { player_id: string; name: string; total_cents: number; items: number }[];
  ledger: LedgerRow[];
  categories_all: Record<string, string>;
  kinds: Record<string, string>;
  note: string;
  booked?: number;
}

type Tab = "contracts" | "ledger" | "bonuses" | "costs";

export function Finance() {
  const { data, setData, error, loading, reload } = useApi<FinanceView>("/api/coach/finance");
  const [tab, setTab] = useState<Tab>("contracts");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const t = data.totals;

  async function act(path: string, json: unknown, done: (v: FinanceView) => string) {
    setBusy(true);
    setMsg(null);
    try {
      const out = await api<FinanceView>(path, { method: "POST", json });
      setData(out);
      setMsg(done(out));
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  const chart = data.months.map((m) => ({
    month: new Date(m.month + "-01T12:00:00").toLocaleDateString("en-GB", { month: "short" }),
    Income: m.income / 100,
    Costs: m.expense / 100,
  }));
  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Club"
        title="Club finances"
        subtitle={`Season ${data.season}: academy fees, salaries and bonuses, staff, pitches, sponsors and prize money.`}
        actions={
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            loading={busy}
            onClick={() =>
              act("/api/coach/finance/run-month", { month: data.today.slice(0, 7) }, (v) =>
                v.booked ? `Booked ${v.booked} entries for this month.` : "This month is already booked.",
              )
            }
          >
            Book this month
          </Button>
          <TitleButton onSave={(title, prize) => act("/api/coach/finance/titles", { title, prize_cents: prize }, (v) => `Title recorded: ${v.booked} entries booked.`)} />
        </div>
        }
      />
      {msg && (
        <p role="status" className="text-sm font-semibold">
          {msg}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Income" value={eur(t.income_cents)} tone="text-win" accent="var(--color-win)" />
        <Kpi label="Costs" value={eur(t.expense_cents)} tone="text-loss" accent="var(--color-loss)" />
        <Kpi label="Result" value={eur(t.net_cents)} sub={t.net_cents >= 0 ? "Profit so far" : "Loss so far"} tone={t.net_cents >= 0 ? "text-win" : "text-loss"} />
        <Kpi
          label="Fees outstanding"
          value={eur(t.fees_due_cents)}
          sub={t.overdue_count ? `${t.overdue_count} overdue (${eur(t.fees_overdue_cents)})` : "none overdue"}
          tone={t.overdue_count ? "text-amber-700 dark:text-caution" : ""}
          accent={t.overdue_count ? "var(--color-caution)" : undefined}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="flex h-72 flex-col p-0">
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-3">
            <p className="font-bold">Income and costs by month</p>
            <p className="text-ink-2 flex gap-4 text-xs">
              <span className="flex items-center gap-1.5">
                <span className="bg-win h-2.5 w-2.5 rounded-sm" aria-hidden /> Income
              </span>
              <span className="flex items-center gap-1.5">
                <span className="bg-loss h-2.5 w-2.5 rounded-sm" aria-hidden /> Costs
              </span>
            </p>
          </div>
          <div className="min-h-0 flex-1 px-1 pt-2 pb-1">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart} margin={{ top: 8, right: 8, left: 4, bottom: 0 }} barGap={4}>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="month" {...AXIS} />
                <YAxis {...AXIS} width={44} tickFormatter={(v) => (v ? `€${Math.round(v / 1000)}k` : "€0")} />
                <Tooltip {...TOOLTIP} formatter={(v: number) => eur(v * 100)} />
                <Bar dataKey="Income" fill="var(--color-win)" radius={[4, 4, 0, 0]} maxBarSize={36} />
                <Bar dataKey="Costs" fill="var(--color-loss)" radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card className="max-h-72 overflow-y-auto p-0">
          <table className="w-full text-sm">
            <tbody className="divide-[color:var(--line)] divide-y">
              {data.categories.map((c) => (
                <tr key={c.category + c.direction}>
                  <td className="p-2">{c.label}</td>
                  <td className={cn("p-2 text-right font-semibold tabular-nums", c.direction === "income" ? "text-win" : "text-loss")}>
                    {c.direction === "income" ? "+" : "−"}
                    {eur(c.amount_cents)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <Tabs
        label="Finance view"
        tone="plain"
        value={tab}
        onChange={setTab}
        items={[
          ["contracts", "Contracts"],
          ["ledger", "Ledger"],
          ["bonuses", "Bonuses"],
          ["costs", "Running costs"],
        ]}
      />

      {tab === "contracts" && <Contracts data={data} onChange={setData} />}
      {tab === "ledger" && <Ledger data={data} onChange={setData} />}
      {tab === "bonuses" && (
        <Card className="divide-[color:var(--line)] divide-y p-0">
          {data.bonuses.length === 0 && <p className="text-ink-2 p-4 text-sm">No bonuses yet.</p>}
          {data.bonuses.map((b) => (
            <div key={b.player_id} className="flex items-center justify-between px-4 py-3">
              <span className="font-semibold">{b.name}</span>
              <span className="text-ink-2 text-sm">
                {b.items} bonuses · <span className="text-ink font-bold">{eur(b.total_cents)}</span>
              </span>
            </div>
          ))}
          <p className="text-ink-2 px-4 py-2 text-xs">Booked automatically from match stats (appearance, goals, assists, wins, clean sheets) and titles.</p>
        </Card>
      )}
      {tab === "costs" && (
        <Card className="divide-[color:var(--line)] divide-y p-0">
          {data.recurring.map((r) => (
            <div key={r.id} className="flex items-center justify-between px-4 py-3">
              <span>
                <span className="font-semibold">{r.name}</span>
                <span className="text-ink-2 block text-xs">{data.categories_all[r.category] ?? r.category}</span>
              </span>
              <span className={cn("font-bold tabular-nums", r.direction === "income" ? "text-win" : "text-loss")}>
                {r.direction === "income" ? "+" : "−"}
                {eur(r.amount_cents)} {PERIOD[r.period]}
              </span>
            </div>
          ))}
          <p className="text-ink-2 px-4 py-2 text-xs">Per-session items are counted from the training plan, per-match items from the fixtures, when a month is booked.</p>
        </Card>
      )}
      <p className="text-ink-2 text-xs">{data.note}</p>
    </div>
  );
}

function Kpi({ label, value, sub, tone, accent }: { label: string; value: string; sub?: string; tone?: string; accent?: string }) {
  return (
    <Card className="relative overflow-hidden">
      {accent && <span className="absolute inset-y-0 left-0 w-1" style={{ background: accent }} aria-hidden />}
      <p className="text-ink-2 text-xs font-semibold uppercase">{label}</p>
      <p className={cn("font-display mt-1 text-[2rem] leading-none font-bold tabular-nums", tone)}>{value}</p>
      {sub && <p className="text-ink-2 mt-1 text-xs">{sub}</p>}
    </Card>
  );
}

function TitleButton({ onSave }: { onSave: (title: string, prizeCents: number) => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [prize, setPrize] = useState(0);
  if (!open)
    return (
      <Button size="sm" onClick={() => setOpen(true)}>
        <Trophy className="h-4 w-4" aria-hidden /> Record a title
      </Button>
    );
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(title, Math.round(prize * 100));
        setOpen(false);
      }}
    >
      <input className="bg-surface border-line h-9 rounded-lg border px-2 text-sm" placeholder="e.g. Kakkonen Group A" aria-label="Title" required minLength={2} value={title} onChange={(e) => setTitle(e.target.value)} />
      <input className="bg-surface border-line h-9 w-28 rounded-lg border px-2 text-sm" type="number" min={0} aria-label="Prize money in euro" placeholder="Prize €" value={prize || ""} onChange={(e) => setPrize(Number(e.target.value))} />
      <Button size="sm" type="submit">
        Save
      </Button>
    </form>
  );
}

function Contracts({ data, onChange }: { data: FinanceView; onChange: (v: FinanceView) => void }) {
  const groups = [
    ["Players pay the club", data.contracts.filter((c) => c.direction === "income")],
    ["Club pays players", data.contracts.filter((c) => c.direction === "expense" && c.player_id)],
    ["Club pays staff", data.contracts.filter((c) => c.staff_id)],
  ] as const;
  return (
    <div className="space-y-4">
      {groups.map(([title, rows]) => (
        <section key={title}>
          <SectionTitle>
            {title} ({rows.length})
          </SectionTitle>
          <Card className="overflow-x-auto p-0">
            <table className="w-full text-sm">
              <tbody className="divide-[color:var(--line)] divide-y">
                {rows.map((c) => (
                  <tr key={c.id} className={cn(c.ends_on && "opacity-50")}>
                    <td className="p-2 font-semibold">{c.party}</td>
                    <td className="p-2">
                      {c.title}
                      <span className="text-ink-2 block text-xs">
                        {c.team ?? ""}
                        {c.ends_on ? ` · ended ${c.ends_on}` : ` · since ${c.starts_on}`}
                      </span>
                    </td>
                    <td className="p-2 text-right font-bold whitespace-nowrap tabular-nums">
                      {eur(c.amount_cents)} {PERIOD[c.period]}
                    </td>
                    <td className="p-2">
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(c.bonus).map(([k, v]) => (
                          <Chip key={k}>
                            {BONUS_LABEL[k] ?? k} {eur(v)}
                          </Chip>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </section>
      ))}
      <AddContract data={data} onChange={onChange} />
    </div>
  );
}

function AddContract({ data, onChange }: { data: FinanceView; onChange: (v: FinanceView) => void }) {
  const players = Array.from(new Map(data.contracts.filter((c) => c.player_id).map((c) => [c.player_id!, c.party])));
  const [f, setF] = useState({ player_id: players[0]?.[0] ?? "", kind: "semi_pro", amount: 300, goal: 100, assist: 50, appearance: 50, win: 75, clean_sheet: 0, title: 1000 });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f, v: string | number) => setF((x) => ({ ...x, [k]: v }));
  const pays = ["semi_pro", "pro", "amateur"].includes(f.kind);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const bonus = pays
      ? Object.fromEntries((["appearance", "goal", "assist", "win", "clean_sheet", "title"] as const).filter((k) => f[k] > 0).map((k) => [k, Math.round(f[k] * 100)]))
      : {};
    try {
      onChange(
        await api<FinanceView>("/api/coach/finance/contracts", {
          method: "POST",
          json: { player_id: f.player_id, kind: f.kind, amount_cents: Math.round(f.amount * 100), bonus, starts_on: new Date().toISOString().slice(0, 10) },
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed");
    }
  }

  const input = "bg-surface-2 border-line mt-1 h-10 w-full rounded-lg border px-2 text-sm";
  return (
    <Card>
      <p className="mb-2 font-bold">New player contract</p>
      <form onSubmit={submit} className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <label className="sm:col-span-2">
          <span className="text-xs font-semibold">Player</span>
          <select className={input} value={f.player_id} onChange={(e) => set("player_id", e.target.value)}>
            {players.map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="text-xs font-semibold">Type</span>
          <select className={input} value={f.kind} onChange={(e) => set("kind", e.target.value)}>
            {["academy_fee", "membership", "amateur", "semi_pro", "pro"].map((k) => (
              <option key={k} value={k}>
                {data.kinds[k]}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="text-xs font-semibold">€ per month</span>
          <input className={input} type="number" min={0} value={f.amount} onChange={(e) => set("amount", Number(e.target.value))} />
        </label>
        {pays &&
          (["appearance", "goal", "assist", "win", "clean_sheet", "title"] as const).map((k) => (
            <label key={k}>
              <span className="text-xs font-semibold">{BONUS_LABEL[k]} bonus €</span>
              <input className={input} type="number" min={0} value={f[k]} onChange={(e) => set(k, Number(e.target.value))} />
            </label>
          ))}
        {error && (
          <p role="alert" className="text-recover text-sm sm:col-span-3">
            {error}
          </p>
        )}
        <Button type="submit" className="self-end">
          Add contract
        </Button>
      </form>
    </Card>
  );
}

function Ledger({ data, onChange }: { data: FinanceView; onChange: (v: FinanceView) => void }) {
  const [filter, setFilter] = useState<"all" | "due">("all");
  const rows = data.ledger.filter((e) => filter === "all" || e.status === "due");
  async function toggle(e: LedgerRow) {
    onChange(await api<FinanceView>(`/api/coach/finance/entries/${e.id}/paid`, { method: "POST", json: { paid: e.status !== "paid" } }));
  }
  return (
    <Card className="p-0">
      <div className="flex gap-2 p-3">
        <Button size="sm" variant={filter === "all" ? "primary" : "secondary"} onClick={() => setFilter("all")}>
          All
        </Button>
        <Button size="sm" variant={filter === "due" ? "primary" : "secondary"} onClick={() => setFilter("due")}>
          Not paid yet
        </Button>
      </div>
      <div className="max-h-[32rem] overflow-y-auto">
        <table className="w-full text-sm">
          <tbody className="divide-[color:var(--line)] divide-y">
            {rows.map((e) => (
              <tr key={e.id}>
                <td className="text-ink-2 p-2 whitespace-nowrap">{fmtDay(e.date, { day: "numeric", month: "short" })}</td>
                <td className="p-2">
                  {e.description}
                  <span className="text-ink-2 block text-xs">{e.category_label}</span>
                </td>
                <td className={cn("p-2 text-right font-bold whitespace-nowrap tabular-nums", e.direction === "income" ? "text-win" : "text-loss")}>
                  {e.direction === "income" ? "+" : "−"}
                  {eur(e.amount_cents)}
                </td>
                <td className="p-2 text-right">
                  <button onClick={() => toggle(e)} className="tap" aria-label={`Mark ${e.status === "paid" ? "not paid" : "paid"}: ${e.description}`}>
                    <Chip tone={e.status === "paid" ? "win" : "amber"}>{e.status === "paid" ? "paid" : "due"}</Chip>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
