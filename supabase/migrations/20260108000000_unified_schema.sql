-- ============================================
-- GrantKit Unified Schema Migration
-- Created: 2026-01-08
-- Consolidates all previous migrations into a clean initial schema
-- ============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- CORE TABLES
-- ============================================

-- Grants table (main entity)
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
  solicitation_url TEXT,
  repo_url TEXT,
  user_id UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Nested JSONB fields for complex data
  metadata JSONB,
  project JSONB,
  contact JSONB,
  nsf_config JSONB,
  scope JSONB,
  impact JSONB,
  advisors JSONB,
  sustainability JSONB,
  budget JSONB,

  -- Queryable fields
  pi_name TEXT,
  pi_email TEXT,
  co_pi_name TEXT,
  fiscal_sponsor TEXT,

  -- Archive support
  archived_at TIMESTAMPTZ,
  archived_reason TEXT CHECK (archived_reason IS NULL OR archived_reason IN (
    'submitted', 'awarded', 'rejected', 'withdrawn', 'superseded', 'expired', 'other'
  ))
);

-- Responses table (grant proposal sections)
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

-- Deliverables table
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

-- Profiles table (user lookup)
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT UNIQUE NOT NULL,
  full_name TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Grant collaborators (sharing)
CREATE TABLE grant_collaborators (
  id SERIAL PRIMARY KEY,
  grant_id TEXT NOT NULL REFERENCES grants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  user_email TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('viewer', 'editor', 'owner')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(grant_id, user_id)
);

-- Waitlist table
CREATE TABLE waitlist (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Device codes for CLI OAuth flow
CREATE TABLE device_codes (
  id SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  access_token TEXT,
  refresh_token TEXT,
  expires_at BIGINT,
  user_email TEXT,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'complete', 'expired')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX idx_grants_metadata ON grants USING GIN (metadata);
CREATE INDEX idx_grants_status ON grants (status);
CREATE INDEX idx_grants_archived_at ON grants(archived_at);
CREATE INDEX idx_grants_user_id ON grants(user_id);
CREATE INDEX idx_grant_collaborators_grant_id ON grant_collaborators(grant_id);
CREATE INDEX idx_grant_collaborators_user_id ON grant_collaborators(user_id);
CREATE INDEX idx_device_codes_code ON device_codes(code);
CREATE INDEX idx_device_codes_created ON device_codes(created_at);
CREATE INDEX idx_responses_grant_id ON responses(grant_id);

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Check grant access (SECURITY DEFINER to bypass RLS)
CREATE OR REPLACE FUNCTION check_grant_access(p_grant_id text, p_user_id uuid)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM grants g WHERE g.id = p_grant_id AND g.user_id = p_user_id
  )
  OR EXISTS (
    SELECT 1 FROM grant_collaborators gc WHERE gc.grant_id = p_grant_id AND gc.user_id = p_user_id
  );
$$;

-- Check if user is grant owner
CREATE OR REPLACE FUNCTION is_grant_owner(p_grant_id text, p_user_id uuid)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
  SELECT EXISTS (SELECT 1 FROM grants WHERE id = p_grant_id AND user_id = p_user_id);
$$;

-- Check if user is editor on grant
CREATE OR REPLACE FUNCTION is_grant_editor(p_grant_id text, p_user_id uuid)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM grant_collaborators
    WHERE grant_id = p_grant_id AND user_id = p_user_id AND role = 'editor'
  );
$$;

-- Archive grant function
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

-- Restore archived grant function
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

-- Cleanup expired device codes
CREATE OR REPLACE FUNCTION cleanup_expired_device_codes()
RETURNS void AS $$
BEGIN
  UPDATE device_codes
  SET status = 'expired'
  WHERE status = 'pending'
    AND created_at < NOW() - INTERVAL '10 minutes';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get user ID by email (for collaborator lookup)
CREATE OR REPLACE FUNCTION get_user_id_by_email(lookup_email TEXT)
RETURNS TABLE(user_id UUID, user_email TEXT) AS $$
BEGIN
  RETURN QUERY
  SELECT p.id, p.email
  FROM profiles p
  WHERE p.email = lookup_email
  LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Auto-create profile on user signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO profiles (id, email, full_name)
  VALUES (new.id, new.email, new.raw_user_meta_data->>'full_name')
  ON CONFLICT (id) DO UPDATE
  SET email = EXCLUDED.email,
      full_name = COALESCE(EXCLUDED.full_name, profiles.full_name),
      updated_at = NOW();
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- TRIGGERS
-- ============================================

CREATE TRIGGER grants_updated_at BEFORE UPDATE ON grants
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER responses_updated_at BEFORE UPDATE ON responses
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER profiles_updated_at BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Trigger to auto-create profile on user signup
CREATE TRIGGER on_auth_user_created
  AFTER INSERT OR UPDATE ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ============================================
-- VIEWS
-- ============================================

CREATE OR REPLACE VIEW archived_grants AS
SELECT
  g.*,
  CASE
    WHEN g.archived_at IS NOT NULL THEN 'archived'
    ELSE g.status
  END as effective_status
FROM grants g
WHERE g.archived_at IS NOT NULL;

CREATE OR REPLACE VIEW active_grants AS
SELECT *
FROM grants
WHERE archived_at IS NULL;

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE deliverables ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE grant_collaborators ENABLE ROW LEVEL SECURITY;
ALTER TABLE waitlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_codes ENABLE ROW LEVEL SECURITY;

-- ============================================
-- GRANTS POLICIES
-- ============================================

CREATE POLICY "grants_select" ON grants
  FOR SELECT USING (
    user_id = auth.uid()
    OR check_grant_access(id, auth.uid())
  );

CREATE POLICY "grants_insert" ON grants
  FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY "grants_update" ON grants
  FOR UPDATE USING (
    user_id = auth.uid()
    OR is_grant_editor(id, auth.uid())
  );

CREATE POLICY "grants_delete" ON grants
  FOR DELETE USING (user_id = auth.uid());

-- ============================================
-- RESPONSES POLICIES
-- ============================================

CREATE POLICY "responses_select" ON responses
  FOR SELECT USING (check_grant_access(grant_id, auth.uid()));

CREATE POLICY "responses_insert" ON responses
  FOR INSERT WITH CHECK (
    is_grant_owner(grant_id, auth.uid())
    OR is_grant_editor(grant_id, auth.uid())
  );

CREATE POLICY "responses_update" ON responses
  FOR UPDATE USING (
    is_grant_owner(grant_id, auth.uid())
    OR is_grant_editor(grant_id, auth.uid())
  );

CREATE POLICY "responses_delete" ON responses
  FOR DELETE USING (is_grant_owner(grant_id, auth.uid()));

-- ============================================
-- DELIVERABLES & REPORTS POLICIES
-- ============================================

CREATE POLICY "deliverables_all" ON deliverables
  FOR ALL USING (check_grant_access(grant_id, auth.uid()));

CREATE POLICY "reports_all" ON reports
  FOR ALL USING (check_grant_access(grant_id, auth.uid()));

-- ============================================
-- PROFILES POLICIES
-- ============================================

CREATE POLICY "profiles_select" ON profiles
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "profiles_update" ON profiles
  FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "profiles_insert" ON profiles
  FOR INSERT WITH CHECK (auth.uid() = id);

-- ============================================
-- GRANT_COLLABORATORS POLICIES
-- ============================================

CREATE POLICY "collaborators_select_own" ON grant_collaborators
  FOR SELECT USING (user_id = auth.uid());

CREATE POLICY "collaborators_select_owner" ON grant_collaborators
  FOR SELECT USING (is_grant_owner(grant_id, auth.uid()));

CREATE POLICY "collaborators_insert" ON grant_collaborators
  FOR INSERT WITH CHECK (is_grant_owner(grant_id, auth.uid()));

CREATE POLICY "collaborators_delete" ON grant_collaborators
  FOR DELETE USING (is_grant_owner(grant_id, auth.uid()));

-- ============================================
-- WAITLIST POLICIES
-- ============================================

CREATE POLICY "waitlist_insert" ON waitlist
  FOR INSERT WITH CHECK (true);

-- ============================================
-- DEVICE_CODES POLICIES
-- ============================================

CREATE POLICY "device_codes_insert" ON device_codes
  FOR INSERT WITH CHECK (status = 'pending' AND user_id IS NULL);

CREATE POLICY "device_codes_select" ON device_codes
  FOR SELECT USING (true);

CREATE POLICY "device_codes_update" ON device_codes
  FOR UPDATE USING (true) WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

-- ============================================
-- GRANTS
-- ============================================

GRANT EXECUTE ON FUNCTION get_user_id_by_email(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION archive_grant(TEXT, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION restore_grant(TEXT, TEXT) TO authenticated;

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE grants IS 'Grant proposals and applications';
COMMENT ON TABLE responses IS 'Individual sections/responses within a grant proposal';
COMMENT ON TABLE deliverables IS 'Key deliverables for a grant';
COMMENT ON TABLE reports IS 'Progress and final reports for grants';
COMMENT ON TABLE profiles IS 'User profiles synced from auth.users';
COMMENT ON TABLE grant_collaborators IS 'Shared access to grants';
COMMENT ON TABLE waitlist IS 'Email waitlist for non-PolicyEngine users';
COMMENT ON TABLE device_codes IS 'OAuth device codes for CLI authentication';
COMMENT ON COLUMN grants.archived_at IS 'Timestamp when grant was archived, NULL if active';
COMMENT ON COLUMN grants.archived_reason IS 'Reason for archiving: submitted, awarded, rejected, withdrawn, superseded, expired, other';
