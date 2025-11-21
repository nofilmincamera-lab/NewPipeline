"""
Database model for downloaded files.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator


class DownloadedFile(BaseModel):
    """Model for downloaded file metadata."""
    
    id: Optional[int] = None
    uuid: Optional[UUID] = None
    source_url: str
    file_url: str
    domain: str
    file_type: str = Field(..., regex='^(pdf|doc|docx)$')
    original_filename: Optional[str] = None
    stored_filename: str
    file_path: str
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    content_type: Optional[str] = None
    parent_page_url: Optional[str] = None
    download_status: str = Field(default='pending', regex='^(pending|downloaded|failed)$')
    download_error: Optional[str] = None
    ocr_status: str = Field(default='pending', regex='^(pending|processing|completed|failed)$')
    ocr_error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    downloaded_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class DownloadedFileDB:
    """Database operations for downloaded files."""
    
    def __init__(self, connection):
        """
        Initialize database operations.
        
        Args:
            connection: Database connection (asyncpg connection)
        """
        self.conn = connection
    
    async def create_file_record(self, file_data: DownloadedFile) -> int:
        """
        Create a new file record in the database.
        
        Args:
            file_data: DownloadedFile model instance
            
        Returns:
            ID of created record
        """
        query = """
            INSERT INTO downloaded_files (
                uuid, source_url, file_url, domain, file_type,
                original_filename, stored_filename, file_path,
                file_size, file_hash, content_type, parent_page_url,
                download_status, download_error, ocr_status, metadata,
                downloaded_at
            ) VALUES (
                COALESCE($1, uuid_generate_v4()), $2, $3, $4, $5,
                $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17
            )
            RETURNING id
        """
        
        result = await self.conn.fetchval(
            query,
            file_data.uuid,
            file_data.source_url,
            file_data.file_url,
            file_data.domain,
            file_data.file_type,
            file_data.original_filename,
            file_data.stored_filename,
            file_data.file_path,
            file_data.file_size,
            file_data.file_hash,
            file_data.content_type,
            file_data.parent_page_url,
            file_data.download_status,
            file_data.download_error,
            file_data.ocr_status,
            file_data.metadata
        )
        
        return result
    
    async def update_file_record(
        self,
        file_id: int,
        download_status: Optional[str] = None,
        download_error: Optional[str] = None,
        file_size: Optional[int] = None,
        file_hash: Optional[str] = None,
        content_type: Optional[str] = None,
        downloaded_at: Optional[datetime] = None
    ) -> bool:
        """
        Update file record after download.
        
        Args:
            file_id: ID of file record
            download_status: New download status
            download_error: Error message if failed
            file_size: File size in bytes
            file_hash: SHA-256 hash
            content_type: Content type
            downloaded_at: Download timestamp
            
        Returns:
            True if updated successfully
        """
        updates = []
        params = []
        param_idx = 1
        
        if download_status is not None:
            updates.append(f"download_status = ${param_idx}")
            params.append(download_status)
            param_idx += 1
        
        if download_error is not None:
            updates.append(f"download_error = ${param_idx}")
            params.append(download_error)
            param_idx += 1
        
        if file_size is not None:
            updates.append(f"file_size = ${param_idx}")
            params.append(file_size)
            param_idx += 1
        
        if file_hash is not None:
            updates.append(f"file_hash = ${param_idx}")
            params.append(file_hash)
            param_idx += 1
        
        if content_type is not None:
            updates.append(f"content_type = ${param_idx}")
            params.append(content_type)
            param_idx += 1
        
        if downloaded_at is not None:
            updates.append(f"downloaded_at = ${param_idx}")
            params.append(downloaded_at)
            param_idx += 1
        
        if not updates:
            return False
        
        params.append(file_id)
        query = f"""
            UPDATE downloaded_files
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
        """
        
        result = await self.conn.execute(query, *params)
        return result == "UPDATE 1"
    
    async def check_file_exists(self, file_url: str) -> Optional[int]:
        """
        Check if file URL already exists in database.
        
        Args:
            file_url: File URL to check
            
        Returns:
            File ID if exists, None otherwise
        """
        query = "SELECT id FROM downloaded_files WHERE file_url = $1"
        result = await self.conn.fetchval(query, file_url)
        return result
    
    async def check_hash_exists(self, file_hash: str) -> Optional[int]:
        """
        Check if file hash already exists (for deduplication).
        
        Args:
            file_hash: SHA-256 hash to check
            
        Returns:
            File ID if hash exists, None otherwise
        """
        query = "SELECT id FROM downloaded_files WHERE file_hash = $1 AND download_status = 'downloaded'"
        result = await self.conn.fetchval(query, file_hash)
        return result
    
    async def get_file_by_id(self, file_id: int) -> Optional[Dict]:
        """
        Get file record by ID.
        
        Args:
            file_id: File ID
            
        Returns:
            File record as dictionary or None
        """
        query = "SELECT * FROM downloaded_files WHERE id = $1"
        row = await self.conn.fetchrow(query, file_id)
        return dict(row) if row else None

