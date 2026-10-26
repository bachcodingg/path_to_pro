// Demo mode (VITE_DEMO=1): the API answered in the browser, so the app runs as a static
// website. Reads come from a snapshot recorded from the real API on the synthetic season
// (backend/scripts/demo_snapshot.py); actions update in-memory state the way the backend
// would, so the whole demo script works. State is kept in this browser's localStorage
// (so switching accounts keeps your changes) until "Reset demo"; nothing leaves the browser.
import { ApiError } from "./api";

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

interface ReadinessMeta {
  weights: Record<"hrv" | "hooper" | "sleep", number>;
  green_min: number;
  amber_min: number;
  sleep_target_hours: number;
  hysteresis_up: number;
  hysteresis_down: number;
}

interface Snapshot {
  meta: { today: string; story: Record<string, string>; password: string; generated?: string; readiness?: ReadinessMeta };
  users: Record<string, { me: Json; responses: Record<string, Json> }>;
  staff: Record<string, Json>;
  pro?: Record<string, Json>; // the competitions list; each competition's data is a file of its own
}

let state: Snapshot | null = null;
let loading: Promise<Snapshot> | null = null;
const STATE_KEY = "pathtopro.demo.state";

async function load(): Promise<Snapshot> {
  if (state) return state;
  loading ??= fetch(`${import.meta.env.BASE_URL}demo/snapshot.json`).then(async (r) => {
    if (!r.ok) throw new ApiError(503, "Demo data could not be loaded");
    const fresh = (await r.json()) as Snapshot;
    let saved: Snapshot | null = null;
    try {
      saved = JSON.parse(localStorage.getItem(STATE_KEY) ?? "null");
    } catch {
      saved = null;
    }
    state = saved && saved.meta?.generated === fresh.meta.generated ? saved : fresh;
    return state;
  });
  return loading;
}

// Pro leagues: one recorded file per competition (several MB each), fetched the first time
// that competition is opened and kept out of the saved demo state
const proFiles = new Map<string, Promise<Record<string, Json>>>();
function proFile(comp: string): Promise<Record<string, Json>> {
  if (!proFiles.has(comp))
    proFiles.set(
      comp,
      fetch(`${import.meta.env.BASE_URL}demo/pro/${encodeURIComponent(comp)}.json`).then((r) => {
        if (!r.ok) proFiles.delete(comp);
        return r.ok ? r.json() : {};
      }),
    );
  return proFiles.get(comp)!;
}

function persist(): void {
  try {
    localStorage.setItem(STATE_KEY, JSON.stringify(state));
  } catch {
    /* storage full or blocked: the demo still works for this page */
  }
}

export function resetDemo(): void {
  try {
    localStorage.removeItem(STATE_KEY);
    localStorage.removeItem("pathtopro.token");
  } catch {
    /* ignore */
  }
  window.location.href = import.meta.env.BASE_URL;
}

const TOKEN_PREFIX = "demo:";
function currentEmail(): string | null {
  try {
    const t = localStorage.getItem("pathtopro.token");
    return t?.startsWith(TOKEN_PREFIX) ? t.slice(TOKEN_PREFIX.length) : null;
  } catch {
    return null;
  }
}

function fail(status: number, msg: string): never {
  throw new ApiError(status, msg);
}

// --------------------------------------------------------------------------- readiness (mirrors analytics/readiness.py)

// Weights, bands and buffer come from the snapshot (exported from config/readiness.yaml by
// demo_snapshot.py), so the demo can't drift from the server. Fallback = the defaults.
const DEFAULT_READINESS: ReadinessMeta = {
  weights: { hrv: 0.4, hooper: 0.35, sleep: 0.25 },
  green_min: 70,
  amber_min: 50,
  sleep_target_hours: 9,
  hysteresis_up: 8,
  hysteresis_down: 0,
};
const RANK: Record<string, number> = { red: 0, amber: 1, green: 2 };
type BandName = "green" | "amber" | "red";

function rawBand(score: number, c: ReadinessMeta): BandName {
  return score >= c.green_min ? "green" : score >= c.amber_min ? "amber" : "red";
}
function bandWithBuffer(score: number, previous: string | null, c: ReadinessMeta): BandName {
  if (!previous) return rawBand(score, c);
  const worse = rawBand(score + c.hysteresis_down, c);
  if (RANK[worse] < RANK[previous]) return worse; // a worse colour applies at once
  const better = rawBand(score - c.hysteresis_up, c);
  return RANK[better] > RANK[previous] ? better : (previous as BandName);
}

/** Check-in score in the browser. The server would use today's HRV; the demo reuses the
 *  last HRV component it recorded (an estimate), or leaves HRV out and rescales. */
function checkinReadiness(body: Json, previous: string | null, lastHrv: number | undefined, c: ReadinessMeta) {
  const h = body.sleep_quality + body.fatigue + body.stress + body.soreness;
  const parts: Record<string, number> = {
    hooper: ((28 - h) / 24) * 100,
    sleep: Math.min((body.sleep_hours ?? 8) / c.sleep_target_hours, 1) * 100,
  };
  if (lastHrv != null) parts.hrv = lastHrv;
  const total = Object.keys(parts).reduce((s, k) => s + c.weights[k as keyof ReadinessMeta["weights"]], 0);
  const score = Object.entries(parts).reduce((s, [k, v]) => s + c.weights[k as keyof ReadinessMeta["weights"]] * v, 0) / total;
  return {
    score: Math.round(score * 10) / 10,
    band: bandWithBuffer(score, previous, c),
    components: Object.fromEntries(Object.entries(parts).map(([k, v]) => [k, Math.round(v * 100) / 100])),
  };
}

// --------------------------------------------------------------------------- self-guided pathway (mirrors pathway/levels.py)

function meets(row: Json, value: number | null, target: number | null): boolean {
  if (value == null || target == null) return false;
  return row.lower_is_better ? value <= target : value >= target;
}

/** Recompute the checklist after a new test result; level up one step when complete. */
function reassess(pw: Json): boolean {
  const a = pw.assessment;
  const next = a.next && pw.ladder.find((l: Json) => l.level === a.next.level);
  for (const r of a.tests) {
    r.target = (next ?? pw.ladder.find((l: Json) => l.level === a.level)).benchmarks[r.test];
    r.met = meets(r, r.value, r.target);
    r.gap = r.value == null ? 1 : r.met ? 0 : Math.abs(r.value - r.target) / Math.abs(r.target);
  }
  const met = a.tests.filter((r: Json) => r.met).length;
  if (a.next) a.next.tests_met = met;
  a.focus = [...a.tests].filter((r: Json) => !r.met).sort((x: Json, y: Json) => y.gap - x.gap).slice(0, 2).map((r: Json) => r.test);
  a.ready_to_level_up = !!a.next && met >= a.next.tests_needed && a.consistency.ok;
  if (!a.ready_to_level_up) return false;
  const lvl = pw.ladder.find((l: Json) => l.level === a.next.level);
  Object.assign(a, { level: lvl.level, name: lvl.name, who: lvl.who, targets: lvl.targets });
  pw.profile.level = lvl.level;
  const after = pw.ladder.find((l: Json) => l.level === lvl.level + 1);
  a.next = after ? { level: after.level, name: after.name, tests_needed: a.next.tests_needed, tests_met: 0 } : null;
  reassess(pw);
  return true;
}

function syncTodayPathway(user: { responses: Record<string, Json> }) {
  const pw = user.responses["/api/me/pathway"];
  const today = user.responses["/api/me/today"];
  if (!pw || !today?.pathway) return;
  const a = pw.assessment;
  today.pathway = {
    level: a.level,
    name: a.name,
    next: a.next,
    consistency: a.consistency,
    focus: a.focus.map((f: string) => a.tests.find((t: Json) => t.test === f)?.label),
  };
}

// --------------------------------------------------------------------------- helpers

const KIND_TITLE: Record<string, string> = {
  session_swap: "Your sessions were changed",
  load_cut: "Your week was made lighter",
  load_increase: "Your week got a bit harder",
  intensity_change: "Session intensity adjusted",
  match_minutes: "Your match minutes are limited",
  new_goal: "New development goal",
};

function userByPlayerId(s: Snapshot, playerId: string) {
  return Object.values(s.users).find((u) => u.me.player_id === playerId);
}

function query(path: string): [string, URLSearchParams] {
  const [p, q = ""] = path.split("?");
  return [p, new URLSearchParams(q)];
}

function csv(rows: Json[]): string {
  const esc = (v: unknown) => `"${String(v ?? "").replaceAll('"', '""')}"`;
  const head = "time,agent,trigger,player,decision,fallback,commentary";
  return [head, ...rows.map((r) => [r.at, r.agent, r.trigger, r.player?.name, r.decision, r.fallback, r.text].map(esc).join(","))].join("\n");
}

// --------------------------------------------------------------------------- router

export async function demoHandle(path: string, method = "GET", body?: Json): Promise<Json> {
  const out = await route(path, method, body);
  if (method !== "GET" && !path.startsWith("/api/auth/")) persist();
  // A fresh copy, like a real response: the UI never shares objects with the demo state.
  return out === undefined ? out : structuredClone(out);
}

async function route(path: string, method: string, body?: Json): Promise<Json> {
  const s = await load();
  const [p, q] = query(path);
  if (p === "/api/health") return { ok: true, today: s.meta.today, demo: true };

  if (p === "/api/auth/login" && method === "POST") {
    const email = String(body?.email ?? "").trim().toLowerCase();
    const user = s.users[email];
    if (!user || body?.password !== s.meta.password) fail(401, "Wrong email or password");
    return { token: TOKEN_PREFIX + email, user: user.me };
  }
  if (p.startsWith("/api/auth/register")) fail(403, "Sign-up needs the live server: this demo runs offline in your browser");

  const email = currentEmail();
  const user = email ? s.users[email] : undefined;
  if (!user) fail(401, "Not signed in");
  const role: string = user.me.role;
  if (p === "/api/auth/me") return user.me;

  // ---- pro leagues: public match data, the same for every account
  if (p.startsWith("/api/pro/")) {
    if (method !== "GET") fail(405, "Read only");
    if (p === "/api/pro/competitions") return s.pro?.[p] ?? fail(404, "Not available in the demo");
    const rec = await proFile(p.split("/")[3]);
    return rec[p] ?? fail(404, "Not in the dataset");
  }

  // ---- player
  if (p.startsWith("/api/me/")) {
    if (role !== "player") fail(403, "Not allowed for your role");
    const r = user.responses;
    if (method === "GET") {
      if (p === "/api/me/devices")
        return {
          ingest_url: "https://<your-server>/api/ingest/apple-health",
          tokens: [],
          consent: { hrv: true, sleep: true, wellness: true },
          latest: { hrv_day: null, sleep_night: null, sleep_hours: null },
          window_days: 60,
        };
      if (p === "/api/me/week" || p === "/api/me/gym") {
        const off = Math.max(-1, Math.min(1, Number(q.get("offset") ?? 0)));
        return r[`${p}?offset=${off}`] ?? fail(404, "Not available in the demo");
      }
      return r[p] ?? fail(404, "Not available in the demo");
    }
    const today = r["/api/me/today"];
    const pw = r["/api/me/pathway"];
    if (p === "/api/me/pathway/tests" && pw) {
      const row = pw.assessment.tests.find((t: Json) => t.test === body.test) ?? fail(422, "Unknown test");
      const value = Number(body.value);
      if (!(value >= 0)) fail(422, "Enter a valid result");
      const better = row.value == null || (row.lower_is_better ? value < row.value : value > row.value);
      if (better) row.value = value;
      pw.history.push({ test: body.test, date: s.meta.today, value });
      const levelled = reassess(pw);
      syncTodayPathway(user);
      return { ...pw, levelled_up: levelled };
    }
    if (p === "/api/me/pathway/profile" && pw) {
      for (const k of ["goal", "equipment", "team_days", "position"]) if (body[k] != null) pw.profile[k] = body[k];
      if (body.match_day != null) pw.profile.match_day = body.match_day < 0 ? null : body.match_day;
      if (body.goal) pw.profile.goal_label = pw.goals[body.goal];
      return pw;
    }
    if (p === "/api/me/log" && pw) {
      today.logged = [...(today.logged ?? []), { minutes: body.minutes, rpe: body.rpe, load: body.minutes * body.rpe }];
      const c = pw.assessment.consistency;
      c.logged += 1;
      c.ok = c.logged >= c.needed;
      const levelled = reassess(pw);
      syncTodayPathway(user);
      return { today, levelled_up: levelled };
    }
    if (p === "/api/me/position") fail(403, "Changing position needs the live server");
    if (p.startsWith("/api/me/devices") || p === "/api/me/health/import") fail(403, "Connecting a watch needs the live server");
    const career = r["/api/me/career"];
    const diary = p.match(/^\/api\/me\/matches\/([^/]+)\/diary$/);
    if (diary && career) {
      if (!(body.self_rating >= 1 && body.self_rating <= 10)) fail(422, "Rate yourself from 1 to 10");
      const recent = career.recent.find((a: Json) => a.match_id === diary[1]);
      if (recent) recent.self_rating = body.self_rating;
      career.diary_due = career.diary_due.filter((d: Json) => d.match_id !== diary[1]);
      if (today) today.diary_due = career.diary_due;
      return career;
    }
    const season = p.match(/^\/api\/me\/career\/seasons\/([^/]+)$/);
    if (season && method === "DELETE" && career) {
      career.past = career.past.filter((x: Json) => x.id !== season[1]);
      return career;
    }
    if (p === "/api/me/career/seasons" && career) {
      const comp = career.competitions.find((c: Json) => c.id === body.competition) ?? fail(422, "Unknown competition");
      career.past.push({
        ...body,
        id: `demo-${Date.now()}`,
        competition_label: comp.label,
        level: comp.level,
        avg_rating: null,
        rating_band: null,
        exposure: Math.round(((body.minutes * comp.level) / 100 / 90) * 10) / 10,
      });
      career.past.sort((a: Json, b: Json) => a.season.localeCompare(b.season));
      return career;
    }
    if (p === "/api/me/checkin") {
      const prev = today.readiness?.band ?? null;
      const { score, band, components } = checkinReadiness(
        body,
        prev,
        today.readiness?.components?.hrv,
        s.meta.readiness ?? DEFAULT_READINESS,
      );
      const flagged = body.mood === "red" || !!body.pain;
      // Self-guided players have no staff queue (the server alerts a linked parent instead).
      const escalated = flagged && user.me.pathway !== "amateur";
      Object.assign(today, {
        checked_in: true,
        readiness_is_today: true,
        streak: today.checked_in ? today.streak : today.streak + 1,
        readiness: { ...(today.readiness ?? {}), date: s.meta.today, score, band, components },
      });
      if (escalated) {
        const kind = body.mood === "red" ? "red_mood" : "pain_report";
        s.staff["/api/physio/queue"].push({
          id: `demo-${Date.now()}`,
          player: { id: user.me.player_id, name: user.me.name },
          kind,
          text: kind === "red_mood" ? "Red mood check-in" : "Pain reported",
          created_at: new Date().toISOString(),
          age_minutes: 0,
          notified_after_s: 0.01,
          readiness: today.readiness,
        });
      }
      return { escalated, notified: escalated ? "staff" : null, today };
    }
    const task = p.match(/^\/api\/me\/tasks\/([^/]+)\/toggle$/);
    if (task) {
      const t = today.tasks.find((x: Json) => x.id === task[1]) ?? fail(404, "Unknown task");
      t.done = !t.done;
      return { task: t.id, done: t.done };
    }
    if (p === "/api/me/growth") {
      const g = r["/api/me/growth"];
      const last = g.measurements.at(-1);
      g.measurements.push({
        date: s.meta.today,
        age: g.age_now,
        ...body,
        maturity_offset: last ? Math.round((last.maturity_offset + (g.age_now - last.age)) * 100) / 100 : 0,
      });
      return g;
    }
    fail(404, "Not available in the demo");
  }

  // ---- staff
  if (p.startsWith("/api/coach/") || p.startsWith("/api/physio/")) {
    if (role !== "coach" && role !== "physio" && role !== "admin") fail(403, "Not allowed for your role");
    // A second team's coach has his own recorded views; everyone else shares the main squad's
    const st: Record<string, Json> = { ...s.staff, ...user.responses };
    if (method === "GET") {
      if (p === "/api/coach/squad-week") {
        const off = Math.max(0, Math.min(1, Number(q.get("offset") ?? 0)));
        return st[`${p}?offset=${off}`] ?? fail(404, "Not available in the demo");
      }
      if (p === "/api/coach/heatmap") {
        const hm = st[p];
        const group = q.get("age_group"),
          flag = q.get("flag");
        return { ...hm, players: hm.players.filter((r: Json) => (!group || r.age_group === group) && (!flag || r.flags.includes(flag))) };
      }
      if (p === "/api/coach/agent-log" || p === "/api/coach/agent-log.csv") {
        const rows = st["/api/coach/agent-log"].filter(
          (r: Json) =>
            (!q.get("agent") || r.agent === q.get("agent")) &&
            (!q.get("decision") || r.decision === q.get("decision")) &&
            (!q.get("player") || r.player?.id === q.get("player")),
        );
        return p.endsWith(".csv") ? csv(rows) : rows;
      }
      return st[p] ?? fail(404, "Not available in the demo");
    }
    if (p.startsWith("/api/coach/finance/")) fail(403, "Booking money needs the live server, not this offline demo");
    if (p === "/api/coach/squad-week/session" || /^\/api\/coach\/matches\/[^/]+\/ratings$/.test(p) || p === "/api/coach/ratings/preview")
      fail(403, "This runs the planner or the rating engine: it needs the live server, not this offline demo");
    const decision = p.match(/^\/api\/coach\/proposals\/([^/]+)\/decision$/);
    if (decision) {
      if (role !== "coach") fail(403, "Only coaches decide on proposals");
      const inbox: Json[] = st["/api/coach/inbox"];
      const prop = inbox.find((x) => x.id === decision[1]) ?? fail(422, "proposal is no longer pending");
      st["/api/coach/inbox"] = inbox.filter((x) => x.id !== prop.id);
      const status = body.action === "reject" ? "rejected" : body.action === "edit" ? "edited" : "approved";
      const target = userByPlayerId(s, prop.player.id);
      if (status !== "rejected" && target) {
        const today = target.responses["/api/me/today"];
        today.why.unshift({
          id: prop.id,
          kind: prop.kind,
          title: KIND_TITLE[prop.kind] ?? "Plan updated",
          explanation: prop.explanation_player ?? prop.reason,
          chips: prop.chips,
          approved_by: user.me.name,
          status,
          changed_days: (prop.payload?.changed_days as string[]) ?? [],
          created_at: new Date().toISOString(),
        });
        const proposed: Json[] = prop.proposed ?? [];
        for (const off of [0, 1]) {
          const wk = target.responses[`/api/me/week?offset=${off}`];
          wk.days = wk.days.map((d: Json) => proposed.find((x) => x.date === d.date) ?? d);
        }
        const todayPlan = proposed.find((x) => x.date === s.meta.today);
        if (todayPlan) today.session = todayPlan;
      }
      return { id: prop.id, status };
    }
    const rating = p.match(/^\/api\/coach\/players\/([^/]+)\/rating$/);
    if (rating) return { player_id: rating[1], day: body.day ?? s.meta.today, band: body.band };
    const note = p.match(/^\/api\/coach\/players\/([^/]+)\/notes$/);
    if (note) {
      st[`/api/coach/players/${note[1]}`]?.notes.unshift({ date: s.meta.today, text: body.text, author: user.me.name });
      return { id: `note-${Date.now()}` };
    }
    if (p === "/api/coach/calibration/apply") {
      if (role !== "coach") fail(403, "Only coaches apply weights");
      const cal = st["/api/coach/calibration"];
      cal.current = body.weights ?? { hrv: 0.4, hooper: 0.35, sleep: 0.25 };
      return cal;
    }
    if (p === "/api/coach/run-nightly") return { players: st["/api/coach/heatmap"].players.length };
    if (/^\/api\/coach\/players\/[^/]+\/instruction$/.test(p))
      fail(403, "Turning a note into a plan runs the planner: it needs the live server, not this offline demo");
    const pos = p.match(/^\/api\/coach\/players\/([^/]+)\/position$/);
    if (pos) {
      const prof = st[`/api/coach/players/${pos[1]}`];
      if (prof) prof.player.position = body.position;
      return { position: body.position, gym: prof?.gym ?? null };
    }
    const ack = p.match(/^\/api\/physio\/escalations\/([^/]+)\/ack$/);
    if (ack) {
      st["/api/physio/queue"] = st["/api/physio/queue"].filter((e: Json) => e.id !== ack[1]);
      return { id: ack[1], acknowledged_at: new Date().toISOString() };
    }
    fail(404, "Not available in the demo");
  }

  // ---- guardian
  if (p.startsWith("/api/guardian/")) {
    if (role !== "guardian") fail(403, "Not allowed for your role");
    const r = user.responses;
    const consent = p.match(/^\/api\/guardian\/children\/([^/]+)\/consent$/);
    if (consent && method === "PUT") {
      const c = r[p];
      const item = c.items.find((i: Json) => i.data_type === body.data_type);
      if (item) item.granted = body.granted;
      return c;
    }
    if (method === "DELETE") fail(403, "Deleting data is switched off in the demo");
    return r[p] ?? fail(404, "Not available in the demo");
  }
  fail(404, "Not available in the demo");
}
