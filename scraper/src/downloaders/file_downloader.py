"""
File Downloader - Download PDF/DOC files with retry logic and deduplication
"""

import hashlib
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from datetime import datetime

from curl_cffi import requests
from loguru import logger


class FileDownloader:
    """Download files with retry logic, hash calculation, and deduplication."""
    
    def __init__(
        self,
        storage_path: str,
        max_file_size: int = 52428800,  # 50MB
        retry_attempts: int = 3,
        retry_delays: list = None,
        timeout: int = 60
    ):
        """
        Initialize file downloader.
        
        Args:
            storage_path: Base path for storing files
            max_file_size: Maximum file size in bytes
            retry_attempts: Number of retry attempts
            retry_delays: List of delay seconds between retries
            timeout: Request timeout in seconds
        """
        self.storage_path = Path(storage_path)
        self.max_file_size = max_file_size
        self.retry_attempts = retry_attempts
        self.retry_delays = retry_delays or [5, 15, 45]
        self.timeout = timeout
        
        # Ensure storage directories exist
        self._ensure_storage_dirs()
    
    def _ensure_storage_dirs(self):
        """Create storage directory structure if it doesn't exist."""
        for file_type in ['pdf', 'doc', 'docx']:
            (self.storage_path / file_type).mkdir(parents=True, exist_ok=True)
    
    def download_file(
        self,
        file_url: str,
        file_type: str,
        domain: str,
        session: Optional[requests.Session] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Download a file with retry logic.
        
        Args:
            file_url: URL of the file to download
            file_type: Type of file ('pdf', 'doc', or 'docx')
            domain: Domain name for organizing files
            session: Optional requests session (for connection pooling)
            headers: Optional custom headers
            
        Returns:
            Dictionary with download results:
            {
                'success': bool,
                'file_path': str,
                'stored_filename': str,
                'file_size': int,
                'file_hash': str,
                'content_type': str,
                'error': str
            }
        """
        if session is None:
            session = requests.Session()
        
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        if headers:
            default_headers.update(headers)
        
        # Generate storage path
        date_str = datetime.now().strftime('%Y-%m-%d')
        domain_dir = self.storage_path / file_type / domain / date_str
        domain_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename using UUID
        from uuid import uuid4
        original_filename = self._extract_filename(file_url)
        file_uuid = uuid4()
        file_ext = self._get_extension(file_type)
        stored_filename = f"{file_uuid}{file_ext}"
        
        file_path = domain_dir / stored_filename
        
        # Download with retry logic
        last_error = None
        for attempt in range(self.retry_attempts):
            try:
                logger.info(f"Downloading {file_url} (attempt {attempt + 1}/{self.retry_attempts})")
                
                response = session.get(
                    file_url,
                    headers=default_headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=True
                )
                response.raise_for_status()
                
                # Check content type
                content_type = response.headers.get('Content-Type', '').lower()
                if not self._is_valid_file_type(content_type, file_type):
                    logger.warning(f"Unexpected content type {content_type} for {file_url}")
                
                # Check file size
                content_length = response.headers.get('Content-Length')
                if content_length:
                    file_size = int(content_length)
                    if file_size > self.max_file_size:
                        error_msg = f"File too large: {file_size} bytes (max: {self.max_file_size})"
                        logger.error(error_msg)
                        return {
                            'success': False,
                            'error': error_msg,
                            'file_path': None,
                            'stored_filename': None,
                            'file_size': None,
                            'file_hash': None,
                            'content_type': content_type
                        }
                
                # Download file
                file_size = 0
                hasher = hashlib.sha256()
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            file_size += len(chunk)
                            hasher.update(chunk)
                            
                            # Check size during download
                            if file_size > self.max_file_size:
                                file_path.unlink()  # Delete partial file
                                error_msg = f"File too large: {file_size} bytes (max: {self.max_file_size})"
                                logger.error(error_msg)
                                return {
                                    'success': False,
                                    'error': error_msg,
                                    'file_path': None,
                                    'stored_filename': None,
                                    'file_size': None,
                                    'file_hash': None,
                                    'content_type': content_type
                                }
                
                file_hash = hasher.hexdigest()
                
                # Get relative path from storage root
                relative_path = str(file_path.relative_to(self.storage_path))
                
                logger.info(f"Successfully downloaded {file_url} ({file_size} bytes, hash: {file_hash[:16]}...)")
                
                return {
                    'success': True,
                    'file_path': relative_path,
                    'stored_filename': stored_filename,
                    'file_size': file_size,
                    'file_hash': file_hash,
                    'content_type': content_type,
                    'error': None
                }
                
            except requests.RequestException as e:
                last_error = str(e)
                logger.warning(f"Download attempt {attempt + 1} failed: {last_error}")
                
                if attempt < self.retry_attempts - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"All download attempts failed for {file_url}")
        
        # Clean up partial file if it exists
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass
        
        return {
            'success': False,
            'error': last_error or "Unknown error",
            'file_path': None,
            'stored_filename': None,
            'file_size': None,
            'file_hash': None,
            'content_type': None
        }
    
    def _extract_filename(self, url: str) -> str:
        """Extract filename from URL."""
        parsed = urlparse(url)
        path = parsed.path
        filename = os.path.basename(path)
        
        # Remove query parameters from filename
        if '?' in filename:
            filename = filename.split('?')[0]
        
        # If no filename, generate one
        if not filename or '.' not in filename:
            filename = "file"
        
        return filename
    
    def _get_extension(self, file_type: str) -> str:
        """Get file extension for file type."""
        return f".{file_type}"
    
    def _is_valid_file_type(self, content_type: str, expected_type: str) -> bool:
        """Check if content type matches expected file type."""
        content_type_lower = content_type.lower()
        
        type_mapping = {
            'pdf': ['application/pdf'],
            'doc': ['application/msword'],
            'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        }
        
        valid_types = type_mapping.get(expected_type, [])
        return any(ct in content_type_lower for ct in valid_types) or not content_type
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA-256 hash of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA-256 hash as hex string
        """
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

