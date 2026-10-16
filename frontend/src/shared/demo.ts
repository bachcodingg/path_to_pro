// Demo mode (VITE_DEMO=1): the API answered in the browser, so the app runs as a static
// website. Reads come from a snapshot recorded from the real API on the synthetic season
// (backend/scripts/demo_snapshot.py); actions update in-memory state the way the backend
// would, so the whole demo script works. State is kept in this browser's localStorage
// (so switching accounts keeps your changes) until "Reset demo"; nothing leaves the browser.
import { ApiError } from "./api";

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

interface Snapshot {
  meta: { today: string; story: Record<string, string>; password: string; generated?: string };
  users: Record<string, { me: Json; responses: Record<string, Json> }>;
  staff: Record<string, Json>;
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

const WEIGHTS = { hooper: 0.35, sleep: 0.25 }; // no HRV for a manual check-in: rescaled
const GREEN = 70,
  AMBER = 50,
  BUFFER_UP = 8;
const RANK: Record<string, number> = { red: 0, amber: 1, green: 2 };

function rawBand(score: number): "green" | "amber" | "red" {
  return score >= GREEN ? "green" : score >= AMBER ? "amber" : "red";
}
function bandWithBuffer(score: number, previous: string | null): "green" | "amber" | "red" {
  const now = rawBand(score);
  if (!previous || RANK[now] <= RANK[previous]) return now; // worse: applies at once
  return RANK[rawBand(score - BUFFER_UP)] > RANK[previous] ? rawBand(score - BUFFER_UP) : (previous as "green" | "amber" | "red");
}

function checkinReadiness(body: Json, previous: string | null) {
  const h = body.sleep_quality + body.fatigue + body.stress + body.soreness;
  const hooper = ((28 - h) / 24) * 100;
  const sleep = Math.min((body.sleep_hours ?? 8) / 9, 1) * 100;
  const total = WEIGHTS.hooper + WEIGHTS.sleep;
  const score = (WEIGHTS.hooper * hooper + WEIGHTS.sleep * sleep) / total;
  return { score: Math.round(score * 10) / 10, band: bandWithBuffer(score, previous) };
}

// --------------------------------------------------------------------------- helpers

const KIND_TITLE: Record<string, string> = {
  session_swap: "Your sessions were changed",
  load_cut: "Your week was made lighter",
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

  const email = currentEmail();
  const user = email ? s.users[email] : undefined;
  if (!user) fail(401, "Not signed in");
  const role: string = user.me.role;
  if (p === "/api/auth/me") return user.me;

  // ---- player
  if (p.startsWith("/api/me/")) {
    if (role !== "player") fail(403, "Not allowed for your role");
    const r = user.responses;
    if (method === "GET") {
      if (p === "/api/me/week") {
        const off = Math.max(-1, Math.min(1, Number(q.get("offset") ?? 0)));
        return r[`/api/me/week?offset=${off}`];
      }
      return r[p] ?? fail(404, "Not available in the demo");
    }
    const today = r["/api/me/today"];
    if (p === "/api/me/checkin") {
      const prev = today.readiness?.band ?? null;
      const { score, band } = checkinReadiness(body, prev);
      const escalated = body.mood === "red" || !!body.pain;
      Object.assign(today, {
        checked_in: true,
        readiness_is_today: true,
        streak: today.checked_in ? today.streak : today.streak + 1,
        readiness: { ...(today.readiness ?? {}), date: s.meta.today, score, band },
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
      return { escalated, today };
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
    const st = s.staff;
    if (method === "GET") {
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
