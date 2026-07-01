-- 0004_generation_modes.sql
-- Adds generation mode support to projects and two new tables for
-- custom templates and chat history.

-- ---------------------------------------------------------------------------
-- 1. Extend projects table
-- ---------------------------------------------------------------------------

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS generation_mode text
    NOT NULL DEFAULT 'universal'
    CHECK (generation_mode IN ('universal', 'fixed_template', 'custom_template')),
  ADD COLUMN IF NOT EXISTS template_id text NULL;

COMMENT ON COLUMN projects.generation_mode IS
  'universal = AI extracts spec from scratch; '
  'fixed_template = use a built-in template spec; '
  'custom_template = user-supplied docx/pdf as reference';

COMMENT ON COLUMN projects.template_id IS
  'For fixed_template: id from templates/manifest.json. '
  'For other modes: NULL.';

-- ---------------------------------------------------------------------------
-- 2. custom_templates
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS custom_templates (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id          uuid NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
  source_storage_path text NOT NULL,
  -- format_only  = apply GOST styles only, no AI processing
  -- minimal_edit = AI makes minimal structural changes
  -- chat         = interactive chat to refine the document
  sub_mode            text NOT NULL DEFAULT 'format_only'
    CHECK (sub_mode IN ('format_only', 'minimal_edit', 'chat')),
  created_at          timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE custom_templates ENABLE ROW LEVEL SECURITY;

-- Users can only access custom_templates for their own projects
CREATE POLICY "custom_templates: owner full access"
  ON custom_templates
  FOR ALL
  USING (
    project_id IN (
      SELECT id FROM projects WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    project_id IN (
      SELECT id FROM projects WHERE user_id = auth.uid()
    )
  );

-- ---------------------------------------------------------------------------
-- 3. chat_messages
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chat_messages (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  role       text NOT NULL CHECK (role IN ('user', 'assistant')),
  content    text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- Users can only access chat messages for their own projects
CREATE POLICY "chat_messages: owner full access"
  ON chat_messages
  FOR ALL
  USING (
    project_id IN (
      SELECT id FROM projects WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    project_id IN (
      SELECT id FROM projects WHERE user_id = auth.uid()
    )
  );

-- Index for chronological chat retrieval per project
CREATE INDEX IF NOT EXISTS chat_messages_project_created
  ON chat_messages (project_id, created_at);
