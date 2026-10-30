// "Growing pains radar": height curve with the shaded PHV band and a "you are here" dot.
import { useState, type FormEvent } from "react";
import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError } from "../shared/api";
import type { Growth as GrowthData } from "../shared/types";
import { useApi } from "../shared/useApi";
import { Button, Card, ErrorNote, SectionTitle, Spinner } from "../shared/ui";

export function Growth() {
  const { data, setData, error, loading, reload } = useApi<GrowthData>("/api/me/growth");
  const [form, setForm] = useState({ height_cm: "", sitting_height_cm: "", weight_kg: "" });
  const [msg, setMsg] = useState<string | null>(null);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  if (!data.consent)
    return (
      <Card className="mt-4">
        <p className="font-semibold">Growth tracking is switched off</p>
        <p className="text-ink-2 text-sm">Your guardian can switch it on in the family view.</p>
      </Card>
    );

  const pts = data.measurements;
  const last = pts[pts.length - 1];

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setData(
        await api<GrowthData>("/api/me/growth", {
          method: "POST",
          json: { height_cm: +form.height_cm, sitting_height_cm: +form.sitting_height_cm, weight_kg: +form.weight_kg },
        }),
      );
      setMsg("Saved. Thanks!");
      setForm({ height_cm: "", sitting_height_cm: "", weight_kg: "" });
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Could not save");
    }
  }

  return (
    <div className="space-y-4 pt-2">
      <h1 className="text-2xl font-extrabold">Growth zone</h1>
      {/* Wide screens: growth chart on the left, the explanation on the right */}
      <div className="space-y-5 lg:grid lg:grid-cols-2 lg:items-start lg:gap-6 lg:space-y-0">
        <div className="space-y-5">
          <Card>
            {data.in_phv_window ? (
              <p>
                <strong className="text-caution">You're in your growth spurt.</strong> Bones grow faster than muscles and tendons
                right now, so jumps and sprints are kept short. It's temporary and normal.
              </p>
            ) : (
              <p>
                {last && last.maturity_offset < 0
                  ? `Your growth spurt is about ${Math.abs(last.maturity_offset).toFixed(1)} years away.`
                  : "Your fastest growth is behind you."}{" "}
                Measuring every month helps us plan around it.
              </p>
            )}
          </Card>
          <Card className="h-72 p-2">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={pts} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.08)" />
                <XAxis dataKey="age" type="number" domain={["dataMin - 0.2", "dataMax + 0.4"]} tickFormatter={(v) => v.toFixed(1)} stroke="#a8b4c8" fontSize={12} />
                <YAxis domain={["dataMin - 3", "dataMax + 3"]} stroke="#a8b4c8" fontSize={12} unit=" cm" width={60} />
                {data.phv_window && (
                  <ReferenceArea x1={data.phv_window[0]} x2={data.phv_window[1]} fill="#e3a008" fillOpacity={0.18} label={{ value: "Growth zone", fill: "#e3a008", fontSize: 11, position: "insideTop" }} />
                )}
                <Tooltip contentStyle={{ background: "#111b30", border: "1px solid #24324d" }} labelFormatter={(v) => `Age ${Number(v).toFixed(1)}`} />
                <Line type="monotone" dataKey="height_cm" stroke="var(--brand-300)" strokeWidth={3} dot={{ r: 3 }} name="Height (cm)" />
                {last && <ReferenceDot x={last.age} y={last.height_cm} r={7} fill="#fff" stroke="var(--brand-500)" strokeWidth={3} label={{ value: "You", position: "top", fill: "#fff", fontSize: 12 }} />}
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </div>

        <div className="space-y-5">
          <section>
            <SectionTitle>Monthly measurement</SectionTitle>
            <Card>
              <details className="mb-3">
                <summary className="tap cursor-pointer font-semibold">How to measure (1 min guide)</summary>
                <ol className="text-ink-2 mt-2 list-decimal space-y-1 pl-5 text-sm">
                  <li>Shoes off, heels against the wall, look straight ahead.</li>
                  <li>Sitting height: sit on a box against the wall, measure from the box to the top of your head.</li>
                  <li>Ask an adult to read the tape. Measure in the morning if you can.</li>
                </ol>
              </details>
              {data.next_measurement_due && <p className="text-ink-2 mb-2 text-sm">Next measurement due {data.next_measurement_due}</p>}
              <form onSubmit={submit} className="grid grid-cols-3 gap-2">
                {(
                  [
                    ["height_cm", "Height cm"],
                    ["sitting_height_cm", "Sitting cm"],
                    ["weight_kg", "Weight kg"],
                  ] as const
                ).map(([k, label]) => (
                  <label key={k} className="text-sm">
                    {label}
                    <input
                      inputMode="decimal"
                      required
                      value={form[k]}
                      onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                      className="bg-surface-2 border-line mt-1 h-11 w-full rounded-lg border px-2 text-base"
                    />
                  </label>
                ))}
                <Button type="submit" className="col-span-3">
                  Save measurement
                </Button>
              </form>
              {msg && (
                <p className="mt-2 text-sm" role="status">
                  {msg}
                </p>
              )}
            </Card>
          </section>
        </div>
      </div>

    </div>
  );
}
