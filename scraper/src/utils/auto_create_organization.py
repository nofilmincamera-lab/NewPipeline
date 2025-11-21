"""
Auto-create organization when domain is added to scrape list.
"""

import asyncio
from pathlib import Path
from typing import Optional
import asyncpg

from ..models.organization import OrganizationDB


async def auto_create_organization_from_domain(
    conn: asyncpg.Connection,
    domain: str,
    canonical_name: Optional[str] = None
) -> int:
    """
    Automatically create organization record when domain is added to scrape list.
    
    Args:
        conn: Database connection
        domain: Domain name
        canonical_name: Optional canonical name if known
        
    Returns:
        Organization ID
    """
    org_db = OrganizationDB(conn)
    
    # Check if organization already exists
    org = await org_db.get_organization_by_domain(domain)
    if org:
        return org['id']
    
    # Try to find canonical name from heuristics
    if not canonical_name:
        base_path = Path(__file__).parent.parent.parent.parent
        aliases_file = base_path / "MasterProfiles" / "Heuristics" / "company_aliases.json"
        
        if aliases_file.exists():
            import json
            with open(aliases_file, 'r', encoding='utf-8') as f:
                aliases = json.load(f)
            
            # Check if domain or any variation maps to a canonical name
            domain_variations = [
                domain,
                domain.replace('.com', ''),
                domain.replace('.', ' '),
                domain.split('.')[0]  # First part of domain
            ]
            
            for variation in domain_variations:
                if variation in aliases:
                    canonical_name = aliases[variation]
                    break
                if variation.lower() in aliases:
                    canonical_name = aliases[variation.lower()]
                    break
    
    # Determine organizational type from domain
    org_type = None
    if any(term in domain.lower() for term in ['.ai', 'tech', 'software', 'platform']):
        org_type = 'Technology Vendor'
    else:
        org_type = 'BPO Provider'  # Default
    
    # Create organization with auto_created flag
    org_id = await org_db.create_or_get_organization(
        domain,
        canonical_name=canonical_name,
        organizational_type=org_type,
        auto_created=True
    )
    
    return org_id


async def sync_scrape_list_to_organizations(conn: asyncpg.Connection, scrape_list_file: Path):
    """
    Sync domains from scrape list file to organizations table.
    Creates organizations for any domains not yet in database.
    
    Args:
        conn: Database connection
        scrape_list_file: Path to bpo_sites.txt or similar scrape list
    """
    if not scrape_list_file.exists():
        print(f"Warning: Scrape list file {scrape_list_file} not found")
        return
    
    # Read domains from file
    domains = []
    with open(scrape_list_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Extract domain from URL if present
            if '://' in line:
                from urllib.parse import urlparse
                parsed = urlparse(line)
                domain = parsed.netloc or parsed.path
            else:
                domain = line
            
            # Remove www. prefix
            domain = domain.replace('www.', '').lower()
            domains.append(domain)
    
    # Create organizations for domains not in database
    org_db = OrganizationDB(conn)
    created_count = 0
    
    for domain in domains:
        org = await org_db.get_organization_by_domain(domain)
        if not org:
            await auto_create_organization_from_domain(conn, domain)
            created_count += 1
    
    print(f"Created {created_count} new organizations from scrape list")


async def main():
    """Main function for testing."""
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
    scrape_list_file = base_path / "scraper" / "config" / "bpo_sites.txt"
    
    conn = await asyncpg.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )
    
    try:
        await sync_scrape_list_to_organizations(conn, scrape_list_file)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

