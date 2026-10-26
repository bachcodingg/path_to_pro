// "Match commentary": every agent action in plain language with time and inputs. Export as CSV.
// A timeline grouped by agent run: escalations pinned on top, routine "no change" checks folded
// into one line per run, and the evidence behind each action laid out as facts rather than JSON.
import { Bot, CalendarCog, ChevronDown, Download, Eye, Search, ShieldAlert, Target, type LucideIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { download } from "../shared/api";
import { PageHeader, Tabs } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { Button, Card, Chip, ErrorNote, PageSkeleton, SectionTitle, StatTile, cn, capitalize, fmtDay } from "../shared/ui";

interface Flag {
  kind: string;
  detail: string;
}

interface SoftRule {
  weight: number;
  why: string;
  type: string;
}

interface LogRow {
  id: string;
  at: string;
  agent: string;
  trigger: string;
  player: { id: string; name: string } | null;
  decision: string;
  text: string;
  fallback: boolean;
  flags: Flag[] | null;
  inputs: Record<string, unknown> | null;
  constraints: { rationale?: string; soft?: SoftRule[] } | null;
}

type AgentKey = "monitor" | "planner" | "development_coach" | "coordinator";

const AGENTS: Record<AgentKey, { label: string; icon: LucideIcon; dot: string; text: string }> = {
  coordinator: { label: "Coordinator", icon: ShieldAlert, dot: "bg-ready-red text-white", text: "text-ready-red" },
  planner: { label: "Planner", icon: CalendarCog, dot: "bg-pitch-600 text-white", text: "text-pitch-600 dark:text-pitch-300" },
  development_coach: { label: "Development Coach", icon: Target, dot: "bg-pitch-300 text-pitch-950", text: "text-pitch-700 dark:text-pitch-300" },
  monitor: { label: "Monitor", icon: Eye, dot: "bg-surface border-line text-ink-2 border", text: "text-ink-2" },
};

const TRIGGERS: Record<string, string> = {
  nightly: "Nightly run",
  test_day: "Test day",
  team_session: "Team session",
  coach_instruction: "Coach instruction",
};

const FLAG_TONE: Record<string, "neutral" | "amber" | "red"> = {
  pain_report: "red",
  readiness_red: "red",
  load_spike: "amber",
  short_sleep: "amber",
  low_hrv: "amber",
};

const TESTS: Record<string, [string, string]> = {
  sprint_10m: ["10 m sprint", " s"],
  sprint_30m: ["30 m sprint", " s"],
  cmj: ["Jump (CMJ)", " cm"],
  yoyo_ir1: ["Yo-Yo IR1", " m"],
};

const MATURITY: Record<string, string> = {
  pre_phv: "Before growth spurt",
  circa_phv: "In growth spurt",
  post_phv: "After growth spurt",
};

const humanize = (s: string) => capitalize(s.replaceAll("_", " "));
const agentOf = (a: string) => AGENTS[a as AgentKey] ?? { ...AGENTS.monitor, label: humanize(a) };
const isRoutine = (r: LogRow) => r.agent === "monitor" && r.decision === "no change";
const clock = (at: string) => new Date(at).toLocaleTimeString("en-GB");

// Rows arrive newest first; a gap of more than five minutes starts a new run
function groupRuns(rows: LogRow[]): LogRow[][] {
  const runs: LogRow[][] = [];
  let last = Infinity;
  for (const r of rows) {
    const t = new Date(r.at).getTime();
    if (last - t > 5 * 60_000 || !runs.length) runs.push([]);
    runs[runs.length - 1].push(r);
    last = t;
  }
  return runs;
}

export function AgentLog() {
  const [agent, setAgent] = useState<"" | AgentKey>("");
  const [decision, setDecision] = useState("");
  const [query, setQuery] = useState("");
  const qs = new URLSearchParams({ ...(agent && { agent }), ...(decision && { decision }) }).toString();
  // All rows in one request: the tabs show counts per agent and filter in the browser
  const { data, error, loading, reload } = useApi<LogRow[]>("/api/coach/agent-log?limit=500");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data ?? []).filter(
      (r) => (!agent || r.agent === agent) && (!decision || r.decision === decision) && (!q || r.player?.name.toLowerCase().includes(q)),
    );
  }, [data, agent, decision, query]);
  const count = (a: string) => (data ?? []).filter((r) => r.agent === a).length;
  const escalated = rows.filter((r) => r.decision === "escalate");

  if (loading && !data) return <PageSkeleton label="Loading commentary" />;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Matchday"
        title="Match commentary"
        subtitle="What the agents did overnight and why, newest first. Open any action to see the evidence behind it."
        actions={
          <Button variant="secondary" onClick={() => download(`/api/coach/agent-log.csv?${qs}`, "agent-log.csv")}>
            <Download className="h-4 w-4" aria-hidden /> Export CSV
          </Button>
        }
        bottom={
          data && (
            <Tabs
              label="Agent"
              value={agent}
              onChange={setAgent}
              items={[
                ["", `All · ${data.length}`],
                ...(Object.keys(AGENTS) as AgentKey[]).map((a) => [a, `${AGENTS[a].label} · ${count(a)}`] as const),
              ]}
            />
          )
        }
      />
      {error && <ErrorNote message={error} onRetry={reload} />}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile label="Escalated to staff" value={count("coordinator")} sub="Safety flags, no agent action" accent="var(--color-ready-red)" />
            <StatTile label="Weeks planned" value={count("planner")} sub="Built or re-planned by the solver" accent="var(--color-pitch-600)" />
            <StatTile label="Goals set" value={count("development_coach")} sub="After test-day results" accent="var(--color-pitch-300)" />
            <StatTile
              label="Rule-based fallback"
              value={data.filter((r) => r.fallback).length}
              sub="Decided by rules, not the LLM"
              accent="var(--color-ready-amber)"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label className="bg-surface border-line tap focus-within:ring-pitch-300 flex min-w-0 flex-1 items-center gap-2 rounded-xl border px-3 focus-within:ring-2 sm:max-w-xs">
              <Search className="text-ink-2 h-4 w-4 shrink-0" aria-hidden />
              <input
                type="search"
                aria-label="Find a player"
                placeholder="Find a player"
                className="min-w-0 flex-1 bg-transparent py-2 outline-none"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
            <select aria-label="Decision" className="bg-surface border-line tap rounded-xl border px-3" value={decision} onChange={(e) => setDecision(e.target.value)}>
              <option value="">All decisions</option>
              <option value="plan">Week planned</option>
              <option value="coach_approval">Coach approval</option>
              <option value="auto_apply_notify_coach">Auto-applied</option>
              <option value="escalate">Escalated</option>
              <option value="no change">No change</option>
            </select>
            <p className="text-ink-2 ml-auto text-sm" role="status">
              {rows.length} of {data.length} actions
            </p>
          </div>

          {escalated.length > 0 && (
            <section aria-label="Needs attention">
              <SectionTitle>Needs attention</SectionTitle>
              <ol className="space-y-2">
                {escalated.map((r) => (
                  <Entry key={r.id} r={r} />
                ))}
              </ol>
            </section>
          )}

          {rows.length === 0 && <Card className="text-ink-2">No actions match these filters.</Card>}
          {groupRuns(rows.filter((r) => r.decision !== "escalate")).map((run) => (
            <Run key={run[0].id} rows={run} />
          ))}
        </>
      )}
    </div>
  );
}

function Run({ rows }: { rows: LogRow[] }) {
  const [showRoutine, setShowRoutine] = useState(false);
  const routine = rows.filter(isRoutine);
  const shown = rows.filter((r) => !isRoutine(r));
  const day = rows[0].at.slice(0, 10);
  const triggers = [...new Set(rows.map((r) => TRIGGERS[r.trigger] ?? humanize(r.trigger)))].join(" + ");

  return (
    <section aria-label={`${triggers}, ${day}`}>
      <SectionTitle>
        {fmtDay(day, { weekday: "short", day: "numeric", month: "short" })} · {triggers}
        <span className="text-ink-2 font-sans text-sm font-semibold tracking-normal normal-case">
          {rows.length} action{rows.length === 1 ? "" : "s"} · {clock(rows[rows.length - 1].at).slice(0, 5)}
        </span>
      </SectionTitle>
      {/* The rail: one dot per action, coloured by agent */}
      <ol className="relative space-y-2 sm:before:absolute sm:before:top-2 sm:before:bottom-2 sm:before:left-[17px] sm:before:w-0.5 sm:before:bg-[var(--line)]">
        {shown.map((r) => (
          <Entry key={r.id} r={r} rail />
        ))}
        {routine.length > 0 && (
          <li className="relative sm:pl-12">
            <Dot agent="monitor" />
            <Card className="p-0">
              <button
                className="tap flex w-full items-center gap-3 px-3 py-2 text-left"
                onClick={() => setShowRoutine(!showRoutine)}
                aria-expanded={showRoutine}
              >
                <span className="flex-1">
                  <span className="text-ink-2 text-xs font-bold tracking-wide uppercase">Monitor</span>
                  <span className="block">
                    Checked <b className="num">{routine.length}</b> player{routine.length === 1 ? "" : "s"}: no change needed
                  </span>
                </span>
                <span className="text-ink-2 text-sm font-semibold">{showRoutine ? "Hide" : "Show all"}</span>
                <ChevronDown className={cn("text-ink-2 h-4 w-4 transition-transform", showRoutine && "rotate-180")} aria-hidden />
              </button>
              {showRoutine && (
                <ul className="border-line divide-y divide-[var(--line)] border-t">
                  {routine.map((r) => (
                    <li key={r.id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
                      <PlayerLink player={r.player} />
                      <span className="flex flex-1 flex-wrap gap-1">
                        {(r.flags ?? []).map((f) => (
                          <Chip key={f.kind} tone={FLAG_TONE[f.kind] ?? "neutral"}>
                            {f.detail}
                          </Chip>
                        ))}
                      </span>
                      <time className="text-ink-2 num font-mono text-xs">{clock(r.at)}</time>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </li>
        )}
      </ol>
    </section>
  );
}

function Dot({ agent }: { agent: string }) {
  const a = agentOf(agent);
  return (
    <span
      className={cn("absolute top-2.5 left-0 hidden h-9 w-9 sm:grid place-items-center rounded-full shadow-sm ring-4 ring-[var(--surface-2)]", a.dot)}
      aria-hidden
    >
      <a.icon className="h-4 w-4" />
    </span>
  );
}

function PlayerLink({ player }: { player: LogRow["player"] }) {
  if (!player) return <span className="font-semibold">Squad</span>;
  return (
    <Link to={`/coach/players/${player.id}`} className="font-semibold hover:underline">
      {player.name}
    </Link>
  );
}

function Entry({ r, rail }: { r: LogRow; rail?: boolean }) {
  const [open, setOpen] = useState(false);
  const a = agentOf(r.agent);
  const hasEvidence = !!(r.constraints || Object.keys(r.inputs ?? {}).length);

  return (
    <li className={cn("relative", rail && "sm:pl-12")}>
      {rail && <Dot agent={r.agent} />}
      <Card className={cn("p-3", r.decision === "escalate" && "border-l-ready-red border-l-4")}>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
          <a.icon className={cn("h-4 w-4", a.text, rail && "sm:hidden")} aria-hidden />
          <span className={cn("font-bold tracking-wide uppercase", a.text)}>{a.label}</span>
          <span className="text-ink-2">·</span>
          <span className="text-sm">
            <PlayerLink player={r.player} />
          </span>
          <span className={cn("text-ink-2", rail && "hidden sm:inline")}>· {TRIGGERS[r.trigger] ?? humanize(r.trigger)}</span>
          {r.fallback && (
            <span className="inline-flex items-center gap-1 text-amber-700 dark:text-ready-amber" title="The LLM was not used: the rules decided">
              <Bot className="h-3.5 w-3.5" aria-hidden /> rule-based
            </span>
          )}
          <time className="text-ink-2 num ml-auto font-mono">{clock(r.at)}</time>
        </div>
        <div className="mt-1 flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <p className="leading-snug">{r.text}</p>
            {(r.flags?.length ?? 0) > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {r.flags!.map((f) => (
                  <Chip key={f.kind} tone={FLAG_TONE[f.kind] ?? "neutral"}>
                    {f.detail}
                  </Chip>
                ))}
              </div>
            )}
          </div>
          {hasEvidence && (
            <Button variant="ghost" size="sm" className="-mr-1 -mb-1 shrink-0" onClick={() => setOpen(!open)} aria-expanded={open}>
              <span className="hidden sm:inline">Evidence</span>
              <span className="sr-only sm:hidden">Evidence</span>
              <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} aria-hidden />
            </Button>
          )}
        </div>
        {open && <Evidence r={r} />}
      </Card>
    </li>
  );
}

// Plan inputs as labelled facts; match and exam days are offsets from the first day of the week
function facts(inputs: Record<string, unknown>): [string, string][] {
  const out: [string, string][] = [];
  const day = typeof inputs.day === "string" ? inputs.day : null;
  const weekday = (n: number) => {
    if (!day) return `day ${n + 1}`;
    const d = new Date(day + "T12:00:00");
    d.setDate(d.getDate() + n);
    return d.toLocaleDateString("en-GB", { weekday: "short" });
  };
  for (const [k, v] of Object.entries(inputs)) {
    if (k === "day" && day) out.push(["Week from", fmtDay(day, { weekday: "short", day: "numeric", month: "short" })]);
    else if (k === "readiness" && typeof v === "number") out.push(["Readiness", String(Math.round(v))]);
    else if (k === "acwr" && typeof v === "number") out.push(["Load ratio (ACWR)", v.toFixed(2)]);
    else if (k === "match_days" && Array.isArray(v)) out.push(["Match days", v.length ? v.map(weekday).join(", ") : "None"]);
    else if (k === "exam_days" && Array.isArray(v)) {
      if (v.length) out.push(["Exam days", v.map(weekday).join(", ")]);
    } else if (k === "goals" && Array.isArray(v)) {
      if (v.length) out.push(["Goals", v.map((g) => humanize(String(g))).join(", ")]);
    }
    else if (k === "maturity" && typeof v === "string") out.push(["Maturity", MATURITY[v] ?? humanize(v)]);
    else if (k === "tests" && v && typeof v === "object")
      for (const [t, x] of Object.entries(v)) {
        const [label, unit] = TESTS[t] ?? [humanize(t), ""];
        out.push([label, `${x}${unit}`]);
      }
    else if (k === "instruction") out.push(["Instruction", String(v)]);
    else out.push([humanize(k), typeof v === "object" ? JSON.stringify(v) : String(v)]);
  }
  return out;
}

function Evidence({ r }: { r: LogRow }) {
  const items = facts(r.inputs ?? {});
  // One line per reason; a reason applied to several days counts once at its highest weight
  const rules = Object.values(
    (r.constraints?.soft ?? []).reduce<Record<string, SoftRule>>((acc, s) => {
      if (!acc[s.why] || acc[s.why].weight < s.weight) acc[s.why] = s;
      return acc;
    }, {}),
  ).sort((x, y) => y.weight - x.weight);
  const maxWeight = Math.max(...rules.map((s) => s.weight), 1);

  return (
    <div className="border-line mt-3 space-y-3 border-t pt-3 text-sm">
      {items.length > 0 && (
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {items.map(([k, v]) => (
            <div key={k} className="bg-surface-2 rounded-xl px-3 py-2">
              <dt className="text-ink-2 text-xs font-semibold">{k}</dt>
              <dd className="font-display num text-lg leading-tight font-bold">{v}</dd>
            </div>
          ))}
        </dl>
      )}
      {r.constraints?.rationale && (
        <p>
          <span className="font-semibold">Planner's reasoning: </span>
          {capitalize(r.constraints.rationale)}.
        </p>
      )}
      {rules.length > 0 && (
        <div>
          <p className="text-ink-2 mb-1.5 text-xs font-semibold uppercase">Rules the solver weighed</p>
          <ul className="space-y-1.5">
            {rules.map((s) => (
              <li key={s.why} className="flex items-center gap-3">
                <span className="bg-surface-2 h-1.5 w-20 shrink-0 overflow-hidden rounded-full" aria-hidden>
                  <span className="bg-pitch-500 block h-full rounded-full" style={{ width: `${(s.weight / maxWeight) * 100}%` }} />
                </span>
                <span className="flex-1">{capitalize(s.why)}</span>
                <span className="text-ink-2 num text-xs">weight {s.weight}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <details>
        <summary className="text-ink-2 cursor-pointer text-xs font-semibold">Raw inputs (JSON)</summary>
        <pre className="bg-surface-2 mt-2 overflow-x-auto rounded-lg p-2 text-xs">{JSON.stringify({ inputs: r.inputs, constraints: r.constraints }, null, 2)}</pre>
      </details>
    </div>
  );
}
