const BASE = import.meta.env.VITE_API_URL || "https://personalized-travel-itinerary-plann-chi.vercel.app";
let uid = localStorage.getItem("uid");
if (!uid) { uid = crypto.randomUUID(); localStorage.setItem("uid", uid); }
async function req(path, method = "GET", body) {
  const r = await fetch(BASE + path, { method, headers: { "Content-Type": "application/json", "X-User-Id": uid },
    body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
export const api = {
  list: () => req("/trips"),
  generate: (p) => req("/trips/generate", "POST", p),
  regen: (id, n) => req(`/trips/${id}/days/${n}/regenerate`, "POST"),
  patch: (id, aid, b) => req(`/trips/${id}/activities/${aid}`, "PATCH", b),
  remove: (id) => req(`/trips/${id}`, "DELETE"),
};
