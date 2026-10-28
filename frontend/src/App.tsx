import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { homeFor, useAuth } from "./shared/auth";
import { Login } from "./shared/Login";
import { Register, RegisterGuardian } from "./shared/Register";
import { ForgotPassword, SetPassword, VerifyEmail } from "./shared/AuthPages";
import { Imprint, Privacy, Terms } from "./legal/Legal";
import type { Role } from "./shared/types";
import { Spinner } from "./shared/ui";

const Account = lazy(() => import("./shared/Account").then((m) => ({ default: m.Account })));
const AdminHome = lazy(() => import("./admin/AdminHome").then((m) => ({ default: m.AdminHome })));
const PlayerTeam = lazy(() => import("./shared/Team").then((m) => ({ default: m.PlayerTeam })));
const CoachTeam = lazy(() => import("./shared/Team").then((m) => ({ default: m.CoachTeam })));
const Schedule = lazy(() => import("./coach/Schedule").then((m) => ({ default: m.Schedule })));
const Landing = lazy(() => import("./landing/Landing").then((m) => ({ default: m.Landing })));
const CoachLayout = lazy(() => import("./coach/CoachLayout").then((m) => ({ default: m.CoachLayout })));
const AgentLog = lazy(() => import("./coach/AgentLog").then((m) => ({ default: m.AgentLog })));
const Calibration = lazy(() => import("./coach/Calibration").then((m) => ({ default: m.Calibration })));
const Heatmap = lazy(() => import("./coach/Heatmap").then((m) => ({ default: m.Heatmap })));
const Inbox = lazy(() => import("./coach/Inbox").then((m) => ({ default: m.Inbox })));
const PlayerProfile = lazy(() => import("./coach/PlayerProfile").then((m) => ({ default: m.PlayerProfile })));
const TacticsBoard = lazy(() => import("./coach/TacticsBoard").then((m) => ({ default: m.TacticsBoard })));
const GuardianHome = lazy(() => import("./guardian/GuardianHome").then((m) => ({ default: m.GuardianHome })));
const PhysioHome = lazy(() => import("./physio/PhysioHome").then((m) => ({ default: m.PhysioHome })));
const CheckIn = lazy(() => import("./player/CheckIn").then((m) => ({ default: m.CheckIn })));
const Career = lazy(() => import("./player/Career").then((m) => ({ default: m.Career })));
const TrainingPitch = lazy(() => import("./coach/TrainingPitch").then((m) => ({ default: m.TrainingPitch })));
const Matches = lazy(() => import("./coach/Matches").then((m) => ({ default: m.Matches })));
const MatchReport = lazy(() => import("./coach/Matches").then((m) => ({ default: m.MatchReport })));
const Devices = lazy(() => import("./player/Devices").then((m) => ({ default: m.Devices })));
const MatchView = lazy(() => import("./player/MatchView").then((m) => ({ default: m.MatchView })));
const Finance = lazy(() => import("./coach/Finance").then((m) => ({ default: m.Finance })));
const TeamAnalysis = lazy(() => import("./pro/TeamAnalysis").then((m) => ({ default: m.TeamAnalysis })));
const ProLayout = lazy(() => import("./pro/ProLayout").then((m) => ({ default: m.ProLayout })));
const ProHome = lazy(() => import("./pro/ProHome").then((m) => ({ default: m.ProHome })));
const CompetitionPage = lazy(() => import("./pro/Competition").then((m) => ({ default: m.CompetitionPage })));
const MatchCentre = lazy(() => import("./pro/Matches").then((m) => ({ default: m.MatchCentre })));
const Skills = lazy(() => import("./player/Skills").then((m) => ({ default: m.Skills })));
const Tips = lazy(() => import("./player/Tips").then((m) => ({ default: m.Tips })));
const Gym = lazy(() => import("./player/Gym").then((m) => ({ default: m.Gym })));
const Pathway = lazy(() => import("./player/Pathway").then((m) => ({ default: m.Pathway })));
const Growth = lazy(() => import("./player/Growth").then((m) => ({ default: m.Growth })));
const MyWeek = lazy(() => import("./player/MyWeek").then((m) => ({ default: m.MyWeek })));
const PlayerCard = lazy(() => import("./player/PlayerCard").then((m) => ({ default: m.PlayerCard })));
const PlayerLayout = lazy(() => import("./player/PlayerLayout").then((m) => ({ default: m.PlayerLayout })));
const RoadToPro = lazy(() => import("./player/RoadToPro").then((m) => ({ default: m.RoadToPro })));
const TodayScreen = lazy(() => import("./player/Today").then((m) => ({ default: m.TodayScreen })));

function Guard({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role) && user.role !== "admin") return <Navigate to={homeFor(user.role)} replace />;
  return <>{children}</>;
}

export function App() {
  const { user, loading } = useAuth();
  return (
    <Suspense fallback={<Spinner />}>
    <Routes>
      {/* Signed out: the overview page; signed in: straight to your home */}
      <Route path="/" element={loading ? <Spinner /> : user ? <Navigate to={homeFor(user.role)} replace /> : <Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/register/guardian" element={<RegisterGuardian />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/set-password" element={<SetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/imprint" element={<Imprint />} />
      <Route
        path="/account"
        element={
          <Guard roles={["player", "coach", "physio", "guardian", "admin"]}>
            <Account />
          </Guard>
        }
      />
      <Route
        path="/admin"
        element={
          <Guard roles={["admin"]}>
            <AdminHome />
          </Guard>
        }
      />
      <Route
        path="/player"
        element={
          <Guard roles={["player"]}>
            <PlayerLayout />
          </Guard>
        }
      >
        <Route index element={<TodayScreen />} />
        <Route path="checkin" element={<CheckIn />} />
        <Route path="week" element={<MyWeek />} />
        <Route path="gym" element={<Gym />} />
        <Route path="skills" element={<Skills />} />
        <Route path="tips" element={<Tips />} />
        <Route path="levels" element={<Pathway />} />
        <Route path="career" element={<Career />} />
        <Route path="team" element={<PlayerTeam />} />
        <Route path="devices" element={<Devices />} />
        <Route path="matches/:id" element={<MatchView />} />
        <Route path="growth" element={<Growth />} />
        <Route path="card" element={<PlayerCard />} />
        <Route path="road" element={<RoadToPro />} />
      </Route>
      <Route
        path="/coach"
        element={
          <Guard roles={["coach", "physio"]}>
            <CoachLayout />
          </Guard>
        }
      >
        <Route index element={<Heatmap />} />
        <Route path="inbox" element={<Inbox />} />
        <Route path="pitch" element={<TrainingPitch />} />
        <Route path="schedule" element={<Schedule />} />
        <Route path="team" element={<CoachTeam />} />
        <Route path="matches" element={<Matches />} />
        <Route path="matches/:id" element={<MatchReport />} />
        <Route path="finance" element={<Finance />} />
        <Route path="tactics" element={<TacticsBoard />} />
        {/* Team analysis moved to its own section, /pro */}
        <Route path="analysis/*" element={<Navigate to="/pro/la-liga" replace />} />
        <Route path="players/:id" element={<PlayerProfile />} />
        <Route path="log" element={<AgentLog />} />
        <Route path="calibration" element={<Calibration />} />
      </Route>
      <Route
        path="/physio"
        element={
          <Guard roles={["physio", "coach"]}>
            <CoachLayout />
          </Guard>
        }
      >
        <Route index element={<PhysioHome />} />
      </Route>
      {/* Pro league analysis: its own section, open to every signed-in account (public match data) */}
      <Route
        path="/pro"
        element={
          <Guard roles={["player", "coach", "physio", "guardian"]}>
            <ProLayout />
          </Guard>
        }
      >
        <Route index element={<ProHome />} />
        <Route path=":comp" element={<CompetitionPage />} />
        <Route path=":comp/teams/:teamId" element={<TeamAnalysis />} />
        <Route path=":comp/matches/:matchId" element={<MatchCentre />} />
      </Route>
      <Route
        path="/guardian"
        element={
          <Guard roles={["guardian"]}>
            <GuardianHome />
          </Guard>
        }
      />
      <Route path="*" element={<Navigate to={user ? homeFor(user.role) : "/"} replace />} />
    </Routes>
    </Suspense>
  );
}
