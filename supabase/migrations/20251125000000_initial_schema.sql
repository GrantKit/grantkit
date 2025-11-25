-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grants table
CREATE TABLE grants (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  foundation TEXT NOT NULL,
  program TEXT,
  deadline DATE,
  status TEXT DEFAULT 'draft',
  amount_requested INTEGER,
  duration_years NUMERIC,
  path TEXT,
  scope TEXT,
  solicitation_url TEXT,
  repo_url TEXT,
  user_id UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Responses table
CREATE TABLE responses (
  id SERIAL PRIMARY KEY,
  grant_id TEXT REFERENCES grants(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  title TEXT NOT NULL,
  question TEXT,
  content TEXT,
  word_limit INTEGER,
  char_limit INTEGER,
  status TEXT DEFAULT 'draft',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(grant_id, key)
);

-- Key deliverables table
CREATE TABLE deliverables (
  id SERIAL PRIMARY KEY,
  grant_id TEXT REFERENCES grants(id) ON DELETE CASCADE,
  description TEXT NOT NULL,
  sort_order INTEGER DEFAULT 0
);

-- Reports table
CREATE TABLE reports (
  id SERIAL PRIMARY KEY,
  grant_id TEXT REFERENCES grants(id) ON DELETE CASCADE,
  period TEXT,
  type TEXT,
  report_date DATE,
  content TEXT
);

-- Enable RLS
ALTER TABLE grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE deliverables ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

-- RLS policies (allow authenticated users to see their own data)
CREATE POLICY "Users can view own grants" ON grants FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own grants" ON grants FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own grants" ON grants FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own grants" ON grants FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own responses" ON responses FOR SELECT USING (
  grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
);
CREATE POLICY "Users can insert own responses" ON responses FOR INSERT WITH CHECK (
  grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
);
CREATE POLICY "Users can update own responses" ON responses FOR UPDATE USING (
  grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
);
CREATE POLICY "Users can delete own responses" ON responses FOR DELETE USING (
  grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
);

-- Similar for deliverables and reports
CREATE POLICY "Users can manage own deliverables" ON deliverables FOR ALL USING (
  grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
);
CREATE POLICY "Users can manage own reports" ON reports FOR ALL USING (
  grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER grants_updated_at BEFORE UPDATE ON grants
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER responses_updated_at BEFORE UPDATE ON responses
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
