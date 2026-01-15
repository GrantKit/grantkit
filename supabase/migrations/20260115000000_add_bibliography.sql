-- ============================================
-- Add Bibliography Support
-- Created: 2026-01-15
-- Stores bibtex entries for citation rendering
-- ============================================

-- Bibliography entries table (parsed bibtex)
CREATE TABLE bibliography_entries (
  id SERIAL PRIMARY KEY,
  grant_id TEXT REFERENCES grants(id) ON DELETE CASCADE,
  citation_key TEXT NOT NULL,  -- e.g., "hm_treasury_atr_2024"
  entry_type TEXT NOT NULL,    -- e.g., "article", "book", "misc"
  title TEXT NOT NULL,
  authors JSONB,               -- Array of author names
  year TEXT,
  journal TEXT,
  volume TEXT,
  pages TEXT,
  publisher TEXT,
  institution TEXT,
  url TEXT,
  doi TEXT,
  raw_bibtex TEXT,             -- Original bibtex entry for reference
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(grant_id, citation_key)
);

-- Index for fast lookups
CREATE INDEX idx_bibliography_grant_id ON bibliography_entries(grant_id);
CREATE INDEX idx_bibliography_citation_key ON bibliography_entries(citation_key);

-- Updated_at trigger
CREATE TRIGGER bibliography_entries_updated_at BEFORE UPDATE ON bibliography_entries
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RLS
ALTER TABLE bibliography_entries ENABLE ROW LEVEL SECURITY;

-- Policies - same access as responses
CREATE POLICY "bibliography_select" ON bibliography_entries
  FOR SELECT USING (check_grant_access(grant_id, auth.uid()));

CREATE POLICY "bibliography_insert" ON bibliography_entries
  FOR INSERT WITH CHECK (
    is_grant_owner(grant_id, auth.uid())
    OR is_grant_editor(grant_id, auth.uid())
  );

CREATE POLICY "bibliography_update" ON bibliography_entries
  FOR UPDATE USING (
    is_grant_owner(grant_id, auth.uid())
    OR is_grant_editor(grant_id, auth.uid())
  );

CREATE POLICY "bibliography_delete" ON bibliography_entries
  FOR DELETE USING (is_grant_owner(grant_id, auth.uid()));

COMMENT ON TABLE bibliography_entries IS 'Parsed bibtex entries for citation rendering in grants';
COMMENT ON COLUMN bibliography_entries.citation_key IS 'Key used in [@key] citations';
COMMENT ON COLUMN bibliography_entries.authors IS 'JSON array of author names in order';
