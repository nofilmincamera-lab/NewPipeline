"""
Database models for organization profiles and related entities.
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator


class Organization(BaseModel):
    """Model for organization master record."""
    
    id: Optional[int] = None
    canonical_name: Optional[str] = None
    domain: str
    aliases: Optional[List[str]] = Field(default_factory=list)
    organizational_type: Optional[str] = None
    organizational_classification: Optional[str] = None
    customer_segment: Optional[str] = Field(None, pattern='^(B2B|B2C|Both)$')
    founded_year: Optional[int] = None
    headquarters_country: Optional[str] = None
    employee_count_range: Optional[str] = None
    auto_created: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class OrganizationProduct(BaseModel):
    """Model for organization product."""
    
    id: Optional[int] = None
    organization_id: int
    product_name: str
    category: Optional[str] = None
    description: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    evidence_count: int = 1
    is_active: bool = True


class OrganizationService(BaseModel):
    """Model for organization service."""
    
    id: Optional[int] = None
    organization_id: int
    service_id: str
    service_name: str
    service_path: Optional[List[str]] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    evidence_count: int = 1
    is_active: bool = True


class OrganizationPlatform(BaseModel):
    """Model for organization platform."""
    
    id: Optional[int] = None
    organization_id: int
    platform_name: str
    platform_type: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    evidence_count: int = 1
    is_active: bool = True


class OrganizationCertification(BaseModel):
    """Model for organization certification."""
    
    id: Optional[int] = None
    organization_id: int
    certification_name: str
    certification_type: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    evidence_count: int = 1
    is_active: bool = True


class OrganizationAward(BaseModel):
    """Model for organization award."""
    
    id: Optional[int] = None
    organization_id: int
    award_name: str
    award_issuer: Optional[str] = None
    award_year: Optional[int] = None
    category: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    evidence_count: int = 1
    is_active: bool = True


class OrganizationOperatingMarket(BaseModel):
    """Model for organization operating market."""
    
    id: Optional[int] = None
    organization_id: int
    country_code: str
    country_name: str
    region: Optional[str] = None
    operation_type: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    evidence_count: int = 1
    is_active: bool = True


class OrganizationRelationship(BaseModel):
    """Model for organization relationship."""
    
    id: Optional[int] = None
    organization_id: int
    related_organization_id: int
    relationship_type: str
    relationship_description: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    evidence_count: int = 1
    is_active: bool = True


class OrganizationEvidence(BaseModel):
    """Model for organization evidence (source URLs)."""
    
    id: Optional[int] = None
    organization_id: int
    fact_type: str
    fact_id: int
    source_url: str
    scraped_site_id: Optional[int] = None
    extracted_at: Optional[datetime] = None


class OrganizationDB:
    """Database operations for organizations."""
    
    def __init__(self, connection):
        """
        Initialize database operations.
        
        Args:
            connection: Database connection (asyncpg connection)
        """
        self.conn = connection
    
    async def create_or_get_organization(self, domain: str, **kwargs) -> int:
        """
        Create organization or get existing by domain.
        
        Args:
            domain: Organization domain
            **kwargs: Additional organization fields
            
        Returns:
            Organization ID
        """
        # Check if exists
        query = "SELECT id FROM organizations WHERE domain = $1"
        org_id = await self.conn.fetchval(query, domain)
        
        if org_id:
            return org_id
        
        # Create new
        insert_query = """
            INSERT INTO organizations (
                domain, canonical_name, aliases, organizational_type,
                organizational_classification, customer_segment, founded_year,
                headquarters_country, employee_count_range, auto_created
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
        """
        
        aliases_json = json.dumps(kwargs.get('aliases', []))
        
        org_id = await self.conn.fetchval(
            insert_query,
            domain,
            kwargs.get('canonical_name'),
            aliases_json,
            kwargs.get('organizational_type'),
            kwargs.get('organizational_classification'),
            kwargs.get('customer_segment'),
            kwargs.get('founded_year'),
            kwargs.get('headquarters_country'),
            kwargs.get('employee_count_range'),
            kwargs.get('auto_created', False)
        )
        
        return org_id
    
    async def get_organization_by_domain(self, domain: str) -> Optional[Dict]:
        """Get organization by domain."""
        query = "SELECT * FROM organizations WHERE domain = $1"
        row = await self.conn.fetchrow(query, domain)
        return dict(row) if row else None
    
    async def update_organization(self, org_id: int, **kwargs) -> bool:
        """Update organization fields."""
        updates = []
        params = []
        param_idx = 1
        
        for key, value in kwargs.items():
            if key == 'aliases' and value is not None:
                updates.append(f"aliases = ${param_idx}")
                params.append(json.dumps(value))
            elif value is not None:
                updates.append(f"{key} = ${param_idx}")
                params.append(value)
            param_idx += 1
        
        if not updates:
            return False
        
        params.append(org_id)
        query = f"""
            UPDATE organizations
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
        """
        
        result = await self.conn.execute(query, *params)
        return result == "UPDATE 1"
    
    async def upsert_product(
        self,
        organization_id: int,
        product_name: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        source_url: Optional[str] = None,
        scraped_site_id: Optional[int] = None
    ) -> int:
        """Upsert organization product."""
        query = """
            INSERT INTO organization_products (
                organization_id, product_name, category, description,
                first_seen_at, last_seen_at, evidence_count, is_active
            ) VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, true)
            ON CONFLICT (organization_id, product_name) DO UPDATE SET
                category = EXCLUDED.category,
                description = COALESCE(EXCLUDED.description, organization_products.description),
                last_seen_at = CURRENT_TIMESTAMP,
                evidence_count = organization_products.evidence_count + 1,
                is_active = true
            RETURNING id
        """
        
        product_id = await self.conn.fetchval(
            query, organization_id, product_name, category, description
        )
        
        # Add evidence if provided
        if source_url:
            await self.add_evidence(
                organization_id, 'product', product_id, source_url, scraped_site_id
            )
        
        return product_id
    
    async def upsert_service(
        self,
        organization_id: int,
        service_id: str,
        service_name: str,
        service_path: Optional[List[str]] = None,
        source_url: Optional[str] = None,
        scraped_site_id: Optional[int] = None
    ) -> int:
        """Upsert organization service."""
        path_json = json.dumps(service_path) if service_path else None
        
        query = """
            INSERT INTO organization_services (
                organization_id, service_id, service_name, service_path,
                first_seen_at, last_seen_at, evidence_count, is_active
            ) VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, true)
            ON CONFLICT (organization_id, service_id) DO UPDATE SET
                service_name = EXCLUDED.service_name,
                service_path = COALESCE(EXCLUDED.service_path, organization_services.service_path),
                last_seen_at = CURRENT_TIMESTAMP,
                evidence_count = organization_services.evidence_count + 1,
                is_active = true
            RETURNING id
        """
        
        service_record_id = await self.conn.fetchval(
            query, organization_id, service_id, service_name, path_json
        )
        
        if source_url:
            await self.add_evidence(
                organization_id, 'service', service_record_id, source_url, scraped_site_id
            )
        
        return service_record_id
    
    async def upsert_platform(
        self,
        organization_id: int,
        platform_name: str,
        platform_type: Optional[str] = None,
        source_url: Optional[str] = None,
        scraped_site_id: Optional[int] = None
    ) -> int:
        """Upsert organization platform."""
        query = """
            INSERT INTO organization_platforms (
                organization_id, platform_name, platform_type,
                first_seen_at, last_seen_at, evidence_count, is_active
            ) VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, true)
            ON CONFLICT (organization_id, platform_name) DO UPDATE SET
                platform_type = COALESCE(EXCLUDED.platform_type, organization_platforms.platform_type),
                last_seen_at = CURRENT_TIMESTAMP,
                evidence_count = organization_platforms.evidence_count + 1,
                is_active = true
            RETURNING id
        """
        
        platform_id = await self.conn.fetchval(
            query, organization_id, platform_name, platform_type
        )
        
        if source_url:
            await self.add_evidence(
                organization_id, 'platform', platform_id, source_url, scraped_site_id
            )
        
        return platform_id
    
    async def upsert_certification(
        self,
        organization_id: int,
        certification_name: str,
        certification_type: Optional[str] = None,
        source_url: Optional[str] = None,
        scraped_site_id: Optional[int] = None
    ) -> int:
        """Upsert organization certification."""
        query = """
            INSERT INTO organization_certifications (
                organization_id, certification_name, certification_type,
                first_seen_at, last_seen_at, evidence_count, is_active
            ) VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, true)
            ON CONFLICT (organization_id, certification_name) DO UPDATE SET
                certification_type = COALESCE(EXCLUDED.certification_type, organization_certifications.certification_type),
                last_seen_at = CURRENT_TIMESTAMP,
                evidence_count = organization_certifications.evidence_count + 1,
                is_active = true
            RETURNING id
        """
        
        cert_id = await self.conn.fetchval(
            query, organization_id, certification_name, certification_type
        )
        
        if source_url:
            await self.add_evidence(
                organization_id, 'certification', cert_id, source_url, scraped_site_id
            )
        
        return cert_id
    
    async def upsert_award(
        self,
        organization_id: int,
        award_name: str,
        award_issuer: Optional[str] = None,
        award_year: Optional[int] = None,
        category: Optional[str] = None,
        source_url: Optional[str] = None,
        scraped_site_id: Optional[int] = None
    ) -> int:
        """Upsert organization award."""
        query = """
            INSERT INTO organization_awards (
                organization_id, award_name, award_issuer, award_year, category,
                first_seen_at, last_seen_at, evidence_count, is_active
            ) VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, true)
            ON CONFLICT (organization_id, award_name, award_year) DO UPDATE SET
                award_issuer = COALESCE(EXCLUDED.award_issuer, organization_awards.award_issuer),
                category = COALESCE(EXCLUDED.category, organization_awards.category),
                last_seen_at = CURRENT_TIMESTAMP,
                evidence_count = organization_awards.evidence_count + 1,
                is_active = true
            RETURNING id
        """
        
        award_id = await self.conn.fetchval(
            query, organization_id, award_name, award_issuer, award_year, category
        )
        
        if source_url:
            await self.add_evidence(
                organization_id, 'award', award_id, source_url, scraped_site_id
            )
        
        return award_id
    
    async def upsert_operating_market(
        self,
        organization_id: int,
        country_code: str,
        country_name: str,
        region: Optional[str] = None,
        operation_type: Optional[str] = None,
        source_url: Optional[str] = None,
        scraped_site_id: Optional[int] = None
    ) -> int:
        """Upsert organization operating market."""
        query = """
            INSERT INTO organization_operating_markets (
                organization_id, country_code, country_name, region, operation_type,
                first_seen_at, last_seen_at, evidence_count, is_active
            ) VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, true)
            ON CONFLICT (organization_id, country_code, operation_type) DO UPDATE SET
                country_name = EXCLUDED.country_name,
                region = COALESCE(EXCLUDED.region, organization_operating_markets.region),
                last_seen_at = CURRENT_TIMESTAMP,
                evidence_count = organization_operating_markets.evidence_count + 1,
                is_active = true
            RETURNING id
        """
        
        market_id = await self.conn.fetchval(
            query, organization_id, country_code, country_name, region, operation_type
        )
        
        if source_url:
            await self.add_evidence(
                organization_id, 'operating_market', market_id, source_url, scraped_site_id
            )
        
        return market_id
    
    async def upsert_relationship(
        self,
        organization_id: int,
        related_organization_id: int,
        relationship_type: str,
        relationship_description: Optional[str] = None,
        source_url: Optional[str] = None,
        scraped_site_id: Optional[int] = None
    ) -> int:
        """Upsert organization relationship."""
        query = """
            INSERT INTO organization_relationships (
                organization_id, related_organization_id, relationship_type,
                relationship_description, first_seen_at, last_seen_at,
                evidence_count, is_active
            ) VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, true)
            ON CONFLICT (organization_id, related_organization_id, relationship_type) DO UPDATE SET
                relationship_description = COALESCE(EXCLUDED.relationship_description, organization_relationships.relationship_description),
                last_seen_at = CURRENT_TIMESTAMP,
                evidence_count = organization_relationships.evidence_count + 1,
                is_active = true
            RETURNING id
        """
        
        rel_id = await self.conn.fetchval(
            query, organization_id, related_organization_id, relationship_type, relationship_description
        )
        
        if source_url:
            await self.add_evidence(
                organization_id, 'relationship', rel_id, source_url, scraped_site_id
            )
        
        return rel_id
    
    async def add_evidence(
        self,
        organization_id: int,
        fact_type: str,
        fact_id: int,
        source_url: str,
        scraped_site_id: Optional[int] = None
    ) -> int:
        """Add evidence record for a fact."""
        query = """
            INSERT INTO organization_evidence (
                organization_id, fact_type, fact_id, source_url, scraped_site_id
            ) VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """
        
        evidence_id = await self.conn.fetchval(
            query, organization_id, fact_type, fact_id, source_url, scraped_site_id
        )
        
        return evidence_id
    
    async def mark_facts_inactive_after_period(self, months: int = 3) -> int:
        """
        Mark facts as inactive if last_seen_at is older than specified months.
        
        Args:
            months: Number of months threshold
            
        Returns:
            Number of facts marked inactive
        """
        cutoff_date = datetime.now().replace(day=1)  # Start of current month
        for _ in range(months):
            if cutoff_date.month == 1:
                cutoff_date = cutoff_date.replace(year=cutoff_date.year - 1, month=12)
            else:
                cutoff_date = cutoff_date.replace(month=cutoff_date.month - 1)
        
        tables = [
            'organization_products',
            'organization_services',
            'organization_platforms',
            'organization_certifications',
            'organization_awards',
            'organization_operating_markets',
            'organization_relationships'
        ]
        
        total_updated = 0
        for table in tables:
            query = f"""
                UPDATE {table}
                SET is_active = false
                WHERE is_active = true
                AND last_seen_at < $1
            """
            result = await self.conn.execute(query, cutoff_date)
            # Extract number from result like "UPDATE 5"
            if result.startswith("UPDATE "):
                total_updated += int(result.split()[1])
        
        return total_updated

