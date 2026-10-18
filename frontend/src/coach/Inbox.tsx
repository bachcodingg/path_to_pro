// "Substitution board": one card per proposal, current vs proposed week.
// Approve (A), edit (E), reject (R): target under 3 clicks and 20 s per decision.
import { Check, Pencil, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../shared/api";
import { t } from "../shared/i18n";
import type { PlanDay, Proposal, SessionKind } from "../shared/types";
import { useApi } from "../shared/useApi";
import { Button, Card, Chip, ErrorNote, Spinner, cn, fmtDay, intensityClass } from "../shared/ui";

const KIND_TITLE: Record<string, string> = {
  session_swap: "Session swap",
  load_cut: "Load cut",
  intensity_change: "Intensity change",
  match_minutes: "Match minutes limit",
  new_goal: "New development goal",
};
const EDITABLE: SessionKind[] = ["rest", "recovery", "technical", "tactical", "strength", "speed"];

export function Inbox() {
  const { data, setData, error, loading, reload } = useApi<Proposal[]>("/api/coach/inbox");
  const [focus, setFocus] = useState(0);
  const [editing, setEditing] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, { kind: SessionKind; rpe: number }>>({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const decide = useCallback(
    async (p: Proposal, action: "approve" | "reject" | "edit") => {
      setBusy(true);
      setMsg(null);
      try {
        await api(`/api/coach/proposals/${p.id}/decision`, {
          method: "POST",
          json: { action, edits: Object.entries(edits).map(([day, v]) => ({ day, ...v })) },
        });
        setData((d) => d && d.filter((x) => x.id !== p.id));
        setEditing(null);
        setEdits({});
        setMsg(`${action === "reject" ? "Rejected" : "Applied"}: ${p.player.name}`);
      } catch (e) {
        setMsg(e instanceof ApiError ? e.message : "Failed");
      } finally {
        setBusy(false);
      }
    },
    [edits, setData],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!data?.length || busy || (e.target as HTMLElement).tagName.match(/INPUT|SELECT|TEXTAREA/)) return;
      const p = data[Math.min(focus, data.length - 1)];
      const k = e.key.toLowerCase();
      if (k === "a") void decide(p, editing === p.id ? "edit" : "approve");
      else if (k === "r") void decide(p, "reject");
      else if (k === "e" && p.proposed.length) setEditing(p.id);
      else if (k === "j" || e.key === "ArrowDown") setFocus((f) => Math.min(f + 1, data.length - 1));
      else if (k === "k" || e.key === "ArrowUp") setFocus((f) => Math.max(f - 1, 0));
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [data, focus, busy, editing, decide]);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-extrabold">Substitution board</h1>
          <p className="text-ink-2 text-sm">
            {data.length} waiting · keys: <kbd className="font-mono">A</kbd> approve, <kbd className="font-mono">E</kbd> edit,{" "}
            <kbd className="font-mono">R</kbd> reject, <kbd className="font-mono">J/K</kbd> next/previous
          </p>
        </div>
        {msg && (
          <p role="status" className="text-sm font-semibold">
            {msg}
          </p>
        )}
      </div>
      {data.length === 0 && <Card className="text-ink-2">Nothing to decide. The agents will post here when a plan needs your approval.</Card>}
      {data.map((p, idx) => (
        <Card
          key={p.id}
          role="article"
          aria-label={`${KIND_TITLE[p.kind] ?? p.kind}: ${p.player.name}`}
          className={cn("space-y-3", idx === focus && "ring-pitch-400 ring-2")}
          onClick={() => setFocus(idx)}
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-ink-2 text-xs font-semibold uppercase">{KIND_TITLE[p.kind] ?? p.kind}</p>
              <p className="text-lg font-bold">{p.player.name}</p>
              <p className="text-sm">{p.reason}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="approve" size="sm" disabled={busy} onClick={() => decide(p, editing === p.id ? "edit" : "approve")}>
                <Check className="h-4 w-4" aria-hidden /> {editing === p.id ? "Save edit" : t("inbox.approve")}
              </Button>
              {p.proposed.length > 0 && editing !== p.id && (
                <Button variant="secondary" size="sm" disabled={busy} onClick={() => setEditing(p.id)}>
                  <Pencil className="h-4 w-4" aria-hidden /> {t("inbox.edit")}
                </Button>
              )}
              <Button variant="danger" size="sm" disabled={busy} onClick={() => decide(p, "reject")}>
                <X className="h-4 w-4" aria-hidden /> {t("inbox.reject")}
              </Button>
            </div>
          </div>
          {(p.chips.length > 0 || (p.teams?.length ?? 0) > 1) && (
            <div className="flex flex-wrap gap-2">
              {(p.teams?.length ?? 0) > 1 && <Chip tone="amber">Dual registration: {p.teams!.join(" + ")}</Chip>}
              {p.chips.map((c) => (
                <Chip key={c}>{c}</Chip>
              ))}
            </div>
          )}
          {p.proposed.length > 0 ? (
            <div className="space-y-2">
              <Strip label="Current" days={p.current} />
              <Strip
                label="Proposed"
                days={p.proposed.map((d) => (edits[d.date] ? { ...d, ...edits[d.date] } : d))}
                compare={p.current}
                editable={editing === p.id}
                onEdit={(date, v) => setEdits({ ...edits, [date]: v })}
              />
            </div>
          ) : (
            <GoalPayload payload={p.payload} />
          )}
          <p className="text-ink-2 text-xs">
            Policy: {p.policy_rule}
            {p.solver_status && ` · solver: ${p.solver_status}`}
          </p>
        </Card>
      ))}
    </div>
  );
}

function Strip({
  label,
  days,
  compare,
  editable,
  onEdit,
}: {
  label: string;
  days: PlanDay[];
  compare?: PlanDay[];
  editable?: boolean;
  onEdit?: (date: string, v: { kind: SessionKind; rpe: number }) => void;
}) {
  return (
    <div className="flex items-stretch gap-2">
      <span className="text-ink-2 w-20 shrink-0 pt-2 text-xs font-semibold uppercase">{label}</span>
      <div className="grid flex-1 gap-1" style={{ gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }}>
        {days.map((d, i) => {
          const changed = compare && (compare[i]?.kind !== d.kind || compare[i]?.rpe !== d.rpe || compare[i]?.minutes !== d.minutes);
          return (
            <div key={d.date} className={cn("rounded-lg p-1.5 text-center text-xs", intensityClass(d.kind, d.rpe), changed && "ring-ready-amber ring-2")}>
              <div className="font-bold">{fmtDay(d.date)}</div>
              {editable && d.kind !== "match" ? (
                <div className="mt-1 space-y-1">
                  <select
                    aria-label={`Session ${d.date}`}
                    value={d.kind}
                    onChange={(e) => onEdit?.(d.date, { kind: e.target.value as SessionKind, rpe: e.target.value === "rest" ? 0 : Math.max(d.rpe, 2) })}
                    className="text-ink w-full rounded bg-white px-0.5 text-[11px]"
                  >
                    {EDITABLE.map((k) => (
                      <option key={k}>{k}</option>
                    ))}
                  </select>
                  <input
                    aria-label={`Effort ${d.date}`}
                    type="number"
                    min={0}
                    max={10}
                    value={d.rpe}
                    onChange={(e) => onEdit?.(d.date, { kind: d.kind, rpe: Number(e.target.value) })}
                    className="text-ink w-full rounded bg-white px-1 text-[11px]"
                  />
                </div>
              ) : (
                <>
                  <div className="truncate">{d.label}</div>
                  <div>{d.kind === "rest" ? "–" : d.kind === "match" ? `${d.minutes}′` : `RPE ${d.rpe}`}</div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GoalPayload({ payload }: { payload: Record<string, unknown> }) {
  const goals = (payload.goals as { kpi: string; baseline: number; target: number; bio_percentile: number; sessions_per_week: number }[]) ?? [];
  return (
    <div className="space-y-1 text-sm">
      {goals.map((g) => (
        <p key={g.kpi}>
          <strong>{g.kpi.replace("_", " ")}</strong>: {g.baseline} → {g.target} ({g.bio_percentile}th percentile at stage of growth),{" "}
          {g.sessions_per_week}×/week
        </p>
      ))}
      {typeof payload.feedback === "string" && <p className="text-ink-2 italic">“{payload.feedback}”</p>}
    </div>
  );
}
