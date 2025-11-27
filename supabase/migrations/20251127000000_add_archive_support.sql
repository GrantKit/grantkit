-- Add archive support to grants table
-- Archived grants are soft-deleted with metadata preserved

-- Add archived_at and archived_reason columns
ALTER TABLE grants ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS archived_reason TEXT;

-- Index for filtering archived grants
CREATE INDEX IF NOT EXISTS idx_grants_archived_at ON grants(archived_at);

-- Add check constraint for valid archive reasons
ALTER TABLE grants ADD CONSTRAINT chk_archive_reason
  CHECK (archived_reason IS NULL OR archived_reason IN (
    'submitted', 'awarded', 'rejected', 'withdrawn',
    'superseded', 'expired', 'other'
  ));

-- Archive grants view (for convenience)
CREATE OR REPLACE VIEW archived_grants AS
SELECT
  g.*,
  CASE
    WHEN g.archived_at IS NOT NULL THEN 'archived'
    ELSE g.status
  END as effective_status
FROM grants g
WHERE g.archived_at IS NOT NULL;

-- Active grants view
CREATE OR REPLACE VIEW active_grants AS
SELECT *
FROM grants
WHERE archived_at IS NULL;

-- Function to archive a grant
CREATE OR REPLACE FUNCTION archive_grant(
  grant_id_param TEXT,
  reason_param TEXT DEFAULT NULL
)
RETURNS void AS $$
BEGIN
  UPDATE grants
  SET
    archived_at = NOW(),
    archived_reason = COALESCE(reason_param, 'other'),
    status = 'archived'
  WHERE id = grant_id_param
    AND user_id = auth.uid()
    AND archived_at IS NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to restore an archived grant
CREATE OR REPLACE FUNCTION restore_grant(
  grant_id_param TEXT,
  new_status TEXT DEFAULT 'draft'
)
RETURNS void AS $$
BEGIN
  UPDATE grants
  SET
    archived_at = NULL,
    archived_reason = NULL,
    status = new_status
  WHERE id = grant_id_param
    AND user_id = auth.uid()
    AND archived_at IS NOT NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON COLUMN grants.archived_at IS 'Timestamp when grant was archived, NULL if active';
COMMENT ON COLUMN grants.archived_reason IS 'Reason for archiving: submitted, awarded, rejected, withdrawn, superseded, expired, other';
