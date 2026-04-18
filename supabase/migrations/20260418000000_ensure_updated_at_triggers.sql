-- ============================================
-- Ensure updated_at columns + triggers on all
-- mutable tables so the CLI sync baseline can
-- detect cloud drift when the web app edits a row.
-- Created: 2026-04-18
-- ============================================

-- internal_documents (letters, emails, budget notes, collaboration docs
-- created in the web app). The table is managed outside migrations
-- historically; add the column + trigger idempotently.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'internal_documents'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'internal_documents' AND column_name = 'updated_at'
    ) THEN
      ALTER TABLE internal_documents
        ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
    END IF;

    DROP TRIGGER IF EXISTS internal_documents_updated_at ON internal_documents;
    CREATE TRIGGER internal_documents_updated_at
      BEFORE UPDATE ON internal_documents
      FOR EACH ROW EXECUTE FUNCTION update_updated_at();
  END IF;
END $$;

-- grant_permissions — newer table, ensure trigger if present.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'grant_permissions'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'grant_permissions' AND column_name = 'updated_at'
    ) THEN
      ALTER TABLE grant_permissions
        ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
    END IF;

    DROP TRIGGER IF EXISTS grant_permissions_updated_at ON grant_permissions;
    CREATE TRIGGER grant_permissions_updated_at
      BEFORE UPDATE ON grant_permissions
      FOR EACH ROW EXECUTE FUNCTION update_updated_at();
  END IF;
END $$;

-- Touch grants.updated_at when a response is edited. The CLI conflict
-- detection reads grant-level updated_at for quick drift checks; this
-- makes web-side response edits visible as grant drift even if the
-- agent isn't tracking individual responses.
CREATE OR REPLACE FUNCTION touch_parent_grant()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE grants SET updated_at = NOW() WHERE id = COALESCE(NEW.grant_id, OLD.grant_id);
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS responses_touch_grant ON responses;
CREATE TRIGGER responses_touch_grant
  AFTER INSERT OR UPDATE OR DELETE ON responses
  FOR EACH ROW EXECUTE FUNCTION touch_parent_grant();

DROP TRIGGER IF EXISTS bibliography_touch_grant ON bibliography_entries;
CREATE TRIGGER bibliography_touch_grant
  AFTER INSERT OR UPDATE OR DELETE ON bibliography_entries
  FOR EACH ROW EXECUTE FUNCTION touch_parent_grant();
