// "Match commentary": every agent action in plain language with time and inputs. Export as CSV.
import { Download } from "lucide-react";
import { useState } from "react";
import { download } from "../shared/api";
import { useApi } from "../shared/useApi";
import { Button, Card, Chip, ErrorNote, Spinner } from "../shared/ui";

interface LogRow {
  id: string;
  at: string;
  agent: string;
  trigger: string;
  player: { id: string; name: string } | null;
  decision: string;
  text: string;
  fallback: boolean;
  inputs: Record<string, unknown> | null;
}

export function AgentLog() {
  const [agent, setAgent] = useState("");
  const [decision, setDecision] = useState("");
  const qs = new URLSearchParams({ ...(agent && { agent }), ...(decision && { decision }), limit: "200" }).toString();
  const { data, error, loading, reload } = useApi<LogRow[]>(`/api/coach/agent-log?${qs}`);
  const [open, setOpen] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold">Match commentary</h1>
          <p className="text-ink-2 text-sm">Every agent action, newest first.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select aria-label="Agent" className="bg-surface border-line tap rounded-xl border px-3" value={agent} onChange={(e) => setAgent(e.target.value)}>
            <option value="">All agents</option>
            <option value="monitor">Monitor</option>
            <option value="planner">Planner</option>
            <option value="development_coach">Development Coach</option>
            <option value="coordinator">Coordinator</option>
          </select>
          <select aria-label="Decision" className="bg-surface border-line tap rounded-xl border px-3" value={decision} onChange={(e) => setDecision(e.target.value)}>
            <option value="">All decisions</option>
            <option value="coach_approval">Coach approval</option>
            <option value="auto_apply_notify_coach">Auto-applied</option>
            <option value="escalate">Escalated</option>
            <option value="no change">No change</option>
          </select>
          <Button variant="secondary" onClick={() => download(`/api/coach/agent-log.csv?${qs}`, "agent-log.csv")}>
            <Download className="h-4 w-4" aria-hidden /> CSV
          </Button>
        </div>
      </div>
      {loading && !data && <Spinner />}
      {error && <ErrorNote message={error} onRetry={reload} />}
      <ol className="space-y-2">
        {data?.map((r) => (
          <li key={r.id}>
            <Card className="p-3">
              <button className="w-full text-left" onClick={() => setOpen(open === r.id ? null : r.id)} aria-expanded={open === r.id}>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-ink-2 font-mono">{new Date(r.at).toLocaleString("en-GB")}</span>
                  <Chip>{r.agent.replace("_", " ")}</Chip>
                  <Chip>{r.trigger}</Chip>
                  {r.decision === "escalate" && <Chip tone="red">escalated</Chip>}
                  {r.fallback && <Chip tone="amber">rule-based fallback</Chip>}
                </div>
                <p className="mt-1">{r.text}</p>
              </button>
              {open === r.id && r.inputs && (
                <pre className="bg-surface-2 mt-2 overflow-x-auto rounded-lg p-2 text-xs">{JSON.stringify(r.inputs, null, 2)}</pre>
              )}
            </Card>
          </li>
        ))}
      </ol>
    </div>
  );
}
