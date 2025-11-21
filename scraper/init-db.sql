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
    requires_browser BOOLEAN DEFAULT false,
    browser_reason TEXT,
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
CREATE INDEX IF NOT EXISTS idx_domain_proxy_browser ON domain_proxy_requirements(requires_browser);

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

-- ============================================================================
-- ORGANIZATION PROFILE TABLES
-- ============================================================================

-- Organizations master table
CREATE TABLE IF NOT EXISTS organizations (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(255),
    domain VARCHAR(255) UNIQUE NOT NULL,
    aliases JSONB DEFAULT '[]'::jsonb,
    organizational_type VARCHAR(100),
    organizational_classification VARCHAR(255),
    customer_segment VARCHAR(10) CHECK (customer_segment IN ('B2B', 'B2C', 'Both', NULL)),
    founded_year INTEGER,
    headquarters_country VARCHAR(100),
    employee_count_range VARCHAR(50),
    auto_created BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_organizations_domain ON organizations(domain);
CREATE INDEX IF NOT EXISTS idx_organizations_canonical_name ON organizations(canonical_name);
CREATE INDEX IF NOT EXISTS idx_organizations_org_type ON organizations(organizational_type);
CREATE INDEX IF NOT EXISTS idx_organizations_customer_segment ON organizations(customer_segment);
CREATE INDEX IF NOT EXISTS idx_organizations_aliases ON organizations USING GIN(aliases);

-- Organization products
CREATE TABLE IF NOT EXISTS organization_products (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(255),
    description TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evidence_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(organization_id, product_name)
);

CREATE INDEX IF NOT EXISTS idx_org_products_org_id ON organization_products(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_products_name ON organization_products(product_name);
CREATE INDEX IF NOT EXISTS idx_org_products_active ON organization_products(is_active);
CREATE INDEX IF NOT EXISTS idx_org_products_last_seen ON organization_products(last_seen_at DESC);

-- Organization services (from taxonomy)
CREATE TABLE IF NOT EXISTS organization_services (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    service_id VARCHAR(100) NOT NULL,
    service_name VARCHAR(255) NOT NULL,
    service_path JSONB,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evidence_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(organization_id, service_id)
);

CREATE INDEX IF NOT EXISTS idx_org_services_org_id ON organization_services(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_services_service_id ON organization_services(service_id);
CREATE INDEX IF NOT EXISTS idx_org_services_active ON organization_services(is_active);
CREATE INDEX IF NOT EXISTS idx_org_services_path ON organization_services USING GIN(service_path);

-- Organization platforms (technology platforms used)
CREATE TABLE IF NOT EXISTS organization_platforms (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    platform_name VARCHAR(255) NOT NULL,
    platform_type VARCHAR(100),
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evidence_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(organization_id, platform_name)
);

CREATE INDEX IF NOT EXISTS idx_org_platforms_org_id ON organization_platforms(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_platforms_name ON organization_platforms(platform_name);
CREATE INDEX IF NOT EXISTS idx_org_platforms_type ON organization_platforms(platform_type);
CREATE INDEX IF NOT EXISTS idx_org_platforms_active ON organization_platforms(is_active);

-- Organization certifications
CREATE TABLE IF NOT EXISTS organization_certifications (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    certification_name VARCHAR(255) NOT NULL,
    certification_type VARCHAR(100),
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evidence_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(organization_id, certification_name)
);

CREATE INDEX IF NOT EXISTS idx_org_certs_org_id ON organization_certifications(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_certs_name ON organization_certifications(certification_name);
CREATE INDEX IF NOT EXISTS idx_org_certs_type ON organization_certifications(certification_type);
CREATE INDEX IF NOT EXISTS idx_org_certs_active ON organization_certifications(is_active);

-- Organization awards
CREATE TABLE IF NOT EXISTS organization_awards (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    award_name VARCHAR(255) NOT NULL,
    award_issuer VARCHAR(255),
    award_year INTEGER,
    category VARCHAR(255),
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evidence_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(organization_id, award_name, award_year)
);

CREATE INDEX IF NOT EXISTS idx_org_awards_org_id ON organization_awards(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_awards_issuer ON organization_awards(award_issuer);
CREATE INDEX IF NOT EXISTS idx_org_awards_year ON organization_awards(award_year);
CREATE INDEX IF NOT EXISTS idx_org_awards_active ON organization_awards(is_active);

-- Organization operating markets
CREATE TABLE IF NOT EXISTS organization_operating_markets (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    country_code VARCHAR(10) NOT NULL,
    country_name VARCHAR(255) NOT NULL,
    region VARCHAR(100),
    operation_type VARCHAR(100),
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evidence_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(organization_id, country_code, operation_type)
);

CREATE INDEX IF NOT EXISTS idx_org_markets_org_id ON organization_operating_markets(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_markets_country_code ON organization_operating_markets(country_code);
CREATE INDEX IF NOT EXISTS idx_org_markets_region ON organization_operating_markets(region);
CREATE INDEX IF NOT EXISTS idx_org_markets_active ON organization_operating_markets(is_active);

-- Organization relationships
CREATE TABLE IF NOT EXISTS organization_relationships (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    related_organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    relationship_type VARCHAR(100) NOT NULL,
    relationship_description TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evidence_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(organization_id, related_organization_id, relationship_type),
    CHECK (organization_id != related_organization_id)
);

CREATE INDEX IF NOT EXISTS idx_org_rels_org_id ON organization_relationships(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_rels_related_id ON organization_relationships(related_organization_id);
CREATE INDEX IF NOT EXISTS idx_org_rels_type ON organization_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_org_rels_active ON organization_relationships(is_active);

-- Organization evidence (source URLs for facts)
CREATE TABLE IF NOT EXISTS organization_evidence (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    fact_type VARCHAR(50) NOT NULL,
    fact_id INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    scraped_site_id INTEGER REFERENCES scraped_sites(id) ON DELETE SET NULL,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_org_evidence_org_id ON organization_evidence(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_evidence_fact ON organization_evidence(fact_type, fact_id);
CREATE INDEX IF NOT EXISTS idx_org_evidence_scraped_site ON organization_evidence(scraped_site_id);
CREATE INDEX IF NOT EXISTS idx_org_evidence_extracted_at ON organization_evidence(extracted_at DESC);

-- ============================================================================
-- CORPORATE ENTITY TABLES
-- ============================================================================

-- Corporate entities master table
CREATE TABLE IF NOT EXISTS corporate_entities (
    id SERIAL PRIMARY KEY,
    entity_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(100),
    legal_name VARCHAR(255),
    dba_name VARCHAR(255),
    jurisdiction VARCHAR(100),
    registration_number VARCHAR(100),
    founded_year INTEGER,
    status VARCHAR(50) DEFAULT 'Active',
    website VARCHAR(255),
    headquarters_address TEXT,
    headquarters_country VARCHAR(100),
    headquarters_city VARCHAR(100),
    employee_count_range VARCHAR(50),
    description TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_corp_entities_name ON corporate_entities(entity_name);
CREATE INDEX IF NOT EXISTS idx_corp_entities_type ON corporate_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_corp_entities_jurisdiction ON corporate_entities(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_corp_entities_status ON corporate_entities(status);
CREATE INDEX IF NOT EXISTS idx_corp_entities_legal_name ON corporate_entities(legal_name);

-- Entity relationships (parent-subsidiary, etc.)
CREATE TABLE IF NOT EXISTS entity_relationships (
    id SERIAL PRIMARY KEY,
    parent_entity_id INTEGER NOT NULL REFERENCES corporate_entities(id) ON DELETE CASCADE,
    child_entity_id INTEGER NOT NULL REFERENCES corporate_entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(100) NOT NULL,
    ownership_percentage DECIMAL(5, 2),
    relationship_start_date DATE,
    relationship_end_date DATE,
    is_active BOOLEAN DEFAULT true,
    notes TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evidence_count INTEGER DEFAULT 1,
    UNIQUE(parent_entity_id, child_entity_id, relationship_type),
    CHECK (parent_entity_id != child_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_entity_rels_parent ON entity_relationships(parent_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_rels_child ON entity_relationships(child_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_rels_type ON entity_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_entity_rels_active ON entity_relationships(is_active);

-- Organization to entity mapping
CREATE TABLE IF NOT EXISTS organization_entity_mapping (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES corporate_entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(100),
    is_primary BOOLEAN DEFAULT false,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evidence_count INTEGER DEFAULT 1,
    UNIQUE(organization_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_org_entity_map_org_id ON organization_entity_mapping(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_entity_map_entity_id ON organization_entity_mapping(entity_id);
CREATE INDEX IF NOT EXISTS idx_org_entity_map_primary ON organization_entity_mapping(is_primary);

-- ============================================================================
-- REFERENCE TABLES (from heuristics)
-- ============================================================================

-- Reference countries
CREATE TABLE IF NOT EXISTS reference_countries (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(10) UNIQUE NOT NULL,
    aliases JSONB DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_ref_countries_code ON reference_countries(code);
CREATE INDEX IF NOT EXISTS idx_ref_countries_name ON reference_countries(name);
CREATE INDEX IF NOT EXISTS idx_ref_countries_aliases ON reference_countries USING GIN(aliases);

-- Reference industries (from taxonomy)
CREATE TABLE IF NOT EXISTS reference_industries (
    id SERIAL PRIMARY KEY,
    industry_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    level INTEGER NOT NULL,
    parent_id VARCHAR(100) REFERENCES reference_industries(industry_id),
    path JSONB
);

CREATE INDEX IF NOT EXISTS idx_ref_industries_id ON reference_industries(industry_id);
CREATE INDEX IF NOT EXISTS idx_ref_industries_parent ON reference_industries(parent_id);
CREATE INDEX IF NOT EXISTS idx_ref_industries_level ON reference_industries(level);
CREATE INDEX IF NOT EXISTS idx_ref_industries_path ON reference_industries USING GIN(path);

-- Reference services (from taxonomy)
CREATE TABLE IF NOT EXISTS reference_services (
    id SERIAL PRIMARY KEY,
    service_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    level INTEGER NOT NULL,
    parent_id VARCHAR(100) REFERENCES reference_services(service_id),
    path JSONB
);

CREATE INDEX IF NOT EXISTS idx_ref_services_id ON reference_services(service_id);
CREATE INDEX IF NOT EXISTS idx_ref_services_parent ON reference_services(parent_id);
CREATE INDEX IF NOT EXISTS idx_ref_services_level ON reference_services(level);
CREATE INDEX IF NOT EXISTS idx_ref_services_path ON reference_services USING GIN(path);

-- Reference tech terms
CREATE TABLE IF NOT EXISTS reference_tech_terms (
    id SERIAL PRIMARY KEY,
    term VARCHAR(255) UNIQUE NOT NULL,
    canonical VARCHAR(255),
    synonyms JSONB DEFAULT '[]'::jsonb,
    category VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_ref_tech_terms_term ON reference_tech_terms(term);
CREATE INDEX IF NOT EXISTS idx_ref_tech_terms_category ON reference_tech_terms(category);
CREATE INDEX IF NOT EXISTS idx_ref_tech_terms_synonyms ON reference_tech_terms USING GIN(synonyms);

-- Reference BPO/CX terms
CREATE TABLE IF NOT EXISTS reference_bpo_terms (
    id SERIAL PRIMARY KEY,
    term VARCHAR(255) NOT NULL,
    full_form VARCHAR(255),
    ner_category VARCHAR(50),
    industry VARCHAR(100),
    fuzzy_variations JSONB DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_ref_bpo_terms_term ON reference_bpo_terms(term);
CREATE INDEX IF NOT EXISTS idx_ref_bpo_terms_category ON reference_bpo_terms(ner_category);
CREATE INDEX IF NOT EXISTS idx_ref_bpo_terms_industry ON reference_bpo_terms(industry);
CREATE INDEX IF NOT EXISTS idx_ref_bpo_terms_variations ON reference_bpo_terms USING GIN(fuzzy_variations);

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================================

CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_corporate_entities_updated_at BEFORE UPDATE ON corporate_entities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS FOR ACTIVE/INACTIVE DATA
-- ============================================================================

-- View for active organization products
CREATE OR REPLACE VIEW active_organization_products AS
SELECT op.*, o.domain, o.canonical_name as organization_name
FROM organization_products op
JOIN organizations o ON op.organization_id = o.id
WHERE op.is_active = true;

-- View for active organization services
CREATE OR REPLACE VIEW active_organization_services AS
SELECT os.*, o.domain, o.canonical_name as organization_name
FROM organization_services os
JOIN organizations o ON os.organization_id = o.id
WHERE os.is_active = true;

-- View for organization summary
CREATE OR REPLACE VIEW organization_summary AS
SELECT 
    o.id,
    o.canonical_name,
    o.domain,
    o.organizational_type,
    o.customer_segment,
    COUNT(DISTINCT op.id) as product_count,
    COUNT(DISTINCT os.id) as service_count,
    COUNT(DISTINCT opl.id) as platform_count,
    COUNT(DISTINCT oc.id) as certification_count,
    COUNT(DISTINCT oa.id) as award_count,
    COUNT(DISTINCT om.id) as market_count
FROM organizations o
LEFT JOIN organization_products op ON o.id = op.organization_id AND op.is_active = true
LEFT JOIN organization_services os ON o.id = os.organization_id AND os.is_active = true
LEFT JOIN organization_platforms opl ON o.id = opl.organization_id AND opl.is_active = true
LEFT JOIN organization_certifications oc ON o.id = oc.organization_id AND oc.is_active = true
LEFT JOIN organization_awards oa ON o.id = oa.organization_id AND oa.is_active = true
LEFT JOIN organization_operating_markets om ON o.id = om.organization_id AND om.is_active = true
GROUP BY o.id, o.canonical_name, o.domain, o.organizational_type, o.customer_segment;

-- Grant permissions on new tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bpo_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bpo_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO bpo_user;