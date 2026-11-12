import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { Crest, clubMeta, FormGuide, resultOf } from "./Club";
import { PlayerPhoto } from "./PlayerPhoto";
import { Tabs } from "./PageHeader";
import { useDocumentTitle } from "./useDocumentTitle";

describe("club identity", () => {
  it("uses LaLiga's codes for the data's club names, a stable code for anyone else", () => {
    expect(clubMeta("Real Madrid").code).toBe("RMA");
    expect(clubMeta("Atlético Madrid").code).toBe("ATM");
    expect(clubMeta("PathToPro Academy U13-U18").code).toBe("PTP");
    expect(clubMeta("Opponent 12").code).toBe("O12");
    expect(clubMeta("FC Somewhere Else").colors).toEqual(clubMeta("FC Somewhere Else").colors);
  });

  it("shows a real crest: the free one kept in the app, then Wikipedia's, then the data's logo, else a drawn badge", () => {
    const src = (ui: ReactElement) => render(ui).container.querySelector("img")?.getAttribute("src");
    expect(src(<Crest name="Barcelona" />)).toMatch(/crests\/barcelona\.svg$/);
    expect(src(<Crest name="Real Madrid" />)).toMatch(/^https:\/\/[a-z]+\.wikimedia\.org\//);
    expect(src(<Crest name="Tottenham" />)).toMatch(/wikimedia\.org.*Tottenham/); // API-Football's name
    expect(src(<Crest name="Como" src="https://media.api-sports.io/football/teams/895.png" />)).toBe("https://media.api-sports.io/football/teams/895.png");
    expect(src(<Crest name="Opponent 12" />)).toBeUndefined();
  });

  it("a player without a photo shows his initials", () => {
    const { container } = render(<PlayerPhoto name="Riyad Mahrez" />);
    expect(container).toHaveTextContent("RM");
    expect(container.querySelector("img")).toBeNull();
  });

  it("form guide reads the results out in order, not only as colours", () => {
    render(<FormGuide form={["W", "D", "L"]} />);
    expect(screen.getByLabelText("Form, oldest first: won, drawn, lost")).toBeInTheDocument();
    expect(resultOf(2, 1)).toBe("W");
    expect(resultOf(1, 1)).toBe("D");
    expect(resultOf(0, 3)).toBe("L");
  });

  it("tabs mark the selected one for screen readers", () => {
    render(<Tabs label="Sections" value="b" onChange={() => {}} items={[["a", "First"], ["b", "Second"]]} />);
    expect(screen.getByRole("tab", { name: "Second" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "First" })).toHaveAttribute("aria-selected", "false");
  });

  it("tab title follows the most specific matching link", () => {
    const links = [
      { to: "/coach", label: "Dressing room" },
      { to: "/coach/analysis", label: "Team analysis" },
    ];
    function Page() {
      useDocumentTitle(links, "Staff");
      return null;
    }
    render(
      <MemoryRouter initialEntries={["/coach/analysis/real-madrid"]}>
        <Page />
      </MemoryRouter>,
    );
    expect(document.title).toBe("Team analysis · PathToPro");
  });
});
