// First focusable element on every page: jump past the navigation (WCAG 2.4.1)
export function SkipLink() {
  return (
    <a
      href="#main"
      className="bg-pitch-300 text-pitch-950 sr-only z-50 rounded-lg px-4 py-2 font-bold focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
    >
      Skip to main content
    </a>
  );
}
