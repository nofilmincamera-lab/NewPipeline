-- Migration: Add markdown content and organization UUID link to scraped_sites
-- Adds UUID to organizations and links scraped sites to organizations

-- 1. Add UUID column to organizations table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'organizations' AND column_name = 'uuid'
    ) THEN
        ALTER TABLE organizations ADD COLUMN uuid UUID DEFAULT uuid_generate_v4() UNIQUE;
        CREATE INDEX IF NOT EXISTS idx_organizations_uuid ON organizations(uuid);
    END IF;
END $$;

-- 2. Add markdown_content column to scraped_sites
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'scraped_sites' AND column_name = 'markdown_content'
    ) THEN
        ALTER TABLE scraped_sites ADD COLUMN markdown_content TEXT;
    END IF;
END $$;

-- 3. Add organization_uuid foreign key to scraped_sites
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'scraped_sites' AND column_name = 'organization_uuid'
    ) THEN
        ALTER TABLE scraped_sites ADD COLUMN organization_uuid UUID REFERENCES organizations(uuid) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_scraped_sites_org_uuid ON scraped_sites(organization_uuid);
    END IF;
END $$;

-- 4. Populate UUIDs for existing organizations that don't have them
UPDATE organizations SET uuid = uuid_generate_v4() WHERE uuid IS NULL;

-- 5. Link existing scraped_sites to organizations by domain
UPDATE scraped_sites ss
SET organization_uuid = o.uuid
FROM organizations o
WHERE ss.domain = o.domain
  AND ss.organization_uuid IS NULL;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bpo_user;

