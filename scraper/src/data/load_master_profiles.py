"""
Load initial organization data from MasterProfiles Excel file and BPO_SITES_LIST.md.
"""

import json
import re
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import asyncpg
import pandas as pd


def parse_bpo_sites_list(md_file: Path) -> List[Tuple[str, str]]:
    """
    Parse BPO_SITES_LIST.md to extract domain and company name pairs.
    
    Returns:
        List of (domain, company_name) tuples
    """
    domains = []
    
    if not md_file.exists():
        print(f"Warning: {md_file} not found")
        return domains
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Match lines like: "1. **accenture.com** - Accenture"
    pattern = r'\d+\.\s+\*\*([^\*]+)\*\*\s+-\s+(.+)'
    matches = re.findall(pattern, content)
    
    for domain, name in matches:
        # Clean domain (remove www. and https:// if present)
        domain = domain.strip().lower()
        domain = re.sub(r'^(https?://)?(www\.)?', '', domain)
        name = name.strip()
        domains.append((domain, name))
    
    return domains


def load_company_aliases(aliases_file: Path) -> Dict[str, str]:
    """Load company aliases from JSON file."""
    if not aliases_file.exists():
        return {}
    
    with open(aliases_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_canonical_name(domain: str, company_name: str, aliases: Dict[str, str]) -> str:
    """
    Get canonical name for organization using aliases mapping.
    
    Args:
        domain: Organization domain
        company_name: Company name from BPO list
        aliases: Aliases dictionary
        
    Returns:
        Canonical name
    """
    # Try to find canonical name from aliases
    domain_lower = domain.lower()
    name_lower = company_name.lower()
    
    # Check if domain or name maps to a canonical name
    if domain_lower in aliases:
        return aliases[domain_lower]
    if name_lower in aliases:
        return aliases[name_lower]
    
    # Return the company name as-is
    return company_name


def determine_organizational_type(company_name: str, domain: str) -> Optional[str]:
    """
    Determine organizational type from name/domain patterns.
    
    Returns:
        Organizational type string or None
    """
    name_lower = company_name.lower()
    domain_lower = domain.lower()
    
    # Award organizations
    if any(term in name_lower for term in ['award', 'gartner', 'forrester', 'idc', 'nelsonhall']):
        return 'Award Organization'
    
    # Research/analyst firms
    if any(term in name_lower for term in ['research', 'analyst', 'consulting', 'advisory']):
        return 'Research/Analyst Firm'
    
    # Technology vendors
    if any(term in domain_lower for term in ['.ai', 'tech', 'software', 'platform']):
        return 'Technology Vendor'
    
    # BPO providers (default for most)
    return 'BPO Provider'


async def load_organizations_from_excel(
    db_conn: asyncpg.Connection,
    excel_file: Path,
    org_db
) -> int:
    """
    Load organizations from Excel file.
    
    Returns:
        Number of organizations loaded
    """
    if not excel_file.exists():
        print(f"Warning: Excel file {excel_file} not found")
        return 0
    
    try:
        df = pd.read_excel(excel_file)
        count = 0
        
        for _, row in df.iterrows():
            # Extract domain and other fields from Excel
            # Adjust column names based on actual Excel structure
            domain = None
            canonical_name = None
            
            # Try common column names
            for col in ['domain', 'Domain', 'website', 'Website', 'url', 'URL']:
                if col in df.columns:
                    domain = str(row[col]).strip().lower()
                    domain = re.sub(r'^(https?://)?(www\.)?', '', domain)
                    break
            
            for col in ['name', 'Name', 'company', 'Company', 'company_name', 'Company Name']:
                if col in df.columns:
                    canonical_name = str(row[col]).strip()
                    break
            
            if not domain:
                continue
            
            # Extract other fields
            org_type = None
            customer_segment = None
            founded_year = None
            
            for col in ['type', 'Type', 'organizational_type', 'Organizational Type']:
                if col in df.columns:
                    org_type = str(row[col]).strip() if pd.notna(row[col]) else None
                    break
            
            for col in ['segment', 'Segment', 'customer_segment', 'Customer Segment', 'B2B/B2C']:
                if col in df.columns:
                    segment = str(row[col]).strip() if pd.notna(row[col]) else None
                    if segment:
                        if 'both' in segment.lower() or 'b2b' in segment.lower() and 'b2c' in segment.lower():
                            customer_segment = 'Both'
                        elif 'b2b' in segment.lower():
                            customer_segment = 'B2B'
                        elif 'b2c' in segment.lower():
                            customer_segment = 'B2C'
                    break
            
            for col in ['founded', 'Founded', 'founded_year', 'Founded Year', 'year']:
                if col in df.columns and pd.notna(row[col]):
                    try:
                        founded_year = int(row[col])
                    except (ValueError, TypeError):
                        pass
                    break
            
            org_id = await org_db.create_or_get_organization(
                domain,
                canonical_name=canonical_name,
                organizational_type=org_type,
                customer_segment=customer_segment,
                founded_year=founded_year
            )
            count += 1
        
        return count
    
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return 0


async def load_organizations_from_bpo_list(
    db_conn: asyncpg.Connection,
    bpo_list_file: Path,
    aliases_file: Path,
    org_db
) -> int:
    """
    Load organizations from BPO_SITES_LIST.md.
    
    Returns:
        Number of organizations loaded
    """
    domains = parse_bpo_sites_list(bpo_list_file)
    aliases = load_company_aliases(aliases_file)
    
    count = 0
    for domain, company_name in domains:
        canonical_name = get_canonical_name(domain, company_name, aliases)
        org_type = determine_organizational_type(company_name, domain)
        
        org_id = await org_db.create_or_get_organization(
            domain,
            canonical_name=canonical_name,
            organizational_type=org_type,
            auto_created=False
        )
        count += 1
    
    return count


async def main():
    """Main loading function."""
    # Database connection
    db_host = "localhost"
    db_name = "bpo_intelligence"
    db_user = "bpo_user"
    
    # Get password from file
    password_file = Path("ops/secrets/postgres_password.txt")
    if password_file.exists():
        with open(password_file, 'r') as f:
            db_password = f.read().strip()
    else:
        db_password = input("Enter PostgreSQL password: ")
    
    # File paths
    base_path = Path(__file__).parent.parent.parent.parent
    master_profiles_path = base_path / "MasterProfiles"
    excel_file = master_profiles_path / "bpo_companies_final.xlsx"
    bpo_list_file = base_path / "BPO_SITES_LIST.md"
    aliases_file = master_profiles_path / "Heuristics" / "company_aliases.json"
    
    conn = await asyncpg.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )
    
    try:
        from ..models.organization import OrganizationDB
        org_db = OrganizationDB(conn)
        
        print("Loading organizations from Excel...")
        excel_count = await load_organizations_from_excel(conn, excel_file, org_db)
        print(f"Loaded {excel_count} organizations from Excel")
        
        print("Loading organizations from BPO list...")
        bpo_count = await load_organizations_from_bpo_list(
            conn, bpo_list_file, aliases_file, org_db
        )
        print(f"Loaded {bpo_count} organizations from BPO list")
        
        print(f"Total organizations loaded: {excel_count + bpo_count}")
    
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

