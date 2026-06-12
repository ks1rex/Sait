-- 0006_nullable_source_path.sql
-- Allow source_storage_path to be NULL in custom_templates.
-- Required for chat sub_mode where a template is optional
-- (user starts from scratch with no reference document).

ALTER TABLE custom_templates
  ALTER COLUMN source_storage_path DROP NOT NULL;

COMMENT ON COLUMN custom_templates.source_storage_path IS
  'Storage path to the reference docx template. '
  'NULL for chat sub_mode when no template is provided.';
