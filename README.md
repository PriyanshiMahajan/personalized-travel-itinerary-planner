# AI Travel Itinerary Planner
React (Vite) + FastAPI + Supabase. LLM via any OpenAI-compatible API (Llama-3 on Groq by default).

## Run
Backend:
    cd backend && python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env      # optional: add keys
    uvicorn main:app --reload --port 8000
Frontend:
    cd frontend && npm install && npm run dev     # http://localhost:5173

With no keys set, the app still works: it uses a mock itinerary generator and in-memory storage.
For persistence, run supabase/schema.sql in the Supabase SQL editor and fill SUPABASE_URL / SUPABASE_SERVICE_KEY.
Set LLM_API_KEY for real AI generation.

## Not included yet
Supabase Auth login (the app uses an anonymous per-browser user id sent as X-User-Id) and shared/group trips.
The schema already has user_id and RLS for adding both.
