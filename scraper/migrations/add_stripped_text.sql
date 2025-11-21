-- Migration: Add stripped_text column to scraped_sites
-- Stores visible text extracted from HTML (HTML tags removed)

-- Add stripped_text column to scraped_sites
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'scraped_sites' AND column_name = 'stripped_text'
    ) THEN
        ALTER TABLE scraped_sites ADD COLUMN stripped_text TEXT;
        CREATE INDEX IF NOT EXISTS idx_scraped_sites_stripped_text ON scraped_sites USING gin(to_tsvector('english', stripped_text));
    END IF;
END $$;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bpo_user;

