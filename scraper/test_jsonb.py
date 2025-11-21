#!/usr/bin/env python3
"""Test JSONB insertion with asyncpg"""
import asyncio
import json
import asyncpg
import os

async def test_jsonb():
    """Test JSONB insertion methods"""
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
        # Test 1: Dict directly
        try:
            result = await conn.fetchval('SELECT $1::jsonb', {'test': 123, 'nested': {'a': 1}})
            print(f"✓ Dict works: {result}")
        except Exception as e:
            print(f"✗ Dict failed: {e}")
        
        # Test 2: JSON string
        try:
            result = await conn.fetchval('SELECT $1::jsonb', json.dumps({'test': 456, 'nested': {'b': 2}}))
            print(f"✓ JSON string works: {result}")
        except Exception as e:
            print(f"✗ JSON string failed: {e}")
        
        # Test 3: Actual INSERT
        test_metadata = {'main_content_length': 1000, 'html_length': 5000}
        try:
            await conn.execute(
                "INSERT INTO scraped_sites (url, domain, scraped_at, strategy, success, metadata) VALUES ($1, $2, NOW(), $3, $4, $5) ON CONFLICT (url) DO NOTHING",
                'https://test.example.com',
                'example.com',
                'test',
                True,
                json.dumps(test_metadata)  # Using JSON string
            )
            print("✓ INSERT with JSON string works")
            
            # Verify
            result = await conn.fetchval("SELECT metadata FROM scraped_sites WHERE url = $1", 'https://test.example.com')
            print(f"✓ Retrieved metadata: {result}")
        except Exception as e:
            print(f"✗ INSERT failed: {e}")
            
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(test_jsonb())

