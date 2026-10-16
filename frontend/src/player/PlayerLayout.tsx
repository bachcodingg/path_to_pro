import { CalendarDays, Home, LogOut, Map, Ruler, Shield } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../shared/auth";
import { t } from "../shared/i18n";
import { cn } from "../shared/ui";

const NAV = [
  { to: "/player", label: t("nav.today"), icon: Home, end: true },
  { to: "/player/week", label: t("nav.week"), icon: CalendarDays },
  { to: "/player/growth", label: t("nav.growth"), icon: Ruler },
  { to: "/player/card", label: t("nav.card"), icon: Shield },
  { to: "/player/road", label: t("nav.road"), icon: Map },
];

// Mobile-first PWA shell; dark by default (players use it in the evening).
export function PlayerLayout() {
  const { user, logout } = useAuth();
  return (
    <div className="dark bg-surface-2 text-ink min-h-full">
      <div className="mx-auto flex min-h-screen max-w-md flex-col">
        <header className="flex items-center justify-between px-4 pt-[max(env(safe-area-inset-top),12px)] pb-2">
          <div className="flex items-center gap-2">
            <img src="/icon.svg" alt="" className="h-8 w-8" />
            <span className="text-lg font-extrabold">PathToPro</span>
          </div>
          <button className="tap text-ink-2 flex items-center gap-1 text-sm" onClick={logout} aria-label={t("common.signout")}>
            <span className="max-w-[9rem] truncate">{user?.name}</span>
            <LogOut className="h-4 w-4" aria-hidden />
          </button>
        </header>
        <main className="flex-1 px-4 pb-28">
          <Outlet />
        </main>
        <nav
          className="bg-surface border-line fixed inset-x-0 bottom-0 border-t pb-[env(safe-area-inset-bottom)]"
          aria-label="Player navigation"
        >
          <ul className="mx-auto grid max-w-md grid-cols-5">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      "tap flex flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-semibold",
                      isActive ? "text-pitch-300" : "text-ink-2",
                    )
                  }
                >
                  <Icon className="h-5 w-5" aria-hidden />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </div>
  );
}
