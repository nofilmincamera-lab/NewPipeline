"""
Domain Boundary Checker - Validate URLs stay within domain boundaries
"""

from urllib.parse import urlparse
from typing import Set, Optional, List
import re


class DomainBoundaryChecker:
    """Check if URLs are within allowed domain boundaries"""
    
    def __init__(
        self,
        base_domain: str,
        allow_subdomains: bool = True,
        allow_derivatives: bool = True,
        allow_file_downloads: bool = True
    ):
        """
        Initialize domain boundary checker.
        
        Args:
            base_domain: Base domain (e.g., 'worldline.com')
            allow_subdomains: Allow subdomains (e.g., blog.worldline.com)
            allow_derivatives: Allow derivative domains (e.g., worldline-solutions.com)
            allow_file_downloads: Allow direct file downloads from any domain
        """
        self.base_domain = self._normalize_domain(base_domain)
        self.allow_subdomains = allow_subdomains
        self.allow_derivatives = allow_derivatives
        self.allow_file_downloads = allow_file_downloads
        
        # Extract root domain parts
        parts = self.base_domain.split('.')
        if len(parts) >= 2:
            self.root_domain = '.'.join(parts[-2:])  # e.g., 'worldline.com'
            self.company_name = parts[-2]  # e.g., 'worldline'
        else:
            self.root_domain = self.base_domain
            self.company_name = self.base_domain
    
    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain name."""
        # Remove protocol if present
        domain = re.sub(r'^https?://', '', domain)
        # Remove trailing slash
        domain = domain.rstrip('/')
        # Remove www. prefix for matching
        domain = re.sub(r'^www\.', '', domain)
        # Extract just the domain part
        parsed = urlparse(f'http://{domain}')
        return parsed.netloc.lower()
    
    def is_within_boundary(self, url: str) -> bool:
        """
        Check if URL is within allowed boundaries.
        
        Args:
            url: URL to check
            
        Returns:
            True if within boundary, False otherwise
        """
        try:
            parsed = urlparse(url)
            url_domain = parsed.netloc.lower()
            
            # Allow direct file downloads
            if self.allow_file_downloads and self._is_file_url(url):
                return True
            
            # Check exact match
            if url_domain == self.base_domain or url_domain == f'www.{self.base_domain}':
                return True
            
            # Check subdomain
            if self.allow_subdomains:
                if url_domain.endswith(f'.{self.base_domain}') or \
                   url_domain.endswith(f'.www.{self.base_domain}'):
                    return True
            
            # Check derivative domains
            if self.allow_derivatives:
                # Match patterns like worldline-solutions.com, worldline-solutions.eu, etc.
                if self.company_name in url_domain:
                    # Check if it's a legitimate derivative (not a completely different site)
                    # e.g., worldline-solutions.com, worldline.com.de
                    derivative_patterns = [
                        rf'^{re.escape(self.company_name)}[-.].*\.',
                        rf'.*[-.]{re.escape(self.company_name)}[-.]',
                        rf'{re.escape(self.company_name)}\..*\.',
                    ]
                    for pattern in derivative_patterns:
                        if re.search(pattern, url_domain):
                            return True
            
            return False
            
        except Exception:
            return False
    
    def _is_file_url(self, url: str) -> bool:
        """Check if URL points to a file download."""
        file_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                          '.zip', '.txt', '.csv', '.json', '.xml']
        url_lower = url.lower()
        return any(url_lower.endswith(ext) for ext in file_extensions)
    
    def extract_base_domain_from_url(self, url: str) -> str:
        """Extract base domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            domain = re.sub(r'^www\.', '', domain)
            return domain
        except Exception:
            return ""


def load_domain_list(file_path: str) -> List[str]:
    """
    Load domain list from file (comments and blank lines ignored).
    
    Args:
        file_path: Path to domain list file
        
    Returns:
        List of domain URLs
    """
    domains = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and blank lines
                if line and not line.startswith('#'):
                    # Ensure it has protocol
                    if not line.startswith('http://') and not line.startswith('https://'):
                        line = f'https://{line}'
                    domains.append(line)
        return domains
    except Exception as e:
        raise Exception(f"Error loading domain list: {e}")

