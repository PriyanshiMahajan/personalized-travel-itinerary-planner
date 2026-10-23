create table if not exists trips (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  prefs jsonb not null,
  days jsonb not null,
  total_cost numeric default 0,
  created_at timestamptz default now()
);
create index on trips (user_id);
alter table trips enable row level security;
-- Backend uses the service key (bypasses RLS). When you add Supabase Auth,
-- switch user_id to uuid and add: create policy "own trips" on trips using (user_id = auth.uid()::text);
