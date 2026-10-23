import { useEffect, useState } from "react";
import { api } from "./api.js";

const INTERESTS = ["food", "sightseeing", "adventure", "culture", "nature", "nightlife", "shopping", "relaxation"];
const money = (n, c) => `${c} ${Math.round(n).toLocaleString()}`;

function Builder({ onDone, busy, setBusy, setErr }) {
  const [f, setF] = useState({ destination: "", start_date: "", days: 3, budget: 500, currency: "USD", travelers: 1,
    pace: "balanced", stay: "mid-range", interests: ["food", "sightseeing"] });
  const set = (k, v) => setF({ ...f, [k]: v });
  const toggle = (i) => set("interests", f.interests.includes(i) ? f.interests.filter((x) => x !== i) : [...f.interests, i]);
  const submit = async () => {
    if (!f.destination.trim()) return setErr("Enter a destination");
    setBusy(true); setErr("");
    try { onDone(await api.generate({ ...f, days: +f.days, budget: +f.budget, travelers: +f.travelers })); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="card">
      <h2>Plan a new trip</h2>
      <div className="grid">
        <label>Destination<input value={f.destination} onChange={(e) => set("destination", e.target.value)} placeholder="e.g. Jaipur" /></label>
        <label>Start date<input type="date" value={f.start_date} onChange={(e) => set("start_date", e.target.value)} /></label>
        <label>Days<input type="number" min="1" max="14" value={f.days} onChange={(e) => set("days", e.target.value)} /></label>
        <label>Travelers<input type="number" min="1" value={f.travelers} onChange={(e) => set("travelers", e.target.value)} /></label>
        <label>Budget<input type="number" value={f.budget} onChange={(e) => set("budget", e.target.value)} /></label>
        <label>Currency<select value={f.currency} onChange={(e) => set("currency", e.target.value)}>{["USD", "INR", "EUR", "GBP"].map((c) => <option key={c}>{c}</option>)}</select></label>
        <label>Pace<select value={f.pace} onChange={(e) => set("pace", e.target.value)}>{["relaxed", "balanced", "packed"].map((c) => <option key={c}>{c}</option>)}</select></label>
        <label>Stay<select value={f.stay} onChange={(e) => set("stay", e.target.value)}>{["budget", "mid-range", "premium"].map((c) => <option key={c}>{c}</option>)}</select></label>
      </div>
      <div className="chips">{INTERESTS.map((i) => <button key={i} className={f.interests.includes(i) ? "chip on" : "chip"} onClick={() => toggle(i)}>{i}</button>)}</div>
      <button className="primary" disabled={busy} onClick={submit}>{busy ? "Generating…" : "Generate itinerary"}</button>
    </div>
  );
}

function Activity({ a, cur, onSave }) {
  const [edit, setEdit] = useState(false);
  const [d, setD] = useState(a);
  if (edit) return (
    <div className="act editing">
      <input value={d.time} onChange={(e) => setD({ ...d, time: e.target.value })} style={{ width: 80 }} />
      <input value={d.title} onChange={(e) => setD({ ...d, title: e.target.value })} />
      <input type="number" value={d.cost} onChange={(e) => setD({ ...d, cost: +e.target.value })} style={{ width: 90 }} />
      <button className="primary sm" onClick={() => { onSave(a.id, { time: d.time, title: d.title, cost: d.cost }); setEdit(false); }}>Save</button>
      <button className="sm" onClick={() => setEdit(false)}>Cancel</button>
    </div>);
  return (
    <div className="act">
      <div className="time">{a.time}</div>
      <div className="body"><b>{a.title}</b> <span className="tag">{a.category}</span>
        <p>{a.description}</p>{a.travel_min > 0 && <small>🚶 {a.travel_min} min travel</small>}</div>
      <div className="cost">{money(a.cost, cur)}<br /><button className="link" onClick={() => setEdit(true)}>Edit</button></div>
    </div>);
}

function Itinerary({ trip, setTrip, setErr }) {
  const [tab, setTab] = useState(0);
  const [busy, setBusy] = useState(false);
  const cur = trip.prefs.currency, day = trip.days[tab] || trip.days[0];
  const over = trip.total_cost > trip.prefs.budget;
  const wrap = async (fn) => { setBusy(true); setErr(""); try { setTrip(await fn()); } catch (e) { setErr(e.message); } finally { setBusy(false); } };
  return (
    <div className="card">
      <div className="row"><h2>{trip.prefs.destination}</h2>
        <div className={over ? "budget over" : "budget"}>Estimated {money(trip.total_cost, cur)} / {money(trip.prefs.budget, cur)}</div></div>
      <div className="tabs">{trip.days.map((d, i) => <button key={i} className={i === tab ? "tab on" : "tab"} onClick={() => setTab(i)}>Day {d.day}</button>)}</div>
      <div className="row"><h3>{day.theme}</h3>
        <button disabled={busy} onClick={() => wrap(() => api.regen(trip.id, day.day))}>{busy ? "…" : "↻ Regenerate day"}</button></div>
      {day.activities.map((a) => <Activity key={a.id} a={a} cur={cur} onSave={(aid, b) => wrap(() => api.patch(trip.id, aid, b))} />)}
    </div>);
}

export default function App() {
  const [trips, setTrips] = useState([]), [cur, setCur] = useState(null), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const load = () => api.list().then(setTrips).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  const open = (t) => { setCur(t); load(); };
  const upd = (t) => { setCur(t); setTrips((ts) => ts.map((x) => (x.id === t.id ? t : x))); };
  return (
    <div className="shell">
      <aside><h1>🧭 Wayfinder</h1>
        <button className="primary" onClick={() => setCur(null)}>+ New trip</button>
        <h4>Saved trips</h4>
        {trips.length === 0 && <small>No trips yet</small>}
        {trips.map((t) => (
          <div key={t.id} className={cur?.id === t.id ? "trip on" : "trip"} onClick={() => setCur(t)}>
            <span>{t.prefs.destination}<small> · {t.prefs.days}d</small></span>
            <button className="link" onClick={async (e) => { e.stopPropagation(); await api.remove(t.id); if (cur?.id === t.id) setCur(null); load(); }}>✕</button>
          </div>))}
      </aside>
      <main>
        {err && <div className="err">{err}</div>}
        {cur ? <Itinerary key={cur.id} trip={cur} setTrip={upd} setErr={setErr} /> : <Builder onDone={open} busy={busy} setBusy={setBusy} setErr={setErr} />}
      </main>
    </div>);
}
