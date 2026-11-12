// The Pro League app's shell: a top bar with the competitions as tabs (as on the league
// websites), a link over to PathToPro, and sign-out. Light theme for everyone: it is for
// reading, like a league site.
import { ArrowUpRight, LogOut, Trophy, Users } from "lucide-react";
import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation, useMatch } from "react-router-dom";
import { APPS } from "../shared/apps";
import { useAuth } from "../shared/auth";
import { SkipLink } from "../shared/SkipLink";
import { useApi } from "../shared/useApi";
import { cn } from "../shared/ui";
import { COMP_COLOR, ProContext, type Competition } from "./context";

export function LeaguesLayout() {
  const { user, logout } = useAuth();
  const match = useMatch("/:comp/*");
  const comp = match?.params.comp;
  const comps = useApi<Competition[]>("/api/pro/competitions");
  const competition = comps.data?.find((c) => c.id === comp) ?? null;

  // A new page starts at its top, not where the last one was scrolled to
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  useEffect(() => {
    document.title = `${competition ? `${competition.name} · ` : ""}${APPS.leagues.name}`;
  }, [competition]);

  return (
    <div className="app-bg text-ink min-h-full">
      <SkipLink />
      <header className="sticky top-0 z-30 bg-[#060b1a] text-white shadow-lg">
        <div className="flex items-center justify-between gap-3 px-4 pt-2.5 md:px-6">
          <Link to="/" className="flex min-w-0 items-center gap-2.5" aria-label={`${APPS.leagues.name}, all competitions`}>
            <img src={APPS.leagues.icon} alt="" className="h-8 w-8" />
            <span className="font-display truncate text-xl font-extrabold tracking-wide uppercase">
              Pro League <span className="text-pitch-300 hidden sm:inline">Data Tracking</span>
            </span>
          </Link>
          <span className="flex shrink-0 items-center gap-1">
            <a
              href={APPS.pathtopro.url}
              aria-label="Open PathToPro"
              className="tap flex items-center gap-1.5 rounded-md px-2 text-sm font-semibold text-white/80 hover:bg-white/10 hover:text-white"
            >
              <img src={APPS.pathtopro.icon} alt="" className="h-5 w-5" />
              <span>
                Open <span className="hidden sm:inline">PathToPro</span>
              </span>
              <ArrowUpRight className="h-4 w-4" aria-hidden />
            </a>
            {user && (
              <button
                onClick={logout}
                aria-label="Sign out"
                className="tap flex items-center gap-1.5 rounded-md px-2 text-sm font-semibold text-white/80 hover:bg-white/10 hover:text-white"
                title={`Signed in as ${user.name}`}
              >
                <LogOut className="h-4 w-4" aria-hidden /> <span className="hidden sm:inline">Sign out</span>
              </button>
            )}
          </span>
        </div>
        <nav aria-label="Competitions" className="no-scrollbar mt-1 flex gap-1 overflow-x-auto px-2 md:px-4">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              cn("tap flex shrink-0 items-center gap-1.5 border-b-[3px] px-3 py-2 text-sm font-bold", isActive ? "border-pitch-300" : "border-transparent text-white/65 hover:text-white")
            }
          >
            <Trophy className="h-4 w-4" aria-hidden /> All
          </NavLink>
          <NavLink
            to="/players"
            className={({ isActive }) =>
              cn("tap flex shrink-0 items-center gap-1.5 border-b-[3px] px-3 py-2 text-sm font-bold", isActive ? "border-pitch-300" : "border-transparent text-white/95 hover:text-white")
            }
          >
            <Users className="h-4 w-4" aria-hidden /> Players
          </NavLink>
          {comps.data?.map((c) => (
            <NavLink
              key={c.id}
              to={`/${c.id}`}
              className={({ isActive }) =>
                cn("tap flex shrink-0 items-center gap-2 border-b-[3px] px-3 py-2 text-sm font-bold", isActive ? "text-white" : "border-transparent text-white/65 hover:text-white")
              }
              style={({ isActive }) => (isActive ? { borderColor: COMP_COLOR[c.id] } : undefined)}
            >
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: COMP_COLOR[c.id] }} aria-hidden />
              {c.name}
            </NavLink>
          ))}
        </nav>
      </header>
      <main id="main" tabIndex={-1} className="p-4 outline-none md:p-6">
        <ProContext.Provider value={{ comp: comp ?? "la-liga", competition }}>
          <Outlet />
        </ProContext.Provider>
      </main>
    </div>
  );
}
