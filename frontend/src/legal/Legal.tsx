// Privacy notice, imprint (Impressum, required for German websites) and terms of use.
// TEMPLATES: whoever runs a deployment for real people fills in OPERATOR and has a lawyer
// or data-protection officer review the text. Until then every page says it is a template.
import { ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { cn } from "../shared/ui";
import { useDocumentTitle } from "../shared/useDocumentTitle";

export const OPERATOR = {
  name: "[Club or company name]",
  representative: "[Name of the person legally responsible]",
  address: "[Street and number, postcode, city, country]",
  email: "[contact email]",
  phone: "[phone number]",
  register: "[Register court and number, if registered (e.g. Vereinsregister)]",
  dpo: "[Data protection officer: name and email, if one is required]",
  authority: "[Supervisory authority, e.g. the Bavarian State Office for Data Protection Supervision (BayLDA)]",
  hosting: "Render Services, Inc. (servers in Frankfurt, Germany)",
  email_provider: "[Email service used to send notifications]",
  updated: "[date of the last review]",
};

const IS_TEMPLATE = OPERATOR.name.startsWith("[");
const NO_LINKS: { to: string; label: string }[] = [];

export function LegalLinks({ className }: { className?: string }) {
  return (
    <nav aria-label="Legal" className={cn("flex flex-wrap gap-x-4 gap-y-1 text-xs", className)}>
      <Link to="/privacy" className="hover:underline">
        Privacy
      </Link>
      <Link to="/terms" className="hover:underline">
        Terms
      </Link>
      <Link to="/imprint" className="hover:underline">
        Imprint
      </Link>
    </nav>
  );
}

function Page({ title, children }: { title: string; children: ReactNode }) {
  useDocumentTitle(NO_LINKS, title);
  return (
    <div className="bg-surface-2 text-ink min-h-full">
      <header className="hero dark px-4 py-6 md:px-6">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2">
            <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="h-8 w-8" />
            <span className="font-display text-xl font-extrabold tracking-wide uppercase">PathToPro</span>
          </Link>
          <LegalLinks className="text-sm text-white/75" />
        </div>
        <h1 className="font-display mx-auto mt-6 max-w-3xl text-4xl font-extrabold uppercase">{title}</h1>
      </header>
      <main id="main" className="legal mx-auto max-w-3xl space-y-4 px-4 py-8 text-[15px] leading-relaxed md:px-6">
        {IS_TEMPLATE && (
          <p role="note" className="border-ready-amber bg-ready-amber/10 flex gap-2 rounded-xl border p-3 text-sm">
            <ShieldAlert className="h-5 w-5 shrink-0 text-amber-700 dark:text-ready-amber" aria-hidden />
            <span>
              <strong>Template.</strong> The text in [brackets] has to be filled in by whoever runs this service, and the page
              reviewed by a lawyer or data-protection officer, before real players sign up.
            </span>
          </p>
        )}
        {children}
        <p className="text-ink-2 pt-4 text-sm">Last reviewed: {OPERATOR.updated}</p>
      </main>
    </div>
  );
}

function H({ children }: { children: ReactNode }) {
  return <h2 className="font-display pt-4 text-xl font-bold uppercase">{children}</h2>;
}

export function Imprint() {
  return (
    <Page title="Imprint">
      <p>Information according to § 5 DDG (German Digital Services Act):</p>
      <p>
        {OPERATOR.name}
        <br />
        {OPERATOR.address}
        <br />
        Represented by: {OPERATOR.representative}
      </p>
      <p>
        Email: {OPERATOR.email}
        <br />
        Phone: {OPERATOR.phone}
      </p>
      <p>{OPERATOR.register}</p>
      <H>Data used under licence</H>
      <p>
        The Pro leagues section uses StatsBomb Open Data (https://github.com/statsbomb/open-data) under its terms of use. Club and
        competition names are used to identify the data; there is no affiliation with the clubs, leagues or StatsBomb.
      </p>
    </Page>
  );
}

export function Privacy() {
  return (
    <Page title="Privacy notice">
      <p>
        PathToPro plans training for young footballers. To do that it stores information about each player's training, sleep,
        wellbeing and growth, which counts as health data under the GDPR (Art. 9). This notice explains what is stored, why, who can
        see it and what rights you have.
      </p>
      <H>Who is responsible</H>
      <p>
        {OPERATOR.name}, {OPERATOR.address}, {OPERATOR.email}. {OPERATOR.dpo}.
      </p>
      <H>What we store and why</H>
      <ul className="list-disc space-y-1 pl-5">
        <li>
          <strong>Account:</strong> name, email, password (only as a secure hash), role, date of birth, sex and playing position. To
          sign you in and to apply age-appropriate limits.
        </li>
        <li>
          <strong>Training and health data</strong> (only with consent, separately for each kind): the morning check-in (sleep
          quality, fatigue, stress, soreness, mood, pain yes/no), sleep duration, heart-rate variability from a wearable, height,
          sitting height and weight, fitness test results, and the effort (RPE) and minutes of each session. To plan a safe training
          week, to warn about load spikes and growth spurts, and to show progress.
        </li>
        <li>
          <strong>Football data:</strong> matches, minutes, match ratings, a match diary and a playing career.
        </li>
        <li>
          <strong>Records required for safety and accountability:</strong> every plan change with its reason and who approved it, and
          a log of who looked at health data and when.
        </li>
      </ul>
      <p>
        We do not store location, free-text diaries or anything about weight loss or diet, and the app never predicts whether a player
        will become a professional.
      </p>
      <H>Legal basis</H>
      <p>
        Health data is processed only with explicit consent (Art. 9(2)(a) and Art. 6(1)(a) GDPR), given per kind of data and
        revocable at any time in the app; withdrawing consent does not affect processing before it. Below the age of 16, a parent or
        guardian gives this consent (Art. 8 GDPR; 16 is the age of digital consent in Germany). Account data is processed to provide the
        service you asked for (Art. 6(1)(b) GDPR); the access log to keep health data secure (Art. 6(1)(f) and Art. 32 GDPR).
      </p>
      <H>Who can see it</H>
      <ul className="list-disc space-y-1 pl-5">
        <li>The player.</li>
        <li>Their linked parent or guardian (a weekly summary, alerts, and the consent settings).</li>
        <li>The coach and physio of the player's own team (academy players). Nobody at another team or club.</li>
        <li>
          Processors acting on our instructions: hosting by {OPERATOR.hosting}; email by {OPERATOR.email_provider}. If the AI planner
          is switched on, Anthropic PBC receives the player's readiness score and colour, load ratio, safety flags and planned week to
          suggest and explain plan changes, without name or email; coach instructions typed in plain words are sent as written.
        </li>
      </ul>
      <p>
        Emails about safety alerts name the player but never what was reported; the details are only in the app. Health fields are
        stored encrypted. If you turn on notifications on a device, the same short text travels encrypted through your browser
        maker's push service (Google, Apple or Mozilla). A calendar address you create shows your sessions and matches to anyone
        who has it; you can replace or switch it off at any time. Availability answers (with a reason from a fixed list) are seen by
        your team's staff.
      </p>
      <H>How long</H>
      <p>
        As long as the account exists. When an account or a player is deleted, everything stored about them is deleted at once; the
        access log keeps the fact that a deletion happened, without the deleted data. [Backups: state how long backups are kept.]
      </p>
      <H>Your rights</H>
      <p>
        You can see and download your data (parents: “Download data” in the family view), correct it, have it deleted (your account
        settings, the family view, or the club administrator for academy players), restrict or object to processing, and withdraw
        consent at any time. You can complain to a supervisory authority: {OPERATOR.authority}.
      </p>
      <H>Cookies</H>
      <p>
        PathToPro uses no cookies and no tracking or analytics. Your sign-in is kept in your browser's local storage on your device
        until you sign out.
      </p>
    </Page>
  );
}

export function Terms() {
  return (
    <Page title="Terms of use">
      <H>What PathToPro is</H>
      <p>
        PathToPro is a training planner. It gives training guidance, not medical advice, diagnosis or treatment. It does not replace
        a coach, physio or doctor. If you are in pain, feel unwell or are worried, stop training and talk to a trusted adult and a
        doctor or physio.
      </p>
      <H>Who can use it</H>
      <p>
        Players from 13 years. Below 16, a parent or guardian must agree before health data is stored. Academy accounts are created by
        the club; self-guided players sign up themselves.
      </p>
      <H>Your account</H>
      <p>
        Keep your password to yourself. Enter honest check-ins: the plan is only as good as the data. Don't use the service to harm
        others or to get at data that isn't yours.
      </p>
      <H>Plans and limits</H>
      <p>
        Safety limits (rest days, growth-spurt limits, match minutes for under-18s) are built in and cannot be switched off. Coaches
        approve bigger changes. Benchmarks and norms are estimates and may change.
      </p>
      <H>Ending</H>
      <p>
        You can delete your account at any time in your account settings (academy players: through the club or a parent). We may close
        accounts that break these terms.
      </p>
      <H>Liability</H>
      <p>[To be completed by the operator with legal advice: liability limits under the applicable law.]</p>
      <p>Contact: {OPERATOR.email}</p>
    </Page>
  );
}
