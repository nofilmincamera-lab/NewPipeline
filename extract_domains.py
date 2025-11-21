#!/usr/bin/env python3
"""Extract unique domains from Word document"""
from docx import Document
from urllib.parse import urlparse
import re
import json

doc = Document('DataSample/url.docx')
domains = set()

for para in doc.paragraphs:
    text = para.text.strip()
    if not text:
        continue
    
    # Try to extract URLs from JSON-like format
    if '"url":' in text:
        # Extract URL from JSON format
        match = re.search(r'"url":\s*"([^"]+)"', text)
        if match:
            url = match.group(1)
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            if domain:
                domains.add(domain)
    elif 'http' in text:
        # Direct URL
        parsed = urlparse(text)
        domain = parsed.netloc.lower().replace('www.', '')
        if domain:
            domains.add(domain)

# Print sorted unique domains
for domain in sorted(domains):
    print(domain)

print(f"\nTotal unique domains: {len(domains)}")

