// Readiness calibration: compare the score with staff ratings, review suggested weights, apply.
import { useState } from "react";
import { api, ApiError } from "../shared/api";
import { PageHeader } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { useAuth } from "../shared/auth";
import { Button, Card, ErrorNote, SectionTitle, Spinner, cn } from "../shared/ui";

type Weights = Record<"hrv" | "hooper" | "sleep", number>;
interface Agreement {
  n: number;
  accuracy: number;
  kappa: number;
  red_recall: number | null;
}
interface Report {
  n: number;
  min_samples: number;
  enough_data: boolean;
  current: Weights;
  suggested: Weights;
  before: Agreement;
  after: Agreement;
  cv_before: number | null;
  cv_after: number | null;
  cv_noise: number | null;
  recommended: boolean;
  min_gain: number;
  hysteresis: { up: number; down: number };
}

const LABEL: Record<keyof Weights, string> = { hrv: "Heart-rate variability", hooper: "Morning check-in", sleep: "Sleep" };
const pct = (x: number | null) => (x == null ? "–" : `${Math.round(x * 100)}%`);
const k2 = (x: number | null) => (x == null ? "–" : x.toFixed(2));

export function Calibration() {
  const { user } = useAuth();
  const { data, setData, error, loading, reload } = useApi<Report>("/api/coach/calibration");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function apply(weights: Weights | null, force = false) {
    setBusy(true);
    setMsg(null);
    try {
      setData(await api<Report>("/api/coach/calibration/apply", { method: "POST", json: { weights, force } }));
      setMsg(weights ? "New weights applied. They are used for every score from now on." : "Back to the default weights.");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading && !data) return <Spinner label="Fitting weights" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  const same = (Object.keys(data.current) as (keyof Weights)[]).every((k) => data.current[k] === data.suggested[k]);
  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Club"
        title="Readiness calibration"
        subtitle="How well the readiness score agrees with your own eye, and better weights when the data supports them."
      />
      <div className="space-y-4">
        <p className="text-ink-2 max-w-3xl text-sm">
          Rate players in the Dressing room ("How ready does he look?"). Your ratings are compared with the score, and the weights
          that agree best with staff are suggested. A suggestion is only allowed if it spots at least as many of your red days as
          today's weights.
        </p>
        {!data.enough_data && (
          <Card className="border-ready-amber/50">
            {data.n} rated days so far. At least {data.min_samples} are needed before suggesting new weights.
          </Card>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          <WeightsCard title="Current weights" w={data.current} />
          <WeightsCard title="Suggested weights" w={data.suggested} highlight={!same} />
        </div>

        <section>
          <SectionTitle>Agreement with staff ({data.n} rated days)</SectionTitle>
          <Card className="overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead className="text-ink-2 text-left">
                <tr>
                  <th className="p-3">Measure</th>
                  <th className="p-3">Current</th>
                  <th className="p-3">Suggested</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[color:var(--line)]">
                <tr>
                  <td className="p-3">Agreement beyond chance (weighted kappa)</td>
                  <td className="p-3">{k2(data.before.kappa)}</td>
                  <td className="p-3 font-semibold">{k2(data.after.kappa)}</td>
                </tr>
                <tr>
                  <td className="p-3">Same on players it wasn't fitted on (cross-validated)</td>
                  <td className="p-3">{k2(data.cv_before)}</td>
                  <td className="p-3 font-semibold">{k2(data.cv_after)}</td>
                </tr>
                <tr>
                  <td className="p-3">Same colour as staff</td>
                  <td className="p-3">{pct(data.before.accuracy)}</td>
                  <td className="p-3 font-semibold">{pct(data.after.accuracy)}</td>
                </tr>
                <tr>
                  <td className="p-3">Staff red days the score also calls red</td>
                  <td className="p-3">{pct(data.before.red_recall)}</td>
                  <td className="p-3 font-semibold">{pct(data.after.red_recall)}</td>
                </tr>
              </tbody>
            </table>
          </Card>
          {data.enough_data && !same && (
            <Card className={cn("mt-2", data.recommended ? "border-ready-green/50" : "border-ready-amber/50")} role="status">
              {data.recommended ? (
                <p>
                  <span className="font-semibold">Recommended.</span> On players the weights were not fitted on, agreement improves by{" "}
                  {k2((data.cv_after ?? 0) - (data.cv_before ?? 0))}, more than twice the fold-to-fold noise (±{k2(data.cv_noise)}).
                </p>
              ) : (
                <p>
                  <span className="font-semibold">Not recommended yet.</span> The held-out gain ({k2((data.cv_after ?? 0) - (data.cv_before ?? 0))}) is
                  not clearly above the noise (±{k2(data.cv_noise)}, minimum {data.min_gain}). The suggestion may only fit these
                  ratings by chance: keep rating players and check again.
                </p>
              )}
            </Card>
          )}
          <p className="text-ink-2 mt-2 text-xs">
            Colour buffer: a better colour needs the score {data.hysteresis.up} points past the boundary; a worse colour applies
            {data.hysteresis.down === 0 ? " immediately" : ` after ${data.hysteresis.down} points`}, so warnings are never delayed.
          </p>
        </section>

        {user?.role === "coach" && (
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => apply(data.suggested)} disabled={busy || same || !data.enough_data || !data.recommended} loading={busy}>
              Apply suggested weights
            </Button>
            {data.enough_data && !same && !data.recommended && (
              <Button variant="ghost" onClick={() => apply(data.suggested, true)} disabled={busy}>
                Apply anyway
              </Button>
            )}
            <Button variant="secondary" onClick={() => apply(null)} disabled={busy}>
              Reset to defaults
            </Button>
            {msg && (
              <p role="status" className="text-sm font-semibold">
                {msg}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function WeightsCard({ title, w, highlight }: { title: string; w: Weights; highlight?: boolean }) {
  return (
    <Card className={cn(highlight && "border-pitch-500")}>
      <p className="mb-3 font-bold">{title}</p>
      {(Object.keys(LABEL) as (keyof Weights)[]).map((k) => (
        <div key={k} className="mb-2 flex items-center gap-3">
          <span className="w-44 text-sm">{LABEL[k]}</span>
          <div className="bg-surface-2 h-2.5 flex-1 rounded-full" aria-hidden>
            <div className="bg-pitch-500 h-full rounded-full" style={{ width: `${w[k] * 100}%` }} />
          </div>
          <span className="w-10 text-right text-sm font-semibold">{w[k].toFixed(2)}</span>
        </div>
      ))}
    </Card>
  );
}
