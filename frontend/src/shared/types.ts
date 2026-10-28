export type Role = "player" | "guardian" | "coach" | "physio" | "admin";
export type Band = "green" | "amber" | "red";
export type SessionKind = "rest" | "recovery" | "technical" | "tactical" | "strength" | "speed" | "match";

export type Pathway = "academy" | "amateur";
export type Position = "goalkeeper" | "centre_back" | "full_back" | "midfielder" | "winger" | "striker";

export interface User {
  id: string;
  email: string;
  role: Role;
  name: string;
  player_id: string | null;
  pathway?: Pathway | null;
  position?: Position | null;
  email_verified?: boolean;
  mfa_enabled?: boolean;
}

export interface PlanDay {
  date: string;
  kind: SessionKind;
  label: string;
  rpe: number;
  minutes: number;
  load: number;
  actual_load?: number | null;
  team_day?: boolean;
  content?: SessionContent | null;
  match?: { opponent: string; team: string; primary: boolean };
}

export interface SessionContent {
  title: string;
  items: { name: string; minutes: number | null; how: string }[];
}

export interface GymItem {
  id: string;
  name: string;
  block: string;
  tag: "everyone" | "position";
  sets: number;
  amount: string;
  rest_s: number;
  cue: string;
  equipment: string;
  plyometric: boolean;
  heavy: boolean;
}

export interface GymProgramme {
  position: Position;
  position_label: string;
  focus: string;
  stage: "foundation" | "development" | "performance";
  stage_label: string;
  intensity: string;
  title: string;
  minutes: number;
  blocks: { title: string; kind: string; tag: "everyone" | "position"; items: GymItem[] }[];
  adjustments: string[];
}

export interface GymWeek {
  start: string;
  position: Position;
  position_label: string;
  focus: string;
  equipment: "gym" | "home" | "none";
  sessions: { session: PlanDay; programme: GymProgramme }[];
  optional: GymProgramme | null;
  positions: { id: Position; label: string; focus: string }[];
}

export interface Flag {
  kind: string;
  detail: string;
}

export interface Status {
  date: string;
  score: number | null;
  band: Band | null;
  acwr: number | null;
  in_phv_window: boolean;
  maturity_offset: number | null;
  flags: Flag[];
  chips: string[];
  components?: Partial<Record<"hrv" | "hooper" | "sleep", number>>;
}

export interface WhyCard {
  id: string;
  kind: string;
  title: string;
  explanation: string | null;
  chips: string[];
  approved_by: string;
  status: string;
  changed_days: string[];
  created_at: string;
}

export interface Today {
  date: string;
  name: string;
  checked_in: boolean;
  readiness: Status | null;
  readiness_is_today: boolean;
  flags: { kind: string; text: string }[];
  session: PlanDay;
  tasks: { id: string; label: string; done: boolean }[];
  why: WhyCard[];
  streak: number;
  gym?: GymProgramme | null;
  pathway?: TodayPathway | null;
  content?: SessionContent | null;
  safety?: string[];
  logged?: { minutes: number; rpe: number; load: number }[];
  consent?: { wellness: boolean; test_results: boolean };
  diary_due?: DiaryDue[];
}

export interface TodayPathway {
  level: number;
  name: string;
  next: { level: number; name: string; tests_needed: number; tests_met: number } | null;
  consistency: { logged: number; needed: number; planned: number; ok: boolean };
  focus: string[];
}

export interface BenchmarkRow {
  test: string;
  label: string;
  unit: string;
  kind: "physical" | "technical";
  how: string;
  lower_is_better: boolean;
  value: number | null;
  target: number | null;
  met: boolean;
  gap: number;
}

export interface PathwayView {
  profile: {
    level: number;
    level_since: string;
    goal: string;
    goal_label: string;
    equipment: "gym" | "home" | "none";
    team_days: number[];
    match_day: number | null;
    position: Position;
  };
  assessment: {
    level: number;
    name: string;
    who: string;
    targets: string;
    benchmark_level: number;
    next: { level: number; name: string; tests_needed: number; tests_met: number } | null;
    tests: BenchmarkRow[];
    focus: string[];
    consistency: { logged: number; needed: number; planned: number; ok: boolean };
    ready_to_level_up: boolean;
  };
  ladder: {
    level: number;
    name: string;
    who: string;
    targets: string;
    sessions_per_week: number;
    gym_per_week: number;
    benchmarks: Record<string, number | null>;
  }[];
  goals: Record<string, string>;
  can_store_tests: boolean;
  guardian_invite: string | null;
  history: { test: string; date: string; value: number }[];
  note: string;
  levelled_up?: boolean;
}

export interface Week {
  start: string;
  today: string;
  days: PlanDay[];
  last_week: PlanDay[];
}

export interface GrowthPoint {
  date: string;
  age: number;
  height_cm: number;
  sitting_height_cm: number;
  weight_kg: number;
  maturity_offset: number;
}

export interface Growth {
  consent: boolean;
  measurements: GrowthPoint[];
  phv_age: number | null;
  phv_window: [number, number] | null;
  in_phv_window: boolean;
  age_now: number;
  next_measurement_due: string | null;
}

export interface Drill {
  id: string;
  name: string;
  kpi: string;
  minutes: number;
  rpe: number;
  description: string;
}

export interface Attribute {
  attribute: "speed" | "power" | "endurance";
  kpi: string;
  label: string;
  unit: string;
  value: number;
  bio_percentile: number;
  age_percentile: number;
  history: { date: string; value: number }[];
  drills: Drill[];
}

export interface Card {
  name: string;
  maturity_status: string;
  attributes: Attribute[];
}

export interface Goal {
  id: string;
  kpi: string;
  label: string;
  unit: string;
  baseline: number;
  target: number;
  current: number;
  lower_is_better: boolean;
  starts_on: string;
  ends_on: string;
  sessions_per_week: number;
  progress: number;
  status: string;
}

export interface Roadmap {
  goals: Goal[];
  checkpoints: { date: string; done: boolean }[];
  badges: { id: string; name: string; earned: boolean; rule: string }[];
  streak: number;
}

export interface Proposal {
  id: string;
  player: { id: string; name: string };
  kind: string;
  reason: string;
  chips: string[];
  policy_rule: string;
  status: string;
  created_at: string;
  payload: Record<string, unknown>;
  current: PlanDay[];
  proposed: PlanDay[];
  explanation_player: string | null;
  solver_status: string | null;
  teams?: string[];
}

export interface HeatmapRow {
  id: string;
  name: string;
  age: number;
  age_group: string;
  phv: boolean;
  load_flag: boolean;
  flags: string[];
  cells: { date: string; score: number | null; band: Band | null }[];
}

export interface Heatmap {
  dates: string[];
  today: string;
  players: HeatmapRow[];
}

export type RatingBand = "elite" | "good" | "fair" | "average" | "poor";

export interface BreakdownItem {
  label: string;
  value: number;
}

export interface AppearanceRow {
  match_id: string;
  date: string;
  team: string;
  opponent: string;
  competition: string | null;
  competition_label: string;
  minutes: number;
  started: boolean;
  position: Position | null;
  goals: number;
  assists: number;
  rating: number | null;
  rating_band: RatingBand | null;
  rating_source: "stats" | "diary" | null;
  breakdown: BreakdownItem[];
  self_rating: number | null;
  stats: Record<string, number | string>;
}

export interface DiaryDue {
  match_id: string;
  date: string;
  team: string;
  opponent: string;
  minutes: number | null;
}

export interface SeasonRow {
  id?: string;
  season: string;
  club?: string;
  team?: string;
  competition: string;
  competition_label: string;
  level: number;
  apps: number;
  starts: number;
  minutes: number;
  goals: number;
  assists: number;
  avg_rating: number | null;
  rating_band: RatingBand | null;
  exposure: number;
}

export interface Career {
  season: string;
  registrations: { team_id: string; team: string; club: string | null; competition: string; competition_label: string; level: number; primary: boolean }[];
  summary: Omit<SeasonRow, "season" | "competition" | "competition_label" | "level">;
  current: SeasonRow[];
  past: SeasonRow[];
  ladder: { season: string; level: number; competition_label: string }[];
  recent: AppearanceRow[];
  trend: { date: string; rating: number }[];
  history: import("./RatingHistory").RatingHistoryData;
  clubs: import("../player/ClubHistory").ClubStint[];
  diary_due: DiaryDue[];
  competitions: { id: string; label: string; level: number; category: string }[];
  note: string;
}
