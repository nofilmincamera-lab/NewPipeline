"""
Load heuristics data into reference tables and populate initial organization facts.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncpg


async def load_countries(conn: asyncpg.Connection, countries_file: Path) -> int:
    """Load countries reference data."""
    if not countries_file.exists():
        print(f"Warning: {countries_file} not found")
        return 0
    
    with open(countries_file, 'r', encoding='utf-8') as f:
        countries = json.load(f)
    
    count = 0
    for country in countries:
        query = """
            INSERT INTO reference_countries (name, code, aliases)
            VALUES ($1, $2, $3)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                aliases = EXCLUDED.aliases
        """
        await conn.execute(
            query,
            country['name'],
            country['code'],
            json.dumps(country.get('aliases', []))
        )
        count += 1
    
    return count


async def load_industries(conn: asyncpg.Connection, industries_file: Path) -> int:
    """Load industries taxonomy."""
    if not industries_file.exists():
        print(f"Warning: {industries_file} not found")
        return 0
    
    with open(industries_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    industries = data.get('industries', [])
    count = 0
    
    for industry in industries:
        query = """
            INSERT INTO reference_industries (
                industry_id, name, description, level, parent_id, path
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (industry_id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                level = EXCLUDED.level,
                parent_id = EXCLUDED.parent_id,
                path = EXCLUDED.path
        """
        await conn.execute(
            query,
            industry['id'],
            industry['name'],
            industry.get('description'),
            industry['level'],
            industry.get('parent_id'),
            json.dumps(industry.get('path', []))
        )
        count += 1
    
    return count


async def load_services(conn: asyncpg.Connection, services_file: Path) -> int:
    """Load services taxonomy."""
    if not services_file.exists():
        print(f"Warning: {services_file} not found")
        return 0
    
    with open(services_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    services = data.get('services', [])
    count = 0
    
    for service in services:
        query = """
            INSERT INTO reference_services (
                service_id, name, description, level, parent_id, path
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (service_id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                level = EXCLUDED.level,
                parent_id = EXCLUDED.parent_id,
                path = EXCLUDED.path
        """
        await conn.execute(
            query,
            service['id'],
            service['name'],
            service.get('description'),
            service['level'],
            service.get('parent_id'),
            json.dumps(service.get('path', []))
        )
        count += 1
    
    return count


async def load_tech_terms(conn: asyncpg.Connection, tech_terms_file: Path) -> int:
    """Load technology terms."""
    if not tech_terms_file.exists():
        print(f"Warning: {tech_terms_file} not found")
        return 0
    
    with open(tech_terms_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    terms = data.get('tech_terms', [])
    count = 0
    
    for term_data in terms:
        query = """
            INSERT INTO reference_tech_terms (term, canonical, synonyms, category)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (term) DO UPDATE SET
                canonical = EXCLUDED.canonical,
                synonyms = EXCLUDED.synonyms,
                category = EXCLUDED.category
        """
        await conn.execute(
            query,
            term_data['term'],
            term_data.get('canonical'),
            json.dumps(term_data.get('synonyms', [])),
            term_data.get('category')
        )
        count += 1
    
    return count


async def load_bpo_terms(conn: asyncpg.Connection, bpo_terms_file: Path) -> int:
    """Load BPO/CX terms."""
    if not bpo_terms_file.exists():
        print(f"Warning: {bpo_terms_file} not found")
        return 0
    
    with open(bpo_terms_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    terms = data.get('terms', [])
    count = 0
    
    for term_data in terms:
        query = """
            INSERT INTO reference_bpo_terms (
                term, full_form, ner_category, industry, fuzzy_variations
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT DO NOTHING
        """
        await conn.execute(
            query,
            term_data.get('term'),
            term_data.get('full_form'),
            term_data.get('ner_category'),
            term_data.get('industry'),
            json.dumps(term_data.get('fuzzy_variations', []))
        )
        count += 1
    
    return count


async def load_products_from_heuristics(
    conn: asyncpg.Connection,
    products_file: Path,
    org_db
) -> int:
    """Load products from products.json and link to organizations."""
    if not products_file.exists():
        print(f"Warning: {products_file} not found")
        return 0
    
    with open(products_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    products = data.get('products', [])
    count = 0
    
    # Load ner_relationships to map products to organizations
    base_path = Path(__file__).parent.parent.parent.parent
    ner_file = base_path / "MasterProfiles" / "Heuristics" / "ner_relationships.json"
    
    org_product_map = {}
    if ner_file.exists():
        with open(ner_file, 'r', encoding='utf-8') as f:
            ner_data = json.load(f)
        
        # Extract product-organization mappings from relationship strings
        relationship_strings = ner_data.get('relationship_strings', [])
        for rel_str in relationship_strings:
            if ' belongs to ' in rel_str:
                parts = rel_str.split(' belongs to ')
                if len(parts) == 2:
                    product_name = parts[0].strip()
                    org_name = parts[1].strip()
                    if org_name not in org_product_map:
                        org_product_map[org_name] = []
                    org_product_map[org_name].append(product_name)
    
    # Also check relationships section
    relationships = ner_data.get('relationships', {})
    for org_name, rel_data in relationships.items():
        products_list = rel_data.get('products', [])
        if org_name not in org_product_map:
            org_product_map[org_name] = []
        org_product_map[org_name].extend(products_list)
    
    # Load company aliases for name matching
    aliases_file = base_path / "MasterProfiles" / "Heuristics" / "company_aliases.json"
    aliases = {}
    if aliases_file.exists():
        with open(aliases_file, 'r', encoding='utf-8') as f:
            aliases = json.load(f)
    
    # Create reverse alias map (canonical -> all aliases)
    reverse_aliases = {}
    for alias, canonical in aliases.items():
        if canonical not in reverse_aliases:
            reverse_aliases[canonical] = []
        reverse_aliases[canonical].append(alias.lower())
    
    # Process products
    for product in products:
        product_name = product.get('name')
        category = product.get('category')
        description = product.get('description')
        
        # Find organization for this product
        # Check if product name appears in any org's product list
        for org_name, product_list in org_product_map.items():
            if product_name in product_list:
                # Find organization by canonical name or alias
                org = await org_db.get_organization_by_domain(org_name.lower().replace(' ', '').replace('.com', ''))
                if not org:
                    # Try to find by canonical name
                    query = "SELECT id FROM organizations WHERE canonical_name = $1 OR canonical_name ILIKE $2"
                    org_id = await conn.fetchval(query, org_name, f"%{org_name}%")
                    if org_id:
                        await org_db.upsert_product(
                            org_id, product_name, category, description
                        )
                        count += 1
                else:
                    await org_db.upsert_product(
                        org['id'], product_name, category, description
                    )
                    count += 1
                break
    
    return count


async def load_relationships_from_heuristics(
    conn: asyncpg.Connection,
    ner_file: Path,
    org_db
) -> int:
    """Load organization relationships from ner_relationships.json."""
    if not ner_file.exists():
        print(f"Warning: {ner_file} not found")
        return 0
    
    with open(ner_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    relationships = data.get('relationships', {})
    count = 0
    
    # Load company aliases
    base_path = Path(__file__).parent.parent.parent.parent
    aliases_file = base_path / "MasterProfiles" / "Heuristics" / "company_aliases.json"
    aliases = {}
    if aliases_file.exists():
        with open(aliases_file, 'r', encoding='utf-8') as f:
            aliases = json.load(f)
    
    # Helper to get org ID by name
    async def get_org_id_by_name(name: str) -> Optional[int]:
        # Try canonical name
        query = "SELECT id FROM organizations WHERE canonical_name = $1 OR canonical_name ILIKE $2"
        org_id = await conn.fetchval(query, name, f"%{name}%")
        if org_id:
            return org_id
        
        # Try aliases
        canonical = aliases.get(name, aliases.get(name.lower()))
        if canonical:
            query = "SELECT id FROM organizations WHERE canonical_name = $1"
            org_id = await conn.fetchval(query, canonical)
            return org_id
        
        return None
    
    for org_name, rel_data in relationships.items():
        org_id = await get_org_id_by_name(org_name)
        if not org_id:
            continue
        
        # Process partners
        partners = rel_data.get('partners', [])
        for partner_name in partners:
            partner_id = await get_org_id_by_name(partner_name)
            if partner_id:
                await org_db.upsert_relationship(
                    org_id, partner_id, 'Partner'
                )
                count += 1
    
    return count


async def main():
    """Main loading function."""
    db_host = "localhost"
    db_name = "bpo_intelligence"
    db_user = "bpo_user"
    
    password_file = Path("ops/secrets/postgres_password.txt")
    if password_file.exists():
        with open(password_file, 'r') as f:
            db_password = f.read().strip()
    else:
        db_password = input("Enter PostgreSQL password: ")
    
    base_path = Path(__file__).parent.parent.parent.parent
    heuristics_path = base_path / "MasterProfiles" / "Heuristics"
    
    conn = await asyncpg.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )
    
    try:
        from ..models.organization import OrganizationDB
        org_db = OrganizationDB(conn)
        
        print("Loading reference countries...")
        countries_count = await load_countries(conn, heuristics_path / "countries.json")
        print(f"Loaded {countries_count} countries")
        
        print("Loading reference industries...")
        industries_count = await load_industries(conn, heuristics_path / "taxonomy_industries.json")
        print(f"Loaded {industries_count} industries")
        
        print("Loading reference services...")
        services_count = await load_services(conn, heuristics_path / "taxonomy_services.json")
        print(f"Loaded {services_count} services")
        
        print("Loading tech terms...")
        tech_terms_count = await load_tech_terms(conn, heuristics_path / "tech_terms.json")
        print(f"Loaded {tech_terms_count} tech terms")
        
        print("Loading BPO terms...")
        bpo_terms_count = await load_bpo_terms(conn, heuristics_path / "bpo_cx_terms_with_fuzzy_logic.json")
        print(f"Loaded {bpo_terms_count} BPO terms")
        
        print("Loading products from heuristics...")
        products_count = await load_products_from_heuristics(
            conn, heuristics_path / "products.json", org_db
        )
        print(f"Loaded {products_count} product-organization links")
        
        print("Loading relationships from heuristics...")
        rels_count = await load_relationships_from_heuristics(
            conn, heuristics_path / "ner_relationships.json", org_db
        )
        print(f"Loaded {rels_count} organization relationships")
        
        print("Heuristics loading complete!")
    
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

