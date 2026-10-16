export default async function globalSetup() {
  if (process.env.E2E_DEMO) return; // static demo site: data comes from the snapshot
  const api = process.env.E2E_API ?? "http://127.0.0.1:8000";
  const res = await fetch(`${api}/api/demo/seed?players=25`, { method: "POST" });
  if (!res.ok) throw new Error(`seeding failed: ${res.status}`);
}
