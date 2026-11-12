// Pro League app home: the competitions as cards, each saying honestly how much of it the open
// data covers, and the way in to the player analysis.
import { ArrowRight, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { Crest } from "../shared/Club";
import { PageHeader } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { ErrorNote, PageSkeleton, cn } from "../shared/ui";
import { COMP_COLOR, type Competition } from "./context";
import { CrestCredits } from "./PlayerParts";
import { CompMark, Fact, Label } from "./ui";

export const COVERAGE: Record<Competition["coverage"], string> = {
  league: "Full season",
  club: "One club's season",
  finals: "Finals only",
};

// The clubs whose whole squads the player analysis has
const FEATURED = ["Real Madrid", "Barcelona", "Paris Saint-Germain", "Manchester City", "Manchester United", "Chelsea", "Liverpool", "Arsenal", "Bayern Munich"];

export function ProHome() {
  const { data, error, loading, reload } = useApi<Competition[]>("/api/pro/competitions");
  if (loading && !data) return <PageSkeleton label="Loading the competitions" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  const matches = data.reduce((n, c) => n + (c.matches ?? 0), 0);
  return (
    <div className="space-y-5 md:space-y-6">
      <PageHeader
        eyebrow={<span className="lg-label !text-white/85">Real matches, every event</span>}
        title="Pro league analysis"
        subtitle="How the pros play: passing, shooting, pressing, set pieces and players, from StatsBomb's free event data. Study an opponent's style, or the players in your position."
        bottom={
          <div className="flex flex-wrap gap-x-8 gap-y-3 border-t border-white/20 pt-3 pb-4 md:gap-x-12 md:pb-6">
            <Fact label="Competitions">{data.length}</Fact>
            <Fact label="Matches">{matches.toLocaleString("en-GB")}</Fact>
            <Fact label="Full seasons">{data.filter((c) => c.coverage === "league").length}</Fact>
          </div>
        }
      />

      <section aria-label="Competitions">
        <h2 className="font-display mb-3 text-xl font-extrabold">Competitions</h2>
        <div className="grid gap-4 md:grid-cols-2 md:gap-5 xl:grid-cols-3">
          {data.map((c) => (
            <Link
              key={c.id}
              to={`/${c.id}`}
              aria-label={`${c.name} ${c.season}`}
              className="lg-panel group hover:border-pitch-500 flex flex-col transition-[border-color,box-shadow] hover:shadow-md"
            >
              <div className="h-1" style={{ background: COMP_COLOR[c.id] }} aria-hidden />
              <div className="flex items-center gap-3 px-4 pt-4">
                <CompMark id={c.id} name={c.name} color={COMP_COLOR[c.id] ?? "#1597d0"} size={48} />
                <div className="min-w-0 flex-1">
                  <h3 className="font-display truncate text-2xl leading-tight font-extrabold">{c.name}</h3>
                  <p className="text-ink-2 num text-sm font-bold">{c.season}</p>
                </div>
                <span
                  className={cn(
                    "shrink-0 self-start rounded px-1.5 py-1 text-[11px] leading-none font-bold tracking-wide uppercase",
                    c.coverage === "league" ? "bg-good/12 text-good" : "bg-surface-2 text-ink-2 border-line border",
                  )}
                >
                  {COVERAGE[c.coverage]}
                </span>
              </div>
              <p className="text-ink-2 flex-1 px-4 pt-3 pb-4 text-sm">{c.note}</p>
              <div className="border-line bg-surface-2/60 flex items-center gap-6 border-t px-4 py-2.5">
                <Stat label="Matches" value={c.matches} />
                {c.coverage !== "finals" && <Stat label={c.teams === 1 ? "Club" : "Clubs"} value={c.teams} />}
                <span className="text-pitch-600 ml-auto flex items-center gap-1 text-sm font-bold">
                  Open <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" aria-hidden />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <Link to="/players" className="lg-panel group hover:border-pitch-500 block transition-[border-color,box-shadow] hover:shadow-md">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 p-4 md:p-5">
          <span className="bg-[#0b1230] text-pitch-300 flex h-12 w-12 shrink-0 items-center justify-center rounded-md">
            <Users className="h-6 w-6" aria-hidden />
          </span>
          <span className="min-w-0 flex-1 basis-64">
            <span className="font-display block text-2xl leading-tight font-extrabold">Pro player analysis</span>
            <span className="text-ink-2 text-sm">
              Full squads of Real Madrid, Barcelona, PSG, Manchester City, Manchester United, Chelsea, Liverpool, Arsenal and Bayern, and the best player of every
              other club.
            </span>
          </span>
          <span className="flex flex-wrap items-center gap-2" aria-hidden>
            {FEATURED.map((t) => (
              <Crest key={t} name={t} size={30} />
            ))}
          </span>
          <span className="text-pitch-600 flex items-center gap-1 font-bold">
            Open Players <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" aria-hidden />
          </span>
        </div>
      </Link>

      <p className="text-ink-2 text-xs">
        Data: <a className="underline" href="https://github.com/statsbomb/open-data">StatsBomb Open Data</a>, used under StatsBomb's
        open-data terms. No league logos. Club crests: the free ones kept in the app, the others from Wikipedia; player photos from Wikimedia Commons, credited.
      </p>
      <CrestCredits />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | undefined }) {
  return (
    <span>
      <Label className="block">{label}</Label>
      <span className="font-display num text-xl leading-tight font-extrabold">{value}</span>
    </span>
  );
}
