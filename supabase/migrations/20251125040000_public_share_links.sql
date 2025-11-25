-- Add public share token for grants
-- Allows sharing via URL without authentication

-- Add share_token column (nullable - only set when sharing is enabled)
ALTER TABLE grants ADD COLUMN IF NOT EXISTS share_token TEXT UNIQUE;

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_grants_share_token ON grants (share_token) WHERE share_token IS NOT NULL;

-- Function to generate a random share token
CREATE OR REPLACE FUNCTION generate_share_token()
RETURNS TEXT AS $$
BEGIN
  RETURN encode(gen_random_bytes(16), 'hex');
END;
$$ LANGUAGE plpgsql;
