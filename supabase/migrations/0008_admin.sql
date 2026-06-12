-- 0008_admin.sql
-- Admin flag for profiles

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS is_admin boolean NOT NULL DEFAULT false;

-- Tighten the user-update policy: prevent self-elevation of is_admin
DROP POLICY IF EXISTS "profiles: update own non-sensitive fields" ON public.profiles;

CREATE POLICY "profiles: update own non-sensitive fields"
    ON public.profiles FOR UPDATE
    USING (id = auth.uid())
    WITH CHECK (
        id = auth.uid()
        AND has_access       = (SELECT has_access       FROM public.profiles WHERE id = auth.uid())
        AND unlimited_access = (SELECT unlimited_access FROM public.profiles WHERE id = auth.uid())
        AND is_admin         = (SELECT is_admin         FROM public.profiles WHERE id = auth.uid())
    );
