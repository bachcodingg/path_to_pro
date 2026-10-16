import { render, screen } from "@testing-library/react";
import { Battery } from "../player/Today";
import { t } from "./i18n";
import { BandBadge, intensityClass } from "./ui";

describe("design system", () => {
  it("colours lanes by intensity, matches and rest stand out", () => {
    expect(intensityClass("match", 8)).toContain("pitch-900");
    expect(intensityClass("rest", 0)).toContain("surface-2");
    expect(intensityClass("speed", 3)).not.toEqual(intensityClass("speed", 8));
  });

  it("readiness badge carries an icon and text, not colour alone", () => {
    render(<BandBadge band="red" />);
    expect(screen.getByText("Recover")).toBeInTheDocument();
  });

  it("battery has an accessible description", () => {
    render(<Battery score={45.5} band="red" />);
    expect(screen.getByLabelText("Readiness 46 of 100, Recover")).toBeInTheDocument();
  });

  it("translations fall back to the key", () => {
    expect(t("nav.today")).toBe("Today");
    expect(t("missing.key")).toBe("missing.key");
  });
});
