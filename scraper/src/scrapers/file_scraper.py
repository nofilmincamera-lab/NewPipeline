"""
File Scraper - Integrate file downloading into scraping workflow
"""

import asyncio
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from uuid import uuid4
from datetime import datetime

import asyncpg
from curl_cffi import requests
from loguru import logger

from ..parsers.link_extractor import LinkExtractor
from ..downloaders.file_downloader import FileDownloader
from ..models.downloaded_file import DownloadedFile, DownloadedFileDB


class FileScraper:
    """Handle file downloading as part of scraping workflow."""
    
    def __init__(
        self,
        db_connection: asyncpg.Connection,
        storage_path: str,
        config: Dict[str, Any]
    ):
        """
        Initialize file scraper.
        
        Args:
            db_connection: Database connection
            storage_path: Base path for file storage
            config: Configuration dictionary
        """
        self.db = DownloadedFileDB(db_connection)
        self.storage_path = storage_path
        
        file_config = config.get('file_download', {})
        self.enabled = file_config.get('enabled', True)
        self.file_types = file_config.get('file_types', ['pdf', 'doc', 'docx'])
        self.max_file_size = file_config.get('max_file_size', 52428800)
        self.enable_deduplication = file_config.get('enable_deduplication', True)
        self.download_direct_urls_only = file_config.get('download_direct_urls_only', True)
        
        self.downloader = FileDownloader(
            storage_path=storage_path,
            max_file_size=self.max_file_size,
            retry_attempts=config.get('max_retries', 3),
            retry_delays=config.get('retry_delays', [5, 15, 45])
        )
    
    async def process_page_for_files(
        self,
        page_url: str,
        html_content: str,
        session: Optional[requests.Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract and download files from a scraped page.
        
        Args:
            page_url: URL of the page being scraped
            html_content: HTML content of the page
            session: Optional requests session
            
        Returns:
            List of download results
        """
        if not self.enabled:
            return []
        
        results = []
        
        try:
            # Extract file links
            extractor = LinkExtractor(page_url, file_types=self.file_types)
            file_urls = extractor.extract_file_links(html_content)
            
            logger.info(f"Found {len(file_urls)} file links on {page_url}")
            
            # Process each file URL
            for file_url in file_urls:
                try:
                    result = await self._process_file_url(
                        file_url=file_url,
                        source_url=page_url,
                        session=session
                    )
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error processing file {file_url}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error extracting files from {page_url}: {e}")
        
        return results
    
    async def _process_file_url(
        self,
        file_url: str,
        source_url: str,
        session: Optional[requests.Session] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single file URL: check if exists, download if needed.
        
        Args:
            file_url: URL of file to download
            source_url: URL where file was found
            session: Optional requests session
            
        Returns:
            Dictionary with processing result or None
        """
        parsed_url = urlparse(file_url)
        domain = parsed_url.netloc
        file_type = self._get_file_type(file_url)
        
        if not file_type:
            logger.warning(f"Unknown file type for {file_url}")
            return None
        
        # Check if file URL already exists
        existing_id = await self.db.check_file_exists(file_url)
        if existing_id:
            logger.info(f"File {file_url} already in database (ID: {existing_id})")
            return {
                'file_url': file_url,
                'status': 'exists',
                'file_id': existing_id
            }
        
        # Create file record
        original_filename = self._extract_filename(file_url)
        file_uuid = uuid4()
        stored_filename = f"{file_uuid}{self._get_extension(file_type)}"
        
        # Generate expected file path
        date_str = datetime.now().strftime('%Y-%m-%d')
        expected_path = f"{file_type}/{domain}/{date_str}/{stored_filename}"
        
        file_data = DownloadedFile(
            source_url=source_url,
            file_url=file_url,
            domain=domain,
            file_type=file_type,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=expected_path,
            download_status='pending',
            parent_page_url=source_url
        )
        
        # Insert record
        file_id = await self.db.create_file_record(file_data)
        logger.info(f"Created file record (ID: {file_id}) for {file_url}")
        
        # Download file (modify downloader to use our filename)
        # We need to pass the stored_filename to the downloader
        download_result = await asyncio.to_thread(
            self._download_with_filename,
            file_url, file_type, domain, stored_filename, session
        )
        
        # Update record with download results
        if download_result['success']:
            # Check for duplicate hash if deduplication enabled
            if self.enable_deduplication and download_result['file_hash']:
                duplicate_id = await self.db.check_hash_exists(download_result['file_hash'])
                if duplicate_id and duplicate_id != file_id:
                    logger.info(f"Duplicate file detected (hash: {download_result['file_hash'][:16]}...), existing ID: {duplicate_id}")
                    # Mark as duplicate in metadata
                    metadata = {'duplicate_of': duplicate_id}
                    await self.db.conn.execute(
                        "UPDATE downloaded_files SET metadata = $1 WHERE id = $2",
                        metadata, file_id
                    )
            
            await self.db.update_file_record(
                file_id=file_id,
                download_status='downloaded',
                file_size=download_result['file_size'],
                file_hash=download_result['file_hash'],
                content_type=download_result['content_type'],
                downloaded_at=datetime.now()
            )
            
            logger.info(f"Successfully downloaded {file_url} (ID: {file_id})")
            
            return {
                'file_url': file_url,
                'status': 'downloaded',
                'file_id': file_id,
                'file_path': updated_path,
                'file_size': download_result['file_size'],
                'file_hash': download_result['file_hash']
            }
        else:
            # Update with error
            await self.db.update_file_record(
                file_id=file_id,
                download_status='failed',
                download_error=download_result['error']
            )
            
            logger.error(f"Failed to download {file_url}: {download_result['error']}")
            
            return {
                'file_url': file_url,
                'status': 'failed',
                'file_id': file_id,
                'error': download_result['error']
            }
    
    def _get_file_type(self, url: str) -> Optional[str]:
        """Get file type from URL."""
        url_lower = url.lower()
        if url_lower.endswith('.pdf'):
            return 'pdf'
        elif url_lower.endswith('.docx'):
            return 'docx'
        elif url_lower.endswith('.doc'):
            return 'doc'
        return None
    
    def _get_extension(self, file_type: str) -> str:
        """Get file extension for file type."""
        return f".{file_type}"
    
    def _extract_filename(self, url: str) -> str:
        """Extract filename from URL."""
        from urllib.parse import urlparse
        import os
        parsed = urlparse(url)
        path = parsed.path
        filename = os.path.basename(path)
        if '?' in filename:
            filename = filename.split('?')[0]
        return filename or "file"
    
    def _download_with_filename(
        self,
        file_url: str,
        file_type: str,
        domain: str,
        stored_filename: str,
        session: Optional[requests.Session] = None
    ) -> Dict[str, Any]:
        """Download file with specific filename."""
        # Temporarily modify downloader to use our filename
        # We'll need to update the downloader or handle this differently
        result = self.downloader.download_file(
            file_url=file_url,
            file_type=file_type,
            domain=domain,
            session=session
        )
        
        # Rename file to use UUID if download was successful
        if result['success'] and result['file_path']:
            from pathlib import Path
            old_path = self.storage_path / result['file_path']
            if old_path.exists():
                # Extract directory from old path
                new_path = old_path.parent / stored_filename
                old_path.rename(new_path)
                # Update result with new path
                result['file_path'] = str(new_path.relative_to(self.storage_path))
                result['stored_filename'] = stored_filename
        
        return result

