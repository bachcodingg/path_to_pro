// Browser tab title from the layout's navigation: the most specific link that matches the
// current path ("Team analysis · PathToPro"), so tabs and history entries are told apart.
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

export function useDocumentTitle(links: { to: string; label: string }[], fallback: string) {
  const { pathname } = useLocation();
  useEffect(() => {
    const match = links
      .filter((l) => pathname === l.to || pathname.startsWith(`${l.to}/`))
      .sort((a, b) => b.to.length - a.to.length)[0];
    document.title = `${match?.label ?? fallback} · PathToPro`;
  }, [pathname, links, fallback]);
}
