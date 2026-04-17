-- ============================================================
-- JungleCoach — Migration 001: Post-game analysis tables
-- Run this in the Supabase SQL editor (Database > SQL Editor)
-- ============================================================

-- Riot match timeline cache — shared across all users.
-- Only accessed server-side via service role; no RLS needed.
create table if not exists timeline_cache (
    match_id   text primary key,
    data       jsonb not null,
    cached_at  timestamptz default now()
);

-- Per-user post-game analyses persisted by the cloud API.
create table if not exists post_game_analyses (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid references auth.users not null,
    match_id            text not null,
    jungler_champion    text,
    analysed_at         timestamptz,
    gank_count          int,
    objective_count     int,
    pathing_issue_count int,
    moments             jsonb not null default '[]',
    created_at          timestamptz default now(),
    unique (user_id, match_id)
);

-- RLS: users can only read their own analyses
alter table post_game_analyses enable row level security;

create policy "users_read_own"
    on post_game_analyses
    for select
    using (auth.uid() = user_id);
