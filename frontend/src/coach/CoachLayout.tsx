import { type LucideIcon, CalendarDays, CalendarRange, CalendarCheck, ClipboardList, Euro, Gauge, Grid3x3, LogOut, MessageSquareText, Play, Settings, Star, Stethoscope, Trophy, Users } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { api } from "../shared/api";
import { useAuth } from "../shared/auth";
import { t } from "../shared/i18n";
import { SkipLink } from "../shared/SkipLink";
import { Button, cn } from "../shared/ui";
import { useDocumentTitle } from "../shared/useDocumentTitle";

// Grouped the way staff think about the week; built per call so labels follow the language
type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean; coachOnly?: boolean };
const nav = (): { group: string; items: NavItem[] }[] => [
  {
    group: "Squad",
    items: [
      { to: "/coach", label: t("nav.heatmap"), icon: Grid3x3, end: true },
      { to: "/coach/inbox", label: t("nav.inbox"), icon: ClipboardList },
      { to: "/coach/pitch", label: t("nav.pitch"), icon: CalendarRange },
      { to: "/coach/schedule", label: t("nav.schedule"), icon: CalendarDays },
      { to: "/coach/team", label: t("nav.team"), icon: CalendarCheck },
      { to: "/coach/tactics", label: t("nav.tactics"), icon: Users },
    ],
  },
  {
    group: "Matchday",
    items: [
      { to: "/coach/matches", label: t("nav.matches"), icon: Star },
      { to: "/coach/log", label: t("nav.log"), icon: MessageSquareText },
    ],
  },
  {
    group: "Scouting",
    items: [{ to: "/pro", label: t("nav.pro"), icon: Trophy }],
  },
  {
    group: "Club",
    items: [
      { to: "/physio", label: t("nav.physio"), icon: Stethoscope },
      { to: "/coach/finance", label: t("nav.finance"), icon: Euro, coachOnly: true },
      { to: "/coach/calibration", label: t("nav.calibration"), icon: Gauge },
    ],
  },
];

// Desktop-first staff shell; light by default.
export function CoachLayout() {
  const { user, logout } = useAuth();
  // club money and opponent analysis are for coaches
  const GROUPS = nav().map((g) => ({ ...g, items: g.items.filter((n) => !n.coachOnly || user?.role !== "physio") }));
  const NAV = GROUPS.flatMap((g) => g.items);
  useDocumentTitle(NAV, "Staff");
  const initials = (user?.name ?? "?").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
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
    <div className="app-bg text-ink flex min-h-full">
      <SkipLink />
      {/* The column runs the page's full height; its contents stay in view while scrolling */}
      <aside className="app-rail hidden w-64 shrink-0 text-white md:block">
        <div className="sticky top-0 flex h-[calc(100vh-var(--banner-h,0px))] flex-col px-3 py-4">
          <div className="mb-5 flex items-center gap-2.5 px-2">
            <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="h-9 w-9" />
            <div className="leading-none">
              <span className="font-display block text-xl font-extrabold tracking-wide uppercase">PathToPro</span>
              <span className="text-pitch-300 text-[11px] font-semibold tracking-[0.12em] uppercase">Staff · U13-U18</span>
            </div>
          </div>
          <nav aria-label="Staff navigation" className="no-scrollbar flex-1 space-y-4 overflow-y-auto">
            {GROUPS.filter((g) => g.items.length).map((g) => (
              <div key={g.group}>
                <p className="mb-1 px-3 text-[11px] font-bold tracking-[0.14em] text-white/45 uppercase">{g.group}</p>
                <div className="space-y-0.5">
                  {g.items.map(({ to, label, icon: Icon, end }) => (
                    <NavLink
                      key={to}
                      to={to}
                      end={end}
                      className={({ isActive }) =>
                        cn(
                          "tap relative flex items-center gap-3 rounded-lg px-3 py-2 text-[15px] font-semibold transition-colors",
                          isActive
                            ? "bg-white/12 text-white before:bg-pitch-300 before:absolute before:inset-y-2 before:left-0 before:w-1 before:rounded-full"
                            : "text-pitch-100/80 hover:bg-white/6 hover:text-white",
                        )
                      }
                    >
                      <Icon className="h-[18px] w-[18px]" aria-hidden /> {label}
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}
          </nav>
          {user?.role === "coach" && (
            <Button variant="secondary" size="sm" onClick={runNightly} loading={running} className="mt-3 mb-2 border-0 bg-white/10 text-white hover:bg-white/15">
              <Play className="h-4 w-4" aria-hidden /> Run agents now
            </Button>
          )}
          {msg && <p className="text-pitch-200 mb-2 px-2 text-xs">{msg}</p>}
          <div className="flex items-center gap-3 border-t border-white/10 px-2 pt-3 text-sm">
            <Link to="/account" className="group flex min-w-0 flex-1 items-center gap-3" title={t("nav.account")}>
              <span className="bg-pitch-300 text-pitch-950 font-display flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-base font-bold" aria-hidden>
                {initials}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold group-hover:underline">{user?.name}</span>
                <span className="text-pitch-200 flex items-center gap-1 text-xs capitalize">
                  {user?.role} · <Settings className="h-3 w-3" aria-hidden /> {t("nav.account")}
                </span>
              </span>
            </Link>
            <button onClick={logout} className="tap text-pitch-200 flex items-center justify-center hover:text-white" aria-label={t("common.signout")} title={t("common.signout")}>
              <LogOut className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="app-rail sticky top-0 z-20 md:hidden">
          <div className="flex items-center justify-between px-4 pt-3">
            <span className="flex items-center gap-2 text-white">
              <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="h-7 w-7" />
              <span className="font-display text-lg font-extrabold tracking-wide uppercase">PathToPro</span>
            </span>
            <span className="flex items-center gap-1">
              <Link to="/account" className="tap text-pitch-200 flex h-11 w-11 items-center justify-center" aria-label={t("nav.account")}>
                <Settings className="h-4 w-4" aria-hidden />
              </Link>
              <button onClick={logout} className="tap text-pitch-200 flex items-center gap-1 text-sm" aria-label={t("common.signout")}>
                {user?.name} <LogOut className="h-4 w-4" aria-hidden />
              </button>
            </span>
          </div>
          <nav className="no-scrollbar flex gap-1 overflow-x-auto px-2 pb-1" aria-label="Staff navigation">
            {NAV.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn("tap shrink-0 border-b-[3px] px-3 py-2 text-sm font-bold", isActive ? "border-pitch-300 text-white" : "border-transparent text-white/65")
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
        <main id="main" tabIndex={-1} className="min-w-0 flex-1 p-4 outline-none md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
