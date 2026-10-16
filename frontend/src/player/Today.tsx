// "Match day sheet": readiness battery, today's session, recovery tasks, "Why?" cards.
import { CheckCircle2, ChevronDown, Circle, Flame, HeartHandshake } from "lucide-react";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../shared/api";
import { t } from "../shared/i18n";
import type { Today, WhyCard } from "../shared/types";
import { useApi } from "../shared/useApi";
import { BAND_BG, BAND_TEXT, BandIcon, Button, Card, Chip, ErrorNote, SectionTitle, Spinner, cn, intensityClass } from "../shared/ui";

export function TodayScreen() {
  const { data, setData, error, loading, reload } = useApi<Today>("/api/me/today");
  const escalated = (useLocation().state as { escalated?: boolean } | null)?.escalated;

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  async function toggle(id: string) {
    setData((d) => d && { ...d, tasks: d.tasks.map((x) => (x.id === id ? { ...x, done: !x.done } : x)) });
    await api(`/api/me/tasks/${id}/toggle`, { method: "POST" }).catch(reload);
  }

  const r = data.readiness;
  return (
    <div className="space-y-5 pt-2">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-ink-2 text-sm">
            {new Date(data.date + "T12:00:00").toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}
          </p>
          <h1 className="text-2xl font-extrabold">Hi {data.name.split(" ")[0]}</h1>
        </div>
        {data.streak > 0 && (
          <span className="text-ready-amber flex items-center gap-1 font-bold" title="Check-in streak">
            <Flame className="h-5 w-5" aria-hidden /> {data.streak}
          </span>
        )}
      </div>

      {escalated && (
        <Card className="border-pitch-400 flex gap-3">
          <HeartHandshake className="text-pitch-300 h-6 w-6 shrink-0" aria-hidden />
          <p>Thanks for your honest check-in. Someone from the staff will talk to you today. You don't need to do anything else.</p>
        </Card>
      )}

      {!data.checked_in && (
        <Link to="/player/checkin">
          <Card className="bg-pitch-700 border-pitch-500 text-white">
            <p className="text-lg font-bold">{t("checkin.title")}</p>
            <p className="text-pitch-100 text-sm">{t("checkin.subtitle")} Tap to start.</p>
          </Card>
        </Link>
      )}

      <Battery score={r?.score ?? null} band={r?.band ?? null} stale={!data.readiness_is_today} />

      {data.flags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {data.flags.map((f) => (
            <Chip key={f.kind}>{f.text}</Chip>
          ))}
        </div>
      )}

      <section>
        <SectionTitle>{t("today.session")}</SectionTitle>
        <Card className="flex items-center gap-4">
          <div className={cn("flex h-14 w-14 items-center justify-center rounded-xl text-lg font-extrabold", intensityClass(data.session.kind, data.session.rpe))}>
            {data.session.kind === "rest" ? "–" : data.session.rpe}
          </div>
          <div>
            <p className="text-lg font-bold">{data.session.label}</p>
            <p className="text-ink-2 text-sm">
              {data.session.kind === "rest"
                ? "Recover and enjoy your day off"
                : `${data.session.minutes} min · effort ${data.session.rpe}/10`}
            </p>
          </div>
        </Card>
      </section>

      <section>
        <SectionTitle>{t("today.tasks")}</SectionTitle>
        <Card className="divide-[color:var(--line)] divide-y p-0">
          {data.tasks.map((task) => (
            <button
              key={task.id}
              onClick={() => toggle(task.id)}
              className="tap flex w-full items-center gap-3 px-4 py-3 text-left"
              aria-pressed={task.done}
            >
              {task.done ? (
                <CheckCircle2 className="text-pitch-300 h-6 w-6" aria-hidden />
              ) : (
                <Circle className="text-ink-2 h-6 w-6" aria-hidden />
              )}
              <span className={cn(task.done && "text-ink-2 line-through")}>{task.label}</span>
            </button>
          ))}
        </Card>
      </section>

      {data.why.length > 0 && (
        <section>
          <SectionTitle>{t("today.why")}</SectionTitle>
          <div className="space-y-2">
            {data.why.map((w) => (
              <WhyCardView key={w.id} card={w} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export function Battery({ score, band, stale }: { score: number | null; band: "green" | "amber" | "red" | null; stale?: boolean }) {
  const pct = score == null ? 0 : Math.max(4, Math.min(100, score));
  return (
    <Card aria-label={`Readiness ${score == null ? "unknown" : Math.round(score)} of 100, ${band ? BAND_TEXT[band] : "no data"}`}>
      <div className="flex items-center gap-4">
        <div className="border-ink-2 relative h-16 flex-1 rounded-xl border-2 p-1">
          <div
            className={cn("h-full rounded-lg transition-[width] duration-500 motion-reduce:transition-none", band ? BAND_BG[band] : "bg-surface-2")}
            style={{ width: `${pct}%` }}
          />
          <div className="bg-ink-2 absolute top-1/2 -right-2 h-6 w-1.5 -translate-y-1/2 rounded-r" />
        </div>
        <div className="w-24 text-right">
          <p className="text-3xl font-extrabold">{score == null ? "–" : Math.round(score)}</p>
          <p className="flex items-center justify-end gap-1 text-sm font-semibold">
            <BandIcon band={band} className="h-4 w-4" />
            {band ? BAND_TEXT[band] : "No data"}
          </p>
        </div>
      </div>
      <p className="text-ink-2 mt-2 text-sm">
        {t("today.battery")} from sleep, heart-rate variability and your check-in.
        {stale && " Showing your last reading: check in to update it."}
      </p>
    </Card>
  );
}

function WhyCardView({ card }: { card: WhyCard }) {
  const [open, setOpen] = useState(false);
  return (
    <Card className="p-0">
      <button className="tap flex w-full items-center justify-between px-4 py-3 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="font-semibold">{card.title}</span>
        <ChevronDown className={cn("h-5 w-5 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div className="space-y-3 px-4 pb-4">
          {card.explanation && <p>{card.explanation}</p>}
          {card.chips.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {card.chips.map((c) => (
                <Chip key={c}>{c}</Chip>
              ))}
            </div>
          )}
          <p className="text-ink-2 text-sm">Approved by {card.approved_by}</p>
          <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
            Got it
          </Button>
        </div>
      )}
    </Card>
  );
}
