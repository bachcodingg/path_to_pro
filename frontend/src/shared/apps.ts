// The apps built on this platform. They share one account, one API and one design system, but
// each is its own app: its own address, name, icon, theme and install, the way two devices from
// the same maker run the same system. A link from one to the other leaves the app, like opening
// another app on a phone.

export type AppId = "pathtopro" | "leagues";

export interface AppInfo {
  id: AppId;
  name: string;
  shortName: string;
  tagline: string;
  icon: string;
  url: string;
}

const BASE = import.meta.env.BASE_URL;

export const APPS: Record<AppId, AppInfo> = {
  pathtopro: {
    id: "pathtopro",
    name: "PathToPro",
    shortName: "PathToPro",
    tagline: "Training, recovery and growth for academy players",
    icon: `${BASE}icon.svg`,
    url: BASE,
  },
  leagues: {
    id: "leagues",
    name: "Pro League Data Tracking",
    shortName: "Pro League",
    tagline: "Tables, team styles, players and every match of five top competitions",
    icon: `${BASE}leagues/icon.svg`,
    url: `${BASE}leagues/`,
  },
};

// An address inside the Pro League app: leaguesUrl("/la-liga") -> /<base>/leagues/la-liga
export const leaguesUrl = (path = "/") => `${APPS.leagues.url}${path.replace(/^\//, "")}`;
