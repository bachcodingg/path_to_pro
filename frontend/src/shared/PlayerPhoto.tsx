// A real player's photo in a circle, with his club's crest on its edge. Photos come from
// Wikimedia Commons (free licences, credited where they are shown: PhotoCredit) or, for the
// API-Football seasons, from API-Football. No photo, or one that fails to load: his initials.
import { useState } from "react";
import { Crest } from "./Club";
import { cn } from "./ui";

export interface Photo {
  url: string;
  /** Wikimedia Commons: the file's page, author and licence */
  page?: string | null;
  author?: string | null;
  licence?: string | null;
  licence_url?: string | null;
  /** Where it comes from when it is not Commons ("API-Football") */
  via?: string | null;
}

function initials(name: string) {
  const w = name.replace(/[^\p{L} ]/gu, "").split(/\s+/).filter(Boolean);
  return ((w[0]?.[0] ?? "") + (w.length > 1 ? w[w.length - 1][0] : "")).toUpperCase() || "?";
}

export function PlayerPhoto({
  name,
  photo,
  team,
  logo,
  size = 40,
  className,
}: {
  name: string;
  photo?: Photo | null;
  /** The club, for the crest on the photo's edge */
  team?: string;
  logo?: string | null;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const crest = Math.max(16, Math.round(size * 0.42));
  return (
    <span className={cn("relative inline-block shrink-0", className)} style={{ width: size, height: size }}>
      {photo?.url && !failed ? (
        <img
          src={photo.url}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          className="bg-surface-2 border-line h-full w-full rounded-full border object-cover object-top"
        />
      ) : (
        <span
          aria-hidden
          className="bg-surface-2 border-line text-ink-2 font-display flex h-full w-full items-center justify-center rounded-full border font-bold"
          style={{ fontSize: Math.round(size * 0.36) }}
        >
          {initials(name)}
        </span>
      )}
      {team && (
        <span className="absolute -right-1 -bottom-1 drop-shadow">
          <Crest name={team} src={logo} size={crest} />
        </span>
      )}
    </span>
  );
}

/** "Photo: Author, CC BY-SA 4.0, via Wikimedia Commons", with links */
export function PhotoCredit({ photo, className }: { photo?: Photo | null; className?: string }) {
  if (!photo?.url) return null;
  if (!photo.page)
    return <span className={className}>Photo: {photo.via ?? "the data source"}.</span>;
  return (
    <span className={className}>
      Photo:{" "}
      <a className="underline" href={photo.page}>
        {photo.author || "Wikimedia Commons"}
      </a>
      {photo.licence &&
        (photo.licence_url ? (
          <>
            ,{" "}
            <a className="underline" href={photo.licence_url}>
              {photo.licence}
            </a>
          </>
        ) : (
          `, ${photo.licence}`
        ))}
      , via Wikimedia Commons.
    </span>
  );
}

/** Every photo on a page, credited, folded away */
export function PhotoCredits({ people }: { people: { name: string; photo?: Photo | null }[] }) {
  const seen = new Set<string>();
  const list = people.filter((p) => p.photo?.page && !seen.has(p.name) && seen.add(p.name));
  const api = people.some((p) => p.photo?.url && !p.photo.page);
  if (!list.length && !api) return null;
  return (
    <details className="text-ink-2 text-xs">
      <summary className="cursor-pointer font-semibold">Player photos</summary>
      {api && <p className="mt-1">Photos of the API-Football seasons: API-Football, shown from its servers.</p>}
      {list.length > 0 && (
        <>
          <p className="mt-1 max-w-3xl">
            From Wikimedia Commons, free to reuse under the licence given with each. The players and their clubs have no connection with this app.
          </p>
          <ul className="mt-1 grid gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((p) => (
              <li key={p.name}>
                {p.name}: <PhotoCredit photo={p.photo} />
              </li>
            ))}
          </ul>
        </>
      )}
    </details>
  );
}
