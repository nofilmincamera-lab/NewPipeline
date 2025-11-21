"""
Test script to send a test notification to Webhooky
"""

import asyncio
import httpx
from datetime import datetime, timedelta


async def test_webhook():
    """Send a test notification to Webhooky."""
    webhook_url = "https://webhookreceiver-ps6nryst2a-ey.a.run.app/ntlgwuz5nvgs9lxyokgyf44veib3x6gi"
    
    # Create test payload similar to what the notification system sends
    test_data = {
        'title': '[SUCCESS] Domain Scraped: example.com',
        'message': 'Domain: example.com\nPages: 25 crawled, 2 failed\nFiles: 8 total\nQuality Score: 85.5/100 (excellent)\nDuration: 45.3s\nFiles by type: pdf: 5, docx: 3',
        'domain': 'example.com',
        'pages_crawled': 25,
        'files_found': 8,
        'quality_score': 85.5,
        'quality_status': 'excellent',
        'duration_seconds': 45.3
    }
    
    print("Sending test notification to Webhooky...")
    print(f"Webhook URL: {webhook_url}")
    print(f"Payload:")
    for key, value in test_data.items():
        print(f"  {key}: {value}")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=test_data,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            
            print("[SUCCESS] Test notification sent successfully!")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            print()
            print("Check your mobile device for the push notification!")
            
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] HTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
    except httpx.RequestError as e:
        print(f"[ERROR] Request Error: {e}")
    except Exception as e:
        print(f"[ERROR] Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_webhook())

