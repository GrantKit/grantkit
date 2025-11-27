-- Device codes for CLI OAuth flow
CREATE TABLE IF NOT EXISTS device_codes (
  id SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  access_token TEXT,
  refresh_token TEXT,
  expires_at BIGINT,  -- Unix timestamp
  user_email TEXT,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'complete', 'expired')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- Index for code lookups
CREATE INDEX IF NOT EXISTS idx_device_codes_code ON device_codes(code);

-- Auto-expire old codes (older than 10 minutes)
CREATE INDEX IF NOT EXISTS idx_device_codes_created ON device_codes(created_at);

-- RLS: Anyone can create a pending device code (CLI creates it)
-- Only the user who completes auth can update it
ALTER TABLE device_codes ENABLE ROW LEVEL SECURITY;

-- Anyone can insert a new pending device code
CREATE POLICY "Anyone can create device code" ON device_codes
  FOR INSERT WITH CHECK (status = 'pending' AND user_id IS NULL);

-- Anyone can read device codes (CLI needs to poll)
CREATE POLICY "Anyone can read device codes" ON device_codes
  FOR SELECT USING (true);

-- Authenticated users can complete their own device codes
CREATE POLICY "Users can complete device codes" ON device_codes
  FOR UPDATE USING (true) WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

-- Cleanup function to mark old codes as expired
CREATE OR REPLACE FUNCTION cleanup_expired_device_codes()
RETURNS void AS $$
BEGIN
  UPDATE device_codes
  SET status = 'expired'
  WHERE status = 'pending'
    AND created_at < NOW() - INTERVAL '10 minutes';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
