"""
Link Extractor - Extract PDF/DOC file links from HTML content
"""

import re
from typing import List, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class LinkExtractor:
    """Extract direct file URLs (PDF, DOC, DOCX) from HTML content."""
    
    # File extensions to look for
    FILE_EXTENSIONS = {'.pdf', '.doc', '.docx'}
    
    # Content types that indicate file downloads
    FILE_CONTENT_TYPES = {
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    
    def __init__(self, base_url: str, file_types: List[str] = None):
        """
        Initialize link extractor.
        
        Args:
            base_url: Base URL of the page being parsed
            file_types: List of file types to extract (default: ['pdf', 'doc', 'docx'])
        """
        self.base_url = base_url
        self.parsed_base = urlparse(base_url)
        self.file_types = file_types or ['pdf', 'doc', 'docx']
        self.file_extensions = {f'.{ft}' for ft in self.file_types}
    
    def extract_file_links(self, html_content: str) -> Set[str]:
        """
        Extract all direct file URLs from HTML content.
        
        Args:
            html_content: HTML content to parse
            
        Returns:
            Set of absolute file URLs
        """
        file_urls = set()
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
        except Exception:
            # Fallback to html.parser if lxml fails
            soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract from <a> tags with href attributes
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not href:
                continue
            
            # Check if it's a direct file URL
            file_url = self._normalize_url(href)
            if file_url and self._is_direct_file_url(file_url):
                file_urls.add(file_url)
        
        # Also check for direct links in text content (less common but possible)
        # Look for URLs ending with file extensions
        text_urls = re.findall(
            r'https?://[^\s<>"{}|\\^`\[\]]+\.(?:pdf|doc|docx)(?:\?[^\s<>"{}|\\^`\[\]]*)?',
            html_content,
            re.IGNORECASE
        )
        for url in text_urls:
            if self._is_direct_file_url(url):
                file_urls.add(url)
        
        return file_urls
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL to absolute form.
        
        Args:
            url: URL to normalize (can be relative or absolute)
            
        Returns:
            Absolute URL or None if invalid
        """
        if not url:
            return None
        
        # Remove fragments
        url = url.split('#')[0]
        
        # Skip javascript:, mailto:, tel:, etc.
        if ':' in url and not url.startswith(('http://', 'https://')):
            return None
        
        # Convert relative URLs to absolute
        try:
            absolute_url = urljoin(self.base_url, url)
            parsed = urlparse(absolute_url)
            
            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return None
            
            return absolute_url
        except Exception:
            return None
    
    def _is_direct_file_url(self, url: str) -> bool:
        """
        Check if URL is a direct file URL (not a page that might contain files).
        
        Args:
            url: URL to check
            
        Returns:
            True if URL points directly to a file
        """
        if not url:
            return False
        
        parsed = urlparse(url.lower())
        path = parsed.path
        
        # Check if path ends with file extension
        for ext in self.file_extensions:
            if path.endswith(ext):
                # Additional check: ensure it's not a page that serves files
                # (e.g., /download.php?file=something.pdf)
                # We want direct URLs like /documents/file.pdf
                if ext in path.lower():
                    return True
        
        return False
    
    def get_file_type(self, url: str) -> str:
        """
        Determine file type from URL.
        
        Args:
            url: File URL
            
        Returns:
            File type ('pdf', 'doc', or 'docx')
        """
        url_lower = url.lower()
        if url_lower.endswith('.pdf'):
            return 'pdf'
        elif url_lower.endswith('.docx'):
            return 'docx'
        elif url_lower.endswith('.doc'):
            return 'doc'
        else:
            # Try to infer from content-type if available
            return None

