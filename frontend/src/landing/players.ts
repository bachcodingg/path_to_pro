// Photos of real footballers on the overview page. Every one is from Wikimedia Commons under a
// Creative Commons licence that allows reuse with credit; the files in public/players are crops.
// None of these players has any connection with PathToPro, and the page says so.

export type Photo = {
  file: string;
  alt: string;
  author: string;
  license: string;
  licenseUrl: string;
  source: string;
};

export type Prospect = Photo & { name: string; age: number; team: string; year: string; later: string };

// Famous players photographed near the start of their careers, youngest first
export const PROSPECTS: Prospect[] = [
  {
    name: "Jude Bellingham",
    age: 16,
    team: "Birmingham City",
    year: "2019",
    later: "Later Dortmund, then Real Madrid",
    file: "young-bellingham.webp",
    alt: "Jude Bellingham, aged 16, warming up in a blue Birmingham City shirt",
    author: "Struway2",
    license: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
    source: "https://commons.wikimedia.org/wiki/File:Jude_Bellingham_Birmingham_2019.jpg",
  },
  {
    name: "Lionel Messi",
    age: 18,
    team: "Barcelona",
    year: "2005",
    later: "Later eight Ballon d'Or awards",
    file: "young-messi.webp",
    alt: "Lionel Messi, aged 18, with long hair in a Barcelona shirt",
    author: "Josep Tomàs",
    license: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
    source: "https://commons.wikimedia.org/wiki/File:Leo_messi_barce_2005.jpg",
  },
  {
    name: "Kylian Mbappé",
    age: 18,
    team: "France",
    year: "2017",
    later: "Later a World Cup winner at 19",
    file: "young-mbappe.webp",
    alt: "Kylian Mbappé, aged 18, on the ball for France",
    author: "Biser Todorov",
    license: "CC BY 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by/4.0/",
    source: "https://commons.wikimedia.org/wiki/File:Kylian_Mbappe_2017.jpg",
  },
  {
    name: "Erling Haaland",
    age: 18,
    team: "Red Bull Salzburg",
    year: "2019",
    later: "Later 36 goals in one Premier League season",
    file: "young-haaland.webp",
    alt: "Erling Haaland, aged 18, running in a Red Bull Salzburg shirt",
    author: "Werner100359",
    license: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
    source: "https://commons.wikimedia.org/wiki/File:FC_RB_Salzburg_gegen_CSKA_Sofia_(Testspiel_3._Juli_2019)_18.jpg",
  },
  {
    name: "Cristiano Ronaldo",
    age: 21,
    team: "Manchester United",
    year: "2006",
    later: "Later five Ballon d'Or awards",
    file: "young-ronaldo.webp",
    alt: "Cristiano Ronaldo, aged 21, in a red Manchester United shirt",
    author: "Ray Booysen",
    license: "CC BY 2.0",
    licenseUrl: "https://creativecommons.org/licenses/by/2.0/",
    source: "https://commons.wikimedia.org/wiki/File:Ronaldo_-_Manchester_United_vs_Chelsea.jpg",
  },
];

// One face for each competition in the Pro League app, from the club or season the data covers
export const COMP_FACES: Record<string, Photo & { name: string; team: string }> = {
  "la-liga": {
    name: "Lionel Messi",
    team: "Barcelona",
    file: "pro-messi.webp",
    alt: "Lionel Messi in Barcelona's 2015/16 shirt",
    author: "Олег Дубина (Oleg Dubyna)",
    license: "CC BY-SA 3.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/3.0/",
    source: "https://commons.wikimedia.org/wiki/File:2015_UEFA_Super_Cup_64_crop.jpg",
  },
  "premier-league": {
    name: "Jamie Vardy",
    team: "Leicester City",
    file: "pro-vardy.webp",
    alt: "Jamie Vardy in Leicester City blue during the 2015/16 title run",
    author: "Egghead06",
    license: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
    source: "https://commons.wikimedia.org/wiki/File:Leicester_City_v_West_Ham_United_April_2016.jpeg",
  },
  "ligue-1": {
    name: "Zlatan Ibrahimović",
    team: "Paris Saint-Germain",
    file: "pro-zlatan.webp",
    alt: "Zlatan Ibrahimović in a Paris Saint-Germain shirt in February 2016",
    author: "Liondartois",
    license: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
    source: "https://commons.wikimedia.org/wiki/File:Tacalfred_and_Signorino_vs_Ibrahimovic.JPG",
  },
  bundesliga: {
    name: "Florian Wirtz",
    team: "Bayer Leverkusen",
    file: "pro-wirtz.webp",
    alt: "Florian Wirtz at Bayer Leverkusen's season opening",
    author: "Pyaet",
    license: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
    source: "https://commons.wikimedia.org/wiki/File:Florian_Wirtz,_2022-07-31,_Saisoner%C3%B6ffnung_Bayer_04,_Leverkusen_(1)_(cropped).jpg",
  },
  "champions-league": {
    name: "Steven Gerrard",
    team: "Liverpool",
    file: "pro-gerrard.webp",
    alt: "Steven Gerrard striking a ball in Liverpool red",
    author: "Phillip Chambers",
    license: "CC BY-SA 2.5",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/2.5/",
    source: "https://commons.wikimedia.org/wiki/File:Liverpool_footballer_Steven_Gerrard.jpg",
  },
};

export const photoUrl = (file: string) => `${import.meta.env.BASE_URL}players/${file}`;

export const ALL_PHOTOS: (Photo & { name: string })[] = [...PROSPECTS, ...Object.values(COMP_FACES)];
