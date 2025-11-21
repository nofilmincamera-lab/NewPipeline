#!/usr/bin/env python3
import asyncio
import asyncpg
import os
from datetime import datetime, timedelta

async def main():
    password_file = '/run/secrets/postgres_password'
    with open(password_file, 'r') as f:
        db_password = f.read().strip()
    
    conn = await asyncpg.connect(
        host='postgres',
        database='bpo_intelligence',
        user='bpo_user',
        password=db_password
    )
    
    try:
        # Check recent scrapes
        recent = await conn.fetchval("""
            SELECT COUNT(*) FROM scraped_sites 
            WHERE scraped_at > NOW() - INTERVAL '1 hour'
        """)
        
        # Check by domain
        domains = await conn.fetch("""
            SELECT domain, COUNT(*) as cnt 
            FROM scraped_sites 
            WHERE success = true
            GROUP BY domain 
            ORDER BY cnt DESC 
            LIMIT 10
        """)
        
        # Check zero content pages
        zero_content = await conn.fetchval("""
            SELECT COUNT(*) FROM scraped_sites
            WHERE success = true
              AND (title IS NULL OR title = '')
              AND (content_hash IS NULL OR content_hash = '')
              AND metadata->>'needs_rescrape' = 'true'
        """)
        
        print(f"Recent scrapes (last hour): {recent}")
        print(f"\nTop domains:")
        for row in domains:
            print(f"  {row['domain']}: {row['cnt']} pages")
        print(f"\nZero-content pages marked for rescrape: {zero_content}")
        
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())


