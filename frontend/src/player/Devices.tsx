// Apple Watch: connect via an iPhone Shortcut (daily, automatic) or upload the Health
// app's export. HRV, sleep and workouts feed the battery and the training load.
import { Check, Copy, Trash2, Upload, Watch } from "lucide-react";
import { useState, type ChangeEvent } from "react";
import { api, ApiError, DEMO, getToken } from "../shared/api";
import { useApi } from "../shared/useApi";
import { Button, Card, Chip, ErrorNote, SectionTitle, Spinner, fmtDay } from "../shared/ui";

interface Summary {
  hrv_days?: number;
  sleep_nights?: number;
  workouts?: number;
  skipped?: string[];
}
interface DevicesView {
  ingest_url: string;
  tokens: { id: string; label: string; created_at: string; last_used_at: string | null; last_summary: Summary }[];
  consent: Record<"hrv" | "sleep" | "wellness", boolean>;
  latest: { hrv_day: string | null; sleep_night: string | null; sleep_hours: number | null };
  window_days: number;
  new_token?: { id: string; token: string };
}

function CopyField({ label, value }: { label: string; value: string }) {
  const [done, setDone] = useState(false);
  return (
    <div>
      <p className="text-ink-2 text-xs font-semibold uppercase">{label}</p>
      <div className="mt-1 flex gap-2">
        <code className="bg-surface-2 border-line min-w-0 flex-1 truncate rounded-lg border px-2 py-2 text-xs" aria-label={label}>
          {value}
        </code>
        <Button
          variant="secondary"
          size="sm"
          aria-label={`Copy ${label}`}
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(value);
              setDone(true);
            } catch {
              /* clipboard blocked: the text is selectable */
            }
          }}
        >
          {done ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}

function summaryText(s: Summary): string {
  const parts = [
    s.hrv_days ? `${s.hrv_days} days of HRV` : "",
    s.sleep_nights ? `${s.sleep_nights} nights of sleep` : "",
    s.workouts ? `${s.workouts} workouts` : "",
  ].filter(Boolean);
  return (parts.join(", ") || "nothing new") + (s.skipped?.length ? ` (skipped: ${s.skipped.join("; ")})` : "");
}

export function Devices() {
  const { data, setData, error, loading, reload } = useApi<DevicesView>("/api/me/devices");
  const [fresh, setFresh] = useState<{ token: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  async function connect() {
    setMsg(null);
    try {
      const out = await api<DevicesView>("/api/me/devices", { method: "POST", json: { label: "Apple Watch" } });
      setData(out);
      setFresh(out.new_token ?? null);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Failed");
    }
  }

  async function remove(id: string) {
    setData(await api<DevicesView>(`/api/me/devices/${id}`, { method: "DELETE" }));
    setFresh(null);
  }

  async function upload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setMsg(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/me/health/import", { method: "POST", body: form, headers: { Authorization: `Bearer ${getToken()}` } });
      const body = await res.json();
      if (!res.ok) throw new ApiError(res.status, body.detail ?? res.statusText);
      setMsg(`Imported ${summaryText(body)}.`);
      await reload();
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  const missing = Object.entries(data.consent).filter(([, ok]) => !ok);
  return (
    <div className="space-y-5 pt-2">
      <div className="flex items-center gap-3">
        <Watch className="text-pitch-300 h-8 w-8" aria-hidden />
        <div>
          <h1 className="text-2xl font-extrabold">Apple Watch</h1>
          <p className="text-ink-2 text-sm">Heart-rate variability, sleep and workouts go straight into your battery and training load.</p>
        </div>
      </div>

      {DEMO && (
        <Card className="border-caution/50 text-sm">This offline demo can't receive watch data: connect on the live server.</Card>
      )}
      {missing.length > 0 && (
        <Card className="border-caution/50 text-sm">
          Not stored until a parent agrees: {missing.map(([k]) => ({ hrv: "heart-rate variability", sleep: "sleep", wellness: "workouts" })[k as "hrv"]).join(", ")}.
        </Card>
      )}

      {/* Wide screens: connect on the left, what was received on the right */}
      <div className="space-y-5 lg:grid lg:grid-cols-2 lg:items-start lg:gap-6 lg:space-y-0">
        <div className="space-y-5">
          <Card>
            <p className="font-bold">Latest from your watch</p>
            <ul className="text-ink-2 mt-1 space-y-1 text-sm">
              <li>Heart-rate variability: {data.latest.hrv_day ? fmtDay(data.latest.hrv_day, { weekday: "short", day: "numeric", month: "short" }) : "nothing yet"}</li>
              <li>
                Sleep:{" "}
                {data.latest.sleep_night
                  ? `${data.latest.sleep_hours?.toFixed(1)} h on ${fmtDay(data.latest.sleep_night, { weekday: "short", day: "numeric", month: "short" })}`
                  : "nothing yet"}
              </li>
            </ul>
          </Card>

          <section>
            <SectionTitle>1. Automatic daily sync (iPhone Shortcut)</SectionTitle>
            <Card className="space-y-3">
              {data.tokens.map((t) => (
                <div key={t.id} className="border-line flex items-center justify-between gap-2 rounded-xl border p-3">
                  <div className="min-w-0">
                    <p className="font-semibold">{t.label}</p>
                    <p className="text-ink-2 text-xs">
                      {t.last_used_at ? `Last sync ${new Date(t.last_used_at).toLocaleString("en-GB")}: ${summaryText(t.last_summary)}` : "Waiting for the first sync"}
                    </p>
                  </div>
                  <Button variant="ghost" size="sm" aria-label={`Disconnect ${t.label}`} onClick={() => remove(t.id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              {fresh ? (
                <div className="border-pitch-500 space-y-3 rounded-xl border p-3">
                  <p className="font-semibold">Your connection details (the code is shown only once)</p>
                  <CopyField label="URL" value={`${window.location.origin}/api/ingest/apple-health`} />
                  <CopyField label="Device code" value={fresh.token} />
                </div>
              ) : (
                <Button onClick={connect} disabled={DEMO}>
                  <Watch className="h-4 w-4" aria-hidden /> Connect Apple Watch
                </Button>
              )}
              <details className="text-sm">
                <summary className="cursor-pointer font-semibold">How to set up the Shortcut (5 minutes, once)</summary>
                <ol className="text-ink-2 mt-2 list-decimal space-y-1.5 pl-5">
                  <li>On your iPhone open <b>Shortcuts → Automation → New Automation → Time of Day</b>: 08:00, Daily, Run Immediately.</li>
                  <li>
                    Add <b>Find Health Samples</b>: Heart Rate Variability, Start Date is in the last 1 day. Then <b>Calculate Statistics</b>:
                    Average. Rename the result <b>HRV</b>.
                  </li>
                  <li>
                    Add <b>Find Health Samples</b>: Sleep Analysis, Start Date is in the last 1 day, Value is not In Bed / Awake. Then{" "}
                    <b>Get Details of Health Samples</b>: Duration, and <b>Calculate Statistics</b>: Sum. Divide by 3600 (seconds to hours) if
                    needed and rename it <b>Sleep</b>.
                  </li>
                  <li>
                    Add <b>Dictionary</b> with keys <code>date</code> (Current Date, format yyyy-MM-dd), <code>hrv_sdnn_ms</code> (HRV) and{" "}
                    <code>sleep_hours</code> (Sleep).
                  </li>
                  <li>
                    Add <b>Get Contents of URL</b>: the URL above, Method POST, Header <code>Authorization</code> ={" "}
                    <code>Bearer &lt;device code&gt;</code>, Request Body JSON with key <code>days</code> = a list containing the Dictionary.
                  </li>
                  <li>Run it once by hand: "Last sync" above shows what arrived.</li>
                </ol>
              </details>
              {msg && !busy && <p className="text-sm font-semibold">{msg}</p>}
            </Card>
          </section>
        </div>

        <div className="space-y-5">
          <section>
            <SectionTitle>2. Or upload your Health data</SectionTitle>
            <Card className="space-y-2">
              <p className="text-ink-2 text-sm">
                On your iPhone: <b>Health → your picture → Export All Health Data</b>, save the zip, then choose it here. Only the last{" "}
                {data.window_days} days of HRV, sleep and workouts are read; the file isn't kept.
              </p>
              <label className="block">
                <span className="sr-only">Apple Health export</span>
                <input type="file" accept=".zip,.xml,application/zip,text/xml" onChange={upload} disabled={busy || DEMO} className="text-sm" />
              </label>
              {busy && (
                <p className="flex items-center gap-2 text-sm">
                  <Upload className="h-4 w-4 animate-pulse" aria-hidden /> Reading your export: large files take a minute…
                </p>
              )}
              {msg && busy === false && msg.startsWith("Imported") && (
                <p role="status" className="text-sm font-semibold">
                  {msg}
                </p>
              )}
            </Card>
          </section>

          <Card className="text-ink-2 space-y-1 text-xs">
            <p>
              <Chip>About the numbers</Chip> Apple Watch measures heart-rate variability as SDNN; chest straps usually give RMSSD. Your battery
              compares each day with your own 7-day baseline from the same kind of measurement, so the two are never mixed.
            </p>
            <p>
              Workouts become training load using your average heart rate (an effort estimate). Days you already logged, or your club logged,
              aren't counted twice. You can disconnect at any time.
            </p>
          </Card>
        </div>
      </div>

    </div>
  );
}
