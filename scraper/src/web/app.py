"""
Web viewer application for organization profiles and relationships.
"""

from pathlib import Path
from typing import Optional
import asyncpg
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import json
from loguru import logger

app = FastAPI(title="BPO Intelligence Viewer")

# Configure logging
logger.add("web_viewer.log", rotation="10 MB", level="INFO")

# Templates directory
base_path = Path(__file__).parent
templates = Jinja2Templates(directory=str(base_path / "templates"))

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None


def get_db_connection():
    """Get database connection from pool (context manager)."""
    if db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return db_pool.acquire()


@app.on_event("startup")
async def startup():
    """Initialize database connection pool."""
    global db_pool
    
    # Get password from file - try multiple possible paths
    password_file = None
    possible_paths = [
        Path("ops/secrets/postgres_password.txt"),
        Path(__file__).parent.parent.parent.parent / "ops" / "secrets" / "postgres_password.txt",
        Path.cwd() / "ops" / "secrets" / "postgres_password.txt"
    ]
    
    for path in possible_paths:
        if path.exists():
            password_file = path
            break
    
    if password_file and password_file.exists():
        with open(password_file, 'r') as f:
            db_password = f.read().strip()
    else:
        db_password = "postgres"  # Default for development
        print(f"Warning: Password file not found, using default password. Tried: {possible_paths}")
    
    try:
        db_pool = await asyncpg.create_pool(
            host="localhost",
            database="bpo_intelligence",
            user="bpo_user",
            password=db_password,
            min_size=2,
            max_size=10
        )
        logger.info("Database connection pool created successfully")
        
        # Test connection
        async with get_db_connection() as conn:
            await conn.fetchval("SELECT 1")
        logger.info("Database connection test successful")
    except Exception as e:
        logger.error(f"Error creating database pool: {e}")
        print(f"ERROR: Could not connect to database: {e}")
        print("Please check:")
        print("  1. PostgreSQL is running")
        print("  2. Database 'bpo_intelligence' exists")
        print("  3. User 'bpo_user' has access")
        print("  4. Password is correct")
        raise


@app.on_event("shutdown")
async def shutdown():
    """Close database connection pool."""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error_code": exc.status_code, "error_message": exc.detail},
        status_code=exc.status_code
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error_code": 500, "error_message": str(exc)},
        status_code=500
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        if db_pool is None:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "reason": "Database pool not initialized"}
            )
        
        async with get_db_connection() as conn:
            await conn.fetchval("SELECT 1")
        
        return JSONResponse(
            content={"status": "healthy", "database": "connected"}
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "reason": str(e)}
        )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, search: Optional[str] = Query(None)):
    """Home page - list all organizations."""
    async with get_db_connection() as conn:
        # Build query with optional search
        base_query = """
            SELECT 
                o.id, o.canonical_name, o.domain, o.organizational_type,
                o.customer_segment, o.founded_year, o.headquarters_country,
                COUNT(DISTINCT op.id) FILTER (WHERE op.is_active) as product_count,
                COUNT(DISTINCT os.id) FILTER (WHERE os.is_active) as service_count,
                COUNT(DISTINCT opl.id) FILTER (WHERE opl.is_active) as platform_count,
                COUNT(DISTINCT oc.id) FILTER (WHERE oc.is_active) as cert_count,
                COUNT(DISTINCT oa.id) FILTER (WHERE oa.is_active) as award_count,
                COUNT(DISTINCT om.id) FILTER (WHERE om.is_active) as market_count
            FROM organizations o
            LEFT JOIN organization_products op ON o.id = op.organization_id
            LEFT JOIN organization_services os ON o.id = os.organization_id
            LEFT JOIN organization_platforms opl ON o.id = opl.organization_id
            LEFT JOIN organization_certifications oc ON o.id = oc.organization_id
            LEFT JOIN organization_awards oa ON o.id = oa.organization_id
            LEFT JOIN organization_operating_markets om ON o.id = om.organization_id
        """
        
        if search:
            base_query += """
                WHERE o.canonical_name ILIKE $1 
                   OR o.domain ILIKE $1
                   OR o.organizational_type ILIKE $1
            """
            search_param = f"%{search}%"
            base_query += """
                GROUP BY o.id, o.canonical_name, o.domain, o.organizational_type,
                         o.customer_segment, o.founded_year, o.headquarters_country
                ORDER BY o.canonical_name NULLS LAST, o.domain
            """
            rows = await conn.fetch(base_query, search_param)
        else:
            base_query += """
                GROUP BY o.id, o.canonical_name, o.domain, o.organizational_type,
                         o.customer_segment, o.founded_year, o.headquarters_country
                ORDER BY o.canonical_name NULLS LAST, o.domain
            """
            rows = await conn.fetch(base_query)
        
        organizations = [dict(row) for row in rows]
        
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "organizations": organizations, "search": search or ""}
        )


@app.get("/organization/{org_id}", response_class=HTMLResponse)
async def organization_detail(request: Request, org_id: int):
    """Organization detail page."""
    async with get_db_connection() as conn:
        # Get organization
        org_query = "SELECT * FROM organizations WHERE id = $1"
        org_row = await conn.fetchrow(org_query, org_id)
        if not org_row:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        org = dict(org_row)
        if org.get('aliases'):
            org['aliases'] = json.loads(org['aliases']) if isinstance(org['aliases'], str) else org['aliases']
        
        # Get products
        products_query = """
            SELECT * FROM organization_products
            WHERE organization_id = $1 AND is_active = true
            ORDER BY last_seen_at DESC
        """
        products = [dict(row) for row in await conn.fetch(products_query, org_id)]
        
        # Get services
        services_query = """
            SELECT * FROM organization_services
            WHERE organization_id = $1 AND is_active = true
            ORDER BY last_seen_at DESC
        """
        services = [dict(row) for row in await conn.fetch(services_query, org_id)]
        for service in services:
            if service.get('service_path'):
                service['service_path'] = json.loads(service['service_path']) if isinstance(service['service_path'], str) else service['service_path']
        
        # Get platforms
        platforms_query = """
            SELECT * FROM organization_platforms
            WHERE organization_id = $1 AND is_active = true
            ORDER BY last_seen_at DESC
        """
        platforms = [dict(row) for row in await conn.fetch(platforms_query, org_id)]
        
        # Get certifications
        certs_query = """
            SELECT * FROM organization_certifications
            WHERE organization_id = $1 AND is_active = true
            ORDER BY last_seen_at DESC
        """
        certifications = [dict(row) for row in await conn.fetch(certs_query, org_id)]
        
        # Get awards
        awards_query = """
            SELECT * FROM organization_awards
            WHERE organization_id = $1 AND is_active = true
            ORDER BY award_year DESC NULLS LAST, last_seen_at DESC
        """
        awards = [dict(row) for row in await conn.fetch(awards_query, org_id)]
        
        # Get operating markets
        markets_query = """
            SELECT * FROM organization_operating_markets
            WHERE organization_id = $1 AND is_active = true
            ORDER BY country_name
        """
        markets = [dict(row) for row in await conn.fetch(markets_query, org_id)]
        
        # Get relationships
        rels_query = """
            SELECT 
                or_rel.*,
                o2.canonical_name as related_org_name,
                o2.domain as related_org_domain
            FROM organization_relationships or_rel
            JOIN organizations o2 ON or_rel.related_organization_id = o2.id
            WHERE or_rel.organization_id = $1 AND or_rel.is_active = true
            ORDER BY or_rel.last_seen_at DESC
        """
        relationships = [dict(row) for row in await conn.fetch(rels_query, org_id)]
        
        # Get corporate entities
        entities_query = """
            SELECT 
                oem.*,
                ce.entity_name, ce.entity_type, ce.legal_name, ce.jurisdiction
            FROM organization_entity_mapping oem
            JOIN corporate_entities ce ON oem.entity_id = ce.id
            WHERE oem.organization_id = $1
            ORDER BY oem.is_primary DESC
        """
        entities = [dict(row) for row in await conn.fetch(entities_query, org_id)]
        
        return templates.TemplateResponse(
            "organization.html",
            {
                "request": request,
                "org": org,
                "products": products,
                "services": services,
                "platforms": platforms,
                "certifications": certifications,
                "awards": awards,
                "markets": markets,
                "relationships": relationships,
                "entities": entities
            }
        )


@app.get("/entities", response_class=HTMLResponse)
async def entities_list(request: Request):
    """List all corporate entities."""
    async with get_db_connection() as conn:
        query = """
            SELECT 
                ce.*,
                COUNT(DISTINCT oem.organization_id) as org_count,
                COUNT(DISTINCT er1.id) FILTER (WHERE er1.is_active) as parent_count,
                COUNT(DISTINCT er2.id) FILTER (WHERE er2.is_active) as child_count
            FROM corporate_entities ce
            LEFT JOIN organization_entity_mapping oem ON ce.id = oem.entity_id
            LEFT JOIN entity_relationships er1 ON ce.id = er1.child_entity_id
            LEFT JOIN entity_relationships er2 ON ce.id = er2.parent_entity_id
            GROUP BY ce.id
            ORDER BY ce.entity_name
        """
        rows = await conn.fetch(query)
        entities = [dict(row) for row in rows]
        
        return templates.TemplateResponse(
            "entities.html",
            {"request": request, "entities": entities}
        )


@app.get("/entity/{entity_id}", response_class=HTMLResponse)
async def entity_detail(request: Request, entity_id: int):
    """Corporate entity detail page."""
    async with get_db_connection() as conn:
        # Get entity
        entity_query = "SELECT * FROM corporate_entities WHERE id = $1"
        entity_row = await conn.fetchrow(entity_query, entity_id)
        if not entity_row:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        entity = dict(entity_row)
        
        # Get parent relationships
        parents_query = """
            SELECT 
                er.*,
                ce.entity_name as parent_name, ce.entity_type as parent_type
            FROM entity_relationships er
            JOIN corporate_entities ce ON er.parent_entity_id = ce.id
            WHERE er.child_entity_id = $1 AND er.is_active = true
        """
        parents = [dict(row) for row in await conn.fetch(parents_query, entity_id)]
        
        # Get child relationships
        children_query = """
            SELECT 
                er.*,
                ce.entity_name as child_name, ce.entity_type as child_type
            FROM entity_relationships er
            JOIN corporate_entities ce ON er.child_entity_id = ce.id
            WHERE er.parent_entity_id = $1 AND er.is_active = true
        """
        children = [dict(row) for row in await conn.fetch(children_query, entity_id)]
        
        # Get linked organizations
        orgs_query = """
            SELECT 
                oem.*,
                o.canonical_name, o.domain, o.organizational_type
            FROM organization_entity_mapping oem
            JOIN organizations o ON oem.organization_id = o.id
            WHERE oem.entity_id = $1
            ORDER BY oem.is_primary DESC
        """
        organizations = [dict(row) for row in await conn.fetch(orgs_query, entity_id)]
        
        return templates.TemplateResponse(
            "entity.html",
            {
                "request": request,
                "entity": entity,
                "parents": parents,
                "children": children,
                "organizations": organizations
            }
        )


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    """Statistics dashboard."""
    async with get_db_connection() as conn:
        # Get overall statistics
        stats_query = """
            SELECT 
                COUNT(DISTINCT o.id) as total_orgs,
                COUNT(DISTINCT op.id) FILTER (WHERE op.is_active) as total_products,
                COUNT(DISTINCT os.id) FILTER (WHERE os.is_active) as total_services,
                COUNT(DISTINCT opl.id) FILTER (WHERE opl.is_active) as total_platforms,
                COUNT(DISTINCT oc.id) FILTER (WHERE oc.is_active) as total_certs,
                COUNT(DISTINCT oa.id) FILTER (WHERE oa.is_active) as total_awards,
                COUNT(DISTINCT om.id) FILTER (WHERE om.is_active) as total_markets,
                COUNT(DISTINCT or_rel.id) FILTER (WHERE or_rel.is_active) as total_relationships,
                COUNT(DISTINCT ce.id) as total_entities
            FROM organizations o
            LEFT JOIN organization_products op ON o.id = op.organization_id
            LEFT JOIN organization_services os ON o.id = os.organization_id
            LEFT JOIN organization_platforms opl ON o.id = opl.organization_id
            LEFT JOIN organization_certifications oc ON o.id = oc.organization_id
            LEFT JOIN organization_awards oa ON o.id = oa.organization_id
            LEFT JOIN organization_operating_markets om ON o.id = om.organization_id
            LEFT JOIN organization_relationships or_rel ON o.id = or_rel.organization_id
            LEFT JOIN organization_entity_mapping oem ON o.id = oem.organization_id
            LEFT JOIN corporate_entities ce ON oem.entity_id = ce.id
        """
        stats_row = await conn.fetchrow(stats_query)
        stats = dict(stats_row) if stats_row else {}
        
        # Get organizations by type
        type_query = """
            SELECT 
                organizational_type,
                COUNT(*) as count
            FROM organizations
            WHERE organizational_type IS NOT NULL
            GROUP BY organizational_type
            ORDER BY count DESC
        """
        org_types = [dict(row) for row in await conn.fetch(type_query)]
        
        # Get organizations by segment
        segment_query = """
            SELECT 
                customer_segment,
                COUNT(*) as count
            FROM organizations
            WHERE customer_segment IS NOT NULL
            GROUP BY customer_segment
            ORDER BY count DESC
        """
        segments = [dict(row) for row in await conn.fetch(segment_query)]
        
        return templates.TemplateResponse(
            "stats.html",
            {
                "request": request,
                "stats": stats,
                "org_types": org_types,
                "segments": segments
            }
        )


@app.get("/api/organizations")
async def api_organizations():
    """API endpoint for organizations list."""
    async with get_db_connection() as conn:
        query = """
            SELECT id, canonical_name, domain, organizational_type, customer_segment
            FROM organizations
            ORDER BY canonical_name NULLS LAST, domain
        """
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]


if __name__ == "__main__":
    import uvicorn
    import sys
    from pathlib import Path
    
    # Add project root to path if running directly
    project_root = Path(__file__).parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

