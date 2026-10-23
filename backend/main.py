import os, json, uuid, datetime
from typing import List, Optional
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
app = FastAPI(title="Travel Itinerary Planner")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------- models ----------
class Prefs(BaseModel):
    destination: str
    start_date: str = ""
    days: int = Field(3, ge=1, le=14)
    budget: float = 500
    currency: str = "USD"
    travelers: int = Field(1, ge=1, le=20)
    pace: str = "balanced"
    stay: str = "mid-range"
    interests: List[str] = []

class Activity(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    time: str = "09:00"
    title: str
    category: str = "sightseeing"
    description: str = ""
    cost: float = 0
    travel_min: int = 0

class Day(BaseModel):
    day: int
    theme: str = ""
    activities: List[Activity] = []

class ActivityPatch(BaseModel):
    time: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    cost: Optional[float] = None

# ---------- storage (Supabase REST, in-memory fallback) ----------
SB_URL, SB_KEY = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY")
MEM: dict = {}

def _h():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json",
            "Prefer": "return=representation"}

def db_list(uid):
    if not SB_URL:
        return sorted([t for t in MEM.values() if t["user_id"] == uid], key=lambda t: t["created_at"], reverse=True)
    r = httpx.get(f"{SB_URL}/rest/v1/trips", headers=_h(), params={"user_id": f"eq.{uid}", "order": "created_at.desc"})
    r.raise_for_status(); return r.json()

def db_get(tid, uid):
    if not SB_URL:
        t = MEM.get(tid); return t if t and t["user_id"] == uid else None
    r = httpx.get(f"{SB_URL}/rest/v1/trips", headers=_h(), params={"id": f"eq.{tid}", "user_id": f"eq.{uid}"})
    r.raise_for_status(); rows = r.json(); return rows[0] if rows else None

def db_save(trip):
    if not SB_URL:
        MEM[trip["id"]] = trip; return trip
    r = httpx.post(f"{SB_URL}/rest/v1/trips", headers={**_h(), "Prefer": "resolution=merge-duplicates,return=representation"}, json=trip)
    r.raise_for_status(); return r.json()[0]

def db_delete(tid, uid):
    if not SB_URL:
        MEM.pop(tid, None); return
    httpx.delete(f"{SB_URL}/rest/v1/trips", headers=_h(), params={"id": f"eq.{tid}", "user_id": f"eq.{uid}"})

# ---------- AI layer ----------
def build_prompt(p: Prefs, only_day: Optional[int], avoid: List[str]):
    scope = f"ONLY day {only_day} of {p.days}" if only_day else f"all {p.days} days"
    return f"""You are an expert travel planner. Create {scope} of an itinerary for {p.destination}.
Travelers: {p.travelers}. Pace: {p.pace}. Accommodation style: {p.stay}. Interests: {', '.join(p.interests) or 'general'}.
Total trip budget: {p.budget} {p.currency} (all travelers). Start date: {p.start_date or 'flexible'}.
Group nearby places on the same day to minimise travel. Include breakfast/lunch/dinner, attractions, and a stay or transport entry where relevant.
{('Do NOT reuse these places: ' + ', '.join(avoid)) if avoid else ''}
Return ONLY JSON: {{"days":[{{"day":1,"theme":"...","activities":[{{"time":"09:00","title":"...","category":"food|sightseeing|stay|transport|activity","description":"one sentence","cost":0,"travel_min":0}}]}}]}}
Costs are numbers in {p.currency} for the whole group."""

def call_llm(prompt: str) -> dict:
    r = httpx.post(os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1") + "/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv('LLM_API_KEY')}"}, timeout=90,
        json={"model": os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"), "temperature": 0.7,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])

def mock(p: Prefs, only_day: Optional[int]):
    nums = [only_day] if only_day else range(1, p.days + 1)
    per = p.budget / p.days / 4
    out = []
    for n in nums:
        out.append({"day": n, "theme": f"Explore {p.destination} - Day {n}", "activities": [
            {"time": "08:30", "title": "Local breakfast café", "category": "food", "description": "Start with a regional breakfast.", "cost": per * .2, "travel_min": 10},
            {"time": "10:00", "title": f"{p.destination} landmark visit", "category": "sightseeing", "description": "Top-rated landmark; go early to avoid crowds.", "cost": per * .4, "travel_min": 20},
            {"time": "13:00", "title": "Popular lunch spot", "category": "food", "description": "Well-reviewed local cuisine.", "cost": per * .5, "travel_min": 15},
            {"time": "15:00", "title": f"{(p.interests or ['Cultural'])[0].title()} experience", "category": "activity", "description": "Matches your interests.", "cost": per * .6, "travel_min": 15},
            {"time": "19:30", "title": "Dinner at a local favourite", "category": "food", "description": "Relaxed evening meal.", "cost": per * .7, "travel_min": 10}]})
    return {"days": out}

def generate(p: Prefs, only_day: Optional[int] = None, avoid: List[str] = []) -> List[Day]:
    err = None
    for _ in range(2):  # retry once on malformed output
        try:
            raw = call_llm(build_prompt(p, only_day, avoid)) if os.getenv("LLM_API_KEY") else mock(p, only_day)
            days = [Day(**d) for d in raw["days"]]
            if days: return days
        except Exception as e:
            err = e
    raise HTTPException(502, f"AI generation failed: {err}")

def totals(days: List[dict]) -> float:  # budget math done in code, not by the model
    return round(sum(a["cost"] for d in days for a in d["activities"]), 2)

def uid_of(x):
    if not x: raise HTTPException(401, "Missing X-User-Id")
    return x

# ---------- routes ----------
@app.post("/trips/generate")
def create(p: Prefs, x_user_id: str = Header(None)):
    uid = uid_of(x_user_id)
    days = [d.model_dump() for d in generate(p)]
    trip = {"id": str(uuid.uuid4()), "user_id": uid, "prefs": p.model_dump(), "days": days,
            "total_cost": totals(days), "created_at": datetime.datetime.utcnow().isoformat()}
    return db_save(trip)

@app.get("/trips")
def list_trips(x_user_id: str = Header(None)):
    return db_list(uid_of(x_user_id))

@app.get("/trips/{tid}")
def get_trip(tid: str, x_user_id: str = Header(None)):
    t = db_get(tid, uid_of(x_user_id))
    if not t: raise HTTPException(404, "Trip not found")
    return t

@app.post("/trips/{tid}/days/{n}/regenerate")
def regen(tid: str, n: int, x_user_id: str = Header(None)):
    t = get_trip(tid, x_user_id)
    if not 1 <= n <= len(t["days"]): raise HTTPException(404, "Day not found")
    avoid = [a["title"] for d in t["days"] for a in d["activities"]]
    new = generate(Prefs(**t["prefs"]), only_day=n, avoid=avoid)[0].model_dump()
    new["day"] = n
    t["days"][n - 1] = new
    t["total_cost"] = totals(t["days"])
    return db_save(t)

@app.patch("/trips/{tid}/activities/{aid}")
def patch_activity(tid: str, aid: str, patch: ActivityPatch, x_user_id: str = Header(None)):
    t = get_trip(tid, x_user_id)
    for d in t["days"]:
        for a in d["activities"]:
            if a["id"] == aid:
                a.update(patch.model_dump(exclude_none=True))
                t["total_cost"] = totals(t["days"])
                return db_save(t)
    raise HTTPException(404, "Activity not found")

@app.delete("/trips/{tid}")
def delete_trip(tid: str, x_user_id: str = Header(None)):
    db_delete(tid, uid_of(x_user_id)); return {"ok": True}
