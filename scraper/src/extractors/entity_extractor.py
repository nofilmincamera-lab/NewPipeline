"""
Extract organization facts from scraped content.
"""

import re
from typing import Dict, List, Optional, Set, Any
from bs4 import BeautifulSoup
from loguru import logger


class EntityExtractor:
    """Extract organization facts from HTML content."""
    
    def __init__(self, conn=None):
        """
        Initialize entity extractor.
        
        Args:
            conn: Optional database connection for reference lookups
        """
        self.conn = conn
        self.certification_patterns = [
            r'\b(ISO\s*\d{4,5})\b',
            r'\b(SOC\s*[12])\b',
            r'\b(HIPAA)\b',
            r'\b(PCI\s*DSS)\b',
            r'\b(GDPR)\b',
            r'\b(COPC)\b',
            r'\b(CMMI)\b',
            r'\b(PCI\s*SSC)\b'
        ]
        
        self.award_issuers = [
            'Gartner', 'Forrester', 'Stevie', 'Webby', 'Effie',
            'J.D. Power', 'G2', 'Capterra', 'TrustRadius'
        ]
        
        self.b2b_indicators = [
            r'\benterprise\b', r'\bb2b\b', r'\bbusiness[-\s]to[-\s]business\b',
            r'\bcorporate\b', r'\bclients?\b', r'\bpartners?\b'
        ]
        
        self.b2c_indicators = [
            r'\bconsumer\b', r'\bb2c\b', r'\bbusiness[-\s]to[-\s]consumer\b',
            r'\bcustomers?\b', r'\bend[-\s]users?\b'
        ]
    
    def extract_certifications(self, text: str) -> List[str]:
        """Extract certification mentions from text."""
        certifications = set()
        text_upper = text.upper()
        
        for pattern in self.certification_patterns:
            matches = re.findall(pattern, text_upper, re.IGNORECASE)
            for match in matches:
                certifications.add(match.strip())
        
        return list(certifications)
    
    def extract_awards(self, text: str) -> List[Dict[str, str]]:
        """Extract award mentions from text."""
        awards = []
        text_lower = text.lower()
        
        for issuer in self.award_issuers:
            # Look for patterns like "Gartner Magic Quadrant", "Stevie Award", etc.
            patterns = [
                rf'\b{re.escape(issuer.lower())}\s+([^.!?]+?)(?:award|winner|leader|recognized)',
                rf'(?:won|received|awarded)\s+.*?\b{re.escape(issuer.lower())}',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    award_name = match.strip() if isinstance(match, str) else issuer
                    awards.append({
                        'award_name': f"{issuer} {award_name}",
                        'award_issuer': issuer
                    })
        
        return awards
    
    def extract_countries(self, text: str) -> List[str]:
        """Extract country mentions (basic implementation)."""
        # This is a simplified version - could be enhanced with NER
        countries = set()
        
        # Common country patterns
        country_patterns = [
            r'\b(United States|USA|U\.S\.|U\.S\.A\.)\b',
            r'\b(United Kingdom|UK|U\.K\.)\b',
            r'\b(India|Philippines|Mexico|Brazil|Canada|Australia)\b',
        ]
        
        for pattern in country_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                countries.add(match)
        
        return list(countries)
    
    def determine_customer_segment(self, text: str) -> Optional[str]:
        """
        Determine if organization is B2B, B2C, or Both based on content.
        
        Returns:
            'B2B', 'B2C', 'Both', or None
        """
        text_lower = text.lower()
        
        b2b_count = sum(1 for pattern in self.b2b_indicators if re.search(pattern, text_lower))
        b2c_count = sum(1 for pattern in self.b2c_indicators if re.search(pattern, text_lower))
        
        if b2b_count > 0 and b2c_count > 0:
            return 'Both'
        elif b2b_count > 0:
            return 'B2B'
        elif b2c_count > 0:
            return 'B2C'
        
        return None
    
    def extract_facts_from_html(
        self,
        html_content: str,
        url: str
    ) -> Dict[str, Any]:
        """
        Extract organization facts from HTML content.
        
        Returns:
            Dictionary with extracted facts
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Get text content
        text = soup.get_text(separator=' ', strip=True)
        
        facts = {
            'certifications': self.extract_certifications(text),
            'awards': self.extract_awards(text),
            'countries': self.extract_countries(text),
            'customer_segment': self.determine_customer_segment(text),
            'products': [],  # Would need NER or heuristics matching
            'services': [],  # Would need taxonomy matching
            'platforms': []  # Would need tech term matching
        }
        
        return facts


async def extract_and_store_organization_facts(
    conn,
    domain: str,
    url: str,
    html_content: str,
    scraped_site_id: Optional[int] = None
):
    """
    Extract organization facts from scraped content and store in database.
    
    Args:
        conn: Database connection
        domain: Organization domain
        url: Source URL
        html_content: HTML content
        scraped_site_id: ID of scraped_sites record
    """
    try:
        from ..models.organization import OrganizationDB
        org_db = OrganizationDB(conn)
        
        # Ensure organization exists
        org = await org_db.get_organization_by_domain(domain)
        if not org:
            from ..utils.auto_create_organization import auto_create_organization_from_domain
            org_id = await auto_create_organization_from_domain(conn, domain)
        else:
            org_id = org['id']
        
        # Extract facts
        extractor = EntityExtractor(conn)
        facts = extractor.extract_facts_from_html(html_content, url)
        
        # Store certifications
        for cert_name in facts['certifications']:
            cert_type = 'Security' if any(x in cert_name.upper() for x in ['ISO', 'SOC', 'HIPAA', 'PCI']) else 'Quality'
            await org_db.upsert_certification(
                org_id, cert_name, cert_type, url, scraped_site_id
            )
        
        # Store awards
        for award in facts['awards']:
            await org_db.upsert_award(
                org_id,
                award['award_name'],
                award.get('award_issuer'),
                None,  # year
                None,  # category
                url,
                scraped_site_id
            )
        
        # Store operating markets
        for country in facts['countries']:
            # Map country name to code (simplified)
            country_code_map = {
                'United States': 'US', 'USA': 'US', 'U.S.': 'US', 'U.S.A.': 'US',
                'United Kingdom': 'GB', 'UK': 'GB', 'U.K.': 'GB',
                'India': 'IN', 'Philippines': 'PH', 'Mexico': 'MX',
                'Brazil': 'BR', 'Canada': 'CA', 'Australia': 'AU'
            }
            country_code = country_code_map.get(country, country[:2].upper())
            
            await org_db.upsert_operating_market(
                org_id, country_code, country, None, None, url, scraped_site_id
            )
        
        # Update customer segment if determined
        if facts['customer_segment']:
            await org_db.update_organization(
                org_id,
                customer_segment=facts['customer_segment']
            )
        
        logger.debug(f"Extracted and stored facts for {domain} from {url}")
    
    except Exception as e:
        logger.error(f"Error extracting facts for {domain}: {e}")

