// Pro leagues home: one card per competition, saying honestly how much of it the open data covers.
import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../shared/PageHeader";
import { useApi } from "../shared/useApi";
import { Card, Chip, ErrorNote, PageSkeleton } from "../shared/ui";
import { COMP_COLOR, type Competition } from "./context";

export const COVERAGE: Record<Competition["coverage"], string> = {
  league: "Full season",
  club: "One club's season",
  finals: "Finals only",
};

export function ProHome() {
  const { data, error, loading, reload } = useApi<Competition[]>("/api/pro/competitions");
  if (loading && !data) return <PageSkeleton label="Loading the competitions" />;
  if (error || !data) return <ErrorNote message={error ?? "No data"} onRetry={reload} />;
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Real matches, every event"
        title="Pro league analysis"
        subtitle="How the pros play: passing, shooting, pressing, set pieces and players, from StatsBomb's free event data. Study an opponent's style, or the players in your position."
      />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.map((c) => (
          <Link key={c.id} to={`/pro/${c.id}`} className="group" aria-label={`${c.name} ${c.season}`}>
            <Card className="relative h-full overflow-hidden p-0 transition-shadow group-hover:shadow-md">
              <div className="h-1.5" style={{ background: COMP_COLOR[c.id] }} aria-hidden />
              <div className="space-y-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h2 className="font-display text-2xl leading-tight font-bold uppercase">{c.name}</h2>
                    <p className="text-ink-2 text-sm font-semibold">{c.season}</p>
                  </div>
                  <Chip tone={c.coverage === "league" ? "green" : "amber"}>{COVERAGE[c.coverage]}</Chip>
                </div>
                <p className="text-ink-2 text-sm">{c.note}</p>
                <p className="flex items-center justify-between pt-1 text-sm">
                  <span className="num">
                    <span className="font-display text-xl font-bold">{c.matches}</span> matches
                    {c.coverage !== "finals" && (
                      <>
                        {" · "}
                        <span className="font-display text-xl font-bold">{c.teams}</span> {c.teams === 1 ? "club" : "clubs"} to study
                      </>
                    )}
                  </span>
                  <ArrowRight className="text-pitch-600 h-5 w-5 transition-transform group-hover:translate-x-1" aria-hidden />
                </p>
              </div>
            </Card>
          </Link>
        ))}
      </div>
      <p className="text-ink-2 text-xs">
        Data: <a className="underline" href="https://github.com/statsbomb/open-data">StatsBomb Open Data</a>, used under StatsBomb's
        open-data terms. Competition and club names only; no league or club logos.
      </p>
    </div>
  );
}
