// Account settings for every role: email confirmation, password, signing out everywhere,
// and deleting the account where the person may do that themselves.
import { ArrowLeft, CheckCircle2, LogOut, MailWarning, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError, DEMO } from "./api";
import { homeFor, useAuth } from "./auth";
import { Connections, TwoStep } from "./AccountConnections";
import { Field, input, Shell } from "./Register";
import type { User } from "./types";
import { Button, SectionTitle } from "./ui";
import { useApi } from "./useApi";

function message(err: unknown): string {
  return err instanceof ApiError ? err.message : "Cannot reach the server";
}

export function Account() {
  const { user, adopt, logout } = useAuth();
  const nav = useNavigate();
  const deletion = useApi<{ allowed: boolean; reason: string | null }>(DEMO ? null : "/api/auth/me/deletion");
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");

  if (!user) return null;

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    setNote(null);
    try {
      await fn();
    } catch (err) {
      setNote({ ok: false, text: message(err) });
    } finally {
      setBusy(null);
    }
  }

  const resend = () =>
    run("verify", async () => {
      await api("/api/auth/verify-email/resend", { method: "POST" });
      setNote({ ok: true, text: `We sent a new link to ${user.email}.` });
    });

  const changePassword = (e: FormEvent) => {
    e.preventDefault();
    return run("password", async () => {
      const out = await api<{ token: string; user: User }>("/api/auth/password/change", {
        method: "POST",
        json: { current_password: current, new_password: next },
      });
      adopt(out.token, out.user);
      setCurrent("");
      setNext("");
      setNote({ ok: true, text: "Password changed. Your other devices are signed out." });
    });
  };

  const everywhere = () =>
    run("everywhere", async () => {
      await api("/api/auth/logout-everywhere", { method: "POST" });
      logout();
      nav("/login");
    });

  const remove = (e: FormEvent) => {
    e.preventDefault();
    return run("delete", async () => {
      await api("/api/auth/me/delete", { method: "POST", json: { password: deletePassword } });
      logout();
      nav("/", { replace: true });
    });
  };

  return (
    <Shell
      title="Your account"
      subtitle={`${user.name} · ${user.email}`}
      footer={
        <p className="mt-4 text-center text-sm">
          <Link to={homeFor(user.role)} className="inline-flex items-center gap-1 font-semibold text-white underline">
            <ArrowLeft className="h-4 w-4" aria-hidden /> Back to PathToPro
          </Link>
        </p>
      }
    >
      <div className="space-y-6">
        {note && (
          <p role={note.ok ? "status" : "alert"} className={note.ok ? "text-ready-green text-sm font-semibold" : "text-ready-red text-sm font-medium"}>
            {note.text}
          </p>
        )}

        <section>
          <SectionTitle>Email</SectionTitle>
          {user.email_verified || DEMO ? (
            <p className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="text-ready-green h-5 w-5" aria-hidden /> {user.email} is confirmed.
            </p>
          ) : (
            <div className="space-y-2 text-sm">
              <p className="flex items-center gap-2">
                <MailWarning className="h-5 w-5 text-amber-600" aria-hidden /> {user.email} is not confirmed yet. Open the link we emailed you, so
                you can reset your password if you forget it.
              </p>
              <Button variant="secondary" size="sm" onClick={resend} loading={busy === "verify"} disabled={DEMO}>
                Send the link again
              </Button>
            </div>
          )}
        </section>

        <section>
          <SectionTitle>Password</SectionTitle>
          <form onSubmit={changePassword} className="space-y-3">
            <input type="email" autoComplete="username" value={user.email} readOnly hidden />
            <Field label="Current password">
              <input className={input} type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
            </Field>
            <Field label="New password" hint="At least 8 characters. Your other devices will be signed out.">
              <input className={input} type="password" autoComplete="new-password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)} />
            </Field>
            <Button type="submit" loading={busy === "password"} disabled={DEMO}>
              Change password
            </Button>
          </form>
        </section>

        <TwoStep onNote={setNote} />

        <Connections onNote={setNote} />

        <section>
          <SectionTitle>Devices</SectionTitle>
          <p className="text-ink-2 mb-2 text-sm">Lost a phone, or signed in on a shared computer? Sign out on every device, this one included.</p>
          <Button variant="secondary" onClick={everywhere} loading={busy === "everywhere"} disabled={DEMO}>
            <LogOut className="h-4 w-4" aria-hidden /> Sign out everywhere
          </Button>
        </section>

        <section>
          <SectionTitle>Delete account</SectionTitle>
          {deletion.data?.allowed ? (
            confirmDelete ? (
              <form onSubmit={remove} className="border-ready-red/40 space-y-3 rounded-xl border p-3">
                <p className="text-sm">
                  This deletes your account and everything PathToPro stores about you, at once. It can't be undone.
                </p>
                <Field label="Your password">
                  <input className={input} type="password" autoComplete="current-password" required value={deletePassword} onChange={(e) => setDeletePassword(e.target.value)} />
                </Field>
                <div className="flex flex-wrap gap-2">
                  <Button type="submit" variant="danger" loading={busy === "delete"}>
                    <Trash2 className="h-4 w-4" aria-hidden /> Delete everything
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setConfirmDelete(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <Button variant="secondary" onClick={() => setConfirmDelete(true)}>
                <Trash2 className="h-4 w-4" aria-hidden /> Delete my account
              </Button>
            )
          ) : (
            <p className="text-ink-2 text-sm">{DEMO ? "Not available in the demo." : (deletion.data?.reason ?? "…")}</p>
          )}
        </section>
      </div>
    </Shell>
  );
}
