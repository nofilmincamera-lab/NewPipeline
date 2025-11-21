"""
Browser Fetcher - Use Playwright to fetch JavaScript-rendered content
"""

import asyncio
import time
from typing import Dict, Optional, Any, List
from urllib.parse import urlparse

from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

try:
    from playwright_stealth.stealth import async_api as stealth_async
    STEALTH_AVAILABLE = True
except (ImportError, AttributeError):
    STEALTH_AVAILABLE = False
    logger.warning("playwright-stealth not available, stealth mode disabled")


class BrowserFetcher:
    """Fetch pages using Playwright browser automation."""
    
    def __init__(
        self,
        config: Dict[str, Any],
        headless: bool = True,
        timeout: int = 30,
        wait_strategy: str = 'networkidle',
        wait_timeout: int = 10,
        enable_shadow_dom: bool = True,
        enable_iframe: bool = True
    ):
        """
        Initialize browser fetcher.
        
        Args:
            config: Configuration dictionary
            headless: Run browser in headless mode
            timeout: Page load timeout in seconds
            wait_strategy: Wait strategy ('networkidle', 'load', 'domcontentloaded')
            wait_timeout: Maximum wait time in seconds
            enable_shadow_dom: Enable shadow DOM extraction
            enable_iframe: Enable iframe extraction
        """
        self.config = config
        self.headless = headless
        self.timeout = timeout * 1000  # Convert to milliseconds
        self.wait_strategy = wait_strategy
        self.wait_timeout = wait_timeout * 1000
        self.enable_shadow_dom = enable_shadow_dom
        self.enable_iframe = enable_iframe
        
        # Browser instance (will be initialized on first use)
        self._browser: Optional[Browser] = None
        self._playwright = None
    
    async def _get_browser(self, proxy_url: Optional[str] = None) -> Browser:
        """Get or create browser instance."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            
            # Configure proxy if provided
            launch_options = {
                'headless': self.headless,
                'timeout': self.timeout
            }
            
            if proxy_url:
                # Parse proxy URL: http://user:pass@host:port
                parsed = urlparse(proxy_url)
                launch_options['proxy'] = {
                    'server': f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
                    'username': parsed.username if parsed.username else None,
                    'password': parsed.password if parsed.password else None
                }
            
            self._browser = await self._playwright.chromium.launch(**launch_options)
        
        return self._browser
    
    async def _create_context(self, proxy_url: Optional[str] = None) -> BrowserContext:
        """Create a new browser context."""
        browser = await self._get_browser(proxy_url)
        
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        context = await browser.new_context(**context_options)
        
        # Apply stealth mode if available
        if STEALTH_AVAILABLE:
            try:
                await stealth_async(context)
            except Exception as e:
                logger.debug(f"Could not apply stealth mode: {e}")
        
        return context
    
    async def _wait_for_content(self, page: Page) -> None:
        """Wait for page content to load based on wait strategy."""
        try:
            if self.wait_strategy == 'networkidle':
                await page.wait_for_load_state('networkidle', timeout=self.wait_timeout)
            elif self.wait_strategy == 'load':
                await page.wait_for_load_state('load', timeout=self.wait_timeout)
            elif self.wait_strategy == 'domcontentloaded':
                await page.wait_for_load_state('domcontentloaded', timeout=self.wait_timeout)
            else:
                # Default to networkidle
                await page.wait_for_load_state('networkidle', timeout=self.wait_timeout)
        except Exception as e:
            logger.warning(f"Wait strategy timeout: {e}, continuing anyway")
    
    async def _extract_shadow_dom(self, page: Page) -> str:
        """Extract content from shadow DOM elements."""
        if not self.enable_shadow_dom:
            return ""
        
        try:
            shadow_content = await page.evaluate("""
                () => {
                    function extractShadowContent(element) {
                        let text = '';
                        if (element.shadowRoot) {
                            const shadowText = element.shadowRoot.textContent || '';
                            text += shadowText + ' ';
                            
                            // Recursively check for nested shadow DOM
                            const shadowChildren = element.shadowRoot.querySelectorAll('*');
                            shadowChildren.forEach(child => {
                                text += extractShadowContent(child);
                            });
                        }
                        return text;
                    }
                    
                    let allText = '';
                    const allElements = document.querySelectorAll('*');
                    allElements.forEach(el => {
                        allText += extractShadowContent(el);
                    });
                    return allText;
                }
            """)
            return shadow_content if shadow_content else ""
        except Exception as e:
            logger.debug(f"Error extracting shadow DOM: {e}")
            return ""
    
    async def _extract_iframe_content(self, page: Page) -> str:
        """Recursively extract content from iframes."""
        if not self.enable_iframe:
            return ""
        
        iframe_content = []
        
        try:
            # Get all iframes
            iframes = await page.query_selector_all('iframe')
            
            for iframe in iframes:
                try:
                    # Try to get iframe content (may fail for cross-origin)
                    frame = await iframe.content_frame()
                    if frame:
                        # Extract text from iframe
                        iframe_text = await frame.evaluate("""
                            () => {
                                return document.body ? document.body.innerText : '';
                            }
                        """)
                        if iframe_text:
                            iframe_content.append(iframe_text)
                        
                        # Recursively check for nested iframes
                        nested_iframes = await frame.query_selector_all('iframe')
                        for nested_iframe in nested_iframes:
                            try:
                                nested_frame = await nested_iframe.content_frame()
                                if nested_frame:
                                    nested_text = await nested_frame.evaluate("""
                                        () => {
                                            return document.body ? document.body.innerText : '';
                                        }
                                    """)
                                    if nested_text:
                                        iframe_content.append(nested_text)
                            except Exception:
                                pass  # Cross-origin or other error
                except Exception as e:
                    logger.debug(f"Could not extract iframe content (may be cross-origin): {e}")
                    continue
            
            return ' '.join(iframe_content)
        except Exception as e:
            logger.debug(f"Error extracting iframe content: {e}")
            return ""
    
    async def _get_rendered_html(self, page: Page) -> str:
        """Get fully rendered HTML from page."""
        try:
            html = await page.content()
            return html
        except Exception as e:
            logger.error(f"Error getting rendered HTML: {e}")
            return ""
    
    async def fetch_with_browser(
        self,
        url: str,
        proxy_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch page using browser automation.
        
        Args:
            url: URL to fetch
            proxy_url: Optional proxy URL
            
        Returns:
            Dictionary with fetch results:
            {
                'success': bool,
                'url': str,
                'status_code': int,
                'content': str,
                'html_content': str,
                'headers': dict,
                'response_time': float,
                'error': str,
                'proxy_used': bool
            }
        """
        start_time = time.time()
        context = None
        page = None
        
        try:
            # Create browser context
            context = await self._create_context(proxy_url)
            page = await context.new_page()
            
            # Navigate to URL
            response = await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
            
            # Wait for content based on strategy
            await self._wait_for_content(page)
            
            # Get status code
            status_code = response.status if response else 200
            
            # Get rendered HTML
            html_content = await self._get_rendered_html(page)
            
            # Extract text content
            text_content = await page.evaluate("""
                () => {
                    return document.body ? document.body.innerText : '';
                }
            """)
            
            # Extract shadow DOM content
            shadow_content = await self._extract_shadow_dom(page)
            if shadow_content:
                text_content += ' ' + shadow_content
            
            # Extract iframe content
            iframe_content = await self._extract_iframe_content(page)
            if iframe_content:
                text_content += ' ' + iframe_content
            
            # Get response headers
            headers = {}
            if response:
                headers = response.headers
            
            response_time = time.time() - start_time
            
            return {
                'success': True,
                'url': page.url,
                'status_code': status_code,
                'content': text_content,
                'html_content': html_content,
                'headers': headers,
                'response_time': response_time,
                'error': None,
                'proxy_used': proxy_url is not None
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Browser fetch failed for {url}: {error_msg}")
            response_time = time.time() - start_time
            
            return {
                'success': False,
                'url': url,
                'status_code': None,
                'content': None,
                'html_content': None,
                'headers': {},
                'response_time': response_time,
                'error': error_msg,
                'proxy_used': proxy_url is not None
            }
            
        finally:
            # Clean up
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
    
    async def close(self):
        """Close browser and cleanup resources."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

