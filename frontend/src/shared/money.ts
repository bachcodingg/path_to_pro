// Euro amounts are stored in cents.
const fmt = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const fmt2 = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR", minimumFractionDigits: 2 });

export function eur(cents: number | null | undefined, exact = false): string {
  if (cents == null) return "–";
  return (exact || cents % 100 !== 0 ? fmt2 : fmt).format(cents / 100);
}

export const PERIOD: Record<string, string> = { month: "/ month", season: "/ season", match: "/ match", session: "/ session" };

export const BONUS_LABEL: Record<string, string> = {
  appearance: "Appearance",
  goal: "Goal",
  assist: "Assist",
  win: "Win",
  clean_sheet: "Clean sheet",
  title: "Title",
};
