-- 0010_billing_atomicity.sql
-- Close TOCTOU windows in the two billing RPCs.
--
-- Both functions did: SELECT (check) ... then UPDATE, with no row lock in
-- between. Under concurrent calls for the same user/code, two transactions
-- could pass the check against a stale snapshot and both apply the UPDATE
-- (double-spend into a negative balance / double-credit of one code).
-- Adding SELECT ... FOR UPDATE serializes concurrent callers on the row.

-- ── consume_tokens: lock the profile row before checking the balance ────────
CREATE OR REPLACE FUNCTION public.consume_tokens(
    p_amount     integer,
    p_reason     text,
    p_project_id uuid DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_unlimited boolean;
    v_balance   integer;
BEGIN
    IF p_amount < 0 THEN
        RAISE EXCEPTION 'invalid_amount';
    END IF;

    SELECT unlimited_access, token_balance
    INTO v_unlimited, v_balance
    FROM public.profiles
    WHERE id = auth.uid()
    FOR UPDATE;          -- row lock: concurrent calls wait here

    IF NOT FOUND THEN
        RAISE EXCEPTION 'profile_not_found';
    END IF;

    IF v_unlimited THEN
        INSERT INTO public.token_transactions (user_id, amount, reason, project_id)
        VALUES (auth.uid(), 0, p_reason, p_project_id);
        RETURN true;
    END IF;

    IF v_balance < p_amount THEN
        RAISE EXCEPTION 'insufficient_tokens need=% have=%', p_amount, v_balance;
    END IF;

    UPDATE public.profiles
    SET token_balance = token_balance - p_amount
    WHERE id = auth.uid();

    INSERT INTO public.token_transactions (user_id, amount, reason, project_id)
    VALUES (auth.uid(), -p_amount, p_reason, p_project_id);

    RETURN true;
END;
$$;

-- ── redeem_code: atomic claim of the code row ───────────────────────────────
CREATE OR REPLACE FUNCTION public.redeem_code(p_code text)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_code_id   uuid;
    v_tokens    integer;
    v_new_bal   integer;
BEGIN
    -- Claim the code atomically: only one concurrent caller can flip used_by
    -- from NULL, because the row is locked and re-checked under the lock.
    SELECT id, tokens INTO v_code_id, v_tokens
    FROM public.access_codes
    WHERE code = p_code AND used_by IS NULL
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'invalid_or_used_code';
    END IF;

    UPDATE public.access_codes
    SET used_by = auth.uid(), used_at = now()
    WHERE id = v_code_id;

    UPDATE public.profiles
    SET token_balance = token_balance + v_tokens
    WHERE id = auth.uid()
    RETURNING token_balance INTO v_new_bal;

    INSERT INTO public.token_transactions (user_id, amount, reason)
    VALUES (auth.uid(), v_tokens, 'code_redeem');

    RETURN v_new_bal;
END;
$$;
