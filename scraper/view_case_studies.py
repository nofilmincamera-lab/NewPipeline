#!/usr/bin/env python3
"""View case study records from database"""
import asyncio
import asyncpg
import os
from bs4 import BeautifulSoup

async def view_case_studies():
    """Fetch and display case study records"""
    password_file = '/run/secrets/postgres_password'
    if os.path.exists(password_file):
        with open(password_file, 'r') as f:
            db_password = f.read().strip()
    else:
        db_password = os.getenv('POSTGRES_PASSWORD', 'bpo_secure_password_2025')
    
    conn = await asyncpg.connect(
        host='postgres',
        database='bpo_intelligence',
        user='bpo_user',
        password=db_password
    )
    
    try:
        urls = [
            'https://foundever.com/case-studies/a-leading-global-healthcare-brand-achieves-a-13-point-jump-in-nps/',
            'https://foundever.com/case-studies/a-global-consumer-electronics-giant-blends-ai-with-human-talent/',
            'https://foundever.com/case-studies/banking-disruptor-excels-in-risk-management-and-compliance/',
            'https://foundever.com/case-studies/hospitality-innovator-uses-multilingual-hubs-to-achieve-an-outstanding-nps-and-cut-employee-attrition/'
        ]
        
        for i, url in enumerate(urls, 1):
            row = await conn.fetchrow(
                'SELECT title, metadata, scraped_at FROM scraped_sites WHERE url = $1',
                url
            )
            if row:
                print(f"\n{'='*80}")
                print(f"CASE STUDY #{i}")
                print(f"{'='*80}")
                print(f"Title: {row['title']}")
                print(f"URL: {url}")
                print(f"Scraped: {row['scraped_at']}")
                print(f"Metadata: {row['metadata']}")
                print(f"{'='*80}\n")
            else:
                print(f"Record not found for: {url}")
                
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(view_case_studies())

