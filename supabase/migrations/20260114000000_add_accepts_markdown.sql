-- Add accepts_markdown field to grants table
-- Default is true (most grants accept rich formatting)
-- Set to false for grants that only accept plain text (like Nuffield Foundation)

ALTER TABLE grants ADD COLUMN IF NOT EXISTS accepts_markdown BOOLEAN DEFAULT true;

COMMENT ON COLUMN grants.accepts_markdown IS 'Whether the grant portal accepts markdown/rich text formatting. False means plain text only.';
