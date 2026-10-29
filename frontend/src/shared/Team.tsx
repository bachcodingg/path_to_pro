// Team life: players say whether they can make the next sessions and matches; coaches see
// who's in and post announcements. Announcements also show on the player's Today screen.
import { Check, Megaphone, Send, Trash2, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, ApiError, DEMO } from "./api";
import { useAuth } from "./auth";
import { PageHeader } from "./PageHeader";
import { Button, Card, Chip, ErrorNote, SectionTitle, Spinner, cn, fmtDay } from "./ui";
import { useApi } from "./useApi";

interface TeamEvent {
  key: string;
  kind: "match" | "session";
  day: string;
  time: string | null;
  title: string;
  // player view
  available?: boolean | null;
  reason?: string | null;
  // staff view (`available` is then a count)
  unavailable?: { name: string; reason: string }[];
  no_answer?: number;
}
interface Events {
  team: string | null;
  events: TeamEvent[];
  reasons: Record<string, string>;
}
interface Announcement {
  id: string;
  text: string;
  author: string;
  created_at: string;
}

function when(e: TeamEvent): string {
  return fmtDay(e.day, { weekday: "short", day: "numeric", month: "short" }) + (e.time ? ` · ${e.time}` : "");
}

function ago(iso: string): string {
  const h = Math.round((Date.now() - new Date(iso).getTime()) / 3.6e6);
  return h < 1 ? "just now" : h < 24 ? `${h} h ago` : `${Math.round(h / 24)} d ago`;
}

// Today screen: the team's latest messages (nothing shown if there are none or no team)
export function AnnouncementsCard() {
  const { data } = useApi<Announcement[]>(DEMO ? null : "/api/team/announcements");
  if (!data?.length) return null;
  return (
    <Card className="border-pitch-400/60">
      <p className="text-pitch-300 mb-1 flex items-center gap-2 text-xs font-bold tracking-[0.12em] uppercase">
        <Megaphone className="h-4 w-4" aria-hidden /> From your coach
      </p>
      <ul className="space-y-2">
        {data.slice(0, 3).map((a) => (
          <li key={a.id}>
            <p className="whitespace-pre-line">{a.text}</p>
            <p className="text-ink-2 text-xs">
              {a.author} · {ago(a.created_at)}
            </p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function PlayerTeam() {
  const { data, setData, error, loading, reload } = useApi<Events>(DEMO ? null : "/api/team/events");
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  if (DEMO) return <Card className="mt-4">Availability works with the full system only, not in the browser demo.</Card>;
  if (loading && !data) return <Spinner />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;

  async function answer(e: TeamEvent, available: boolean, reason: string | null = null) {
    setBusy(e.key);
    setFailed(null);
    try {
      const out = await api<{ available: boolean; reason: string | null }>("/api/team/availability", {
        method: "PUT",
        json: { event: e.key, available, reason },
      });
      setData((d) => d && { ...d, events: d.events.map((x) => (x.key === e.key ? { ...x, ...out } : x)) });
    } catch (err) {
      setFailed(err instanceof ApiError ? err.message : "Cannot reach the server");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4 pt-2">
      <div>
        <h1 className="text-2xl font-extrabold">{data.team ?? "Team"}</h1>
        <p className="text-ink-2 text-sm">Can you make it? Your coach sees your answer. Not feeling well? Say so in your morning check-in instead.</p>
      </div>
      {failed && (
        <p role="alert" className="text-recover text-sm font-medium">
          {failed}
        </p>
      )}
      {data.events.length === 0 && <Card className="text-ink-2">No team sessions or matches in the next three weeks.</Card>}
      <ul className="space-y-2">
        {data.events.map((e) => (
          <li key={e.key}>
            <Card className={cn("space-y-2", e.kind === "match" && "border-pitch-400/60")}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-bold">{e.title}</p>
                  <p className="text-ink-2 text-sm">{when(e)}</p>
                </div>
                {e.available === true && <Chip tone="green">I'm in</Chip>}
                {e.available === false && <Chip tone="amber">Can't make it</Chip>}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant={e.available === true ? "primary" : "secondary"} disabled={busy === e.key} onClick={() => answer(e, true)}>
                  <Check className="h-4 w-4" aria-hidden /> I'm in
                </Button>
                <Button size="sm" variant={e.available === false ? "primary" : "secondary"} disabled={busy === e.key} onClick={() => answer(e, false, e.reason ?? "other")}>
                  <X className="h-4 w-4" aria-hidden /> Can't make it
                </Button>
                {e.available === false && (
                  <select
                    aria-label={`Why you can't make ${e.title}`}
                    className="bg-surface-2 border-line h-11 rounded-xl border px-2 text-sm"
                    value={e.reason ?? "other"}
                    onChange={(ev) => answer(e, false, ev.target.value)}
                  >
                    {Object.entries(data.reasons).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CoachTeam() {
  const { user } = useAuth();
  const events = useApi<Events>("/api/team/events");
  const news = useApi<Announcement[]>("/api/team/announcements");
  const [text, setText] = useState("");
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const coach = user?.role === "coach";

  async function post(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    try {
      await api("/api/team/announcements", { method: "POST", json: { text } });
      setText("");
      setNote({ ok: true, text: "Posted. Players see it on their Today screen (and as a notification if they turned those on)." });
      await news.reload();
    } catch (err) {
      setNote({ ok: false, text: err instanceof ApiError ? err.message : "Cannot reach the server" });
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    await api(`/api/team/announcements/${id}`, { method: "DELETE" }).catch(() => undefined);
    await news.reload();
  }

  if (events.loading && !events.data) return <Spinner />;
  if (events.error || !events.data) return <ErrorNote message={events.error ?? "No data"} onRetry={events.reload} />;
  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow={events.data.team ?? "Team"}
        title="Availability"
        subtitle="Who can make the next three weeks of sessions and matches, and messages to the whole team."
      />
      {note && (
        <p role={note.ok ? "status" : "alert"} className={cn("text-sm font-semibold", note.ok ? "text-ready" : "text-recover")}>
          {note.text}
        </p>
      )}
      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <section>
          <SectionTitle>Next three weeks</SectionTitle>
          <Card className="overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead className="text-ink-2 text-left text-xs uppercase">
                <tr>
                  <th className="px-4 py-2">Event</th>
                  <th className="px-4 py-2">In</th>
                  <th className="px-4 py-2">Out</th>
                  <th className="px-4 py-2">No answer</th>
                </tr>
              </thead>
              <tbody>
                {events.data.events.map((e) => (
                  <tr key={e.key} className="border-line border-t align-top">
                    <td className="px-4 py-2">
                      <p className={cn("font-semibold", e.kind === "match" && "text-pitch-600 dark:text-pitch-300")}>{e.title}</p>
                      <p className="text-ink-2 text-xs">{when(e)}</p>
                    </td>
                    <td className="num px-4 py-2 font-bold">{Number(e.available ?? 0)}</td>
                    <td className="px-4 py-2">
                      {e.unavailable?.length ? (
                        <ul className="space-y-0.5">
                          {e.unavailable.map((u) => (
                            <li key={u.name}>
                              {u.name} <span className="text-ink-2 text-xs">({u.reason || "no reason"})</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-ink-2">-</span>
                      )}
                    </td>
                    <td className="num text-ink-2 px-4 py-2">{e.no_answer}</td>
                  </tr>
                ))}
                {events.data.events.length === 0 && (
                  <tr>
                    <td colSpan={4} className="text-ink-2 px-4 py-6 text-center">
                      Nothing planned yet: set the training week and fixtures on the Schedule page.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </Card>
          <p className="text-ink-2 mt-2 text-xs">Availability is the player's answer; illness and injuries come through the check-in to the physio, not here.</p>
        </section>
        <section className="space-y-4">
          {coach && (
            <Card>
              <SectionTitle>Message the team</SectionTitle>
              <form onSubmit={post} className="space-y-3">
                <textarea
                  aria-label="Message"
                  className="bg-surface-2 border-line text-ink min-h-28 w-full rounded-xl border p-3 text-[15px]"
                  required
                  minLength={2}
                  maxLength={1000}
                  placeholder="Kick-off moved to 14:00. Bring both kits."
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
                <p className="text-ink-2 text-xs">Goes to every player in the team. Don't write about anyone's health here.</p>
                <Button type="submit" className="w-full" loading={busy}>
                  <Send className="h-4 w-4" aria-hidden /> Post
                </Button>
              </form>
            </Card>
          )}
          <div>
            <SectionTitle>Recent messages</SectionTitle>
            {news.data?.length === 0 && <Card className="text-ink-2 text-sm">No messages yet.</Card>}
            <ul className="space-y-2">
              {news.data?.map((a) => (
                <li key={a.id}>
                  <Card className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm whitespace-pre-line">{a.text}</p>
                      <p className="text-ink-2 text-xs">
                        {a.author} · {ago(a.created_at)}
                      </p>
                    </div>
                    {coach && (
                      <Button size="sm" variant="ghost" onClick={() => remove(a.id)} aria-label="Delete message">
                        <Trash2 className="h-4 w-4" aria-hidden />
                      </Button>
                    )}
                  </Card>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </div>
  );
}
