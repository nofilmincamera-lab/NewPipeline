"""
Domain Notifier - Sends notifications when domain scraping completes
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

import asyncpg
import httpx
from loguru import logger


class DomainNotifier:
    """Handle notifications when domain scraping completes."""
    
    def __init__(
        self,
        db_connection: asyncpg.Connection,
        webhook_url: Optional[str] = None,
        webhook_enabled: bool = True
    ):
        """
        Initialize domain notifier.
        
        Args:
            db_connection: Database connection
            webhook_url: Webhook URL for notifications (e.g., IFTTT, Zapier, Discord, etc.)
            webhook_enabled: Whether to enable webhook notifications
        """
        self.db = db_connection
        self.webhook_url = webhook_url
        self.webhook_enabled = webhook_enabled and bool(webhook_url)
    
    async def notify_domain_completion(
        self,
        domain: str,
        crawl_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process domain completion: quality check, file counts, and notification.
        
        Args:
            domain: Domain that was scraped
            crawl_results: Results from domain crawler
            
        Returns:
            Dictionary with notification results
        """
        logger.info(f"Processing completion notification for domain: {domain}")
        
        # Run quality checks
        quality_metrics = await self._run_quality_checks(domain)
        
        # Calculate file counts
        file_stats = await self._calculate_file_counts(domain)
        
        # Prepare notification payload
        notification_data = {
            'domain': domain,
            'timestamp': datetime.now().isoformat(),
            'crawl_summary': {
                'pages_crawled': crawl_results.get('pages_crawled', 0),
                'pages_failed': crawl_results.get('pages_failed', 0),
                'files_found': crawl_results.get('files_found', 0),
                'duration_seconds': crawl_results.get('duration_seconds', 0),
                'start_time': crawl_results.get('start_time').isoformat() if crawl_results.get('start_time') else None,
                'end_time': crawl_results.get('end_time').isoformat() if crawl_results.get('end_time') else None
            },
            'quality_metrics': quality_metrics,
            'file_statistics': file_stats
        }
        
        # Send webhook notification
        webhook_result = None
        if self.webhook_enabled:
            webhook_result = await self._send_webhook(notification_data)
        
        return {
            'success': True,
            'quality_metrics': quality_metrics,
            'file_statistics': file_stats,
            'webhook_sent': webhook_result is not None,
            'webhook_result': webhook_result
        }
    
    async def _run_quality_checks(self, domain: str) -> Dict[str, Any]:
        """
        Run quality checks on scraped content for a domain.
        
        Args:
            domain: Domain to check
            
        Returns:
            Dictionary with quality metrics
        """
        try:
            # Get all successfully scraped pages for this domain
            query = """
                SELECT 
                    COUNT(*) as total_pages,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_pages,
                    AVG(CASE WHEN success THEN response_time ELSE NULL END) as avg_response_time,
                    AVG(CASE WHEN success THEN (metadata->>'main_content_length')::int ELSE NULL END) as avg_content_length,
                    COUNT(DISTINCT content_hash) as unique_content_count,
                    SUM(CASE WHEN proxy_used THEN 1 ELSE 0 END) as proxy_used_count
                FROM scraped_sites
                WHERE domain = $1
                AND scraped_at > NOW() - INTERVAL '1 hour'
            """
            
            row = await self.db.fetchrow(query, domain)
            
            total_pages = row['total_pages'] or 0
            successful_pages = row['successful_pages'] or 0
            success_rate = (successful_pages / total_pages * 100) if total_pages > 0 else 0
            
            # Check for pages with very low content (possible errors)
            low_content_query = """
                SELECT COUNT(*) as low_content_count
                FROM scraped_sites
                WHERE domain = $1
                AND success = true
                AND scraped_at > NOW() - INTERVAL '1 hour'
                AND (metadata->>'main_content_length')::int < 100
            """
            low_content_row = await self.db.fetchrow(low_content_query, domain)
            low_content_count = low_content_row['low_content_count'] or 0
            
            # Check for duplicate content
            duplicate_query = """
                SELECT content_hash, COUNT(*) as count
                FROM scraped_sites
                WHERE domain = $1
                AND success = true
                AND scraped_at > NOW() - INTERVAL '1 hour'
                AND content_hash IS NOT NULL
                GROUP BY content_hash
                HAVING COUNT(*) > 1
                LIMIT 10
            """
            duplicate_rows = await self.db.fetch(duplicate_query, domain)
            duplicate_count = sum(row['count'] - 1 for row in duplicate_rows)
            
            # Calculate quality score (0-100)
            quality_score = 100.0
            if total_pages > 0:
                # Deduct for low success rate
                quality_score -= (100 - success_rate) * 0.5
                # Deduct for low content pages
                if successful_pages > 0:
                    low_content_ratio = (low_content_count / successful_pages) * 100
                    quality_score -= min(low_content_ratio * 0.3, 20)
                # Deduct for duplicates
                if successful_pages > 0:
                    duplicate_ratio = (duplicate_count / successful_pages) * 100
                    quality_score -= min(duplicate_ratio * 0.2, 15)
            
            quality_score = max(0, min(100, quality_score))
            
            return {
                'total_pages': total_pages,
                'successful_pages': successful_pages,
                'success_rate': round(success_rate, 2),
                'avg_response_time_ms': round(row['avg_response_time'] or 0, 2),
                'avg_content_length': int(row['avg_content_length'] or 0),
                'unique_content_count': row['unique_content_count'] or 0,
                'low_content_pages': low_content_count,
                'duplicate_content_count': duplicate_count,
                'proxy_used_count': row['proxy_used_count'] or 0,
                'quality_score': round(quality_score, 2),
                'quality_status': self._get_quality_status(quality_score)
            }
            
        except Exception as e:
            logger.error(f"Error running quality checks for {domain}: {e}")
            return {
                'error': str(e),
                'quality_score': 0,
                'quality_status': 'error'
            }
    
    def _get_quality_status(self, score: float) -> str:
        """Get quality status based on score."""
        if score >= 80:
            return 'excellent'
        elif score >= 60:
            return 'good'
        elif score >= 40:
            return 'fair'
        else:
            return 'poor'
    
    async def _calculate_file_counts(self, domain: str) -> Dict[str, Any]:
        """
        Calculate file statistics for a domain.
        
        Args:
            domain: Domain to check
            
        Returns:
            Dictionary with file statistics
        """
        try:
            # Get file counts by type and status
            query = """
                SELECT 
                    file_type,
                    download_status,
                    COUNT(*) as count,
                    SUM(file_size) as total_size
                FROM downloaded_files
                WHERE domain = $1
                AND downloaded_at > NOW() - INTERVAL '1 hour'
                GROUP BY file_type, download_status
            """
            
            rows = await self.db.fetch(query, domain)
            
            # Organize by file type
            file_stats = {
                'total_files': 0,
                'by_type': {},
                'by_status': {
                    'downloaded': 0,
                    'failed': 0,
                    'pending': 0
                },
                'total_size_bytes': 0,
                'total_size_mb': 0
            }
            
            for row in rows:
                file_type = row['file_type']
                status = row['download_status']
                count = row['count'] or 0
                size = row['total_size'] or 0
                
                file_stats['total_files'] += count
                file_stats['by_status'][status] = file_stats['by_status'].get(status, 0) + count
                file_stats['total_size_bytes'] += size
                
                if file_type not in file_stats['by_type']:
                    file_stats['by_type'][file_type] = {
                        'total': 0,
                        'downloaded': 0,
                        'failed': 0,
                        'pending': 0,
                        'size_bytes': 0
                    }
                
                file_stats['by_type'][file_type]['total'] += count
                file_stats['by_type'][file_type][status] += count
                file_stats['by_type'][file_type]['size_bytes'] += size
            
            file_stats['total_size_mb'] = round(file_stats['total_size_bytes'] / (1024 * 1024), 2)
            
            # Round size_bytes for each type
            for file_type in file_stats['by_type']:
                file_stats['by_type'][file_type]['size_mb'] = round(
                    file_stats['by_type'][file_type]['size_bytes'] / (1024 * 1024), 2
                )
            
            return file_stats
            
        except Exception as e:
            logger.error(f"Error calculating file counts for {domain}: {e}")
            return {
                'error': str(e),
                'total_files': 0
            }
    
    async def _send_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send webhook notification.
        
        Supports multiple webhook formats:
        - IFTTT: { "value1": "...", "value2": "...", "value3": "..." }
        - Discord: { "content": "..." }
        - Generic JSON: sends data as-is
        
        Args:
            data: Notification data to send
            
        Returns:
            Webhook response or None if failed
        """
        if not self.webhook_url:
            return None
        
        try:
            # Format message for mobile notification
            message = self._format_notification_message(data)
            
            # Try to detect webhook type and format accordingly
            webhook_type = self._detect_webhook_type(self.webhook_url)
            
            if webhook_type == 'ifttt':
                payload = {
                    'value1': f"Domain Scraped: {data['domain']}",
                    'value2': message,
                    'value3': f"Quality: {data['quality_metrics'].get('quality_status', 'unknown').upper()}"
                }
            elif webhook_type == 'discord':
                payload = {
                    'content': f"**Domain Scraping Complete**\n\n{message}"
                }
            elif webhook_type == 'webhooky':
                # Webhooky format - optimized for mobile push notifications
                quality = data['quality_metrics']
                files = data['file_statistics']
                payload = {
                    'title': f"✅ Domain Scraped: {data['domain']}",
                    'message': message,
                    'domain': data['domain'],
                    'pages_crawled': data['crawl_summary']['pages_crawled'],
                    'files_found': files.get('total_files', 0),
                    'quality_score': quality.get('quality_score', 0),
                    'quality_status': quality.get('quality_status', 'unknown'),
                    'duration_seconds': data['crawl_summary'].get('duration_seconds', 0)
                }
            else:
                # Generic JSON webhook
                payload = {
                    'event': 'domain_scraping_complete',
                    'message': message,
                    'data': data
                }
            
            # Send webhook
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                )
                response.raise_for_status()
                
                logger.info(f"Webhook notification sent successfully for {data['domain']}")
                return {
                    'success': True,
                    'status_code': response.status_code,
                    'response': response.text[:200]  # Truncate long responses
                }
                
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _format_notification_message(self, data: Dict[str, Any]) -> str:
        """Format notification message for mobile display."""
        domain = data['domain']
        crawl = data['crawl_summary']
        quality = data['quality_metrics']
        files = data['file_statistics']
        
        lines = [
            f"Domain: {domain}",
            f"Pages: {crawl['pages_crawled']} crawled, {crawl['pages_failed']} failed",
            f"Files: {files.get('total_files', 0)} total",
            f"Quality Score: {quality.get('quality_score', 0)}/100 ({quality.get('quality_status', 'unknown')})",
            f"Duration: {crawl.get('duration_seconds', 0):.1f}s"
        ]
        
        # Add file breakdown if available
        if files.get('by_type'):
            file_types = ', '.join([
                f"{ft}: {stats['downloaded']}" 
                for ft, stats in files['by_type'].items()
            ])
            if file_types:
                lines.append(f"Files by type: {file_types}")
        
        return '\n'.join(lines)
    
    def _detect_webhook_type(self, url: str) -> str:
        """Detect webhook type from URL."""
        url_lower = url.lower()
        if 'ifttt.com' in url_lower or 'maker.ifttt.com' in url_lower:
            return 'ifttt'
        elif 'discord.com' in url_lower or 'discordapp.com' in url_lower:
            return 'discord'
        elif 'webhookreceiver' in url_lower or 'webhooky' in url_lower:
            return 'webhooky'
        else:
            return 'generic'

