-- 0011_template_overrides.sql
-- Admin-editable overrides for fixed_template specs (normally read from
-- backend/templates/specs/{id}.json). A row here takes priority over the
-- file on disk; deleting the row reverts to the file.

CREATE TABLE gost_template_overrides (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  template_id text NOT NULL UNIQUE,
  display_name text NOT NULL,
  spec jsonb NOT NULL,
  updated_at timestamptz DEFAULT now(),
  updated_by text
);

ALTER TABLE gost_template_overrides
  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "read_authenticated"
  ON gost_template_overrides FOR SELECT
  TO authenticated USING (true);

CREATE POLICY "admin_write"
  ON gost_template_overrides FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE profiles.id = auth.uid()
      AND profiles.is_admin = true
    )
  );
