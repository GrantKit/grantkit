-- Add JSONB columns for complex nested data from grant.yaml
-- This enables storing rich grant metadata while keeping core fields flat

-- Add columns for nested structures
ALTER TABLE grants ADD COLUMN IF NOT EXISTS metadata JSONB;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS project JSONB;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS contact JSONB;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS nsf_config JSONB;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS scope JSONB;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS impact JSONB;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS advisors JSONB;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS sustainability JSONB;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS budget JSONB;

-- Add individual fields that should be queryable
ALTER TABLE grants ADD COLUMN IF NOT EXISTS pi_name TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS pi_email TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS co_pi_name TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS fiscal_sponsor TEXT;

-- Add indexes for common queries on JSONB fields
CREATE INDEX IF NOT EXISTS idx_grants_metadata ON grants USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_grants_status ON grants (status);
