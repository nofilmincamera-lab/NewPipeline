"""
Utility to refresh organization data by marking inactive facts after specified period.
"""

import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import asyncpg

from ..models.organization import OrganizationDB


async def refresh_organization_data(
    conn: asyncpg.Connection,
    months: int = 3,
    dry_run: bool = False
) -> dict:
    """
    Mark organization facts as inactive if last_seen_at is older than specified months.
    
    Args:
        conn: Database connection
        months: Number of months threshold
        dry_run: If True, only report what would be changed
        
    Returns:
        Dictionary with statistics
    """
    org_db = OrganizationDB(conn)
    
    if dry_run:
        # Count facts that would be marked inactive
        cutoff_date = datetime.now() - timedelta(days=months * 30)
        
        stats = {}
        tables = [
            ('organization_products', 'products'),
            ('organization_services', 'services'),
            ('organization_platforms', 'platforms'),
            ('organization_certifications', 'certifications'),
            ('organization_awards', 'awards'),
            ('organization_operating_markets', 'operating_markets'),
            ('organization_relationships', 'relationships')
        ]
        
        for table, key in tables:
            query = f"""
                SELECT COUNT(*) FROM {table}
                WHERE is_active = true
                AND last_seen_at < $1
            """
            count = await conn.fetchval(query, cutoff_date)
            stats[key] = count
        
        return {
            'dry_run': True,
            'cutoff_date': cutoff_date.isoformat(),
            'stats': stats
        }
    else:
        # Actually mark as inactive
        count = await org_db.mark_facts_inactive_after_period(months)
        
        return {
            'dry_run': False,
            'facts_marked_inactive': count
        }


async def get_data_freshness_report(conn: asyncpg.Connection) -> dict:
    """
    Generate report on data freshness.
    
    Returns:
        Dictionary with freshness statistics
    """
    report = {}
    
    # Count active vs inactive facts
    tables = [
        ('organization_products', 'products'),
        ('organization_services', 'services'),
        ('organization_platforms', 'platforms'),
        ('organization_certifications', 'certifications'),
        ('organization_awards', 'awards'),
        ('organization_operating_markets', 'operating_markets'),
        ('organization_relationships', 'relationships')
    ]
    
    for table, key in tables:
        query = f"""
            SELECT 
                COUNT(*) FILTER (WHERE is_active = true) as active_count,
                COUNT(*) FILTER (WHERE is_active = false) as inactive_count,
                MIN(last_seen_at) FILTER (WHERE is_active = true) as oldest_active,
                MAX(last_seen_at) FILTER (WHERE is_active = true) as newest_active
            FROM {table}
        """
        row = await conn.fetchrow(query)
        report[key] = {
            'active': row['active_count'],
            'inactive': row['inactive_count'],
            'oldest_active': row['oldest_active'].isoformat() if row['oldest_active'] else None,
            'newest_active': row['newest_active'].isoformat() if row['newest_active'] else None
        }
    
    # Organization statistics
    org_query = """
        SELECT 
            COUNT(*) as total_orgs,
            COUNT(*) FILTER (WHERE auto_created = true) as auto_created_orgs,
            COUNT(*) FILTER (WHERE customer_segment IS NOT NULL) as orgs_with_segment
        FROM organizations
    """
    org_row = await conn.fetchrow(org_query)
    report['organizations'] = {
        'total': org_row['total_orgs'],
        'auto_created': org_row['auto_created_orgs'],
        'with_customer_segment': org_row['orgs_with_segment']
    }
    
    return report


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Refresh organization data')
    parser.add_argument(
        '--months',
        type=int,
        default=3,
        help='Number of months threshold for marking facts inactive (default: 3)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without making changes'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate data freshness report'
    )
    
    args = parser.parse_args()
    
    db_host = "localhost"
    db_name = "bpo_intelligence"
    db_user = "bpo_user"
    
    password_file = Path("ops/secrets/postgres_password.txt")
    if password_file.exists():
        with open(password_file, 'r') as f:
            db_password = f.read().strip()
    else:
        db_password = input("Enter PostgreSQL password: ")
    
    conn = await asyncpg.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )
    
    try:
        if args.report:
            print("Generating data freshness report...")
            report = await get_data_freshness_report(conn)
            
            print("\n=== Data Freshness Report ===\n")
            print(f"Organizations: {report['organizations']['total']} total")
            print(f"  - Auto-created: {report['organizations']['auto_created']}")
            print(f"  - With customer segment: {report['organizations']['with_customer_segment']}\n")
            
            for key, stats in report.items():
                if key == 'organizations':
                    continue
                print(f"{key.replace('_', ' ').title()}:")
                print(f"  - Active: {stats['active']}")
                print(f"  - Inactive: {stats['inactive']}")
                if stats['oldest_active']:
                    print(f"  - Oldest active: {stats['oldest_active']}")
                if stats['newest_active']:
                    print(f"  - Newest active: {stats['newest_active']}")
                print()
        
        else:
            result = await refresh_organization_data(conn, args.months, args.dry_run)
            
            if result['dry_run']:
                print(f"\n=== Dry Run Results (cutoff: {result['cutoff_date']}) ===\n")
                for key, count in result['stats'].items():
                    print(f"{key.replace('_', ' ').title()}: {count} facts would be marked inactive")
            else:
                print(f"\nMarked {result['facts_marked_inactive']} facts as inactive")
    
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

