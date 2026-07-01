-- 0007_tokens.sql
-- Token-based access system

-- ── 1. profiles: add token_balance ──────────────────────────────────────────
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS token_balance integer NOT NULL DEFAULT 0;

-- unlimited_access already exists from 0001_init.sql

-- ── 2. access_codes: replace duration_days with tokens ─────────────────────
ALTER TABLE public.access_codes
    DROP COLUMN IF EXISTS duration_days;

ALTER TABLE public.access_codes
    ADD COLUMN IF NOT EXISTS tokens integer NOT NULL DEFAULT 0;

-- ── 3. token_transactions ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.token_transactions (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid        NOT NULL REFERENCES public.profiles (id) ON DELETE CASCADE,
    amount      integer     NOT NULL,   -- positive = credit, negative = debit
    reason      text        NOT NULL,   -- 'code_redeem' | 'extract' | 'format_gost' | 'chat_turn' …
    project_id  uuid        REFERENCES public.projects (id) ON DELETE SET NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS token_transactions_user_id_idx
    ON public.token_transactions (user_id);

ALTER TABLE public.token_transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "token_transactions: select own"
    ON public.token_transactions FOR SELECT
    USING (user_id = auth.uid());

-- ── 4. RPC redeem_code ───────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.redeem_code(p_code text)
RETURNS integer          -- returns new token_balance
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_code_row  public.access_codes%ROWTYPE;
    v_tokens    integer;
    v_new_bal   integer;
BEGIN
    SELECT * INTO v_code_row
    FROM public.access_codes
    WHERE code = p_code AND used_by IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'invalid_or_used_code';
    END IF;

    v_tokens := v_code_row.tokens;

    UPDATE public.access_codes
    SET used_by = auth.uid(), used_at = now()
    WHERE id = v_code_row.id;

    UPDATE public.profiles
    SET token_balance = token_balance + v_tokens
    WHERE id = auth.uid()
    RETURNING token_balance INTO v_new_bal;

    INSERT INTO public.token_transactions (user_id, amount, reason)
    VALUES (auth.uid(), v_tokens, 'code_redeem');

    RETURN v_new_bal;
END;
$$;

GRANT EXECUTE ON FUNCTION public.redeem_code(text) TO authenticated;

-- ── 5. RPC consume_tokens ────────────────────────────────────────────────────
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
    SELECT unlimited_access, token_balance
    INTO v_unlimited, v_balance
    FROM public.profiles
    WHERE id = auth.uid();

    -- Admin bypass: log zero-cost transaction, don't touch balance
    IF v_unlimited THEN
        INSERT INTO public.token_transactions (user_id, amount, reason, project_id)
        VALUES (auth.uid(), 0, p_reason, p_project_id);
        RETURN true;
    END IF;

    IF v_balance < p_amount THEN
        -- Encode required/balance into message for client parsing
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

GRANT EXECUTE ON FUNCTION public.consume_tokens(integer, text, uuid) TO authenticated;
