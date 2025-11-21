"""
Boilerplate Detection - Identify and filter headers, footers, and navigation
"""

import re
import asyncio
from typing import Dict, Set, Optional, Any
from bs4 import BeautifulSoup, Tag


class BoilerplateDetector:
    """Detect and filter boilerplate content (headers, footers, navigation)."""
    
    # Common header/footer/nav class/id patterns
    BOILERPLATE_PATTERNS = {
        'header': [
            r'header', r'head', r'topbar', r'top-bar', r'topnav', r'top-nav',
            r'navbar', r'nav-bar', r'menu', r'nav', r'breadcrumb', r'breadcrumbs',
            r'site-header', r'main-header', r'page-header'
        ],
        'footer': [
            r'footer', r'foot', r'bottom', r'site-footer', r'main-footer',
            r'page-footer', r'copyright', r'legal', r'terms'
        ],
        'navigation': [
            r'nav', r'navigation', r'menu', r'sidebar', r'side-bar', r'widget',
            r'aside', r'related', r'related-posts', r'related-articles'
        ],
        'advertisement': [
            r'ad', r'ads', r'advertisement', r'advert', r'sponsor', r'sponsored',
            r'promo', r'promotion', r'banner'
        ],
        'social': [
            r'social', r'share', r'sharing', r'facebook', r'twitter', r'linkedin',
        ]
    }
    
    # Tags that are typically boilerplate
    BOILERPLATE_TAGS = {'header', 'footer', 'nav', 'aside'}
    
    def __init__(self):
        """Initialize boilerplate detector."""
        self.compiled_patterns = {}
        for category, patterns in self.BOILERPLATE_PATTERNS.items():
            self.compiled_patterns[category] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
    
    def is_boilerplate(self, element: Tag) -> bool:
        """
        Check if an element is likely boilerplate.
        
        Args:
            element: BeautifulSoup Tag element
            
        Returns:
            True if element appears to be boilerplate
        """
        if element is None:
            return False
        
        # Check if it's a Tag (not NavigableString or other types)
        if not hasattr(element, 'name') or element.name is None:
            return False
        
        # Check tag name
        if element.name in self.BOILERPLATE_TAGS:
            return True
        
        # Check class and id attributes
        try:
            class_list = element.get('class', [])
            class_attr = ' '.join(class_list) if isinstance(class_list, list) else str(class_list)
            id_attr = element.get('id', '') or ''
        except (AttributeError, TypeError):
            class_attr = ''
            id_attr = ''
        
        combined_attr = f"{class_attr} {id_attr}".lower()
        
        # Check against patterns
        for category, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(combined_attr):
                    return True
        
        return False
    
    def remove_boilerplate(self, html_content: str) -> str:
        """
        Remove boilerplate elements from HTML.
        
        Args:
            html_content: HTML content to clean
            
        Returns:
            Cleaned HTML content
        """
        try:
            soup = BeautifulSoup(html_content, 'lxml')
        except Exception:
            soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove boilerplate elements
        removed_count = 0
        for element in soup.find_all():
            if element and hasattr(element, 'name') and self.is_boilerplate(element):
                element.decompose()
                removed_count += 1
        
        logger.debug(f"Removed {removed_count} boilerplate elements")
        
        return str(soup)
    
    def extract_main_content(self, html_content: str) -> str:
        """
        Extract main content, removing boilerplate.
        
        Args:
            html_content: HTML content
            
        Returns:
            Main content text
        """
        try:
            soup = BeautifulSoup(html_content, 'lxml')
        except Exception:
            soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try to find main content areas
        main_content = None
        
        # Look for common main content selectors (enhanced for modern frameworks)
        main_selectors = [
            'main', 'article', '[role="main"]', '.content', '#content',
            '.main-content', '#main-content', '.post', '.entry',
            '.article-content', '.page-content',
            # Modern framework patterns
            '[data-content]', '.documentation', '.docs-content',
            '.page-body', '.page-main', '.main-body',
            '.content-wrapper', '.content-area', '.content-main',
            # Documentation sites
            '.doc-content', '.documentation-content', '.doc-body',
            '.markdown-body', '.markdown-content'
        ]
        
        for selector in main_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # If no main content found, use body and remove boilerplate
        if not main_content:
            main_content = soup.find('body')
            if main_content:
                # Remove known boilerplate
                for element in main_content.find_all(['header', 'footer', 'nav', 'aside']):
                    element.decompose()
        
        if main_content:
            # Remove remaining boilerplate
            for element in main_content.find_all():
                if element and hasattr(element, 'name') and self.is_boilerplate(element):
                    element.decompose()
            
            return main_content.get_text(separator=' ', strip=True)
        
        # Fallback: return all text
        return soup.get_text(separator=' ', strip=True)
    
    def extract_main_content_from_rendered(
        self,
        html_content: str,
        page: Optional[Any] = None
    ) -> str:
        """
        Extract main content from rendered HTML (including shadow DOM and iframes).
        
        Args:
            html_content: Rendered HTML content
            page: Optional Playwright page object for advanced extraction
            
        Returns:
            Main content text
        """
        # First try standard extraction
        content = self.extract_main_content(html_content)
        
        # If we have a page object, try to extract additional content
        # Note: This requires async context, so we'll handle it in the caller if needed
        # For now, just use the standard extraction
        if page is not None:
            logger.debug("Page object provided but async extraction not implemented in sync context")
        
        return content
    
    async def _extract_from_page(self, page: Any) -> str:
        """Extract content from Playwright page object."""
        try:
            # Try to find main content element
            content_selectors = [
                'main', 'article', '[role="main"]',
                '.content', '#content', '.main-content',
                '.documentation', '.docs-content', '.doc-content'
            ]
            
            for selector in content_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.inner_text()
                        if text and len(text.strip()) > 100:
                            return text.strip()
                except Exception:
                    continue
            
            # Fallback to body
            body = await page.query_selector('body')
            if body:
                return await body.inner_text()
            
            return ""
        except Exception as e:
            logger.debug(f"Error extracting from page: {e}")
            return ""
    
    def get_content_ratio(self, html_content: str) -> float:
        """
        Calculate ratio of main content to total content.
        
        Args:
            html_content: HTML content
            
        Returns:
            Ratio (0.0 to 1.0) of main content
        """
        try:
            soup = BeautifulSoup(html_content, 'lxml')
        except Exception:
            soup = BeautifulSoup(html_content, 'html.parser')
        
        total_text = len(soup.get_text())
        if total_text == 0:
            return 0.0
        
        main_content = self.extract_main_content(html_content)
        main_text = len(main_content)
        
        return main_text / total_text if total_text > 0 else 0.0


# Import logger
from loguru import logger

