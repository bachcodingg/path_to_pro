export type Role = "player" | "guardian" | "coach" | "physio" | "admin";
export type Band = "green" | "amber" | "red";
export type SessionKind = "rest" | "recovery" | "technical" | "tactical" | "strength" | "speed" | "match";

export interface User {
  id: string;
  email: string;
  role: Role;
  name: string;
  player_id: string | null;
}

export interface PlanDay {
  date: string;
  kind: SessionKind;
  label: string;
  rpe: number;
  minutes: number;
  load: number;
  actual_load?: number | null;
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
