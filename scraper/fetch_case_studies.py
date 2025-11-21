#!/usr/bin/env python3
"""Fetch and display full content of case study pages"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from curl_cffi import requests
from bs4 import BeautifulSoup
from src.parsers.boilerplate_detector import BoilerplateDetector

async def fetch_case_studies():
    """Fetch and display case study content"""
    urls = [
        'https://foundever.com/case-studies/a-leading-global-healthcare-brand-achieves-a-13-point-jump-in-nps/',
        'https://foundever.com/case-studies/a-global-consumer-electronics-giant-blends-ai-with-human-talent/',
        'https://foundever.com/case-studies/banking-disruptor-excels-in-risk-management-and-compliance/',
        'https://foundever.com/case-studies/hospitality-innovator-uses-multilingual-hubs-to-achieve-an-outstanding-nps-and-cut-employee-attrition/'
    ]
    
    session = requests.Session()
    detector = BoilerplateDetector()
    
    for i, url in enumerate(urls, 1):
        try:
            print(f"\n{'='*100}")
            print(f"CASE STUDY #{i}")
            print(f"{'='*100}\n")
            
            # Fetch page
            response = session.get(url, timeout=30)
            response.raise_for_status()
            html_content = response.text
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Get title
            title_tag = soup.find('title')
            title = title_tag.get_text(strip=True) if title_tag else "No title"
            
            # Extract main content
            main_content = detector.extract_main_content(html_content)
            
            print(f"Title: {title}")
            print(f"URL: {url}")
            print(f"\n{'─'*100}")
            print("MAIN CONTENT:")
            print(f"{'─'*100}\n")
            print(main_content[:5000])  # First 5000 chars
            if len(main_content) > 5000:
                print(f"\n... (content truncated, total length: {len(main_content)} characters)")
            print(f"\n{'='*100}\n")
            
        except Exception as e:
            print(f"Error fetching {url}: {e}\n")

if __name__ == '__main__':
    asyncio.run(fetch_case_studies())

