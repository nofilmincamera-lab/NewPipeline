# Markdown Storage and Organization UUID Link Update

## Overview
Updated the scraping system to:
1. Store scraped text content as **markdown** instead of just metadata
2. Link scraped sites to **organization UUID** for easier data combining
3. Automatically create organizations when scraping new domains

## Database Schema Changes

### Migration File
`migrations/add_markdown_and_org_link.sql`

### Changes:
1. **organizations table**: Added `uuid` column (UUID, unique, indexed)
2. **scraped_sites table**: 
   - Added `markdown_content` column (TEXT) - stores cleaned content as markdown
   - Added `organization_uuid` column (UUID) - foreign key to organizations.uuid
   - Added index on `organization_uuid` for fast lookups

### Metadata Updates
The `metadata` JSONB field now includes:
- `main_content_length`: Length of extracted text
- `html_length`: Length of original HTML
- `markdown_length`: Length of markdown content

## Code Changes

### Domain Crawler (`src/scrapers/domain_crawler.py`)
- Converts cleaned HTML to markdown using `html2text`
- Automatically creates organizations for new domains
- Links scraped sites to organization UUID
- Stores markdown content instead of HTML

### Dependencies
- Added `html2text==2024.2.26` to `requirements.txt`

## How It Works

1. **Content Extraction**:
   - Removes boilerplate (headers, footers, nav) from HTML
   - Extracts main content area
   - Converts cleaned HTML to markdown

2. **Organization Linking**:
   - Looks up organization by domain
   - If not found, auto-creates organization with UUID
   - Links scraped site to organization UUID

3. **Storage**:
   - Stores markdown content in `markdown_content` field
   - Stores metadata (lengths, etc.) in `metadata` JSONB field
   - Links via `organization_uuid` for easy joins

## Benefits

1. **Easier Data Combining**: Link scraped content to organizations via UUID
2. **Better Content Storage**: Markdown preserves structure while being readable
3. **Automatic Organization Management**: Creates organizations on-the-fly
4. **No HTML Storage**: Only stores cleaned markdown, saving space

## Migration Steps

1. Run the migration script:
```bash
psql -U bpo_user -d bpo_intelligence -f migrations/add_markdown_and_org_link.sql
```

2. Existing scraped sites will be linked to organizations by domain
3. Future scrapes will automatically store markdown and link to organizations

## Example Query

```sql
-- Get all scraped content for an organization
SELECT 
    ss.url,
    ss.title,
    ss.markdown_content,
    ss.scraped_at,
    o.canonical_name,
    o.uuid as org_uuid
FROM scraped_sites ss
JOIN organizations o ON ss.organization_uuid = o.uuid
WHERE o.domain = 'worldline.com'
ORDER BY ss.scraped_at DESC;
```

