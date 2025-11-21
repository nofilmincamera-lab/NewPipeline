# Heuristics Data Directory

This directory contains the consolidated heuristics data used by the NER pipeline for entity extraction and classification.

## Files Overview

### Core Data Files

- **`ner_relationships.json`** - Main heuristics data containing:
  - Entity lists (ORG, PRODUCT, CATEGORY)
  - Provider-product relationships
  - Relationship strings for pattern matching
  - Metadata and statistics

- **`company_aliases.json`** - Company name normalization mapping:
  - Case-insensitive alias mappings
  - Canonical company names
  - Product name variations

### Supporting Files

- **`company_aliases.json`** - Company name aliases and variations
- **`ner_relationships_backup_preupdate.json`** - Backup of original relationships data
- **`countries/`** - Country name data for geographic entity extraction

## Data Sources

The heuristics data is consolidated from multiple sources:

1. **Product Partnerships Mapping** (`product_partnerships_mapping_2025-10-16 (1).json`)
   - 753 products across 61 providers
   - Structured provider-product relationships
   - Category and description information

2. **Relationships Mapping** (`relationships_mapping (1).json`)
   - 1,924 provider-partner relationships
   - Product and service categorizations
   - Source attribution

3. **Taxonomy Schema** (`taxonomy.json`)
   - 10 industry categories with hierarchical structure
   - 11 service categories with subcategories
   - Channel mappings and enablement layers

## Data Structure

### ner_relationships.json

```json
{
  "entities": {
    "ORG": ["Provider1", "Provider2", ...],
    "PRODUCT": ["Product1", "Product2", ...],
    "CATEGORY": ["Service Category1", "Service Category2", ...]
  },
  "relationships": {
    "Provider1": {
      "type": "BPO",
      "partners": ["Partner1", "Partner2"],
      "products": ["Product1", "Product2"],
      "categories": ["Category1", "Category2"]
    }
  },
  "relationship_strings": [
    "Product1 belongs to Provider1",
    "Product2 belongs to Provider1"
  ],
  "metadata": {
    "total_providers": 129,
    "total_products": 940,
    "total_categories": 101,
    "category_mappings": {...}
  }
}
```

### company_aliases.json

```json
{
  "provider name": "Provider Name",
  "PROVIDER NAME": "Provider Name",
  "product name": "Product Name",
  "PRODUCT NAME": "Product Name"
}
```

## Usage in NER Pipeline

The heuristics data is used by the `HeuristicExtractor` class in `src/models/heuristics.py`:

```python
from src.models.heuristics import HeuristicExtractor

# Initialize extractor
extractor = HeuristicExtractor("Heuristics/")

# Extract entities from text
entities = extractor.extract_entities(text)

# Get specific entity types
companies = extractor.extract_companies(text)
categories = extractor.extract_categories(text)
industries = extractor.extract_industries(text)
```

## Content Type Classification Heuristics

The extraction flow also applies a rule-based content classifier that consults `content_types.json` for weighted pattern
matches across the URL, document title, body text, and structural cues. Each rule contributes to a cumulative score that
must exceed a minimum threshold before a label is emitted. The scoring pipeline works as follows:

1. **URL patterns** add the configured `url_weight` when any regular expression matches the normalized URL.
2. **Title patterns** add the configured `title_weight` on the first match against the lower-cased title string.
3. **Body patterns** accumulate `pattern_weight` for each matching expression, provided at least `min_patterns` patterns
   are satisfied (otherwise the interim score is dampened).
4. **Structural signals** add additional points by interrogating the raw and markdown-normalized body for metrics,
   section headings, CTA language, form markup, code blocks, pricing tables, etc. (`_score_structure_signals` in
   `src/flows/extraction_flow.py`).
5. The predicted label must reach its `min_score`; otherwise the classifier returns `Other` with a low-confidence
   annotation.

Below is a breakdown of every supported content type and the heuristics each rule uses:

### Case Study
- **URL cues (`url_weight` = 15):** `/case-stud(y|ies)`, `/success-stor(y|ies)`, `/customer-stor(y|ies)`, `/clients?-stories`.
- **Title cues (`title_weight` = 10):** Phrases such as “case study”, “success story”, “customer story”, and the
  progression pattern `how <subject> <achieved|improved|reduced|increased>`.
- **Body cues (`pattern_weight` = 2, `min_patterns` = 3):** Sections titled challenge/problem/issue, solution/approach,
  results/outcome/impact, percentage-improvement statements, and executive quote attributions.
- **Structural signals:** Requires metrics, the Challenge/Solution/Result trio of sections, quoted content, and ≥400 words
  (`has_metrics`, `has_sections`, `has_quotes`, `min_length`).
- **Threshold:** `min_score` = 18.

### Blog / Article

- **URL cues (`url_weight` = 12):** `/blog/`, `/article/`, `/insights?/`, `/news/`, and dated permalink structures
  (`/\d{4}/\d{2}/`).
- **Title cues (`title_weight` = 8):** “How to…”, numbered listicles, “guide to”, “ultimate guide”, “what is”, and
  “why …”.
- **Body cues (`pattern_weight` = 1.5, `min_patterns` = 2):** Publication metadata (“published on/by”), explicit author
  by-lines, read-time signals, social sharing prompts, and “in this article/post” framing.
- **Structural signals:** Expects a publication date and 300–5,000 word count (`has_date`, `min_length`, `max_length`).
- **Threshold:** `min_score` = 12.

### Company Information

- **URL cues (`url_weight` = 15):** `/about`, `/company`, `/who-we-are`, `/our-story`, `/about-us`.
- **Title cues (`title_weight` = 10):** “About us/our company”, “who we are”, “our story/mission/vision/values”, “company
  overview”, “meet the team”.
- **Body cues (`pattern_weight` = 2, `min_patterns` = 2):** Founding-year phrases, headquarters mentions, team size
  indicators, mission/vision/value statements, belief/commitment language, and leadership team callouts.
- **Structural signals:** Declares a ≥200 word minimum and includes a `has_founding_year` hint for future scoring.
- **Threshold:** `min_score` = 14.

### Services / Offerings

- **URL cues (`url_weight` = 12):** `/services?/`, `/solutions?/`, `/offerings?/`, `/what-we-do`, `/capabilities`.
- **Title cues (`title_weight` = 8):** “Services”, “Solutions”, “Offerings”, “What we do/offer”, “Capabilities”.
- **Body cues (`pattern_weight` = 1.5, `min_patterns` = 2):** “We offer/provide/deliver…”, “our services include…”, and
  descriptors such as “comprehensive”, “end-to-end”, “tailored/customized”, and “service portfolio”.
- **Structural signals:** Rewards documents with explicit lists of offerings and ≥300 words (`has_list`, `min_length`).
- **Threshold:** `min_score` = 13.

### Product / Technology

- **URL cues (`url_weight` = 12):** `/product/`, `/platform/`, `/technology/`, `/features/`, `/software/`.
- **Title cues (`title_weight` = 8):** “Product(s)”, “Platform(s)”, “Technology”, “Software”, “Tool(s)”.
- **Body cues (`pattern_weight` = 1.5, `min_patterns` = 2):** “Features”, “Integrations”, “API”, “Deployment”, “Get started”,
  demo/trial calls-to-action, and sign-up language.
- **Structural signals:** Looks for CTA language and ≥200 words (`has_cta`, `min_length`).
- **Threshold:** `min_score` = 13.

### Pricing

- **URL cues (`url_weight` = 15):** `/pricing`, `/plans?/`, `/packages`, `/cost`.
- **Title cues (`title_weight` = 10):** “Pricing”, “Plan(s)”, “Packages”, “Cost”.
- **Body cues (`pattern_weight` = 2, `min_patterns` = 3):** Currency symbols, billing cadence (“per month/year”), cadence
  adjectives (annual/monthly), “free plan”, “starting at”, and “pricing tier”.
- **Structural signals:** Requires pricing tables and currency mentions (`has_pricing_table`, `has_currency`).
- **Threshold:** `min_score` = 15.

### Documentation / Knowledge Base

- **URL cues (`url_weight` = 15):** `/docs?/`, `/documentation/`, `/kb/`, `/knowledge-?base/`, `/help/`, `/guide/`, `/api/`.
- **Title cues (`title_weight` = 10):** “Documentation”, “Knowledge Base”, “Help Center”, “User Guide”, “API Reference”.
- **Body cues (`pattern_weight` = 2, `min_patterns` = 3):** Numbered steps, prerequisite/requirement headings,
  configuration/installation/setup terminology, tables of contents, and admonitions (“see also”, “note:”, “warning:”).
- **Structural signals:** Looks for code blocks, step lists, and ≥400 words (`has_code_blocks`, `has_steps`, `min_length`).
- **Threshold:** `min_score` = 16.

### News / Press Release

- **URL cues (`url_weight` = 12):** `/news/`, `/press/`, `/press-release/`, `/newsroom/`, `/media/`, `/announcements?/`.
- **Title cues (`title_weight` = 8):** “Announces”, “Launches”, “Press release”, “Acquires”, “Partnership(s)”, “News”.
- **Body cues (`pattern_weight` = 2, `min_patterns` = 2):** “Today announced”, press-release boilerplate, media contact
  lines, spokesperson mentions, quoted-at-saying patterns, and “according to …”.
- **Structural signals:** Expects a date, quoted material, and ≥200 words (flags `has_date`, `has_quote`, `min_length`).
- **Threshold:** `min_score` = 13.

### Careers / Job Posting

- **URL cues (`url_weight` = 15):** `/careers?/`, `/jobs?/`, `/join-us`, `/hiring`, `/opportunities`, `/openings?/`.
- **Title cues (`title_weight` = 10):** “Careers”, “Jobs”, “Hiring”, “Join us/our team”, “Openings”, “We’re hiring”.
- **Body cues (`pattern_weight` = 2, `min_patterns` = 3):** “Apply now/application”, requirements/qualifications/
  responsibilities headings, employment-type modifiers (full/part-time, remote), salary, and benefits language.
- **Structural signals:** Rewards explicit requirements lists and ≥200 words (`has_requirements_list`, `min_length`).
- **Threshold:** `min_score` = 16.

### Landing Page / Marketing

- **URL cues (`url_weight` = 10):** `/lp/`, `/landing`, `/get-started`, `/signup`, `/trial`, `/demo`.
- **Title cues (`title_weight` = 7):** Conversion-oriented phrasing (“Get started”, “Try it free”, “Free trial”, “Request
  demo”, “Transform your …”).
- **Body cues (`pattern_weight` = 1.5, `min_patterns` = 2):** CTA verbs (“sign up”, “get started”), freemium and urgency
  language, and social proof such as “trusted by” or “join thousands”.
- **Structural signals:** Looks for CTA language, embedded forms, and enforces a ≤2,000-word cap (`has_cta`, `has_form`,
  `max_length`).
- **Threshold:** `min_score` = 11.

### Event / Webinar / Workshop

- **URL cues (`url_weight` = 12):** `/events?/`, `/webinars?/`, `/workshops?/`, `/conference`, `/summit`.
- **Title cues (`title_weight` = 8):** “Events”, “Webinars”, “Workshops”, “Conference”, “Register”.
- **Body cues (`pattern_weight` = 2, `min_patterns` = 2):** “Register now/today”, date/time/location headers, speaker and
  agenda sections, “virtual event”, and invitations to “join us”.
- **Structural signals:** Requires a date reference and registration language (`has_date`, `has_registration`).
- **Threshold:** `min_score` = 12.

### Legal / Compliance

- **URL cues (`url_weight` = 15):** `/legal/`, `/privacy`, `/terms`, `/compliance`, `/gdpr`, `/cookie`.
- **Title cues (`title_weight` = 10):** “Privacy policy”, “Terms of service/use”, “Legal”, “Compliance”, “Cookie policy”.
- **Body cues (`pattern_weight` = 2, `min_patterns` = 2):** Policy boilerplate (“this policy/agreement”), effective/last
  updated dates, consent language (“you agree to”), personal data handling, GDPR, and “terms and conditions”.
- **Structural signals:** Looks for sectioned documents and ≥300 words (`has_sections`, `min_length`).
- **Threshold:** `min_score` = 14.

### Testimonials / Customers

- **URL cues (`url_weight` = 12):** `/testimonials?/`, `/customers?/`, `/reviews?/`, `/clients?/`.
- **Title cues (`title_weight` = 10):** “Testimonials”, “Customers”, “Reviews”, “What our customers say”, “Client feedback”.
- **Body cues (`pattern_weight` = 2, `min_patterns` = 2):** Quoted endorsements, leadership titles with “at <company>”,
  rating statements, and explicit “testimonial” language.
- **Structural signals:** Rewards quoted material and named individuals (`has_quotes`, `has_names`).
- **Threshold:** `min_score` = 12.

## Taxonomy Integration

The system now supports taxonomy-based entity extraction:

- **Industries**: Extracted from the 10 main industry categories
- **Service Categories**: Extracted from the 11 service categories
- **Hierarchical Support**: Supports up to 6 levels of hierarchy
- **Case-Insensitive Matching**: Robust extraction regardless of case

### Example Taxonomy Extraction

```python
text = "IBM provides Customer Experience (CX) Operations for Financial Services & Insurance clients"

# Results:
companies = ["IBM"]  # From heuristics
categories = ["Customer Experience (CX) Operations"]  # From taxonomy
industries = ["Financial Services & Insurance"]  # From taxonomy
```

## Data Maintenance

### Automated Sync

Use the sync script to update heuristics from source files:

```bash
# Check if sync is needed
python scripts/sync_heuristics.py --dry-run

# Perform sync
python scripts/sync_heuristics.py

# Force sync even if not needed
python scripts/sync_heuristics.py --force
```

### Validation

Validate data integrity:

```bash
python scripts/validate_heuristics.py
```

### Consolidation

Manually run consolidation:

```bash
python -m src.data.consolidate_heuristics
```

## Statistics

Current data statistics (as of last consolidation):

- **Total Providers**: 129
- **Total Products**: 940
- **Total Categories**: 101
- **Total Relationships**: 960
- **Company Aliases**: 3,925
- **Taxonomy Industries**: 10
- **Taxonomy Services**: 11

## Backup and Recovery

- Automatic backups are created before each sync operation
- Backups are stored in `Heuristics/backups/`
- Only the last 5 backups are retained
- Sync reports are generated for each operation

## Troubleshooting

### Common Issues

1. **Missing Files**: Ensure all source files are present in the project root
2. **JSON Errors**: Validate JSON syntax in source files
3. **Import Errors**: Install required dependencies (`rapidfuzz`, `jsonschema`)
4. **Permission Issues**: Ensure write access to the Heuristics directory

### Validation Warnings

- **Case-insensitive duplicates**: Normal for company aliases
- **Missing aliases**: Some entities may not have alias mappings
- **Empty entries**: Check source data quality

## Contributing

When adding new heuristics data:

1. Update source files in the project root
2. Run validation to check data quality
3. Use the sync script to update heuristics
4. Test entity extraction with new data
5. Update documentation if needed

## Related Files

- `src/models/heuristics.py` - Main extraction logic
- `src/data/consolidate_heuristics.py` - Data consolidation
- `scripts/sync_heuristics.py` - Automated sync
- `scripts/validate_heuristics.py` - Data validation
- `tests/test_heuristics_integration.py` - Test suite
- `taxonomy.json` - Taxonomy schema

