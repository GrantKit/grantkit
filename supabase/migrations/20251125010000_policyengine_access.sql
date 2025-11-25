-- Allow all @policyengine.org users to access all grants
-- Drop existing policies
DROP POLICY IF EXISTS "Users can view own grants" ON grants;
DROP POLICY IF EXISTS "Users can insert own grants" ON grants;
DROP POLICY IF EXISTS "Users can update own grants" ON grants;
DROP POLICY IF EXISTS "Users can delete own grants" ON grants;

DROP POLICY IF EXISTS "Users can view responses for own grants" ON responses;
DROP POLICY IF EXISTS "Users can insert responses for own grants" ON responses;
DROP POLICY IF EXISTS "Users can update responses for own grants" ON responses;
DROP POLICY IF EXISTS "Users can delete responses for own grants" ON responses;

-- Create new policies for @policyengine.org domain access
-- Grants policies
CREATE POLICY "PolicyEngine users can view all grants" ON grants
  FOR SELECT USING (
    auth.jwt() ->> 'email' LIKE '%@policyengine.org'
  );

CREATE POLICY "PolicyEngine users can insert grants" ON grants
  FOR INSERT WITH CHECK (
    auth.jwt() ->> 'email' LIKE '%@policyengine.org'
  );

CREATE POLICY "PolicyEngine users can update grants" ON grants
  FOR UPDATE USING (
    auth.jwt() ->> 'email' LIKE '%@policyengine.org'
  );

CREATE POLICY "PolicyEngine users can delete grants" ON grants
  FOR DELETE USING (
    auth.jwt() ->> 'email' LIKE '%@policyengine.org'
  );

-- Responses policies
CREATE POLICY "PolicyEngine users can view all responses" ON responses
  FOR SELECT USING (
    auth.jwt() ->> 'email' LIKE '%@policyengine.org'
  );

CREATE POLICY "PolicyEngine users can insert responses" ON responses
  FOR INSERT WITH CHECK (
    auth.jwt() ->> 'email' LIKE '%@policyengine.org'
  );

CREATE POLICY "PolicyEngine users can update responses" ON responses
  FOR UPDATE USING (
    auth.jwt() ->> 'email' LIKE '%@policyengine.org'
  );

CREATE POLICY "PolicyEngine users can delete responses" ON responses
  FOR DELETE USING (
    auth.jwt() ->> 'email' LIKE '%@policyengine.org'
  );
