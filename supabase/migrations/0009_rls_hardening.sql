-- 0009_rls_hardening.sql
-- Security audit fixes:
-- 1. profiles: the user-update policy pinned has_access/unlimited_access/is_admin
--    but NOT token_balance — any authenticated user could set their own balance
--    via a direct PostgREST PATCH with the public anon key.
-- 2. access_codes: "select any unused" let every authenticated user enumerate
--    all unused codes (code text + token value) and redeem them for free.
--    redeem_code() is SECURITY DEFINER and does not rely on this policy.

-- ── 1. profiles: forbid direct change of token_balance ──────────────────────
DROP POLICY IF EXISTS "profiles: update own non-sensitive fields" ON public.profiles;

CREATE POLICY "profiles: update own non-sensitive fields"
    ON public.profiles FOR UPDATE
    USING (id = auth.uid())
    WITH CHECK (
        id = auth.uid()
        AND has_access       = (SELECT has_access       FROM public.profiles WHERE id = auth.uid())
        AND unlimited_access = (SELECT unlimited_access FROM public.profiles WHERE id = auth.uid())
        AND is_admin         = (SELECT is_admin         FROM public.profiles WHERE id = auth.uid())
        AND token_balance    = (SELECT token_balance    FROM public.profiles WHERE id = auth.uid())
    );

-- ── 2. access_codes: users may see only codes they have already redeemed ────
DROP POLICY IF EXISTS "access_codes: select any unused" ON public.access_codes;

CREATE POLICY "access_codes: select own redeemed"
    ON public.access_codes FOR SELECT
    USING (used_by = auth.uid());
