-- 0002_storage.sql
-- Storage buckets and policies for GOST Calculator

-- ─────────────────────────────────────────────
-- Buckets
-- ─────────────────────────────────────────────
insert into storage.buckets (id, name, public)
values
    ('uploads', 'uploads', false),
    ('outputs', 'outputs', false)
on conflict (id) do nothing;

-- ─────────────────────────────────────────────
-- Storage RLS policies — uploads bucket
-- Path convention: uploads/{user_id}/{filename}
-- ─────────────────────────────────────────────
create policy "uploads: select own folder"
    on storage.objects for select
    using (
        bucket_id = 'uploads'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy "uploads: insert own folder"
    on storage.objects for insert
    with check (
        bucket_id = 'uploads'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy "uploads: update own folder"
    on storage.objects for update
    using (
        bucket_id = 'uploads'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy "uploads: delete own folder"
    on storage.objects for delete
    using (
        bucket_id = 'uploads'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

-- ─────────────────────────────────────────────
-- Storage RLS policies — outputs bucket
-- Path convention: outputs/{user_id}/{filename}
-- ─────────────────────────────────────────────
create policy "outputs: select own folder"
    on storage.objects for select
    using (
        bucket_id = 'outputs'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy "outputs: insert own folder"
    on storage.objects for insert
    with check (
        bucket_id = 'outputs'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy "outputs: update own folder"
    on storage.objects for update
    using (
        bucket_id = 'outputs'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy "outputs: delete own folder"
    on storage.objects for delete
    using (
        bucket_id = 'outputs'
        and (storage.foldername(name))[1] = auth.uid()::text
    );
