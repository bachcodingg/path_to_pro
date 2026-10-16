export default async function globalSetup() {
  const api = process.env.E2E_API ?? "http://127.0.0.1:8000";
  const res = await fetch(`${api}/api/demo/seed?players=25`, { method: "POST" });
  if (!res.ok) throw new Error(`seeding failed: ${res.status}`);
}
