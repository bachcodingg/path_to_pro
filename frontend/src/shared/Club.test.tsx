import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { clubMeta, FormGuide, resultOf } from "./Club";
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
