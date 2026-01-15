-- ============================================
-- Add Sort Order to Responses
-- Created: 2026-01-15
-- Allows responses to be ordered by section position from grant.yaml
-- ============================================

-- Add sort_order column (nullable to not break existing rows)
ALTER TABLE responses ADD COLUMN IF NOT EXISTS sort_order INTEGER;

-- Index for ordering
CREATE INDEX IF NOT EXISTS idx_responses_sort_order ON responses(grant_id, sort_order);

-- Update order to use sort_order if available, fall back to key
COMMENT ON COLUMN responses.sort_order IS 'Order from grant.yaml sections, lowest first';
