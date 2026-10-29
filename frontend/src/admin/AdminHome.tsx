// Club administrator: teams, staff invitations, academy players (one by one or from a CSV).
import { FileUp, LogOut, MailPlus, Plus, Send, Settings, Trash2, UserX } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, DEMO, getToken } from "../shared/api";
import { useAuth } from "../shared/auth";
import { LegalLinks } from "../legal/Legal";
import { PageHeader, Tabs } from "../shared/PageHeader";
import { SkipLink } from "../shared/SkipLink";
import { Button, Card, Chip, ErrorNote, PageSkeleton, SectionTitle, cn } from "../shared/ui";
import { useApi } from "../shared/useApi";

interface Overview {
  club: string;
  email_mode: "smtp" | "log" | "memory";
  squads: { id: string; name: string; age_group: string; competition: string | null; players: number; has_training_week: boolean }[];
  staff: { id: string; account_id: string | null; name: string; email: string; role: "coach" | "physio"; squad_id: string | null; invite_pending: boolean; active: boolean; mfa: boolean }[];
  players: { id: string; account_id: string | null; name: string; email: string | null; squad_id: string; position: string; age: number; invite_pending: boolean; needs_parent: boolean }[];
}

interface ImportResult {
  dry_run: boolean;
  saved: boolean;
  valid: number;
  errors: { line: number; error: string }[];
}

const POSITIONS = [
  ["goalkeeper", "Goalkeeper"],
  ["centre_back", "Centre-back"],
  ["full_back", "Full-back"],
  ["midfielder", "Midfielder"],
  ["winger", "Winger"],
  ["striker", "Striker"],
] as const;
const field = "bg-surface-2 border-line text-ink mt-1 h-11 w-full rounded-xl border px-3 text-[15px]";
type Tab = "teams" | "staff" | "players" | "import";

function message(err: unknown): string {
  return err instanceof ApiError ? err.message : "Cannot reach the server";
}

function F({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <label className={cn("block", className)}>
      <span className="text-ink-2 text-xs font-semibold">{label}</span>
      {children}
    </label>
  );
}

export function AdminHome() {
  const { user, logout } = useAuth();
  const ov = useApi<Overview>(DEMO ? null : "/api/admin/overview");
  const [tab, setTab] = useState<Tab>("teams");
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);

  async function act(fn: () => Promise<unknown>, ok: string) {
    setNote(null);
    try {
      await fn();
      setNote({ ok: true, text: ok });
      await ov.reload();
      return true;
    } catch (err) {
      setNote({ ok: false, text: message(err) });
      return false;
    }
  }

  const squads = ov.data?.squads ?? [];
  const teamName = (id: string | null) => squads.find((s) => s.id === id)?.name ?? "No team";

  return (
    <div className="bg-surface-2 text-ink min-h-full">
      <SkipLink />
      <div className="bg-pitch-950 flex items-center justify-between px-4 py-2 text-sm text-white md:px-6">
        <span className="flex items-center gap-2">
          <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="h-7 w-7" />
          <span className="font-display text-lg font-extrabold tracking-wide uppercase">PathToPro</span>
          <span className="text-pitch-300 text-xs font-semibold tracking-[0.12em] uppercase">Club admin</span>
        </span>
        <span className="flex items-center gap-3">
          <Link to="/account" className="tap text-pitch-200 flex items-center gap-1 hover:text-white">
            <Settings className="h-4 w-4" aria-hidden /> {user?.email}
          </Link>
          <button onClick={logout} className="tap text-pitch-200 hover:text-white" aria-label="Sign out" title="Sign out">
            <LogOut className="h-4 w-4" aria-hidden />
          </button>
        </span>
      </div>
      <main id="main" tabIndex={-1} className="mx-auto max-w-6xl p-4 outline-none md:p-6">
        <PageHeader
          eyebrow="Club setup"
          title={ov.data?.club ?? "Your club"}
          subtitle="Teams, staff and players. Everyone you add gets an email to choose their own password; parents of players under 16 get an invitation to give consent."
          bottom={
            <Tabs<Tab>
              label="Club setup"
              value={tab}
              onChange={setTab}
              items={[
                ["teams", `Teams (${squads.length})`],
                ["staff", `Staff (${ov.data?.staff.length ?? 0})`],
                ["players", `Players (${ov.data?.players.length ?? 0})`],
                ["import", "Import players"],
              ]}
            />
          }
        />
        {DEMO && <Card>The club admin works with the full system only, not in the browser demo.</Card>}
        {ov.data?.email_mode === "log" && (
          <Card className="border-caution mb-4 text-sm">
            <strong>Emails are not being sent.</strong> The server has no mail server configured (PATHTOPRO_SMTP_HOST), so invitations
            only appear in the server log. Set it up before inviting real people.
          </Card>
        )}
        {note && (
          <p role={note.ok ? "status" : "alert"} className={cn("mb-4 text-sm font-semibold", note.ok ? "text-ready" : "text-recover")}>
            {note.text}
          </p>
        )}
        {ov.loading && !ov.data && !DEMO && <PageSkeleton />}
        {ov.error && <ErrorNote message={ov.error} onRetry={ov.reload} />}
        {ov.data && tab === "teams" && <Teams ov={ov.data} act={act} />}
        {ov.data && tab === "staff" && <Staff ov={ov.data} act={act} />}
        {ov.data && tab === "players" && <Players ov={ov.data} act={act} teamName={teamName} />}
        {ov.data && tab === "import" && <Import ov={ov.data} onDone={ov.reload} />}
        <LegalLinks className="text-ink-2 mt-10" />
      </main>
    </div>
  );
}

type Act = (fn: () => Promise<unknown>, ok: string) => Promise<boolean>;

function Teams({ ov, act }: { ov: Overview; act: Act }) {
  const [name, setName] = useState("");
  const [ageGroup, setAgeGroup] = useState("U15");
  const [club, setClub] = useState("");
  const first = ov.squads.length === 0;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (await act(() => api("/api/admin/squads", { method: "POST", json: { name, age_group: ageGroup, club: club || null } }), `${name} added`)) setName("");
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <section>
        <SectionTitle>Teams</SectionTitle>
        {first && <Card className="text-ink-2">No teams yet. Start with one on the right; then invite its coach and physio.</Card>}
        <ul className="grid gap-2 sm:grid-cols-2">
          {ov.squads.map((s) => (
            <li key={s.id}>
              <Card>
                <p className="font-display text-xl font-bold uppercase">{s.name}</p>
                <p className="text-ink-2 text-sm">
                  {s.age_group} · {s.players} players · {ov.staff.filter((m) => m.squad_id === s.id).length} staff
                </p>
                <div className="mt-2">
                  {s.has_training_week ? <Chip tone="green">Training week set</Chip> : <Chip tone="amber">Coach to set the training week</Chip>}
                </div>
              </Card>
            </li>
          ))}
        </ul>
      </section>
      <Card>
        <SectionTitle>Add a team</SectionTitle>
        <form onSubmit={submit} className="space-y-3">
          <F label="Name">
            <input className={field} required minLength={2} maxLength={100} placeholder="U15 Blue" value={name} onChange={(e) => setName(e.target.value)} />
          </F>
          <F label="Age group">
            <select className={field} value={ageGroup} onChange={(e) => setAgeGroup(e.target.value)}>
              {["U13", "U14", "U15", "U16", "U17", "U18", "U19", "SEN"].map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </F>
          {first && (
            <F label="Club name (shown in emails)">
              <input className={field} maxLength={100} value={club} onChange={(e) => setClub(e.target.value)} />
            </F>
          )}
          <Button type="submit" className="w-full" disabled={DEMO}>
            <Plus className="h-4 w-4" aria-hidden /> Add team
          </Button>
        </form>
      </Card>
    </div>
  );
}

function Staff({ ov, act }: { ov: Overview; act: Act }) {
  const [f, setF] = useState({ name: "", email: "", role: "coach", squad_id: ov.squads[0]?.id ?? "" });

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (await act(() => api("/api/admin/staff", { method: "POST", json: f }), `Invitation sent to ${f.email}`)) setF({ ...f, name: "", email: "" });
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <section>
        <SectionTitle>Staff</SectionTitle>
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="text-ink-2 text-left text-xs uppercase">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Role</th>
                <th className="px-4 py-2">Team</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {ov.staff.map((s) => (
                <tr key={s.id} className="border-line border-t">
                  <td className="px-4 py-2">
                    <p className="font-semibold">{s.name}</p>
                    <p className="text-ink-2 text-xs">{s.email}</p>
                  </td>
                  <td className="px-4 py-2 capitalize">{s.role}</td>
                  <td className="px-4 py-2">
                    <select
                      aria-label={`Team of ${s.name}`}
                      className="bg-surface-2 border-line h-9 rounded-lg border px-2"
                      value={s.squad_id ?? ""}
                      onChange={(e) => act(() => api(`/api/admin/staff/${s.id}`, { method: "PATCH", json: { squad_id: e.target.value } }), `${s.name} moved`)}
                    >
                      {!s.squad_id && <option value="">No team</option>}
                      {ov.squads.map((q) => (
                        <option key={q.id} value={q.id}>
                          {q.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-2">
                    {!s.active ? <Chip>Switched off</Chip> : s.invite_pending ? <Chip tone="amber">Invited</Chip> : <Chip tone="green">Active</Chip>}
                    {s.mfa && <span className="text-ink-2 ml-1 text-xs">2-step</span>}
                  </td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">
                    {s.invite_pending && s.active && s.account_id && (
                      <Button size="sm" variant="ghost" onClick={() => act(() => api(`/api/admin/accounts/${s.account_id}/resend-invite`, { method: "POST" }), `Invitation sent again to ${s.email}`)}>
                        <Send className="h-4 w-4" aria-hidden /> Resend
                      </Button>
                    )}
                    {s.mfa && (
                      <Button size="sm" variant="ghost" onClick={() => act(() => api(`/api/admin/staff/${s.id}`, { method: "PATCH", json: { reset_mfa: true } }), `Two-step sign-in reset for ${s.name}: they can sign in with their password and set it up again`)}>
                        Reset 2-step
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => act(() => api(`/api/admin/staff/${s.id}`, { method: "PATCH", json: { active: !s.active } }), s.active ? `${s.name} switched off and signed out` : `${s.name} switched on`)}
                    >
                      <UserX className="h-4 w-4" aria-hidden /> {s.active ? "Switch off" : "Switch on"}
                    </Button>
                  </td>
                </tr>
              ))}
              {ov.staff.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-ink-2 px-4 py-6 text-center">
                    No staff yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
        <p className="text-ink-2 mt-2 text-xs">Switching someone off signs them out at once; their approvals and notes stay on record.</p>
      </section>
      <Card>
        <SectionTitle>Invite staff</SectionTitle>
        {ov.squads.length === 0 ? (
          <p className="text-ink-2 text-sm">Add a team first.</p>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <F label="Name">
              <input className={field} required minLength={2} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
            </F>
            <F label="Email">
              <input className={field} type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
            </F>
            <div className="grid grid-cols-2 gap-3">
              <F label="Role">
                <select className={field} value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>
                  <option value="coach">Coach</option>
                  <option value="physio">Physio</option>
                </select>
              </F>
              <F label="Team">
                <select className={field} value={f.squad_id} onChange={(e) => setF({ ...f, squad_id: e.target.value })}>
                  {ov.squads.map((q) => (
                    <option key={q.id} value={q.id}>
                      {q.name}
                    </option>
                  ))}
                </select>
              </F>
            </div>
            <p className="text-ink-2 text-xs">The team's physio receives its red check-ins and pain reports; with no physio, the coach does.</p>
            <Button type="submit" className="w-full" disabled={DEMO}>
              <MailPlus className="h-4 w-4" aria-hidden /> Send invitation
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}

function Players({ ov, act, teamName }: { ov: Overview; act: Act; teamName: (id: string | null) => string }) {
  const empty = { name: "", birth_date: "", sex: "male", position: "midfielder", email: "", guardian_email: "" };
  const [f, setF] = useState(empty);
  const [squad, setSquad] = useState(ov.squads[0]?.id ?? "");
  const [filter, setFilter] = useState("all");
  const [confirm, setConfirm] = useState<string | null>(null);
  const age = f.birth_date ? (Date.now() - new Date(f.birth_date + "T12:00:00").getTime()) / (365.25 * 864e5) : null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    const body = { ...f, email: f.email || null, guardian_email: f.guardian_email || null };
    if (await act(() => api(`/api/admin/squads/${squad}/players`, { method: "POST", json: body }), `${f.name} added`)) setF(empty);
  }

  const shown = ov.players.filter((p) => filter === "all" || p.squad_id === filter);
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <section>
        <SectionTitle
          action={
            <select aria-label="Team" className="bg-surface border-line h-9 rounded-lg border px-2 text-sm" value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">All teams</option>
              {ov.squads.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.name}
                </option>
              ))}
            </select>
          }
        >
          Players
        </SectionTitle>
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="text-ink-2 text-left text-xs uppercase">
              <tr>
                <th className="px-4 py-2">Player</th>
                <th className="px-4 py-2">Team</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {shown.map((p) => (
                <tr key={p.id} className="border-line border-t">
                  <td className="px-4 py-2">
                    <p className="font-semibold">{p.name}</p>
                    <p className="text-ink-2 text-xs">
                      {p.age} y · {p.position.replace("_", " ")}
                      {p.email && ` · ${p.email}`}
                    </p>
                  </td>
                  <td className="px-4 py-2">{teamName(p.squad_id)}</td>
                  <td className="space-x-1 px-4 py-2">
                    {!p.account_id ? <Chip>No login</Chip> : p.invite_pending ? <Chip tone="amber">Invited</Chip> : <Chip tone="green">Active</Chip>}
                    {p.needs_parent && <Chip tone="red">Waiting for parent</Chip>}
                  </td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">
                    {p.invite_pending && p.account_id && (
                      <Button size="sm" variant="ghost" onClick={() => act(() => api(`/api/admin/accounts/${p.account_id}/resend-invite`, { method: "POST" }), `Invitation sent again to ${p.email}`)}>
                        <Send className="h-4 w-4" aria-hidden /> Resend
                      </Button>
                    )}
                    {confirm === p.id ? (
                      <Button size="sm" variant="danger" onClick={() => act(() => api(`/api/admin/players/${p.id}`, { method: "DELETE" }), `${p.name} and all their data deleted`)}>
                        Delete all data?
                      </Button>
                    ) : (
                      <Button size="sm" variant="ghost" onClick={() => setConfirm(p.id)} aria-label={`Remove ${p.name}`}>
                        <Trash2 className="h-4 w-4" aria-hidden />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
              {shown.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-ink-2 px-4 py-6 text-center">
                    No players yet. Add them one by one or import a list.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
        <p className="text-ink-2 mt-2 text-xs">
          “Waiting for parent”: under 16, no check-ins, sleep, growth or test results are stored until a parent signs up and agrees.
        </p>
      </section>
      <Card>
        <SectionTitle>Add a player</SectionTitle>
        {ov.squads.length === 0 ? (
          <p className="text-ink-2 text-sm">Add a team first.</p>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <F label="Team">
              <select className={field} value={squad} onChange={(e) => setSquad(e.target.value)}>
                {ov.squads.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.name}
                  </option>
                ))}
              </select>
            </F>
            <F label="Name">
              <input className={field} required minLength={2} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
            </F>
            <div className="grid grid-cols-2 gap-3">
              <F label="Date of birth">
                <input className={field} type="date" required value={f.birth_date} onChange={(e) => setF({ ...f, birth_date: e.target.value })} />
              </F>
              <F label="Sex">
                <select className={field} value={f.sex} onChange={(e) => setF({ ...f, sex: e.target.value })}>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>
              </F>
            </div>
            <F label="Position">
              <select className={field} value={f.position} onChange={(e) => setF({ ...f, position: e.target.value })}>
                {POSITIONS.map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </F>
            <F label="Player's email (for their login; optional)">
              <input className={field} type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
            </F>
            <F label={age != null && age < 16 ? "Parent's email (needed under 16)" : "Parent's email (optional)"}>
              <input className={field} type="email" required={age != null && age < 16} value={f.guardian_email} onChange={(e) => setF({ ...f, guardian_email: e.target.value })} />
            </F>
            <Button type="submit" className="w-full" disabled={DEMO}>
              <Plus className="h-4 w-4" aria-hidden /> Add player
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}

function Import({ ov, onDone }: { ov: Overview; onDone: () => Promise<void> }) {
  const [squad, setSquad] = useState(ov.squads[0]?.id ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // multipart upload: the JSON helper doesn't fit, so fetch directly with the same token
  async function send(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    form.append("dry_run", String(dryRun));
    try {
      const res = await fetch(`/api/admin/squads/${squad}/players/import`, {
        method: "POST",
        body: form,
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      const data = await res.json();
      if (!res.ok) throw new ApiError(res.status, typeof data.detail === "string" ? data.detail : "The file could not be read");
      setResult(data);
      if (data.saved) await onDone();
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <Card>
        <SectionTitle>Import a list of players</SectionTitle>
        <p className="text-ink-2 mb-3 text-sm">
          A CSV file (from Excel or Google Sheets: “Save as CSV”) with a header row. Columns: <code>name</code>, <code>birth_date</code>{" "}
          (YYYY-MM-DD), and optionally <code>sex</code>, <code>position</code>, <code>email</code>, <code>guardian_email</code>. Players
          under 16 need a <code>guardian_email</code>. First check the file; nothing is saved until every row is valid.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <F label="Team">
            <select className={field} value={squad} onChange={(e) => setSquad(e.target.value)}>
              {ov.squads.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.name}
                </option>
              ))}
            </select>
          </F>
          <F label="CSV file">
            <input
              className={cn(field, "pt-2")}
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setResult(null);
              }}
            />
          </F>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => send(true)} loading={busy && !result} disabled={!file || !squad || DEMO}>
            <FileUp className="h-4 w-4" aria-hidden /> Check the file
          </Button>
          <Button onClick={() => send(false)} loading={busy && !!result} disabled={!result || result.errors.length > 0 || result.saved || DEMO}>
            Import {result && !result.errors.length ? `${result.valid} players` : ""} and send invitations
          </Button>
        </div>
        {error && (
          <p role="alert" className="text-recover mt-3 text-sm font-medium">
            {error}
          </p>
        )}
        {result && (
          <div className="mt-4 text-sm" role="status">
            {result.saved ? (
              <p className="text-ready font-semibold">{result.valid} players imported. Invitations are on their way.</p>
            ) : result.errors.length ? (
              <>
                <p className="text-recover font-semibold">
                  {result.errors.length} row{result.errors.length > 1 ? "s" : ""} to fix ({result.valid} fine). Nothing was saved.
                </p>
                <ul className="mt-2 space-y-1">
                  {result.errors.map((e) => (
                    <li key={e.line}>
                      Line {e.line}: {e.error}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="font-semibold">All {result.valid} rows are fine. Import them to save and send the invitations.</p>
            )}
          </div>
        )}
      </Card>
      <Card>
        <SectionTitle>Example</SectionTitle>
        <pre className="bg-surface-2 overflow-x-auto rounded-lg p-3 text-xs">
          {`name,birth_date,position,email,guardian_email
Mia Keller,2011-03-14,winger,mia@example.com,keller@example.com
Jonas Ng,2009-11-02,goalkeeper,jonas@example.com,`}
        </pre>
      </Card>
    </div>
  );
}
