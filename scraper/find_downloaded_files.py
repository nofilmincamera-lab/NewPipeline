#!/usr/bin/env python3
"""
Find and list all downloaded files with their exact locations
"""

import sys
from pathlib import Path
import yaml

# Load config to get storage path
config_path = Path(__file__).parent / 'config' / 'scraper_config.yaml'
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Get storage path
storage_path = config.get('file_download', {}).get('file_storage_path', '/app/data/files')

# Try different possible paths
possible_paths = [
    Path('data/scraped/files'),  # Windows relative path
    Path(storage_path),  # Config path (Docker)
    Path(__file__).parent.parent / 'data' / 'scraped' / 'files',  # Absolute from project root
]

print("="*80)
print("SEARCHING FOR DOWNLOADED FILES")
print("="*80)
print()

actual_path = None
for path in possible_paths:
    abs_path = path.absolute()
    if abs_path.exists():
        actual_path = abs_path
        print(f"[FOUND] Files at: {abs_path}")
        break
    else:
        print(f"[NOT FOUND] {abs_path}")

if not actual_path:
    print("\nERROR: Could not find file storage directory!")
    print("Searched paths:")
    for path in possible_paths:
        print(f"  - {path.absolute()}")
    sys.exit(1)

print()
print("="*80)
print("FILE COUNT BY DOMAIN")
print("="*80)

# Count files by domain and type
pdf_path = actual_path / 'pdf'
doc_path = actual_path / 'doc'
docx_path = actual_path / 'docx'

total_pdf = 0
total_doc = 0
total_docx = 0

domains = {}

if pdf_path.exists():
    for domain_dir in pdf_path.iterdir():
        if domain_dir.is_dir():
            domain_name = domain_dir.name
            pdf_count = 0
            for date_dir in domain_dir.iterdir():
                if date_dir.is_dir():
                    pdf_count += len(list(date_dir.glob('*.pdf')))
            
            if pdf_count > 0:
                domains[domain_name] = domains.get(domain_name, {})
                domains[domain_name]['pdf'] = pdf_count
                total_pdf += pdf_count

if doc_path.exists():
    for domain_dir in doc_path.iterdir():
        if domain_dir.is_dir():
            domain_name = domain_dir.name
            doc_count = 0
            for date_dir in domain_dir.iterdir():
                if date_dir.is_dir():
                    doc_count += len(list(date_dir.glob('*.doc')))
            
            if doc_count > 0:
                domains[domain_name] = domains.get(domain_name, {})
                domains[domain_name]['doc'] = doc_count
                total_doc += doc_count

if docx_path.exists():
    for domain_dir in docx_path.iterdir():
        if domain_dir.is_dir():
            domain_name = domain_dir.name
            docx_count = 0
            for date_dir in domain_dir.iterdir():
                if date_dir.is_dir():
                    docx_count += len(list(date_dir.glob('*.docx')))
            
            if docx_count > 0:
                domains[domain_name] = domains.get(domain_name, {})
                domains[domain_name]['docx'] = docx_count
                total_docx += docx_count

print(f"\nTotal PDF files: {total_pdf}")
print(f"Total DOC files: {total_doc}")
print(f"Total DOCX files: {total_docx}")
print(f"Grand Total: {total_pdf + total_doc + total_docx}")
print()

print("By Domain:")
for domain, types in sorted(domains.items()):
    pdf = types.get('pdf', 0)
    doc = types.get('doc', 0)
    docx = types.get('docx', 0)
    total = pdf + doc + docx
    print(f"  {domain}:")
    if pdf > 0:
        print(f"    PDF: {pdf}")
    if doc > 0:
        print(f"    DOC: {doc}")
    if docx > 0:
        print(f"    DOCX: {docx}")
    print(f"    Total: {total}")

print()
print("="*80)
print("WORLDLINE FILES CHECK")
print("="*80)

worldline_domains = ['worldline.com', 'docs.connect.worldline-solutions.com']
found_any = False

for domain in worldline_domains:
    domain_pdf_path = pdf_path / domain
    domain_doc_path = doc_path / domain
    domain_docx_path = docx_path / domain
    
    pdf_files = []
    doc_files = []
    docx_files = []
    
    if domain_pdf_path.exists():
        for date_dir in domain_pdf_path.iterdir():
            if date_dir.is_dir():
                pdf_files.extend(list(date_dir.glob('*.pdf')))
    
    if domain_doc_path.exists():
        for date_dir in domain_doc_path.iterdir():
            if date_dir.is_dir():
                doc_files.extend(list(date_dir.glob('*.doc')))
    
    if domain_docx_path.exists():
        for date_dir in domain_docx_path.iterdir():
            if date_dir.is_dir():
                docx_files.extend(list(date_dir.glob('*.docx')))
    
    total = len(pdf_files) + len(doc_files) + len(docx_files)
    
    if total > 0:
        found_any = True
        print(f"\n{domain}:")
        print(f"  PDF: {len(pdf_files)}")
        print(f"  DOC: {len(doc_files)}")
        print(f"  DOCX: {len(docx_files)}")
        print(f"  Total: {total}")
        
        if pdf_files:
            print(f"\n  Sample PDF locations:")
            for f in pdf_files[:3]:
                print(f"    {f}")
    else:
        print(f"\n{domain}: No files found")

if not found_any:
    print("\n[WARNING] No files found for worldline.com or docs.connect.worldline-solutions.com")
    print("This could mean:")
    print("  1. No PDF/DOC/DOCX files were linked on those pages")
    print("  2. Files were not downloaded (check logs)")
    print("  3. Files are in a different location")

print()
print("="*80)
print(f"FULL PATH: {actual_path}")
print("="*80)

