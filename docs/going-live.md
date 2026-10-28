# Going live: running PathToPro for a real club

The public demo runs on synthetic data with shared passwords. This page is what it takes to
run a deployment real players, parents and staff use. One deployment is one club.

## What the software now does for a real club

| Need | Where |
| --- | --- |
| Club administrator sets up teams, invites coaches and physios, adds players (form or CSV), moves or removes them | `/admin` · `api/routers/admin.py` |
| Invitations by email: people choose their own password; parents of under-16s get a consent invitation | `api/services/accounts.py` |
| Coach sets the team's training week and fixtures; sessions are generated 8 weeks ahead and extended every Sunday | `/coach/schedule` · `api/routers/schedule.py` |
| Forgot / reset password, email verification, change password, sign out everywhere | `/forgot-password`, `/account` · `api/routers/auth.py` |
| Delete your own account (self-guided adults, parents); club admin deletes academy players (GDPR Art. 17) | `/account`, `/admin` |
| Safety emails: a red check-in or pain report emails the team's physio (or a self-guided minor's parent), with no health detail in the email; the time to send is measured | `api/services/notify.py`, physio queue |
| Email outbox with retries: nothing is lost if the mail server is down | `notifications` table, `python -m api.jobs deliver` |
| Privacy notice, terms, imprint (templates) | `/privacy`, `/terms`, `/imprint` · `frontend/src/legal/Legal.tsx` |
| Notifications on the phone (web push, PWA): safety alerts, check-in reminders, team messages | `/account` · `api/services/push.py`, `frontend/public/push-sw.js` |
| Daily check-in reminder at an hour the player picks (push, else email) | `/account` · `api/services/reminders.py` |
| Calendar feed (.ics) of a player's plan or a team's schedule for Google, Apple and Outlook | `/account` · `api/services/calendar.py` |
| Availability: players answer for each session and match; the coach sees who's in, out and silent | `/player/team`, `/coach/team` · `api/routers/team.py` |
| Team messages from the coach, on the players' Today screen | `/coach/team` |
| Two-step sign-in with an authenticator app, recovery codes; the administrator can reset it | `/account`, `/admin` · `api/services/mfa.py` |

## Checklist before the first real player signs up

### 1. Hosting

- [ ] A paid database plan with **daily backups** (Render's free PostgreSQL expires after 30 days). Note the backup retention in the privacy notice.
- [ ] A paid web service that doesn't sleep (the free one sleeps after 15 minutes, so the nightly run and safety emails would wait for a visitor).
- [ ] A domain with HTTPS; set `PATHTOPRO_PUBLIC_URL=https://your-domain` (links in emails point there) and `PATHTOPRO_CORS` if the website is served from another origin.
- [ ] Servers in the EU (the blueprint uses Frankfurt).

### 2. Environment

```bash
PATHTOPRO_ENV=production
PATHTOPRO_AUTOSEED=off              # no demo data
PATHTOPRO_REGISTRATION=on           # self-guided sign-up (off if the club only adds players itself)
PATHTOPRO_JWT_SECRET=...            # long random value
PATHTOPRO_FIELD_KEY=...             # encryption key for health fields: back it up separately, data is unreadable without it
PATHTOPRO_PUBLIC_URL=https://your-domain
PATHTOPRO_SMTP_HOST=smtp.your-provider.example
PATHTOPRO_SMTP_PORT=587
PATHTOPRO_SMTP_USER=...
PATHTOPRO_SMTP_PASSWORD=...
PATHTOPRO_MAIL_FROM="Your Club <no-reply@your-domain>"
PATHTOPRO_ADMIN_EMAIL=you@your-club.example
PATHTOPRO_ADMIN_PASSWORD=...        # created once on start; change it in /account afterwards
PATHTOPRO_SCHEDULER=on              # one instance only, see below
PATHTOPRO_TIMEZONE=Europe/Berlin    # check-in reminders go out at the player's chosen local hour
PATHTOPRO_VAPID_PUBLIC_KEY=...      # web push: generate once with `python -m api.jobs vapid`
PATHTOPRO_VAPID_PRIVATE_KEY=...
PATHTOPRO_VAPID_SUBJECT=mailto:you@your-club.example
```

Without the VAPID keys there are no phone notifications; everything still arrives by email.
Web push needs HTTPS (or localhost). On iPhone and iPad it works only once the app is added to
the home screen (iOS 16.4 or later).

Without `PATHTOPRO_SMTP_HOST` the server only logs emails (it warns at start, and the admin page
says so). Use a transactional email provider with an EU region and set up SPF and DKIM for the
sending domain, or invitations will land in spam.

### 3. Scheduled jobs

With **one** API instance, `PATHTOPRO_SCHEDULER=on` runs everything in-process: the agents at
23:00, email retries every minute, training weeks extended on Sundays. With more than one
instance, set it `off` and run the jobs from a single cron job instead:

```bash
python -m api.jobs nightly      # daily, 23:00
python -m api.jobs deliver      # every minute (retries; new emails are sent immediately anyway)
python -m api.jobs schedule     # weekly
python -m api.jobs remind       # hourly, on the hour (check-in reminders)
```

### 4. Legal (Germany / EU; minors' health data)

- [ ] Fill in `OPERATOR` in `frontend/src/legal/Legal.tsx` (name, address, contact, register, supervisory authority, email provider). The pages show a "Template" warning until the name is filled in.
- [ ] Have the privacy notice and terms reviewed by a lawyer or data-protection officer. Health data of children is a special category (GDPR Art. 9 and Art. 8).
- [ ] Data protection impact assessment (DPIA, Art. 35): required for large-scale processing of health data of minors.
- [ ] Data processing agreements (Art. 28) with the host, the email provider and, if the AI planner is on, Anthropic.
- [ ] A data-protection officer if your organisation needs one (§ 38 BDSG).
- [ ] Records of processing activities (Art. 30).
- [ ] Keep the app's wording non-medical. It gives training guidance, not diagnosis. A claim to predict or prevent injury could make it a medical device under the EU MDR.

### 5. Data and norms

- [ ] Replace the placeholder benchmark norms in `backend/config/norms.yaml` with published U13-U19 norms.
- [ ] Keep the readiness weights as team defaults until staff have rated at least 60 days (Calibration page).

### 6. First day

1. Sign in with the admin email, open **Teams**, add the first team (and the club's name).
2. **Staff**: invite the coach and the physio. The physio receives red check-ins and pain reports.
3. **Players** or **Import players**: add the squad. Under-16s need a parent's email, and nothing about their health is stored until the parent signs up and agrees.
4. The coach signs in, opens **Schedule**, sets the training week and adds the fixtures.
5. Press **Run agents now** once; from then on the nightly run keeps the plans up to date.

## Try it locally

`docker compose up --build`, then:

- http://localhost:8080: the app (admin: `admin@demo.pathtopro`, password `admin-dev-password`)
- http://localhost:8025: Mailpit, every email the server sends (invitations, resets, safety alerts)

## Not built (needs accounts, partners or people, not only code)

- **SMS.** Needs a paid provider (e.g. Twilio, MessageBird) and a decision on cost per message.
- **Garmin, Polar, Whoop, Fitbit.** Each needs a partner/developer agreement and API credentials;
  the import path would mirror `backend/devices/apple_health.py`.
- **Android Health Connect.** Only readable from a native Android app, not from a website.
- **App Store / Play Store apps.** The PWA installs from the browser; store apps need developer
  accounts and a native wrapper.
- **German (or any other) translation.** Most text is still written in the components; it has
  to move into `frontend/src/shared/i18n/en.json` and be translated by a native speaker.
- **Several clubs in one deployment.** Each club runs its own deployment (and database).
- **Team chat.** Coaches post team messages; players can't reply in the app (a two-way chat
  between adults and minors needs safeguarding rules first: who can message whom, and who reads it).
