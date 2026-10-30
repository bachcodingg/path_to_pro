// The pro-league section's own shell, apart from the staff and player apps: a top bar with
// the competitions as tabs (as on the league websites) and a way back to the user's app.
// Light theme for everyone, players included: it is a reading section, like a league site.
import { ArrowLeft, Trophy } from "lucide-react";
import { useEffect } from "react";
import { Link, NavLink, Outlet, useMatch } from "react-router-dom";
import { homeFor, useAuth } from "../shared/auth";
import { SkipLink } from "../shared/SkipLink";
import { useApi } from "../shared/useApi";
import { cn } from "../shared/ui";
import { COMP_COLOR, ProContext, type Competition } from "./context";

export function ProLayout() {
  const { user } = useAuth();
  const match = useMatch("/pro/:comp/*");
  const comp = match?.params.comp;
  const comps = useApi<Competition[]>("/api/pro/competitions");
  const competition = comps.data?.find((c) => c.id === comp) ?? null;

  useEffect(() => {
    document.title = `${competition ? `${competition.name} · ` : ""}Pro leagues · PathToPro`;
  }, [competition]);

  return (
    <div className="app-bg text-ink min-h-full">
      <SkipLink />
      <header className="sticky top-0 z-30 bg-[#060b1a] text-white shadow-lg">
        <div className="flex items-center justify-between gap-3 px-4 pt-2.5 md:px-6">
          <Link to="/pro" className="flex items-center gap-2.5">
            <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="h-8 w-8" />
            <span className="font-display text-xl font-extrabold tracking-wide uppercase">
              PathToPro <span className="text-pitch-300">Pro leagues</span>
            </span>
          </Link>
          {user && (
            <Link to={homeFor(user.role)} className="tap flex items-center gap-1.5 text-sm font-semibold text-white/80 hover:text-white">
              <ArrowLeft className="h-4 w-4" aria-hidden /> <span className="hidden sm:inline">Back to</span> my app
            </Link>
          )}
        </div>
        <nav aria-label="Competitions" className="no-scrollbar mt-1 flex gap-1 overflow-x-auto px-2 md:px-4">
          <NavLink
            to="/pro"
            end
            className={({ isActive }) =>
              cn("tap flex shrink-0 items-center gap-1.5 border-b-[3px] px-3 py-2 text-sm font-bold", isActive ? "border-pitch-300" : "border-transparent text-white/65 hover:text-white")
            }
          >
            <Trophy className="h-4 w-4" aria-hidden /> All
          </NavLink>
          {comps.data?.map((c) => (
            <NavLink
              key={c.id}
              to={`/pro/${c.id}`}
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
