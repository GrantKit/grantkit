-- Internal documents table for letters, emails, budget files, etc.
-- These are NOT included in public share links
CREATE TABLE internal_documents (
  id SERIAL PRIMARY KEY,
  grant_id TEXT REFERENCES grants(id) ON DELETE CASCADE,
  doc_type TEXT NOT NULL, -- 'letter_request', 'email', 'budget', 'notes', etc.
  title TEXT NOT NULL,
  recipient TEXT, -- For letters/emails: who it's addressed to
  content TEXT,
  status TEXT DEFAULT 'draft', -- 'draft', 'sent', 'received'
  due_date DATE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE internal_documents ENABLE ROW LEVEL SECURITY;

-- RLS policy - only grant owner can see internal docs (NOT public)
CREATE POLICY "Users can manage own internal_documents" ON internal_documents FOR ALL USING (
  grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
);

-- Updated_at trigger
CREATE TRIGGER internal_documents_updated_at BEFORE UPDATE ON internal_documents
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Add index for faster lookups
CREATE INDEX idx_internal_documents_grant_id ON internal_documents(grant_id);
CREATE INDEX idx_internal_documents_doc_type ON internal_documents(doc_type);
