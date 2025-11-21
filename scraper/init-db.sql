-- Database initialization for BPO Intelligence System
-- Creates all necessary tables and indexes

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Scraped sites table
CREATE TABLE IF NOT EXISTS scraped_sites (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    url TEXT UNIQUE NOT NULL,
    domain VARCHAR(255) NOT NULL,
    title TEXT,
    content_hash VARCHAR(64),
    scraped_at TIMESTAMP NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    status_code INTEGER,
    response_time FLOAT,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    proxy_used BOOLEAN DEFAULT false,
    cost FLOAT DEFAULT 0.0,
    metadata JSONB,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_scraped_sites_domain ON scraped_sites(domain);
CREATE INDEX IF NOT EXISTS idx_scraped_sites_scraped_at ON scraped_sites(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_sites_success ON scraped_sites(success);
CREATE INDEX IF NOT EXISTS idx_scraped_sites_content_hash ON scraped_sites(content_hash);
CREATE INDEX IF NOT EXISTS idx_scraped_sites_strategy ON scraped_sites(strategy);

-- Domain proxy requirements table
CREATE TABLE IF NOT EXISTS domain_proxy_requirements (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    requires_proxy BOOLEAN DEFAULT false,
    preferred_provider VARCHAR(50),
    last_direct_attempt TIMESTAMP,
    last_direct_success TIMESTAMP,
    direct_success_count INTEGER DEFAULT 0,
    direct_failure_count INTEGER DEFAULT 0,
    proxy_success_count INTEGER DEFAULT 0,
    proxy_failure_count INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_domain_proxy_domain ON domain_proxy_requirements(domain);
CREATE INDEX IF NOT EXISTS idx_domain_proxy_requires ON domain_proxy_requirements(requires_proxy);

-- Proxy usage log table
CREATE TABLE IF NOT EXISTS proxy_usage_log (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    proxy_provider VARCHAR(50),
    proxy_country VARCHAR(10),
    success BOOLEAN NOT NULL,
    response_time_ms INTEGER,
    status_code INTEGER,
    error_message TEXT,
    bytes_transferred BIGINT,
    cost_estimate DECIMAL(10, 4),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_proxy_usage_domain ON proxy_usage_log(domain);
CREATE INDEX IF NOT EXISTS idx_proxy_usage_timestamp ON proxy_usage_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_proxy_usage_provider ON proxy_usage_log(proxy_provider);

-- Downloaded files table (for PDF/DOC files)
CREATE TABLE IF NOT EXISTS downloaded_files (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    source_url TEXT NOT NULL,
    file_url TEXT UNIQUE NOT NULL,
    domain VARCHAR(255) NOT NULL,
    file_type VARCHAR(10) NOT NULL CHECK (file_type IN ('pdf', 'doc', 'docx')),
    original_filename TEXT,
    stored_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    file_hash VARCHAR(64),
    content_type VARCHAR(100),
    parent_page_url TEXT,
    download_status VARCHAR(20) DEFAULT 'pending' CHECK (download_status IN ('pending', 'downloaded', 'failed')),
    download_error TEXT,
    ocr_status VARCHAR(20) DEFAULT 'pending' CHECK (ocr_status IN ('pending', 'processing', 'completed', 'failed')),
    ocr_error TEXT,
    metadata JSONB,
    downloaded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for downloaded_files
CREATE INDEX IF NOT EXISTS idx_downloaded_files_domain ON downloaded_files(domain);
CREATE INDEX IF NOT EXISTS idx_downloaded_files_file_type ON downloaded_files(file_type);
CREATE INDEX IF NOT EXISTS idx_downloaded_files_download_status ON downloaded_files(download_status);
CREATE INDEX IF NOT EXISTS idx_downloaded_files_ocr_status ON downloaded_files(ocr_status);
CREATE INDEX IF NOT EXISTS idx_downloaded_files_file_hash ON downloaded_files(file_hash);
CREATE INDEX IF NOT EXISTS idx_downloaded_files_downloaded_at ON downloaded_files(downloaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_downloaded_files_source_url ON downloaded_files(source_url);
CREATE INDEX IF NOT EXISTS idx_downloaded_files_parent_page_url ON downloaded_files(parent_page_url);

-- Create updated_at trigger function (must be defined before triggers)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to downloaded_files
CREATE TRIGGER update_downloaded_files_updated_at BEFORE UPDATE ON downloaded_files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to scraped_sites
CREATE TRIGGER update_scraped_sites_updated_at BEFORE UPDATE ON scraped_sites
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to domain_proxy_requirements
CREATE TRIGGER update_domain_proxy_updated_at BEFORE UPDATE ON domain_proxy_requirements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create view for scraping statistics
CREATE OR REPLACE VIEW scraping_stats AS
SELECT
    COUNT(*) as total_scrapes,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures,
    ROUND(AVG(response_time)::numeric, 2) as avg_response_time,
    SUM(CASE WHEN proxy_used THEN 1 ELSE 0 END) as proxy_requests,
    ROUND(SUM(cost)::numeric, 4) as total_cost,
    COUNT(DISTINCT domain) as unique_domains
FROM scraped_sites
WHERE scraped_at > NOW() - INTERVAL '30 days';

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bpo_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bpo_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO bpo_user;

-- Create view for file download statistics
CREATE OR REPLACE VIEW file_download_stats AS
SELECT
    COUNT(*) as total_files,
    SUM(CASE WHEN download_status = 'downloaded' THEN 1 ELSE 0 END) as downloaded_count,
    SUM(CASE WHEN download_status = 'failed' THEN 1 ELSE 0 END) as failed_count,
    SUM(CASE WHEN download_status = 'pending' THEN 1 ELSE 0 END) as pending_count,
    SUM(CASE WHEN ocr_status = 'completed' THEN 1 ELSE 0 END) as ocr_completed_count,
    SUM(CASE WHEN ocr_status = 'pending' THEN 1 ELSE 0 END) as ocr_pending_count,
    SUM(file_size) as total_size_bytes,
    COUNT(DISTINCT domain) as unique_domains,
    COUNT(DISTINCT file_type) as file_types_count
FROM downloaded_files
WHERE downloaded_at > NOW() - INTERVAL '30 days' OR downloaded_at IS NULL;

-- Insert initial configuration
INSERT INTO domain_proxy_requirements (domain, requires_proxy, notes)
VALUES ('example.com', false, 'Initial placeholder')
ON CONFLICT (domain) DO NOTHING;
