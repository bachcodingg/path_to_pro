// Overview page before sign-in: what PathToPro does, for whom, how it stays safe, and one-click
// demo accounts. Night-pitch look of the app; the mock screens are drawn from the demo season.
import {
  Activity,
  ArrowRight,
  CalendarCog,
  Check,
  ChevronDown,
  ClipboardList,
  CodeXml,
  Cpu,
  Database,
  Eye,
  Heart,
  LockKeyhole,
  Moon,
  Mountain,
  ShieldAlert,
  Smartphone,
  Sparkles,
  Stethoscope,
  Target,
  Trophy,
  Watch,
  X,
  type LucideIcon,
} from "lucide-react";
import { MotionConfig, motion } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../shared/auth";
import { COMP_COLOR } from "../pro/context";
import { Button, cn } from "../shared/ui";

const SOURCE = "https://github.com/bachcodingg/path_to_pro";

// Fades a block up as it scrolls into view (skipped for reduced motion by MotionConfig)
function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

function SectionHead({ eyebrow, title, lead, center }: { eyebrow: string; title: ReactNode; lead?: ReactNode; center?: boolean }) {
  return (
    <Reveal className={cn("max-w-3xl", center && "mx-auto text-center")}>
      <p className="text-pitch-300 text-xs font-bold tracking-[0.18em] uppercase">{eyebrow}</p>
      <h2 className="font-display mt-2 text-4xl leading-[0.95] font-extrabold uppercase md:text-6xl">{title}</h2>
      {lead && <p className="mt-4 text-base text-white/70 md:text-lg">{lead}</p>}
    </Reveal>
  );
}

// Signs in with a demo account and opens its home; if demo accounts are off, the sign-in page
function useTryAs() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);
  async function tryAs(email: string) {
    setBusy(email);
    try {
      const u = await login(email, "demo1234");
      nav("mfaToken" in u ? "/login" : homeFor(u.role));
    } catch {
      nav("/login");
    } finally {
      setBusy(null);
    }
  }
  return { tryAs, busy };
}

export function Landing() {
  useEffect(() => {
    document.title = "PathToPro · Train smart, grow safe";
  }, []);
  return (
    <MotionConfig reducedMotion="user">
      <div id="landing" className="dark bg-pitch-950 min-h-full overflow-x-clip text-white">
        <Header />
        <main>
          <Hero />
          <Ticker />
          <BuiltWith />
          <Scoreboard />
          <HowItWorks />
          <Roles />
          <Safety />
          <Pathway />
          <ProLeagues />
          <Faq />
          <FinalCta />
        </main>
        <Footer />
      </div>
    </MotionConfig>
  );
}

// --------------------------------------------------------------------------- header

const ANCHORS = [
  ["#how", "How it works"],
  ["#roles", "Who it's for"],
  ["#safety", "Safety"],
  ["#pro", "Pro leagues"],
  ["#faq", "FAQ"],
] as const;

function Header() {
  return (
    <header className="bg-pitch-950/75 sticky top-0 z-30 border-b border-white/10 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 md:px-6">
        <a href="#top" className="flex items-center gap-2.5">
          <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="h-8 w-8" />
          <span className="font-display text-xl font-extrabold tracking-wide uppercase">PathToPro</span>
        </a>
        <nav aria-label="Sections" className="hidden items-center gap-1 lg:flex">
          {ANCHORS.map(([href, label]) => (
            <a key={href} href={href} className="rounded-lg px-3 py-2 text-sm font-semibold text-white/70 transition-colors hover:bg-white/5 hover:text-white">
              {label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Link to="/login" className="tap hidden items-center rounded-xl px-3 text-sm font-semibold text-white/80 hover:text-white sm:inline-flex">
            Sign in
          </Link>
          <Link to="/login" className="tap bg-pitch-300 text-pitch-950 hover:bg-pitch-200 inline-flex items-center gap-1.5 rounded-xl px-4 text-sm font-bold transition-colors">
            Try the demo <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        </div>
      </div>
    </header>
  );
}

// --------------------------------------------------------------------------- hero

function Hero() {
  return (
    <section id="top" className="hero relative isolate overflow-hidden">
      <PitchBackdrop />
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 pt-14 pb-20 md:px-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:pt-20 lg:pb-28">
        <div>
          <Reveal>
            <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-semibold text-white/80">
              <span className="bg-pitch-300 h-1.5 w-1.5 rounded-full shadow-[0_0_10px_2px_rgb(126_224_168/0.7)]" aria-hidden />
              For academy players aged 13 to 18, their coaches and families
            </p>
          </Reveal>
          <Reveal delay={0.05}>
            <h1 className="font-display mt-5 text-[3.4rem] leading-[0.88] font-extrabold uppercase sm:text-7xl xl:text-[5.6rem]">
              Your week,
              <br />
              rebuilt
              <br />
              <span className="from-pitch-200 to-pitch-400 bg-gradient-to-r bg-clip-text text-transparent">overnight.</span>
            </h1>
          </Reveal>
          <Reveal delay={0.1}>
            <p className="mt-6 max-w-xl text-lg text-white/75">
              PathToPro watches each young footballer's load, growth and recovery, and rebuilds next week's plan before problems
              happen. Coaches approve the risky changes. Players always see why.
            </p>
          </Reveal>
          <Reveal delay={0.15} className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              to="/login"
              className="bg-pitch-300 text-pitch-950 hover:bg-pitch-200 inline-flex h-13 items-center gap-2 rounded-xl px-6 text-base font-bold shadow-[0_8px_30px_-6px_rgb(126_224_168/0.55)] transition-colors"
            >
              Try the live demo <ArrowRight className="h-5 w-5" aria-hidden />
            </Link>
            <a href="#how" className="inline-flex h-13 items-center gap-2 rounded-xl border border-white/20 px-6 text-base font-semibold hover:bg-white/5">
              See how it works
            </a>
          </Reveal>
          <Reveal delay={0.2}>
            <p className="mt-5 flex flex-wrap gap-x-5 gap-y-1 text-sm text-white/55">
              {["No account needed", "Synthetic players", "Free plan outside an academy"].map((t) => (
                <span key={t} className="flex items-center gap-1.5">
                  <Check className="text-pitch-300 h-4 w-4" aria-hidden /> {t}
                </span>
              ))}
            </p>
          </Reveal>
        </div>
        <HeroVisual />
      </div>
    </section>
  );
}

// Half a pitch drawn in light lines behind the hero, with a floodlight glow
function PitchBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden>
      <div className="absolute -top-40 right-[-10%] h-[38rem] w-[38rem] rounded-full bg-[radial-gradient(circle,rgb(126_224_168/0.22),transparent_65%)]" />
      <svg viewBox="0 0 600 400" className="absolute right-[-12rem] bottom-[-6rem] w-[64rem] max-w-none opacity-[0.12]" fill="none" stroke="white" strokeWidth={1.5}>
        <rect x={10} y={10} width={580} height={380} rx={4} />
        <line x1={300} y1={10} x2={300} y2={390} />
        <circle cx={300} cy={200} r={62} />
        <circle cx={300} cy={200} r={3} fill="white" />
        <rect x={490} y={100} width={100} height={200} />
        <rect x={550} y={150} width={40} height={100} />
        <path d="M490 160 a 50 50 0 0 0 0 80" />
      </svg>
    </div>
  );
}

function HeroVisual() {
  return (
    <div className="relative mx-auto w-full max-w-[30rem] lg:mx-0 lg:ml-auto">
      <Reveal delay={0.1}>
        <Phone />
      </Reveal>
      <motion.div
        className="absolute top-36 hidden w-52 sm:-left-16 sm:block lg:-left-24"
        animate={{ y: [0, -8, 0] }}
        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
      >
        <FloatCard>
          <p className="text-[10px] font-bold tracking-wider text-white/50 uppercase">Substitution board</p>
          <p className="mt-0.5 text-sm font-bold">Lighter week for Leon U.</p>
          <div className="mt-2 grid grid-cols-5 gap-1 text-center text-[9px] font-bold">
            {[
              ["Tue", "bg-pitch-200 text-pitch-900"],
              ["Wed", "bg-pitch-200 text-pitch-900"],
              ["Thu", "bg-pitch-400 text-pitch-950"],
              ["Fri", "bg-white/10 text-white/60"],
              ["Sat", "bg-pitch-900 text-white ring-1 ring-white/20"],
            ].map(([d, c]) => (
              <span key={d} className={cn("rounded py-1", c)}>
                {d}
              </span>
            ))}
          </div>
          <p className="bg-pitch-600 mt-2 inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-bold text-white">
            <Check className="h-3.5 w-3.5" aria-hidden /> Approved by the coach
          </p>
        </FloatCard>
      </motion.div>
      <motion.div
        className="absolute top-[58%] hidden w-52 sm:-right-16 sm:block lg:-right-24"
        animate={{ y: [0, 8, 0] }}
        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1 }}
      >
        <FloatCard>
          <p className="flex items-center gap-1.5 text-[10px] font-bold tracking-wider text-white/50 uppercase">
            <Moon className="h-3 w-3" aria-hidden /> Overnight, 02:14
          </p>
          <p className="mt-1 text-sm leading-snug">
            <b>Planner</b> rebuilt Leon's week: ACWR 1.61, sleep under 6 h three nights.
          </p>
        </FloatCard>
      </motion.div>
    </div>
  );
}

function FloatCard({ children }: { children: ReactNode }) {
  return <div className="rounded-2xl border border-white/15 bg-[#111b30]/90 p-3 shadow-2xl shadow-black/40 backdrop-blur">{children}</div>;
}

// The player's "Today" screen for Leon, the demo's tired U15 in his growth spurt
function Phone() {
  return (
    <div className="mx-auto w-[17.5rem] rounded-[2.6rem] border border-white/15 bg-black p-2.5 shadow-[0_30px_80px_-20px_rgb(0_0_0/0.8)] sm:w-[19rem]">
      <div className="relative overflow-hidden rounded-[2.1rem] bg-[#0b1f17] px-4 pt-3 pb-5">
        <div className="mx-auto mb-3 h-5 w-24 rounded-full bg-black" aria-hidden />
        <p className="text-[11px] text-white/50">Thursday 26 November</p>
        <p className="font-display text-3xl leading-none font-extrabold uppercase">Hi Leon</p>
        <div className="mt-3 rounded-2xl border border-white/10 bg-[#111b30] p-3">
          <div className="flex items-center gap-3">
            <div className="relative h-11 flex-1 rounded-lg border-2 border-white/40 p-0.5">
              <div className="bg-recover h-full w-[42%] rounded-md" />
              <div className="absolute top-1/2 -right-1.5 h-4 w-1 -translate-y-1/2 rounded-r bg-white/40" />
            </div>
            <div className="text-right">
              <p className="text-2xl leading-none font-extrabold">42</p>
              <p className="text-recover text-[11px] font-bold">Recover</p>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {["Short sleep", "Growth zone", "Load jumped"].map((c) => (
              <span key={c} className="rounded-full border border-white/15 px-2 py-0.5 text-[10px] font-semibold text-white/80">
                {c}
              </span>
            ))}
          </div>
        </div>
        <p className="font-display mt-4 text-sm font-bold tracking-wide uppercase">Today's session</p>
        <div className="mt-1.5 flex items-center gap-3 rounded-2xl border border-white/10 bg-[#111b30] p-3">
          <span className="bg-pitch-200 text-pitch-900 flex h-10 w-10 items-center justify-center rounded-xl text-base font-extrabold">2</span>
          <span>
            <span className="block text-sm font-bold">Recovery</span>
            <span className="block text-[11px] text-white/55">30 min · effort 2/10</span>
          </span>
        </div>
        <div className="border-pitch-500/40 bg-pitch-900/50 mt-2 rounded-2xl border p-3">
          <p className="text-pitch-300 text-[11px] font-bold">Why is today easy?</p>
          <p className="mt-0.5 text-[11px] leading-snug text-white/75">
            Sleep under 6 h three nights and your training load jumped. In the growth zone, so no jumps or sprints this week.
          </p>
        </div>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- ticker

const TICKER: [LucideIcon, string, string][] = [
  [CalendarCog, "Planner", "Leon U.'s week rebuilt: load 825 AU, ACWR 1.61"],
  [ShieldAlert, "Coordinator", "Noah H. reported pain: escalated to staff, agents took no action"],
  [Target, "Development Coach", "Nico Y.: goals endurance and jump power, 4 drills picked"],
  [Eye, "Monitor", "Jan M. in the growth zone (+0.7 y from PHV): no change needed"],
  [Check, "Coach", "Approved: lighter week for Luca J., HRV -2.5 SD"],
  [CalendarCog, "Planner", "Ben Q.: match minutes capped at 45' after a load spike"],
];

// A broadcast-style crawl of what the agents did overnight (the app's "Match commentary")
function Ticker() {
  const items = [...TICKER, ...TICKER];
  return (
    <div className="border-y border-white/10 bg-black/30" aria-label="Overnight agent actions from the demo season">
      <div className="mx-auto flex max-w-7xl items-stretch">
        <p className="bg-pitch-300 text-pitch-950 font-display z-10 flex shrink-0 items-center gap-2 px-4 text-sm font-extrabold tracking-wider uppercase">
          <span className="bg-recover h-2 w-2 animate-pulse rounded-full" aria-hidden /> Night shift
        </p>
        <div className="relative min-w-0 flex-1 overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_6%,black_94%,transparent)]">
          <ul className="animate-marquee flex w-max gap-10 py-3 hover:[animation-play-state:paused] motion-reduce:animate-none">
            {items.map(([Icon, who, text], i) => (
              <li key={i} className="flex items-center gap-2 text-sm whitespace-nowrap" aria-hidden={i >= TICKER.length}>
                <Icon className="text-pitch-300 h-4 w-4" aria-hidden />
                <b className="font-semibold">{who}</b>
                <span className="text-white/65">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- built with + numbers

function BuiltWith() {
  const items: [LucideIcon, string][] = [
    [Watch, "Apple Watch and Apple Health"],
    [Cpu, "OR-Tools CP-SAT solver"],
    [Database, "StatsBomb Open Data"],
    [Sparkles, "Claude, optional"],
    [Smartphone, "Installs as an app (PWA)"],
  ];
  return (
    <section className="mx-auto max-w-7xl px-4 py-10 md:px-6">
      <p className="text-center text-xs font-bold tracking-[0.18em] text-white/45 uppercase">Works with</p>
      <ul className="mt-4 flex flex-wrap justify-center gap-x-8 gap-y-3">
        {items.map(([Icon, label]) => (
          <li key={label} className="flex items-center gap-2 text-sm font-semibold text-white/70">
            <Icon className="h-4 w-4 text-white/45" aria-hidden /> {label}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Scoreboard() {
  const stats = [
    ["30 s", "Morning check-in", "Four quick questions, on the phone"],
    ["9", "Hard safety rules", "Checked on every plan, every night"],
    ["38", "Ball-skill drills", "A session for each position"],
    ["1,185", "Pro matches", "Five competitions to study"],
  ];
  return (
    <section className="mx-auto max-w-7xl px-4 pb-6 md:px-6">
      <Reveal>
        <div className="grid grid-cols-2 overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-b from-white/[0.06] to-white/[0.02] lg:grid-cols-4">
          {stats.map(([value, label, sub], i) => (
            <div key={label} className={cn("p-6 md:p-8", i % 2 === 1 && "border-l border-white/10", i >= 2 && "border-t border-white/10 lg:border-t-0", i === 2 && "lg:border-l")}>
              <p className="font-display num text-pitch-200 text-5xl leading-none font-extrabold md:text-6xl">{value}</p>
              <p className="mt-2 font-bold">{label}</p>
              <p className="text-sm text-white/55">{sub}</p>
            </div>
          ))}
        </div>
      </Reveal>
    </section>
  );
}

// --------------------------------------------------------------------------- how it works

const STEPS: [LucideIcon, string, string, string][] = [
  [Activity, "07:30", "Check in", "Sleep, soreness, mood and fatigue in under 30 seconds. A watch adds heart-rate variability if there is one."],
  [Eye, "02:00", "Monitor spots it", "Load spikes, short sleep, low HRV and the growth zone each become a flag, with the number behind it."],
  [CalendarCog, "02:01", "Planner rebuilds the week", "A solver re-plans the next seven days around matches and school, inside nine hard safety rules."],
  [ClipboardList, "07:45", "The coach decides", "A fixed policy says who approves. Small changes apply and the coach is told; bigger ones wait for a click."],
];

const POLICY: [string, string, string][] = [
  ["Effort up or down by 1 point", "Applied, coach notified", "text-white/80"],
  ["A session swap or a load cut", "Coach approves", "text-pitch-300"],
  ["A safety flag, such as pain", "Staff only, agents take no action", "text-recover"],
];

function HowItWorks() {
  return (
    <section id="how" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20 md:px-6 md:py-28">
      <SectionHead
        eyebrow="How it works"
        title={
          <>
            One loop. <span className="text-pitch-300">Every night.</span>
          </>
        }
        lead="Four agents work the night shift. Code computes, the language model plans and explains, and a fixed policy decides who approves."
      />
      <ol className="relative mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <span className="via-pitch-400/50 absolute top-7 right-8 left-8 hidden h-px bg-gradient-to-r from-transparent to-transparent lg:block" aria-hidden />
        {STEPS.map(([Icon, time, title, text], i) => (
          <Reveal key={title} delay={i * 0.08}>
            <li className="relative h-full rounded-3xl border border-white/10 bg-white/[0.03] p-5">
              <div className="flex items-center justify-between">
                <span className="bg-pitch-950 border-pitch-400/50 text-pitch-300 relative flex h-14 w-14 items-center justify-center rounded-2xl border">
                  <Icon className="h-6 w-6" aria-hidden />
                </span>
                <span className="font-display num text-2xl font-bold text-white/30">{time}</span>
              </div>
              <p className="font-display mt-5 text-2xl font-bold uppercase">
                <span className="text-pitch-300 mr-2">{i + 1}</span>
                {title}
              </p>
              <p className="mt-2 text-sm text-white/65">{text}</p>
            </li>
          </Reveal>
        ))}
      </ol>
      <Reveal className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <blockquote className="from-pitch-800/60 flex flex-col justify-center rounded-3xl border border-white/10 bg-gradient-to-br to-transparent p-7">
          <p className="font-display text-3xl leading-tight font-bold uppercase md:text-4xl">
            "Code computes. The LLM plans and explains. <span className="text-pitch-300">A fixed policy decides who approves.</span>"
          </p>
          <footer className="mt-3 text-sm text-white/55">The design principle behind every agent</footer>
        </blockquote>
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-black/30">
          <p className="flex items-center gap-2 border-b border-white/10 px-5 py-3 font-mono text-xs text-white/50">
            <LockKeyhole className="h-3.5 w-3.5" aria-hidden /> approval policy
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-white/45 uppercase">
                <th className="px-5 pt-3 pb-1 font-semibold">When the plan changes by</th>
                <th className="px-5 pt-3 pb-1 font-semibold">Who decides</th>
              </tr>
            </thead>
            <tbody>
              {POLICY.map(([change, who, tone]) => (
                <tr key={change} className="border-t border-white/5">
                  <td className="px-5 py-3.5 font-semibold">{change}</td>
                  <td className={cn("px-5 py-3.5 font-mono text-[13px]", tone)}>{who}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="border-t border-white/10 px-5 py-3 text-xs text-white/45">
            Every change, applied or not, appears in the coach's match commentary with its reason.
          </p>
        </div>
      </Reveal>
    </section>
  );
}

// --------------------------------------------------------------------------- roles

type RoleKey = "player" | "coach" | "family" | "physio";
const ROLES: Record<RoleKey, { icon: LucideIcon; tab: string; title: string; points: string[]; demo: string; demoLabel: string }> = {
  player: {
    icon: Activity,
    tab: "Players",
    title: "A plan that listens to your body",
    points: [
      "A readiness battery every morning from sleep, HRV and a 30-second check-in",
      "Today's session with a Why-card whenever the plan changed",
      "Gym and ball skills for your position, adjusted for your growth stage",
      "Match diary, ratings with reasons, and a player card with percentiles",
    ],
    demo: "p15@demo.pathtopro",
    demoLabel: "Try as Leon, U15",
  },
  coach: {
    icon: ClipboardList,
    tab: "Coaches",
    title: "The whole squad on one screen",
    points: [
      "Dressing room: 14 days of readiness, the risky days stand out",
      "Substitution board: approve, edit or reject a plan with one key",
      "Training pitch checks a team session against every player's limits",
      "Plain-words notes: \"Keep Anton light until Thursday\" becomes a plan change",
    ],
    demo: "coach@demo.pathtopro",
    demoLabel: "Try as the coach",
  },
  family: {
    icon: Heart,
    tab: "Families",
    title: "Peace of mind, not surveillance",
    points: [
      "The week at a glance: sessions done, average sleep, check-in streak",
      "Consent per data type: check-in, sleep, heart rate, growth, tests",
      "Under 16, check-ins wait until a parent has linked with an invite code",
      "Academy fees and what is due, in the same place",
    ],
    demo: "guardian02@demo.pathtopro",
    demoLabel: "Try as a parent",
  },
  physio: {
    icon: Stethoscope,
    tab: "Physios",
    title: "Pain goes to a person, straight away",
    points: [
      "Escalation queue: pain reports and red check-ins, oldest first",
      "The agents take no action on these: they are yours",
      "A growth-zone list of who is closest to their growth spurt",
      "Acknowledge with one click once you have spoken to the player",
    ],
    demo: "physio@demo.pathtopro",
    demoLabel: "Try as the physio",
  },
};

function Roles() {
  const [role, setRole] = useState<RoleKey>("player");
  const { tryAs, busy } = useTryAs();
  const r = ROLES[role];
  return (
    <section id="roles" className="relative scroll-mt-20 border-y border-white/10 bg-[#0b1428] py-20 md:py-28">
      <div className="mx-auto max-w-7xl px-4 md:px-6">
        <SectionHead
          center
          eyebrow="Who it's for"
          title="One app, four views"
          lead="Everyone around a young player sees what they need, and nothing they should not."
        />
        <div role="tablist" aria-label="Who it's for" className="mx-auto mt-10 flex w-fit max-w-full gap-1 overflow-x-auto rounded-2xl border border-white/10 bg-black/30 p-1">
          {(Object.keys(ROLES) as RoleKey[]).map((k) => {
            const Icon = ROLES[k].icon;
            return (
              <button
                key={k}
                role="tab"
                id={`tab-${k}`}
                aria-selected={role === k}
                aria-controls="role-panel"
                onClick={() => setRole(k)}
                className={cn(
                  "tap flex shrink-0 items-center gap-2 rounded-xl px-4 text-sm font-bold transition-colors",
                  role === k ? "bg-pitch-300 text-pitch-950" : "text-white/65 hover:text-white",
                )}
              >
                <Icon className="h-4 w-4" aria-hidden /> {ROLES[k].tab}
              </button>
            );
          })}
        </div>
        <motion.div
          key={role}
          id="role-panel"
          role="tabpanel"
          aria-labelledby={`tab-${role}`}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="mt-8 grid items-center gap-8 rounded-3xl border border-white/10 bg-white/[0.03] p-6 md:p-10 lg:grid-cols-2"
        >
          <div>
            <h3 className="font-display text-3xl font-bold uppercase md:text-4xl">{r.title}</h3>
            <ul className="mt-5 space-y-3">
              {r.points.map((p) => (
                <li key={p} className="flex gap-3 text-white/80">
                  <span className="bg-pitch-300/15 text-pitch-300 mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full">
                    <Check className="h-3.5 w-3.5" aria-hidden />
                  </span>
                  {p}
                </li>
              ))}
            </ul>
            <Button className="bg-pitch-300 text-pitch-950 hover:bg-pitch-200 mt-7" loading={busy === r.demo} disabled={!!busy} onClick={() => tryAs(r.demo)}>
              {r.demoLabel} <ArrowRight className="h-4 w-4" aria-hidden />
            </Button>
          </div>
          <div className="flex justify-center">
            {role === "player" && <MiniPlayer />}
            {role === "coach" && <MiniHeatmap />}
            {role === "family" && <MiniFamily />}
            {role === "physio" && <MiniPhysio />}
          </div>
        </motion.div>
      </div>
    </section>
  );
}

function MockFrame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="w-full max-w-md overflow-hidden rounded-2xl border border-white/10 bg-[#111b30] shadow-2xl shadow-black/40">
      <div className="flex items-center gap-1.5 border-b border-white/10 px-4 py-2.5">
        {["bg-white/20", "bg-white/15", "bg-white/10"].map((c) => (
          <span key={c} className={cn("h-2.5 w-2.5 rounded-full", c)} aria-hidden />
        ))}
        <span className="ml-2 text-xs font-semibold text-white/50">{title}</span>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function MiniPlayer() {
  const attrs = [
    ["82", "Speed"],
    ["45", "Power"],
    ["64", "Endurance"],
  ];
  return (
    <MockFrame title="My card">
      <div className="from-pitch-800 to-pitch-950 rounded-2xl border-2 border-amber-400/80 bg-gradient-to-br p-4">
        <p className="text-4xl leading-none font-extrabold">68</p>
        <p className="text-pitch-200 text-[11px] font-semibold uppercase">avg percentile</p>
        <p className="mt-3 text-xl font-extrabold">Leon U.</p>
        <p className="text-pitch-200 text-xs">Compared with players in their growth spurt</p>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {attrs.map(([v, l]) => (
            <div key={l} className="rounded-xl bg-white/10 py-2 text-center">
              <p className="text-xl font-extrabold">{v}</p>
              <p className="text-[10px] font-semibold tracking-wide uppercase">{l}</p>
            </div>
          ))}
        </div>
      </div>
    </MockFrame>
  );
}

// A corner of the Dressing room: tints for ready and take-care days, solid orange to recover
function MiniHeatmap() {
  const rows: [string, number[]][] = [
    ["Anton S.", [54, 82, 56, 67, 50, 35, 71]],
    ["Ben Q.", [89, 64, 49, 39, 66, 89, 85]],
    ["David W.", [40, 79, 72, 39, 70, 44, 79]],
    ["Elias O.", [57, 68, 29, 42, 38, 57, 70]],
    ["Emil L.", [67, 57, 43, 83, 49, 64, 88]],
  ];
  const cell = (v: number) => (v >= 70 ? "bg-ready/25 text-[#7fb2f0]" : v >= 50 ? "bg-caution/25 text-caution" : "bg-recover text-white");
  return (
    <MockFrame title="Dressing room">
      <table className="w-full border-separate border-spacing-1 text-[11px]">
        <tbody>
          {rows.map(([name, vals]) => (
            <tr key={name}>
              <th scope="row" className="pr-1 text-left font-semibold whitespace-nowrap text-white/80">
                {name}
              </th>
              {vals.map((v, i) => (
                <td key={i} className={cn("rounded-md py-2 text-center font-bold", cell(v))}>
                  {v}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </MockFrame>
  );
}

function MiniFamily() {
  return (
    <MockFrame title="Family · Noah H.">
      <div className="grid grid-cols-3 text-center">
        {[
          ["3", "sessions done"],
          ["6.7", "avg sleep (h)"],
          ["9", "check-in streak"],
        ].map(([v, l]) => (
          <div key={l}>
            <p className="text-3xl font-extrabold">{v}</p>
            <p className="text-xs text-white/55">{l}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 space-y-2 border-t border-white/10 pt-3">
        {["Morning check-in", "Sleep duration", "Heart-rate variability"].map((l) => (
          <div key={l} className="flex items-center justify-between text-sm">
            <span className="text-white/80">{l}</span>
            <span className="bg-pitch-500 flex h-6 w-11 items-center justify-end rounded-full p-0.5" aria-hidden>
              <span className="h-5 w-5 rounded-full bg-white" />
            </span>
          </div>
        ))}
      </div>
    </MockFrame>
  );
}

function MiniPhysio() {
  return (
    <MockFrame title="Physio queue">
      <div className="border-recover/50 rounded-xl border border-l-4 bg-white/[0.03] p-3">
        <p className="text-recover text-[11px] font-bold uppercase">Pain reported</p>
        <p className="font-bold">Noah H.</p>
        <p className="text-xs text-white/55">In this queue within a second of the check-in</p>
        <span className="bg-pitch-600 mt-3 inline-flex rounded-lg px-3 py-1.5 text-xs font-bold">I've spoken to them</span>
      </div>
      <p className="font-display mt-4 text-sm font-bold tracking-wide uppercase">Growth zone (PHV) list</p>
      <div className="mt-1 divide-y divide-white/10 text-sm">
        {[
          ["Leon U.", "+0.1 y"],
          ["Max N.", "-0.2 y"],
          ["Ben Q.", "+0.3 y"],
        ].map(([n, v]) => (
          <div key={n} className="flex justify-between py-1.5">
            <span>{n}</span>
            <span className="text-caution font-bold">{v}</span>
          </div>
        ))}
      </div>
    </MockFrame>
  );
}

// --------------------------------------------------------------------------- safety

const COMPARE: [string, string | boolean, string][] = [
  ["Adapts to sleep and recovery", false, "Every night, from the morning check-in"],
  ["Knows about the growth spurt", false, "Limits jumps, sprints and heavy gym work"],
  ["Explains each change", false, "A Why-card with the numbers behind it"],
  ["Coach stays in charge", true, "A fixed approval policy, never the model"],
  ["Works without AI", true, "Rule-based agents when there is no API key"],
];

function Safety() {
  return (
    <section id="safety" className="mx-auto grid max-w-7xl scroll-mt-20 items-center gap-12 px-4 py-20 md:px-6 md:py-28 lg:grid-cols-2">
      <div>
        <SectionHead
          eyebrow="Safety first"
          title={
            <>
              Growth spurt? <span className="text-pitch-300">The plan knows.</span>
            </>
          }
          lead="Around the growth spurt (peak height velocity), young players are more vulnerable to overload. PathToPro estimates each player's growth stage and adapts the week, so the hardest sessions never land on the worst days."
        />
        <Reveal delay={0.1}>
          <GrowthCurve />
        </Reveal>
      </div>
      <Reveal delay={0.05}>
        <div className="overflow-hidden rounded-3xl border border-white/10">
          <table className="w-full text-sm">
            <thead className="bg-white/[0.04]">
              <tr className="text-left">
                <th className="px-4 py-3 font-semibold text-white/60" />
                <th className="px-3 py-3 text-center font-semibold text-white/60">A fixed plan</th>
                <th className="text-pitch-300 px-4 py-3 font-display text-lg font-bold uppercase">PathToPro</th>
              </tr>
            </thead>
            <tbody>
              {COMPARE.map(([what, fixed, ours]) => (
                <tr key={what} className="border-t border-white/10">
                  <th scope="row" className="px-4 py-4 text-left font-semibold">
                    {what}
                  </th>
                  <td className="px-3 py-4 text-center">
                    {fixed ? <Check className="mx-auto h-5 w-5 text-white/50" aria-label="Yes" /> : <X className="mx-auto h-5 w-5 text-white/30" aria-label="No" />}
                  </td>
                  <td className="bg-pitch-300/[0.06] px-4 py-4">
                    <span className="flex gap-2">
                      <Check className="text-pitch-300 h-5 w-5 shrink-0" aria-hidden />
                      <span className="text-white/80">{ours}</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Reveal>
    </section>
  );
}

// Height against age with the growth zone shaded, as on the player's Growth page
function GrowthCurve() {
  return (
    <figure className="mt-8 rounded-3xl border border-white/10 bg-white/[0.03] p-4">
      <svg viewBox="0 0 320 140" className="w-full" role="img" aria-label="Height rises fastest in the growth zone; the player is inside it">
        <rect x={120} y={8} width={90} height={112} fill="#e3a008" opacity={0.15} rx={4} />
        <text x={165} y={22} textAnchor="middle" fill="#e3a008" fontSize={10} fontWeight={700}>
          Growth zone
        </text>
        {[40, 80, 120].map((y) => (
          <line key={y} x1={10} x2={310} y1={y} y2={y} stroke="rgb(255 255 255 / 0.07)" />
        ))}
        <path d="M10 118 C 70 112, 110 104, 140 84 S 200 34, 230 26 S 290 18, 310 16" fill="none" stroke="var(--brand-300)" strokeWidth={3} strokeLinecap="round" />
        <circle cx={150} cy={74} r={6} fill="#fff" stroke="var(--brand-500)" strokeWidth={3} />
        <text x={150} y={60} textAnchor="middle" fill="#fff" fontSize={10} fontWeight={700}>
          You
        </text>
        <text x={10} y={136} fill="rgb(255 255 255 / 0.45)" fontSize={9}>
          Age 12
        </text>
        <text x={310} y={136} textAnchor="end" fill="rgb(255 255 255 / 0.45)" fontSize={9}>
          Age 17
        </text>
      </svg>
      <figcaption className="mt-1 text-xs text-white/50">Illustration: height speeds up, then levels off. The shaded weeks get extra care.</figcaption>
    </figure>
  );
}

// --------------------------------------------------------------------------- pathway

const LEVELS = ["Starter", "Grassroots", "Competitive amateur", "Elite amateur", "Trial-ready"];

function Pathway() {
  return (
    <section className="border-y border-white/10 bg-[#0b1428] py-20 md:py-24">
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 md:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div>
          <SectionHead
            eyebrow="Not in an academy?"
            title={
              <>
                Climb five levels. <span className="text-pitch-300">On your own.</span>
              </>
            }
            lead="A self-guided pathway with benchmark tests, your own weekly plan around your club's training nights, and the same safety engine the academies use."
          />
          <Reveal delay={0.1}>
            <Link
              to="/register"
              className="mt-8 inline-flex h-12 items-center gap-2 rounded-xl border border-white/20 px-5 font-semibold hover:bg-white/5"
            >
              <Mountain className="h-5 w-5" aria-hidden /> Create a free plan
            </Link>
          </Reveal>
        </div>
        <Reveal delay={0.1}>
          <ol className="flex items-end gap-2 md:gap-3" aria-label="The five levels">
            {LEVELS.map((name, i) => (
              <li key={name} className="flex flex-1 flex-col items-center gap-2">
                <span className="text-center text-[11px] leading-tight font-semibold text-white/70 md:text-xs">{name}</span>
                <span
                  className={cn(
                    "font-display flex w-full items-start justify-center rounded-t-xl pt-2 text-2xl font-extrabold",
                    i === 4 ? "bg-pitch-300 text-pitch-950" : "bg-pitch-700/70 text-white/80",
                  )}
                  style={{ height: `${4 + i * 2.6}rem` }}
                >
                  {i + 1}
                </span>
              </li>
            ))}
          </ol>
        </Reveal>
      </div>
    </section>
  );
}

// --------------------------------------------------------------------------- pro leagues

const COMPS = [
  ["la-liga", "La Liga", "2015/16", "All 380 matches"],
  ["premier-league", "Premier League", "2015/16", "Leicester City's title season"],
  ["ligue-1", "Ligue 1", "2015/16", "377 of 380 matches"],
  ["bundesliga", "Bundesliga", "2023/24", "Leverkusen, unbeaten champions"],
  ["champions-league", "Champions League", "Finals 2004-2019", "14 finals"],
] as const;

function ProLeagues() {
  return (
    <section id="pro" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20 md:px-6 md:py-28">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <SectionHead
          eyebrow="Pro leagues"
          title={
            <>
              Learn from <span className="text-pitch-300">the pros.</span>
            </>
          }
          lead="How a team passes, shoots, defends and takes set pieces, player by player. Tables with form and a match centre for every result."
        />
        <Reveal>
          <Link to="/login" className="text-pitch-300 inline-flex items-center gap-1.5 font-semibold hover:underline">
            Open Pro leagues <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        </Reveal>
      </div>
      <ul className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {COMPS.map(([id, name, season, note], i) => (
          <Reveal key={id} delay={i * 0.06}>
            <li className="group relative h-full overflow-hidden rounded-3xl border border-white/10 bg-white/[0.03] p-5 transition-colors hover:border-white/25">
              <span
                className="absolute inset-x-0 top-0 h-1"
                style={{ background: COMP_COLOR[id] }}
                aria-hidden
              />
              <span
                className="pointer-events-none absolute -top-16 -right-16 h-40 w-40 rounded-full opacity-25 blur-2xl transition-opacity group-hover:opacity-50"
                style={{ background: COMP_COLOR[id] }}
                aria-hidden
              />
              <Trophy className="h-6 w-6 text-white/40" aria-hidden />
              <p className="font-display mt-6 text-2xl leading-tight font-bold uppercase">{name}</p>
              <p className="text-sm font-semibold text-white/70">{season}</p>
              <p className="mt-2 text-sm text-white/50">{note}</p>
            </li>
          </Reveal>
        ))}
      </ul>
      <p className="mt-4 text-xs text-white/40">Match events from StatsBomb Open Data.</p>
    </section>
  );
}

// --------------------------------------------------------------------------- FAQ + close

const FAQ: [string, string][] = [
  [
    "Is this medical advice?",
    "No. PathToPro plans training load. Pain reports and red check-ins go straight to the staff, and the agents take no action on them.",
  ],
  ["Do I need a smartwatch?", "No. The morning check-in and your sleep are enough. An Apple Watch adds heart-rate variability to the readiness score."],
  [
    "Does it need AI to work?",
    "No. Without an API key every agent falls back to rules, which is how the live demo runs. With a key, Claude proposes constraints, explanations and drill picks; the solver and the safety rules keep the last word.",
  ],
  [
    "Who sees my data?",
    "Your academy staff, and your family if you link them. Consent is set per data type, and players under 16 need a parent to link before check-ins start.",
  ],
  [
    "What is in the demo?",
    "A synthetic season of 25 players recorded from the real system. It runs in your browser: what you change stays there until you press Reset demo.",
  ],
  ["I'm not in an academy. Can I use it?", "Yes. Create a free plan: five levels, benchmark tests and the same safety engine, planned around your club's training nights."],
];

function Faq() {
  return (
    <section id="faq" className="mx-auto max-w-4xl scroll-mt-20 px-4 pb-20 md:px-6 md:pb-28">
      <SectionHead center eyebrow="FAQ" title="Questions from the touchline" />
      <div className="mt-10 divide-y divide-white/10 rounded-3xl border border-white/10 bg-white/[0.03]">
        {FAQ.map(([q, a]) => (
          <details key={q} className="group px-5 py-1 md:px-6">
            <summary className="tap flex cursor-pointer list-none items-center justify-between gap-4 py-3 font-semibold [&::-webkit-details-marker]:hidden">
              {q}
              <ChevronDown className="h-5 w-5 shrink-0 text-white/50 transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <p className="pb-4 text-white/65">{a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function FinalCta() {
  const { tryAs, busy } = useTryAs();
  const picks: [LucideIcon, string, string][] = [
    [Activity, "Player", "p15@demo.pathtopro"],
    [ClipboardList, "Coach", "coach@demo.pathtopro"],
    [Heart, "Parent", "guardian02@demo.pathtopro"],
    [Stethoscope, "Physio", "physio@demo.pathtopro"],
  ];
  return (
    <section className="px-4 pb-20 md:px-6">
      <Reveal>
        <div className="hero relative mx-auto max-w-7xl overflow-hidden rounded-[2rem] border border-white/10 px-6 py-14 text-center md:py-20">
          <p className="text-pitch-300 text-xs font-bold tracking-[0.18em] uppercase">Kick-off</p>
          <h2 className="font-display mx-auto mt-2 max-w-3xl text-5xl leading-[0.92] font-extrabold uppercase md:text-7xl">Step onto the pitch</h2>
          <p className="mx-auto mt-4 max-w-xl text-white/70">Pick a role and you are in. No account, no install, synthetic players only.</p>
          <div className="mx-auto mt-8 grid max-w-2xl grid-cols-2 gap-3 sm:grid-cols-4">
            {picks.map(([Icon, label, email]) => (
              <button
                key={email}
                onClick={() => tryAs(email)}
                disabled={!!busy}
                className="tap hover:border-pitch-300 group flex flex-col items-center gap-2 rounded-2xl border border-white/15 bg-black/25 px-3 py-4 font-bold transition-colors disabled:opacity-50"
              >
                <Icon className="text-pitch-300 h-6 w-6 transition-transform group-hover:-translate-y-0.5" aria-hidden />
                {busy === email ? "Opening…" : label}
              </button>
            ))}
          </div>
          <p className="mt-6 text-sm text-white/55">
            Have an account?{" "}
            <Link to="/login" className="font-semibold text-white underline">
              Sign in
            </Link>
          </p>
        </div>
      </Reveal>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-white/10">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-white/50 md:px-6">
        <span className="flex items-center gap-2">
          <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="h-6 w-6" />
          <span className="font-display text-base font-bold tracking-wide text-white/80 uppercase">PathToPro</span>
          <span className="hidden sm:inline">· Train smart. Grow safe. Get better.</span>
        </span>
        <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2">
          <Link to="/login" className="hover:text-white">
            Sign in
          </Link>
          <Link to="/register" className="hover:text-white">
            Create a free plan
          </Link>
          <Link to="/privacy" className="hover:text-white">
            Privacy
          </Link>
          <Link to="/terms" className="hover:text-white">
            Terms
          </Link>
          <Link to="/imprint" className="hover:text-white">
            Imprint
          </Link>
          <a href={SOURCE} className="inline-flex items-center gap-1 hover:text-white">
            <CodeXml className="h-4 w-4" aria-hidden /> Source
          </a>
        </nav>
        <p className="w-full text-xs text-white/35">Demo with synthetic players. Team analysis uses StatsBomb Open Data.</p>
      </div>
    </footer>
  );
}
