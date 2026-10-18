# Club finances

All amounts are euro, stored in cents. The demo's numbers are synthetic examples, not tax,
payroll or legal advice.

## What is tracked

| | Examples | Direction |
| --- | --- | --- |
| **Contracts: players pay** | Academy fee (e.g. EUR 120-150 / month), membership | income |
| **Contracts: club pays players** | Amateur expenses, semi-pro salary, professional salary, with bonus clauses | expense |
| **Contracts: club pays staff** | Head coach salary, part-time physio, coach fees | expense |
| **Running items** | Pitch hire per training session or per match, referee fees per match, travel, equipment | expense |
| | Sponsors per month, gate money per match | income |
| **Bonuses** | Per appearance, goal, assist, win, clean sheet (keepers and defenders, 60+ min), title | expense |
| **Titles** | Prize money in, title bonus for every player of the team with that clause | both |
| **Manual entries** | Anything else (e.g. new bibs) | either |

## How it works

- **Book a month** (button, or automatically in the demo): monthly contracts and running
  items are booked; per-session items count that month's planned training sessions, per-match
  items count its fixtures. Booking twice never books twice (each entry has a unique key).
- **Bonuses follow match stats**: saving a match's ratings books that match's bonuses for
  players with bonus clauses. If the coach corrects the stats later, unpaid bonuses follow
  (a goal taken away removes its bonus); paid ones stay.
- **Record a title**: prize money and title bonuses, once per title.
- **Ledger**: every entry with "due" or "paid"; fees still due from an earlier month count as overdue.

## Who sees what

| Role | Sees |
| --- | --- |
| Coach | Their team's finances (the men's coach his team, the academy coach the academy) |
| Admin | The whole club |
| Physio | Nothing (no menu entry, API refuses) |
| Player | Their own contracts, salary, bonuses by type, fees paid and due (Career tab) |
| Guardian | Their child's fees, paid and due |

## Demo

Academy fees for every academy player (three families a month behind), semi-pro contracts
for the three dual-registered U18s with the men's team (EUR 350 / month + EUR 50 appearance,
EUR 100 goal, EUR 50 assist, EUR 75 win, EUR 50 clean sheet, EUR 1,000 title), staff pay,
pitch hire per session, referees and gate money per men's match, two sponsors.

## Club history

The Career tab lists every club the player has been at, newest first: years, teams (U12,
U13 ... Men), leagues and appearances, e.g. FC Lahti U12-U13 (2020-21), FC Honka U14-U15,
PathToPro FC U17, HooGee Men in Kolmonen alongside the U17s, and now PathToPro FC U19 + Men.
Clubs come from past seasons the player (or club) adds, and from current registrations.
