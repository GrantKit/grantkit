-- FIX: Remove overly permissive policies and restore proper user-scoped RLS
-- This fixes the security bug where any authenticated user could see all grants

-- Drop all existing permissive policies
DROP POLICY IF EXISTS "Allow all access to grants" ON grants;
DROP POLICY IF EXISTS "Allow all access to responses" ON responses;
DROP POLICY IF EXISTS "Allow all access to deliverables" ON deliverables;
DROP POLICY IF EXISTS "Allow all access to reports" ON reports;
DROP POLICY IF EXISTS "PolicyEngine users can view all grants" ON grants;
DROP POLICY IF EXISTS "PolicyEngine users can insert grants" ON grants;
DROP POLICY IF EXISTS "PolicyEngine users can update grants" ON grants;
DROP POLICY IF EXISTS "PolicyEngine users can delete grants" ON grants;
DROP POLICY IF EXISTS "PolicyEngine users can view all responses" ON responses;
DROP POLICY IF EXISTS "PolicyEngine users can insert responses" ON responses;
DROP POLICY IF EXISTS "PolicyEngine users can update responses" ON responses;
DROP POLICY IF EXISTS "PolicyEngine users can delete responses" ON responses;

-- Create proper user-scoped policies for grants
-- Users can only see/modify their own grants
CREATE POLICY "Users can view own grants" ON grants
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own grants" ON grants
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own grants" ON grants
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own grants" ON grants
  FOR DELETE USING (auth.uid() = user_id);

-- Create proper user-scoped policies for responses
CREATE POLICY "Users can view own responses" ON responses
  FOR SELECT USING (
    grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can insert own responses" ON responses
  FOR INSERT WITH CHECK (
    grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can update own responses" ON responses
  FOR UPDATE USING (
    grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
  );

CREATE POLICY "Users can delete own responses" ON responses
  FOR DELETE USING (
    grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
  );

-- Create proper user-scoped policies for deliverables
CREATE POLICY "Users can manage own deliverables" ON deliverables
  FOR ALL USING (
    grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
  );

-- Create proper user-scoped policies for reports
CREATE POLICY "Users can manage own reports" ON reports
  FOR ALL USING (
    grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
  );

-- Create proper user-scoped policies for internal_documents
DROP POLICY IF EXISTS "Users can manage own internal_documents" ON internal_documents;
CREATE POLICY "Users can manage own internal_documents" ON internal_documents
  FOR ALL USING (
    grant_id IN (SELECT id FROM grants WHERE user_id = auth.uid())
  );

-- PUBLIC SHARE ACCESS: Allow anonymous read access to grants with share_token
-- This enables the /share/:token feature without authentication
CREATE POLICY "Public can view shared grants" ON grants
  FOR SELECT USING (share_token IS NOT NULL);

CREATE POLICY "Public can view shared grant responses" ON responses
  FOR SELECT USING (
    grant_id IN (SELECT id FROM grants WHERE share_token IS NOT NULL)
  );
