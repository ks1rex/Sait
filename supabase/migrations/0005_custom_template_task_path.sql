-- 0005_custom_template_task_path.sql
-- Add task_storage_path to custom_templates for minimal_edit sub_mode.

ALTER TABLE custom_templates
  ADD COLUMN IF NOT EXISTS task_storage_path text NULL;

COMMENT ON COLUMN custom_templates.task_storage_path IS
  'For minimal_edit sub_mode: storage path to the new task/variant file '
  '(PDF or TXT). NULL for format_only and chat.';
