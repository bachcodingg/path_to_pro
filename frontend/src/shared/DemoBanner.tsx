import { DEMO } from "./api";

// Shown on the static demo website: everything runs in the browser on synthetic data.
export function DemoBanner() {
  if (!DEMO) return null;
  async function reset() {
    const { resetDemo } = await import("./demo");
    resetDemo();
  }
  return (
    <div role="note" className="bg-caution px-3 py-1 text-center text-xs font-semibold text-pitch-950">
      Demo · synthetic data · runs in your browser, nothing is sent anywhere ·{" "}
      <button className="underline" onClick={reset}>
        Reset demo
      </button>{" "}
      ·{" "}
      <a className="underline" href="https://github.com/bachcodingg/path_to_pro">
        Source
      </a>
    </div>
  );
}
