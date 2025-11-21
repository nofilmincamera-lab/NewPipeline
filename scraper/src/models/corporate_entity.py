"""
Database models for corporate entities and relationships.
"""

import json
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class CorporateEntity(BaseModel):
    """Model for corporate entity."""
    
    id: Optional[int] = None
    entity_name: str
    entity_type: Optional[str] = None
    legal_name: Optional[str] = None
    dba_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    registration_number: Optional[str] = None
    founded_year: Optional[int] = None
    status: str = 'Active'
    website: Optional[str] = None
    headquarters_address: Optional[str] = None
    headquarters_country: Optional[str] = None
    headquarters_city: Optional[str] = None
    employee_count_range: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EntityRelationship(BaseModel):
    """Model for entity relationship."""
    
    id: Optional[int] = None
    parent_entity_id: int
    child_entity_id: int
    relationship_type: str
    ownership_percentage: Optional[float] = None
    relationship_start_date: Optional[date] = None
    relationship_end_date: Optional[date] = None
    is_active: bool = True
    notes: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    evidence_count: int = 1


class OrganizationEntityMapping(BaseModel):
    """Model for organization to entity mapping."""
    
    id: Optional[int] = None
    organization_id: int
    entity_id: int
    relationship_type: Optional[str] = None
    is_primary: bool = False
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    evidence_count: int = 1


class CorporateEntityDB:
    """Database operations for corporate entities."""
    
    def __init__(self, connection):
        """
        Initialize database operations.
        
        Args:
            connection: Database connection (asyncpg connection)
        """
        self.conn = connection
    
    async def create_or_get_entity(
        self,
        entity_name: str,
        **kwargs
    ) -> int:
        """
        Create corporate entity or get existing by name.
        
        Args:
            entity_name: Entity name
            **kwargs: Additional entity fields
            
        Returns:
            Entity ID
        """
        # Check if exists by name or legal name
        query = """
            SELECT id FROM corporate_entities
            WHERE entity_name = $1 OR legal_name = $1
        """
        entity_id = await self.conn.fetchval(query, entity_name)
        
        if entity_id:
            return entity_id
        
        # Create new
        insert_query = """
            INSERT INTO corporate_entities (
                entity_name, entity_type, legal_name, dba_name, jurisdiction,
                registration_number, founded_year, status, website,
                headquarters_address, headquarters_country, headquarters_city,
                employee_count_range, description, notes
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            RETURNING id
        """
        
        entity_id = await self.conn.fetchval(
            insert_query,
            entity_name,
            kwargs.get('entity_type'),
            kwargs.get('legal_name'),
            kwargs.get('dba_name'),
            kwargs.get('jurisdiction'),
            kwargs.get('registration_number'),
            kwargs.get('founded_year'),
            kwargs.get('status', 'Active'),
            kwargs.get('website'),
            kwargs.get('headquarters_address'),
            kwargs.get('headquarters_country'),
            kwargs.get('headquarters_city'),
            kwargs.get('employee_count_range'),
            kwargs.get('description'),
            kwargs.get('notes')
        )
        
        return entity_id
    
    async def get_entity_by_id(self, entity_id: int) -> Optional[Dict]:
        """Get entity by ID."""
        query = "SELECT * FROM corporate_entities WHERE id = $1"
        row = await self.conn.fetchrow(query, entity_id)
        return dict(row) if row else None
    
    async def upsert_entity_relationship(
        self,
        parent_entity_id: int,
        child_entity_id: int,
        relationship_type: str,
        ownership_percentage: Optional[float] = None,
        relationship_start_date: Optional[date] = None,
        relationship_end_date: Optional[date] = None,
        notes: Optional[str] = None
    ) -> int:
        """Upsert entity relationship."""
        query = """
            INSERT INTO entity_relationships (
                parent_entity_id, child_entity_id, relationship_type,
                ownership_percentage, relationship_start_date, relationship_end_date,
                notes, first_seen_at, last_seen_at, evidence_count, is_active
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, true)
            ON CONFLICT (parent_entity_id, child_entity_id, relationship_type) DO UPDATE SET
                ownership_percentage = COALESCE(EXCLUDED.ownership_percentage, entity_relationships.ownership_percentage),
                relationship_start_date = COALESCE(EXCLUDED.relationship_start_date, entity_relationships.relationship_start_date),
                relationship_end_date = COALESCE(EXCLUDED.relationship_end_date, entity_relationships.relationship_end_date),
                notes = COALESCE(EXCLUDED.notes, entity_relationships.notes),
                last_seen_at = CURRENT_TIMESTAMP,
                evidence_count = entity_relationships.evidence_count + 1,
                is_active = true
            RETURNING id
        """
        
        rel_id = await self.conn.fetchval(
            query,
            parent_entity_id,
            child_entity_id,
            relationship_type,
            ownership_percentage,
            relationship_start_date,
            relationship_end_date,
            notes
        )
        
        return rel_id
    
    async def upsert_organization_entity_mapping(
        self,
        organization_id: int,
        entity_id: int,
        relationship_type: Optional[str] = None,
        is_primary: bool = False
    ) -> int:
        """Upsert organization to entity mapping."""
        query = """
            INSERT INTO organization_entity_mapping (
                organization_id, entity_id, relationship_type, is_primary,
                first_seen_at, last_seen_at, evidence_count
            ) VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
            ON CONFLICT (organization_id, entity_id) DO UPDATE SET
                relationship_type = COALESCE(EXCLUDED.relationship_type, organization_entity_mapping.relationship_type),
                is_primary = EXCLUDED.is_primary,
                last_seen_at = CURRENT_TIMESTAMP,
                evidence_count = organization_entity_mapping.evidence_count + 1
            RETURNING id
        """
        
        mapping_id = await self.conn.fetchval(
            query, organization_id, entity_id, relationship_type, is_primary
        )
        
        return mapping_id
    
    async def get_entity_hierarchy(self, entity_id: int) -> Dict[str, Any]:
        """
        Get entity hierarchy (parents and children).
        
        Returns:
            Dict with 'parents' and 'children' lists
        """
        # Get parents
        parents_query = """
            SELECT er.*, ce.entity_name as parent_name
            FROM entity_relationships er
            JOIN corporate_entities ce ON er.parent_entity_id = ce.id
            WHERE er.child_entity_id = $1 AND er.is_active = true
        """
        parents = await self.conn.fetch(parents_query, entity_id)
        
        # Get children
        children_query = """
            SELECT er.*, ce.entity_name as child_name
            FROM entity_relationships er
            JOIN corporate_entities ce ON er.child_entity_id = ce.id
            WHERE er.parent_entity_id = $1 AND er.is_active = true
        """
        children = await self.conn.fetch(children_query, entity_id)
        
        return {
            'parents': [dict(row) for row in parents],
            'children': [dict(row) for row in children]
        }
    
    async def get_organization_entities(self, organization_id: int) -> List[Dict]:
        """Get all entities linked to an organization."""
        query = """
            SELECT oem.*, ce.entity_name, ce.entity_type, ce.legal_name
            FROM organization_entity_mapping oem
            JOIN corporate_entities ce ON oem.entity_id = ce.id
            WHERE oem.organization_id = $1
            ORDER BY oem.is_primary DESC, oem.last_seen_at DESC
        """
        rows = await self.conn.fetch(query, organization_id)
        return [dict(row) for row in rows]

