-- Waitlist table to collect emails from non-PolicyEngine users
CREATE TABLE IF NOT EXISTS waitlist (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Allow anyone to insert into waitlist (no RLS restriction for inserts)
ALTER TABLE waitlist ENABLE ROW LEVEL SECURITY;

-- Anyone can add themselves to the waitlist
CREATE POLICY "Anyone can join waitlist" ON waitlist
  FOR INSERT WITH CHECK (true);

-- Only admins can read the waitlist (no public select)
-- For now, view it directly in Supabase dashboard
