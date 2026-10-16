import { ClipboardList, Grid3x3, LogOut, MessageSquareText, Play, Stethoscope, Users } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../shared/api";
import { useAuth } from "../shared/auth";
import { t } from "../shared/i18n";
import { Button, cn } from "../shared/ui";

const NAV = [
  { to: "/coach", label: t("nav.heatmap"), icon: Grid3x3, end: true },
  { to: "/coach/inbox", label: t("nav.inbox"), icon: ClipboardList },
  { to: "/coach/tactics", label: t("nav.tactics"), icon: Users },
  { to: "/coach/log", label: t("nav.log"), icon: MessageSquareText },
  { to: "/physio", label: t("nav.physio"), icon: Stethoscope },
];

// Desktop-first staff shell; light by default.
export function CoachLayout() {
  const { user, logout } = useAuth();
  const [running, setRunning] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function runNightly() {
    setRunning(true);
    try {
      const out = await api<Record<string, number>>("/api/coach/run-nightly", { method: "POST" });
      setMsg(`Agents ran for ${out.players} players`);
      setTimeout(() => window.location.reload(), 800);
    } catch {
      setMsg("Could not run agents");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="bg-surface-2 text-ink flex min-h-full">
      <aside className="bg-pitch-800 hidden w-60 shrink-0 flex-col p-4 text-white md:flex">
        <div className="mb-6 flex items-center gap-2">
          <img src="/icon.svg" alt="" className="h-8 w-8" />
          <span className="text-lg font-extrabold">PathToPro</span>
        </div>
        <nav aria-label="Staff navigation" className="flex-1 space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn("tap flex items-center gap-3 rounded-xl px-3 py-2 font-semibold", isActive ? "bg-white/15" : "text-pitch-100 hover:bg-white/10")
              }
            >
              <Icon className="h-5 w-5" aria-hidden /> {label}
            </NavLink>
          ))}
        </nav>
        {user?.role === "coach" && (
          <Button variant="secondary" size="sm" onClick={runNightly} loading={running} className="mb-2">
            <Play className="h-4 w-4" aria-hidden /> Run agents now
          </Button>
        )}
        {msg && <p className="text-pitch-200 mb-2 text-xs">{msg}</p>}
        <div className="border-t border-white/15 pt-3 text-sm">
          <p className="font-semibold">{user?.name}</p>
          <p className="text-pitch-200 capitalize">{user?.role}</p>
          <button onClick={logout} className="tap text-pitch-200 mt-1 flex items-center gap-1">
            <LogOut className="h-4 w-4" aria-hidden /> {t("common.signout")}
          </button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <nav className="bg-pitch-800 flex gap-1 overflow-x-auto p-2 md:hidden" aria-label="Staff navigation">
          {NAV.map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => cn("tap shrink-0 rounded-lg px-3 py-2 text-sm font-semibold text-white", isActive && "bg-white/15")}>
              {label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
