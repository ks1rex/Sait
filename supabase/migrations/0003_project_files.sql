-- 0003_project_files.sql
-- Replace source_pdf_path on projects with a separate project_files table
-- that supports multiple source files (task / methodology / variant_data).
-- Dev stage: no production data, so we can drop the old column cleanly.

-- ─────────────────────────────────────────────
-- Drop deprecated column from projects
-- ─────────────────────────────────────────────
alter table public.projects drop column if exists source_pdf_path;

-- ─────────────────────────────────────────────
-- project_files
-- ─────────────────────────────────────────────
create table public.project_files (
    id           uuid        primary key default gen_random_uuid(),
    project_id   uuid        not null references public.projects (id) on delete cascade,
    file_type    text        not null
                             check (file_type in ('task', 'methodology', 'variant_data')),
    storage_path text        not null,
    original_name text       not null default '',
    created_at   timestamptz not null default now()
);

create index project_files_project_id_idx on public.project_files (project_id);

-- ─────────────────────────────────────────────
-- RLS
-- ─────────────────────────────────────────────
alter table public.project_files enable row level security;

create policy "project_files: select own"
    on public.project_files for select
    using (
        project_id in (select id from public.projects where user_id = auth.uid())
    );

create policy "project_files: insert own"
    on public.project_files for insert
    with check (
        project_id in (select id from public.projects where user_id = auth.uid())
    );

create policy "project_files: delete own"
    on public.project_files for delete
    using (
        project_id in (select id from public.projects where user_id = auth.uid())
    );
