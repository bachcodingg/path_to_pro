// Pro League Data Tracking: a separate app on the PathToPro platform. Same account, API and
// design system as PathToPro, but its own entry page (leagues/index.html), address, icon, theme
// and install.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "../shared/auth";
import { DemoBanner } from "../shared/DemoBanner";
import { LeaguesApp } from "./LeaguesApp";
import "../index.css";

const home = `${import.meta.env.BASE_URL}leagues`;

// The static demo website sends unknown addresses to 404.html, which hands a deep link in this
// app over as ?p=<path>; put it back before the router reads the address.
const deep = new URLSearchParams(window.location.search).get("p");
if (deep !== null) window.history.replaceState(null, "", `${home}/${deep.replace(/^\//, "")}`);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter basename={home}>
      <AuthProvider>
        <DemoBanner />
        <LeaguesApp />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
