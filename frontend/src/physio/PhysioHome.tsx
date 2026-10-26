// Physio: escalation queue (oldest first) plus the squad's PHV list.
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../shared/api";
import type { Status } from "../shared/types";
import { PageHeader } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { BandBadge, Button, Card, ErrorNote, SectionTitle, Spinner } from "../shared/ui";

interface Escalation {
  id: string;
  player: { id: string; name: string };
  kind: string;
  text: string;
  created_at: string;
  age_minutes: number;
  notified_after_s: number | null;
  readiness: Status | null;
}
interface PhvRow {
  id: string;
  name: string;
  age: number;
  maturity_offset: number;
  in_window: boolean;
}

function age(min: number): string {
  if (min < 60) return `${min} min ago`;
  if (min < 60 * 24) return `${Math.round(min / 60)} h ago`;
  return `${Math.round(min / 1440)} d ago`;
}

export function PhysioHome() {
  const queue = useApi<Escalation[]>("/api/physio/queue");
  const phv = useApi<PhvRow[]>("/api/physio/phv");
  const [busy, setBusy] = useState<string | null>(null);

  async function ack(id: string) {
    setBusy(id);
    await api(`/api/physio/escalations/${id}/ack`, { method: "POST" });
    queue.setData((q) => q && q.filter((e) => e.id !== id));
    setBusy(null);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Medical"
        title="Escalation queue"
        subtitle="Pain reports and red check-ins, oldest first. The agents take no action on these: they are yours."
        actions={
          queue.data && (
            <span className="text-right">
              <span className="font-display block text-4xl leading-none font-bold">{queue.data.length}</span>
              <span className="text-xs font-semibold tracking-wider text-white/70 uppercase">waiting</span>
            </span>
          )
        }
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section>
          {queue.loading && !queue.data && <Spinner />}
          {queue.error && <ErrorNote message={queue.error} onRetry={queue.reload} />}
          {queue.data?.length === 0 && <Card className="text-ink-2">Queue is empty.</Card>}
          <ul className="space-y-2">
            {queue.data?.map((e) => (
              <li key={e.id}>
                <Card className="border-ready-red/50 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-ready-red text-xs font-bold uppercase">{e.text}</p>
                    <Link to={`/coach/players/${e.player.id}`} className="text-lg font-bold hover:underline">
                      {e.player.name}
                    </Link>
                    <p className="text-ink-2 text-sm">
                      {age(e.age_minutes)}
                      {/* Queued, not pushed: there is no push, email or SMS channel yet */}
                      {e.notified_after_s != null &&
                        ` · in this queue ${e.notified_after_s < 1 ? "within a second" : `${Math.round(e.notified_after_s)} s`} after the check-in`}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <BandBadge band={e.readiness?.band ?? null} score={e.readiness?.score} />
                    <Button onClick={() => ack(e.id)} loading={busy === e.id}>
                      I've spoken to them
                    </Button>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <SectionTitle>Growth zone (PHV) list</SectionTitle>
          {phv.loading && !phv.data && <Spinner />}
          <Card className="divide-[color:var(--line)] divide-y p-0">
            {phv.data?.map((p) => (
              <div key={p.id} className="flex items-center justify-between p-3">
                <Link to={`/coach/players/${p.id}`} className="font-semibold hover:underline">
                  {p.name}
                </Link>
                <span className={p.in_window ? "text-ready-amber font-bold" : "text-ink-2"}>
                  {p.maturity_offset > 0 ? "+" : ""}
                  {p.maturity_offset.toFixed(1)} y
                </span>
              </div>
            ))}
            {phv.data?.length === 0 && <p className="text-ink-2 p-3 text-sm">No players near PHV.</p>}
          </Card>
        </section>
      </div>
    </div>
  );
}
