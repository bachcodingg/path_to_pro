// The competition the pro-league pages are showing, and what its teams are compared with:
// the rest of the league, or (one club's season) that club's opponents.
import { createContext, useContext } from "react";

export interface Competition {
  id: string;
  name: string;
  season: string;
  coverage: "league" | "club" | "finals";
  note: string;
  featured: string | null;
  compare_label: string;
  matches?: number;
  teams?: number;
}

export const ProContext = createContext<{ comp: string; competition: Competition | null }>({ comp: "la-liga", competition: null });

export function usePro() {
  const { comp, competition } = useContext(ProContext);
  const league = (competition?.coverage ?? "league") === "league";
  return {
    comp,
    competition,
    base: `/api/pro/${encodeURIComponent(comp)}`,
    // "league 76%" / "opponents 81%", and "the rest of the league" / "their opponents"
    label: league ? "league" : "opponents",
    rest: league ? "the rest of the league" : "their opponents",
  };
}

// Brand colours, used for the competition switcher and header glow (no league logos)
export const COMP_COLOR: Record<string, string> = {
  "la-liga": "#ff4b44",
  "premier-league": "#6b1d7a",
  "ligue-1": "#c9d41b",
  bundesliga: "#d20515",
  "champions-league": "#2a4bb0",
};
