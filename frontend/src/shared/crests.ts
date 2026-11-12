// Real club crests, only where they are free to reuse: public domain (most are simple text
// logos) or, for Barcelona, Bordeaux, Eibar and Paris Saint-Germain, public domain in the US,
// where this site is hosted. Köln's is CC BY-SA 4.0. All are still trademarks of their clubs.
// Every other club keeps the badge drawn from its colours (Club.tsx). Files: public/crests/.
export type CrestLicence = "pd" | "pd-us" | "cc-by-sa-4.0";

export interface RealCrest {
  file: string;
  licence: CrestLicence;
  source: string;
  author?: string;
}

// Keyed by the names in the StatsBomb data
export const REAL_CRESTS: Record<string, RealCrest> = {
  "AC Milan": { file: "ac-milan.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:Logo_of_AC_Milan.svg" },
  "Angers": { file: "angers.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:Angers_Sporting_Club_de_l%27Ouest_logo.svg" },
  "Barcelona": { file: "barcelona.svg", licence: "pd-us", source: "https://en.wikipedia.org/wiki/File:FC_Barcelona_(crest).svg" },
  "Bayern Munich": { file: "bayern-munich.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:FC_Bayern_M%C3%BCnchen_logo_(2024).svg" },
  "Bochum": { file: "bochum.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:VfL_Bochum_logo.svg" },
  "Bordeaux": { file: "bordeaux.svg", licence: "pd-us", source: "https://en.wikipedia.org/wiki/File:FC_Girondins_de_Bordeaux_logo.svg" },
  "Borussia Dortmund": { file: "borussia-dortmund.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:Borussia_Dortmund_logo.svg" },
  "Borussia Mönchengladbach": { file: "borussia-monchengladbach.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:Borussia_M%C3%B6nchengladbach_logo.svg" },
  "Eibar": { file: "eibar.svg", licence: "pd-us", source: "https://en.wikipedia.org/wiki/File:SD_Eibar_logo_2016.svg" },
  "FC Heidenheim": { file: "fc-heidenheim.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:1._FC_Heidenheim_1846.svg" },
  "FC Köln": { file: "fc-koln.svg", licence: "cc-by-sa-4.0", author: "1. FC Köln", source: "https://commons.wikimedia.org/wiki/File:1._FC_Koeln_Logo_2014%E2%80%93.svg" },
  "FSV Mainz 05": { file: "fsv-mainz-05.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:1._FSV_Mainz_05_logo.svg" },
  "Hoffenheim": { file: "hoffenheim.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:Logo_TSG_Hoffenheim.svg" },
  "Inter Milan": { file: "inter-milan.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:FC_Internazionale_Milano_2021.svg" },
  "Juventus": { file: "juventus.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:Juventus_FC_-_logo_black_(Italy,_2020).svg" },
  "Nantes": { file: "nantes.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:Logo_FC_Nantes_(avec_fond)_-_2019.svg" },
  "Paris Saint-Germain": { file: "paris-saint-germain.svg", licence: "pd-us", source: "https://en.wikipedia.org/wiki/File:Paris_Saint-Germain_F.C..svg" },
  "Stade de Reims": { file: "stade-de-reims.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:Stade_de_Reims_logo.svg" },
  "Troyes": { file: "troyes.png", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:ESTAC_Troyes_Logo.svg" },
  "Union Berlin": { file: "union-berlin.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:1._FC_Union_Berlin_Logo.svg" },
  "VfB Stuttgart": { file: "vfb-stuttgart.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:VfB_Stuttgart_1893_Logo.svg" },
  "Werder Bremen": { file: "werder-bremen.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:SV-Werder-Bremen-Logo.svg" },
  "Wolfsburg": { file: "wolfsburg.svg", licence: "pd", source: "https://commons.wikimedia.org/wiki/File:VfL_Wolfsburg_logo_2026.svg" },
};

// API-Football's names for the same clubs (the 2024/25 season data)
const ALIASES: Record<string, string> = {
  "Bayern München": "Bayern Munich",
  "Paris Saint Germain": "Paris Saint-Germain",
  Inter: "Inter Milan",
  "1. FC Köln": "FC Köln",
  "1899 Hoffenheim": "Hoffenheim",
  "VfL Wolfsburg": "Wolfsburg",
  "VfL BOCHUM": "Bochum",
  "VfL Bochum": "Bochum",
  "1. FC Heidenheim": "FC Heidenheim",
  "FSV Mainz 05": "FSV Mainz 05",
  "Borussia Monchengladbach": "Borussia Mönchengladbach",
  Reims: "Stade de Reims",
  Estac: "Troyes",
};

export const LICENCE_TEXT: Record<CrestLicence, string> = {
  pd: "Public domain",
  "pd-us": "Public domain in the US",
  "cc-by-sa-4.0": "CC BY-SA 4.0",
};

export function realCrest(name: string): RealCrest | null {
  return REAL_CRESTS[name] ?? REAL_CRESTS[ALIASES[name] ?? ""] ?? null;
}
