// The Pro League app's pages. Signed out, its own sign-in screen (a PathToPro account works
// here too); signed in, the competitions. Open to every kind of account: it is public match data
// and holds nothing about our players.
import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "../shared/auth";
import { Spinner } from "../shared/ui";
import { LeaguesSignIn } from "./LeaguesSignIn";

const LeaguesLayout = lazy(() => import("./LeaguesLayout").then((m) => ({ default: m.LeaguesLayout })));
const ProHome = lazy(() => import("./ProHome").then((m) => ({ default: m.ProHome })));
const CompetitionPage = lazy(() => import("./Competition").then((m) => ({ default: m.CompetitionPage })));
const TeamAnalysis = lazy(() => import("./TeamAnalysis").then((m) => ({ default: m.TeamAnalysis })));
const MatchCentre = lazy(() => import("./Matches").then((m) => ({ default: m.MatchCentre })));
const PlayersHub = lazy(() => import("./PlayersHub").then((m) => ({ default: m.PlayersHub })));
const PlayerProfile = lazy(() => import("./PlayerProfile").then((m) => ({ default: m.PlayerProfile })));
const SeasonSquad = lazy(() => import("./Season").then((m) => ({ default: m.SeasonSquad })));
const SeasonPlayerPage = lazy(() => import("./Season").then((m) => ({ default: m.SeasonPlayerPage })));

export function LeaguesApp() {
  const { user, loading } = useAuth();
  // This app's own colours (index.css [data-role="leagues"]), light like a league website
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.role = "leagues";
    root.classList.remove("dark");
  }, []);
  if (loading) return <Spinner />;
  if (!user) return <LeaguesSignIn />;
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route element={<LeaguesLayout />}>
          <Route index element={<ProHome />} />
          <Route path="players" element={<PlayersHub />} />
          <Route path="season/teams/:teamId" element={<SeasonSquad />} />
          <Route path="season/teams/:teamId/players/:playerId" element={<SeasonPlayerPage />} />
          <Route path=":comp" element={<CompetitionPage />} />
          <Route path=":comp/teams/:teamId" element={<TeamAnalysis />} />
          <Route path=":comp/matches/:matchId" element={<MatchCentre />} />
          <Route path=":comp/teams/:teamId/players/:playerId" element={<PlayerProfile />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
