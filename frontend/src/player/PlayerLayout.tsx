import {
  CalendarCheck,
  CalendarDays,
  ClipboardCheck,
  Dumbbell,
  Footprints,
  Home,
  Lightbulb,
  LogOut,
  Settings,
  Map,
  Ruler,
  Shield,
  Star,
  TrendingUp,
  Trophy,
  Watch,
} from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { DEMO } from "../shared/api";
import { useAuth } from "../shared/auth";
import { t } from "../shared/i18n";
import { SkipLink } from "../shared/SkipLink";
import { cn } from "../shared/ui";
import { useDocumentTitle } from "../shared/useDocumentTitle";

// Built inside the component so labels follow the current language.
function navFor(selfGuided: boolean) {
  const common = [
    { to: "/player", label: t("nav.today"), icon: Home, end: true },
    { to: "/player/week", label: t("nav.week"), icon: CalendarDays },
    { to: "/player/gym", label: t("nav.gym"), icon: Dumbbell },
  ];
  const career = {
    to: "/player/career",
    label: t("nav.career"),
    icon: Star,
    end: false,
  };
  // Six tabs fit a phone; Road to Pro opens from My card.
  return selfGuided
    ? [
        ...common,
        {
          to: "/player/levels",
          label: t("nav.levels"),
          icon: TrendingUp,
          end: false,
        },
        career,
        {
          to: "/player/growth",
          label: t("nav.growth"),
          icon: Ruler,
          end: false,
        },
      ]
    : [
        ...common,
        career,
        {
          to: "/player/growth",
          label: t("nav.growth"),
          icon: Ruler,
          end: false,
        },
        { to: "/player/card", label: t("nav.card"), icon: Shield, end: false },
      ];
}

// Pages a phone reaches from inside other pages; the desktop sidebar has room to list them.
function extrasFor(selfGuided: boolean) {
  return [
    { to: "/player/skills", label: t("nav.skills"), icon: Footprints },
    { to: "/player/tips", label: t("nav.tips"), icon: Lightbulb },
    { to: "/player/checkin", label: t("nav.checkin"), icon: ClipboardCheck },
    ...(selfGuided
      ? []
      : [{ to: "/player/road", label: t("nav.road"), icon: Map }]),
    // Availability for the team's sessions and matches (academy teams; needs the API)
    ...(selfGuided || DEMO ? [] : [{ to: "/player/team", label: t("nav.myteam"), icon: CalendarCheck }]),
    { to: "/player/devices", label: t("nav.devices"), icon: Watch },
    { to: "/pro", label: t("nav.pro"), icon: Trophy },
  ];
}

// Mobile-first PWA shell, dark by default (players use it in the evening). From tablet
// width up: a sidebar instead of the bottom tabs, and pages lay out in columns.
// The player's initials in a circle of their colour, as staff have in their column
function Avatar({ initials, className }: { initials: string; className?: string }) {
  return (
    <span
      className={cn(
        "bg-pitch-300 text-pitch-950 font-display ring-pitch-300/30 flex shrink-0 items-center justify-center rounded-full font-bold ring-4",
        className,
      )}
      aria-hidden
    >
      {initials}
    </span>
  );
}

export function PlayerLayout() {
  const { user, logout } = useAuth();
  const initials = (user?.name ?? "?").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  const selfGuided = user?.pathway === "amateur";
  const NAV = navFor(selfGuided);
  const EXTRAS = extrasFor(selfGuided);
  useDocumentTitle([...NAV, ...EXTRAS], "Player");
  const link = ({ isActive }: { isActive: boolean }) =>
    cn(
      "tap flex items-center gap-3 rounded-xl px-3 py-2 font-semibold",
      isActive
        ? "relative bg-white/10 text-white before:absolute before:inset-y-2 before:left-0 before:w-1 before:rounded-full before:bg-pitch-300"
        : "text-ink-2 hover:bg-white/5 hover:text-ink",
    );
  return (
    <div className="dark display-headings app-bg text-ink min-h-full md:flex">
      <SkipLink />
      <aside className="bg-surface border-line sticky top-0 hidden h-[calc(100vh-var(--banner-h,0px))] w-60 shrink-0 flex-col border-r p-4 md:flex">
        <div className="mb-6 flex items-center gap-2">
          <img
            src={`${import.meta.env.BASE_URL}icon.svg`}
            alt=""
            className="h-8 w-8"
          />
          <span className="font-display text-xl font-extrabold tracking-wide uppercase">PathToPro</span>
        </div>
        <nav
          aria-label="Player navigation"
          className="flex-1 space-y-1 overflow-y-auto"
        >
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={link}>
              <Icon className="h-5 w-5" aria-hidden /> {label}
            </NavLink>
          ))}
          <div className="border-line my-3 border-t" />
          {EXTRAS.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={link}>
              <Icon className="h-5 w-5" aria-hidden /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-line flex items-center gap-3 border-t pt-3 text-sm">
          <Link to="/account" className="group flex min-w-0 flex-1 items-center gap-3" title={t("nav.account")}>
            <span className="relative">
              <Avatar initials={initials} className="h-9 w-9 text-base" />
              <span className="bg-surface border-line text-ink-2 group-hover:text-ink absolute -right-1.5 -bottom-1.5 flex h-5 w-5 items-center justify-center rounded-full border">
                <Settings className="h-3 w-3" aria-hidden />
              </span>
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-semibold group-hover:underline">{user?.name}</span>
              <span className="text-ink-2 block truncate text-xs">{selfGuided ? "Self-guided player" : "Academy player"}</span>
            </span>
          </Link>
          <button
            onClick={logout}
            className="tap text-ink-2 hover:text-ink flex items-center justify-center"
            aria-label={t("common.signout")}
            title={t("common.signout")}
          >
            <LogOut className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </aside>

      <div className="mx-auto flex min-h-screen w-full max-w-md flex-col md:max-w-6xl">
        <header className="flex items-center justify-between px-4 pt-[max(env(safe-area-inset-top),12px)] pb-2 md:hidden">
          <div className="flex items-center gap-2">
            <img
              src={`${import.meta.env.BASE_URL}icon.svg`}
              alt=""
              className="h-8 w-8"
            />
            <span className="font-display text-xl font-extrabold tracking-wide uppercase">PathToPro</span>
          </div>
          <span className="flex items-center gap-1">
            <Link
              to="/pro"
              className="tap text-ink-2 flex h-11 w-11 items-center justify-center"
              aria-label={t("nav.pro")}
            >
              <Trophy className="h-5 w-5" aria-hidden />
            </Link>
            <Link
              to="/account"
              className="tap flex h-11 w-11 items-center justify-center"
              aria-label={t("nav.account")}
            >
              <Avatar initials={initials} className="h-8 w-8 text-sm" />
            </Link>
            <Link
              to="/player/devices"
              className="tap text-ink-2 flex h-11 w-11 items-center justify-center"
              aria-label="Apple Watch"
            >
              <Watch className="h-5 w-5" aria-hidden />
            </Link>
            <button
              className="tap text-ink-2 flex items-center gap-1 text-sm"
              onClick={logout}
              aria-label={t("common.signout")}
            >
              <LogOut className="h-4 w-4" aria-hidden />
            </button>
          </span>
        </header>
        <main id="main" tabIndex={-1} className="flex-1 px-4 pb-28 outline-none md:px-8 md:pt-6 md:pb-10">
          <Outlet />
        </main>
        <nav
          className="bg-surface border-line fixed inset-x-0 bottom-0 border-t pb-[env(safe-area-inset-bottom)] md:hidden"
          aria-label="Player navigation"
        >
          <ul
            className={cn(
              "mx-auto grid max-w-md",
              NAV.length === 6 ? "grid-cols-6" : "grid-cols-5",
            )}
          >
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      "tap relative flex flex-col items-center justify-center gap-0.5 py-2 text-center text-[10.5px] leading-tight font-semibold",
                      // the active tab gets a bar along the top edge, as in the league apps
                      isActive ? "text-pitch-300 before:bg-pitch-300 before:absolute before:inset-x-3 before:top-0 before:h-[3px] before:rounded-b-full" : "text-ink-2",
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
