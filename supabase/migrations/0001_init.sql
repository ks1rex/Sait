-- 0001_init.sql
-- Schema for GOST Calculation Report Generator

-- ─────────────────────────────────────────────
-- Extensions
-- ─────────────────────────────────────────────
create extension if not exists "pgcrypto";

-- ─────────────────────────────────────────────
-- profiles
-- ─────────────────────────────────────────────
create table public.profiles (
    id                  uuid        primary key references auth.users (id) on delete cascade,
    email               text        not null,
    has_access          boolean     not null default false,
    access_expires_at   timestamptz,
    unlimited_access    boolean     not null default false,
    created_at          timestamptz not null default now()
);

-- Auto-create profile row on new user signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    insert into public.profiles (id, email)
    values (new.id, new.email);
    return new;
end;
$$;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();

-- ─────────────────────────────────────────────
-- access_codes
-- ─────────────────────────────────────────────
create table public.access_codes (
    id            uuid        primary key default gen_random_uuid(),
    code          text        not null unique,
    duration_days int         not null,
    used_by       uuid        references public.profiles (id) on delete set null,
    used_at       timestamptz,
    created_at    timestamptz not null default now()
);

-- ─────────────────────────────────────────────
-- projects
-- ─────────────────────────────────────────────
create table public.projects (
    id                uuid        primary key default gen_random_uuid(),
    user_id           uuid        not null references public.profiles (id) on delete cascade,
    title             text        not null,
    status            text        not null default 'uploaded'
                                  check (status in ('uploaded','extracted','computed','done','error')),
    source_pdf_path   text,
    output_docx_path  text,
    output_pdf_path   text,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

create index projects_user_id_idx on public.projects (user_id);

-- auto-update updated_at
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger projects_updated_at
    before update on public.projects
    for each row execute procedure public.set_updated_at();

-- ─────────────────────────────────────────────
-- calculation_specs
-- ─────────────────────────────────────────────
create table public.calculation_specs (
    id          uuid        primary key default gen_random_uuid(),
    project_id  uuid        not null unique references public.projects (id) on delete cascade,
    spec_json   jsonb       not null,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create trigger calculation_specs_updated_at
    before update on public.calculation_specs
    for each row execute procedure public.set_updated_at();

-- ─────────────────────────────────────────────
-- ai_usage
-- ─────────────────────────────────────────────
create table public.ai_usage (
    id            uuid        primary key default gen_random_uuid(),
    user_id       uuid        not null references public.profiles (id) on delete cascade,
    project_id    uuid        references public.projects (id) on delete set null,
    provider      text        not null,
    model         text        not null,
    input_tokens  int         not null default 0,
    output_tokens int         not null default 0,
    created_at    timestamptz not null default now()
);

create index ai_usage_user_id_idx on public.ai_usage (user_id);

-- ─────────────────────────────────────────────
-- Row-Level Security
-- ─────────────────────────────────────────────
alter table public.profiles           enable row level security;
alter table public.access_codes       enable row level security;
alter table public.projects           enable row level security;
alter table public.calculation_specs  enable row level security;
alter table public.ai_usage           enable row level security;

-- profiles: user sees only own row; cannot update has_access / unlimited_access
create policy "profiles: select own"
    on public.profiles for select
    using (id = auth.uid());

create policy "profiles: update own non-sensitive fields"
    on public.profiles for update
    using (id = auth.uid())
    with check (
        id = auth.uid()
        -- has_access and unlimited_access are immutable via user policy;
        -- enforce by rejecting changes to those columns:
        and has_access       = (select has_access       from public.profiles where id = auth.uid())
        and unlimited_access = (select unlimited_access from public.profiles where id = auth.uid())
    );

-- access_codes: users can only select unused codes (to redeem); insert/update via service role
create policy "access_codes: select any unused"
    on public.access_codes for select
    using (used_by is null or used_by = auth.uid());

-- projects: full CRUD on own rows
create policy "projects: select own"
    on public.projects for select
    using (user_id = auth.uid());

create policy "projects: insert own"
    on public.projects for insert
    with check (user_id = auth.uid());

create policy "projects: update own"
    on public.projects for update
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

create policy "projects: delete own"
    on public.projects for delete
    using (user_id = auth.uid());

-- calculation_specs: access follows project ownership
create policy "calculation_specs: select own"
    on public.calculation_specs for select
    using (
        project_id in (select id from public.projects where user_id = auth.uid())
    );

create policy "calculation_specs: insert own"
    on public.calculation_specs for insert
    with check (
        project_id in (select id from public.projects where user_id = auth.uid())
    );

create policy "calculation_specs: update own"
    on public.calculation_specs for update
    using (
        project_id in (select id from public.projects where user_id = auth.uid())
    )
    with check (
        project_id in (select id from public.projects where user_id = auth.uid())
    );

create policy "calculation_specs: delete own"
    on public.calculation_specs for delete
    using (
        project_id in (select id from public.projects where user_id = auth.uid())
    );

-- ai_usage: users can only select own rows; insert via service role only
create policy "ai_usage: select own"
    on public.ai_usage for select
    using (user_id = auth.uid());
