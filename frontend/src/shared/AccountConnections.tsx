// Account page sections: reminders and notifications on this device, the calendar
// address, and two-step sign-in with an authenticator app.
import { BellRing, CalendarPlus, Copy, KeyRound, ShieldCheck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, DEMO, getToken } from "./api";
import { useAuth } from "./auth";
import { currentSubscription, disablePush, enablePush, pushSupported } from "./push";
import { Field, input } from "./Register";
import type { User } from "./types";
import { Button, SectionTitle } from "./ui";
import { useApi } from "./useApi";

interface NotificationSettings {
  reminder_hour: number | null;
  reminders_available: boolean;
  timezone: string;
  push_public_key: string | null;
  push_devices: number;
  calendar: boolean;
  calendar_available: boolean;
}

type Note = (n: { ok: boolean; text: string }) => void;

function message(err: unknown): string {
  return err instanceof ApiError || err instanceof Error ? err.message : "Cannot reach the server";
}

export function Connections({ onNote }: { onNote: Note }) {
  const s = useApi<NotificationSettings>(DEMO ? null : "/api/account/notifications");
  if (DEMO || !s.data) return null;
  return (
    <>
      <Notifications settings={s.data} reload={s.reload} onNote={onNote} />
      {s.data.calendar_available && <Calendar hasFeed={s.data.calendar} onNote={onNote} />}
    </>
  );
}

function Notifications({ settings, reload, onNote }: { settings: NotificationSettings; reload: () => Promise<void>; onNote: Note }) {
  const [onThisDevice, setOnThisDevice] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    currentSubscription().then((sub) => setOnThisDevice(!!sub));
  }, []);

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    try {
      await fn();
      onNote({ ok: true, text: ok });
      await reload();
    } catch (err) {
      onNote({ ok: false, text: message(err) });
    } finally {
      setBusy(false);
    }
  }

  const setHour = (hour: number | null) =>
    run(() => api("/api/account/reminder", { method: "PUT", json: { hour } }), hour == null ? "Reminders off." : `Reminder set for ${hour}:00.`);

  return (
    <section>
      <SectionTitle>Notifications</SectionTitle>
      {settings.reminders_available && (
        <Field label="Daily check-in reminder" hint={`Only on days you haven't checked in yet. Time zone: ${settings.timezone}.`}>
          <select
            className={input}
            value={settings.reminder_hour ?? ""}
            disabled={busy}
            onChange={(e) => setHour(e.target.value === "" ? null : Number(e.target.value))}
          >
            <option value="">Off</option>
            {Array.from({ length: 18 }, (_, i) => i + 5).map((h) => (
              <option key={h} value={h}>
                {String(h).padStart(2, "0")}:00
              </option>
            ))}
          </select>
        </Field>
      )}
      <div className="mt-3 space-y-2 text-sm">
        {!settings.push_public_key ? (
          <p className="text-ink-2">Notifications on your phone are not set up on this server; alerts and reminders come by email.</p>
        ) : !pushSupported() ? (
          <p className="text-ink-2">
            This browser can't show notifications. On an iPhone or iPad, add PathToPro to the home screen first (Share → Add to Home Screen).
          </p>
        ) : onThisDevice ? (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" disabled={busy} onClick={() => run(() => api("/api/account/push/test", { method: "POST" }), "Test notification sent.")}>
              <BellRing className="h-4 w-4" aria-hidden /> Send a test
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={() => run(async () => {
                await disablePush();
                setOnThisDevice(false);
              }, "Notifications off on this device.")}
            >
              Turn off on this device
            </Button>
          </div>
        ) : (
          <Button
            variant="secondary"
            size="sm"
            loading={busy}
            onClick={() => run(async () => {
              await enablePush(settings.push_public_key!);
              setOnThisDevice(true);
            }, "Notifications are on for this device.")}
          >
            <BellRing className="h-4 w-4" aria-hidden /> Turn on notifications on this device
          </Button>
        )}
        {settings.push_devices > 0 && <p className="text-ink-2 text-xs">{settings.push_devices} device(s) receive notifications.</p>}
      </div>
    </section>
  );
}

function Calendar({ hasFeed, onNote }: { hasFeed: boolean; onNote: Note }) {
  const [feed, setFeed] = useState<{ url: string; webcal: string } | null>(null);
  const [exists, setExists] = useState(hasFeed);
  const [busy, setBusy] = useState(false);

  async function create() {
    setBusy(true);
    try {
      setFeed(await api<{ url: string; webcal: string }>("/api/account/calendar", { method: "POST" }));
      setExists(true);
    } catch (err) {
      onNote({ ok: false, text: message(err) });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api("/api/account/calendar", { method: "DELETE" });
      setFeed(null);
      setExists(false);
      onNote({ ok: true, text: "Calendar address switched off." });
    } catch (err) {
      onNote({ ok: false, text: message(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <SectionTitle>Calendar</SectionTitle>
      <p className="text-ink-2 mb-2 text-sm">
        Your sessions and matches in Google, Apple or Outlook Calendar, updated every few hours. Anyone with the address can see the
        calendar, so keep it to yourself.
      </p>
      {feed ? (
        <div className="space-y-2">
          <input className={input} readOnly value={feed.url} aria-label="Calendar address" onFocus={(e) => e.target.select()} />
          <div className="flex flex-wrap gap-2">
            <a className="bg-pitch-600 hover:bg-pitch-700 tap inline-flex h-11 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-white" href={feed.webcal}>
              <CalendarPlus className="h-4 w-4" aria-hidden /> Add to my calendar
            </a>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigator.clipboard?.writeText(feed.url).then(() => onNote({ ok: true, text: "Address copied." }))}
            >
              <Copy className="h-4 w-4" aria-hidden /> Copy
            </Button>
          </div>
          <p className="text-ink-2 text-xs">Google Calendar: Other calendars → + → From URL, and paste the address.</p>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={create} loading={busy}>
            <CalendarPlus className="h-4 w-4" aria-hidden /> {exists ? "Make a new address" : "Get my calendar address"}
          </Button>
          {exists && (
            <Button variant="ghost" size="sm" onClick={remove} disabled={busy}>
              Switch off
            </Button>
          )}
        </div>
      )}
      {exists && !feed && <p className="text-ink-2 mt-1 text-xs">A calendar address is active. A new one stops the old one working.</p>}
    </section>
  );
}

export function TwoStep({ onNote }: { onNote: Note }) {
  const { user, adopt } = useAuth();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  const staff = user.role !== "player" && user.role !== "guardian";

  async function start() {
    setBusy(true);
    try {
      setSetup(await api("/api/auth/mfa/setup", { method: "POST" }));
    } catch (err) {
      onNote({ ok: false, text: message(err) });
    } finally {
      setBusy(false);
    }
  }

  async function confirm(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const out = await api<{ token: string; user: User; recovery_codes: string[] }>("/api/auth/mfa/enable", { method: "POST", json: { code } });
      adopt(out.token, out.user);
      setCodes(out.recovery_codes);
      setSetup(null);
      onNote({ ok: true, text: "Two-step sign-in is on. Other devices sign in again with a code." });
    } catch (err) {
      onNote({ ok: false, text: message(err) });
    } finally {
      setBusy(false);
    }
  }

  async function turnOff(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await api<User>("/api/auth/mfa/disable", { method: "POST", json: { password } });
      adopt(getToken() ?? "", u);
      setPassword("");
      onNote({ ok: true, text: "Two-step sign-in is off." });
    } catch (err) {
      onNote({ ok: false, text: message(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <SectionTitle>Two-step sign-in</SectionTitle>
      {codes ? (
        <div className="space-y-2 text-sm">
          <p className="font-semibold">Recovery codes: write them down or store them in a password manager now. Each works once if you lose your phone.</p>
          <ul className="bg-surface-2 grid grid-cols-2 gap-1 rounded-lg p-3 font-mono">
            {codes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <Button variant="secondary" size="sm" onClick={() => setCodes(null)}>
            I've saved them
          </Button>
        </div>
      ) : user.mfa_enabled ? (
        <form onSubmit={turnOff} className="space-y-3">
          <p className="flex items-center gap-2 text-sm">
            <ShieldCheck className="text-ready h-5 w-5" aria-hidden /> On: signing in asks for a code from your authenticator app.
          </p>
          <Field label="Password, to turn it off">
            <input className={input} type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Button type="submit" variant="ghost" size="sm" loading={busy}>
            Turn off
          </Button>
        </form>
      ) : setup ? (
        <form onSubmit={confirm} className="space-y-3 text-sm">
          <p>
            1. In your authenticator app (Google Authenticator, Microsoft Authenticator, 1Password…) add an account.{" "}
            <a className="font-semibold underline" href={setup.otpauth_uri}>
              On this phone: tap here
            </a>
            , or type this key:
          </p>
          <p className="bg-surface-2 rounded-lg p-3 text-center font-mono tracking-wider break-all">{setup.secret.match(/.{1,4}/g)?.join(" ")}</p>
          <Field label="2. Enter the 6-digit code it shows">
            <input className={input} inputMode="numeric" autoComplete="one-time-code" required minLength={6} maxLength={7} value={code} onChange={(e) => setCode(e.target.value)} />
          </Field>
          <Button type="submit" size="sm" loading={busy}>
            Turn on
          </Button>
        </form>
      ) : (
        <div className="space-y-2 text-sm">
          <p className="text-ink-2">
            A code from an app on your phone, as well as your password.{" "}
            {staff ? "Recommended for staff: your account can see players' health data." : "Optional, for extra safety."}
          </p>
          <Button variant="secondary" size="sm" onClick={start} loading={busy} disabled={DEMO}>
            <KeyRound className="h-4 w-4" aria-hidden /> Set up two-step sign-in
          </Button>
        </div>
      )}
    </section>
  );
}
