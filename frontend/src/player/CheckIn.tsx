// "Pre-match warm-up": 4 Hooper cards + mood/pain, one per card, under 30 s.
// A ball rolls further across a mini pitch with each answer.
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../shared/api";
import { t } from "../shared/i18n";
import { Ball, Pitch } from "../shared/Pitch";
import type { Today } from "../shared/types";
import { Button, Card, cn } from "../shared/ui";

type HooperKey = "sleep_quality" | "fatigue" | "stress" | "soreness";

// Title keys are translated at render time, so a language switch applies immediately.
const QUESTIONS: { key: HooperKey; title: string; low: string; high: string }[] = [
  { key: "sleep_quality", title: "checkin.sleep_quality", low: "Great", high: "Awful" },
  { key: "fatigue", title: "checkin.fatigue", low: "Fresh", high: "Exhausted" },
  { key: "stress", title: "checkin.stress", low: "Relaxed", high: "Very stressed" },
  { key: "soreness", title: "checkin.soreness", low: "Not sore", high: "Very sore" },
];
const FACES = ["😄", "🙂", "😌", "😐", "😕", "😣", "😫"];
const STEPS = QUESTIONS.length + 1;

export function CheckIn() {
  const nav = useNavigate();
  const reduce = useReducedMotion();
  const started = useRef(performance.now());
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<HooperKey, number>>({ sleep_quality: 3, fatigue: 3, stress: 3, soreness: 3 });
  const [mood, setMood] = useState<"green" | "amber" | "red">("green");
  const [pain, setPain] = useState(false);
  const [sleepHours, setSleepHours] = useState(8);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ escalated: boolean; notified?: "staff" | "guardian" | null; today: Today }>("/api/me/checkin", {
        method: "POST",
        json: {
          ...answers,
          mood,
          pain,
          sleep_hours: sleepHours,
          duration_s: Math.round((performance.now() - started.current) / 100) / 10,
        },
      });
      nav("/player", { state: { escalated: res.escalated, notified: res.notified ?? null, flagged: mood === "red" || pain } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send. Check your connection.");
      setBusy(false);
    }
  }

  const q = QUESTIONS[step];
  return (
    <div className="mx-auto max-w-xl space-y-4 pt-2">
      <div>
        <h1 className="text-2xl font-extrabold">{t("checkin.title")}</h1>
        <p className="text-ink-2">{t("checkin.subtitle")}</p>
      </div>
      <Pitch width={150} height={40} className="w-full" label={`Progress: step ${step + 1} of ${STEPS}`}>
        <motion.g
          animate={{ x: 10 + (step / STEPS) * 128 }}
          initial={false}
          transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 120, damping: 14 }}
        >
          <Ball x={0} y={20} r={4} />
        </motion.g>
      </Pitch>
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={reduce ? false : { opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          exit={reduce ? undefined : { opacity: 0, x: -40 }}
          transition={{ duration: 0.18 }}
        >
          {q ? (
            <Card className="space-y-5">
              <h2 className="text-xl font-bold" id={`q-${q.key}`}>
                {t(q.title)}
              </h2>
              <div className="text-center text-6xl" aria-hidden>
                {FACES[answers[q.key] - 1]}
              </div>
              <input
                type="range"
                min={1}
                max={7}
                step={1}
                value={answers[q.key]}
                aria-labelledby={`q-${q.key}`}
                aria-valuetext={`${answers[q.key]} of 7`}
                onChange={(e) => setAnswers({ ...answers, [q.key]: Number(e.target.value) })}
                className="accent-pitch-400 h-11 w-full"
              />
              <div className="text-ink-2 flex justify-between text-sm">
                <span>{q.low}</span>
                <span>{q.high}</span>
              </div>
              <Button className="w-full" size="lg" onClick={() => setStep(step + 1)}>
                Next
              </Button>
            </Card>
          ) : (
            <Card className="space-y-5">
              <fieldset>
                <legend className="mb-3 text-xl font-bold">{t("checkin.mood")}</legend>
                <div className="grid grid-cols-3 gap-2">
                  {(
                    [
                      ["green", "😊", "Good"],
                      ["amber", "😐", "So-so"],
                      ["red", "😞", "Not good"],
                    ] as const
                  ).map(([v, face, label]) => (
                    <button
                      key={v}
                      type="button"
                      aria-pressed={mood === v}
                      onClick={() => setMood(v)}
                      className={cn(
                        "tap border-line flex flex-col items-center rounded-xl border-2 py-3 font-semibold",
                        mood === v && "border-pitch-300 bg-pitch-800/40",
                      )}
                    >
                      <span className="text-3xl" aria-hidden>
                        {face}
                      </span>
                      {label}
                    </button>
                  ))}
                </div>
                {mood === "red" && (
                  <p className="text-ink-2 mt-2 text-sm">
                    Thanks for telling us. A staff member you know will check in with you today.
                  </p>
                )}
              </fieldset>
              <label className="border-line flex items-center justify-between rounded-xl border p-3">
                <span className="font-semibold">{t("checkin.pain")}</span>
                <input type="checkbox" className="accent-recover h-6 w-6" checked={pain} onChange={(e) => setPain(e.target.checked)} />
              </label>
              <label className="block">
                <span className="font-semibold">Hours slept: {sleepHours} h</span>
                <input
                  type="range"
                  min={3}
                  max={12}
                  step={0.5}
                  value={sleepHours}
                  onChange={(e) => setSleepHours(Number(e.target.value))}
                  className="accent-pitch-400 h-11 w-full"
                />
              </label>
              {error && (
                <p role="alert" className="text-recover text-sm">
                  {error}
                </p>
              )}
              <Button className="w-full" size="lg" onClick={submit} loading={busy}>
                {t("checkin.done")}
              </Button>
            </Card>
          )}
        </motion.div>
      </AnimatePresence>
      {step > 0 && (
        <Button variant="ghost" className="w-full" onClick={() => setStep(step - 1)}>
          Back
        </Button>
      )}
    </div>
  );
}
