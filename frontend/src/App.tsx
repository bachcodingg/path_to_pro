import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { homeFor, useAuth } from "./shared/auth";
import { Login } from "./shared/Login";
import type { Role } from "./shared/types";
import { Spinner } from "./shared/ui";

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
  const { user } = useAuth();
  return (
    <Suspense fallback={<Spinner />}>
    <Routes>
      <Route path="/login" element={<Login />} />
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
        <Route path="tactics" element={<TacticsBoard />} />
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
      <Route
        path="/guardian"
        element={
          <Guard roles={["guardian"]}>
            <GuardianHome />
          </Guard>
        }
      />
      <Route path="*" element={<Navigate to={user ? homeFor(user.role) : "/login"} replace />} />
    </Routes>
    </Suspense>
  );
}
