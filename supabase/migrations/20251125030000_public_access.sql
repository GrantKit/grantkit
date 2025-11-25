-- Allow public access for development/single-user mode
-- In production, you'd use authenticated users with proper RLS

-- Drop existing restrictive policies
DROP POLICY IF EXISTS "Users can view own grants" ON grants;
DROP POLICY IF EXISTS "Users can insert own grants" ON grants;
DROP POLICY IF EXISTS "Users can update own grants" ON grants;
DROP POLICY IF EXISTS "Users can delete own grants" ON grants;

DROP POLICY IF EXISTS "Users can view own responses" ON responses;
DROP POLICY IF EXISTS "Users can insert own responses" ON responses;
DROP POLICY IF EXISTS "Users can update own responses" ON responses;
DROP POLICY IF EXISTS "Users can delete own responses" ON responses;

DROP POLICY IF EXISTS "Users can manage own deliverables" ON deliverables;
DROP POLICY IF EXISTS "Users can manage own reports" ON reports;

-- Create permissive policies for all operations
CREATE POLICY "Allow all access to grants" ON grants FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access to responses" ON responses FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access to deliverables" ON deliverables FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access to reports" ON reports FOR ALL USING (true) WITH CHECK (true);
