-- ============================================
-- Add display_year column to bibliography_entries
-- Created: 2026-01-15
-- Stores disambiguated year (e.g., "2025a", "2025b")
-- ============================================

-- Add display_year column
ALTER TABLE bibliography_entries
  ADD COLUMN IF NOT EXISTS display_year TEXT;

-- Comment
COMMENT ON COLUMN bibliography_entries.display_year IS 'Year with letter suffix for disambiguation (e.g., 2025a, 2025b)';
