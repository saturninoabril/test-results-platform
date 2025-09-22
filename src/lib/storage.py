"""
S3-compatible storage operations using aioboto3.
Provides async file upload, download, and lifecycle management for test artifacts.
Supports both MinIO (development) and S3 (production) backends.
"""

import hashlib
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import IO, Any, Optional

import aioboto3
import structlog
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError, NoCredentialsError  # type: ignore[import-untyped]

from .config import get_settings

logger = structlog.get_logger()

# Global storage client instance
_storage_client: Optional["StorageClient"] = None


class StorageInterface(ABC):
    """Abstract interface for storage operations."""

    @abstractmethod
    async def upload_file(
        self,
        file_obj: IO[bytes],
        storage_key: str,
        content_type: str,
    ) -> dict[str, Any]:
        """Upload file to storage."""
        pass

    @abstractmethod
    async def download_file(self, storage_key: str) -> bytes:
        """Download file from storage."""
        pass

    @abstractmethod
    async def download_file_stream(
        self,
        storage_key: str,
        range_start: int | None = None,
        range_end: int | None = None,
    ) -> AsyncGenerator[bytes]:
        """Download file from storage as streaming bytes with optional range support."""
        pass

    @abstractmethod
    async def generate_signed_url(
        self, storage_key: str, expiration: int = 3600, method: str = "GET"
    ) -> str:
        """Generate signed URL for file access."""
        pass

    @abstractmethod
    async def generate_upload_signed_url(
        self, storage_key: str, content_type: str, expiration: int = 3600
    ) -> dict[str, Any]:
        """Generate signed URL for file upload."""
        pass

    @abstractmethod
    async def delete_file(self, storage_key: str) -> bool:
        """Delete file from storage."""
        pass

    @abstractmethod
    async def delete_files(self, storage_keys: list[str]) -> dict[str, bool]:
        """Delete multiple files from storage."""
        pass

    @abstractmethod
    async def file_exists(self, storage_key: str) -> bool:
        """Check if file exists in storage."""
        pass

    @abstractmethod
    async def list_files(self, prefix: str, limit: int | None = None) -> list[dict[str, Any]]:
        """List files with given prefix."""
        pass

    @abstractmethod
    async def get_file_metadata(self, storage_key: str) -> dict[str, Any] | None:
        """Get file metadata."""
        pass


class StorageClient(StorageInterface):
    """S3-compatible storage client using aioboto3."""

    def __init__(self) -> None:
        """Initialize storage client with settings."""
        self.settings = get_settings()
        self._session = None
        self._bucket_cache: dict[str, bool] = {}

    async def _get_session(self) -> aioboto3.Session:
        """Get or create aioboto3 session."""
        if self._session is None:
            self._session = aioboto3.Session()
        return self._session

    def _get_s3_client(self) -> Any:
        """Get S3 client with proper configuration."""
        session = self._session if self._session else aioboto3.Session()

        # Configure client based on storage type
        config = Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            max_pool_connections=50,
        )

        if self.settings.storage.type == "minio":
            return session.client(
                "s3",
                endpoint_url=self.settings.storage.endpoint,
                aws_access_key_id=self.settings.storage.access_key,
                aws_secret_access_key=self.settings.storage.secret_key,
                region_name=self.settings.storage.region,
                use_ssl=self.settings.storage.use_ssl,
                config=config,
            )
        else:  # S3
            return session.client(
                "s3",
                aws_access_key_id=self.settings.storage.access_key,
                aws_secret_access_key=self.settings.storage.secret_key,
                region_name=self.settings.storage.region,
                config=config,
            )

    async def _ensure_bucket_exists(self, bucket_name: str) -> None:
        """Ensure bucket exists, create if it doesn't."""
        if bucket_name in self._bucket_cache:
            return

        async with self._get_s3_client() as s3:
            try:
                await s3.head_bucket(Bucket=bucket_name)
                self._bucket_cache[bucket_name] = True
                logger.debug("Bucket exists", bucket=bucket_name)
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "404":
                    # Bucket doesn't exist, create it
                    try:
                        if self.settings.storage.region == "us-east-1":
                            await s3.create_bucket(Bucket=bucket_name)
                        else:
                            await s3.create_bucket(
                                Bucket=bucket_name,
                                CreateBucketConfiguration={
                                    "LocationConstraint": self.settings.storage.region
                                },
                            )
                        self._bucket_cache[bucket_name] = True
                        logger.info("Bucket created", bucket=bucket_name)
                    except ClientError as create_error:
                        logger.error(
                            "Failed to create bucket",
                            bucket=bucket_name,
                            error=str(create_error),
                        )
                        raise
                else:
                    logger.error(
                        "Failed to check bucket",
                        bucket=bucket_name,
                        error=str(e),
                    )
                    raise

    def _calculate_checksum(self, file_obj: IO[bytes]) -> str:
        """Calculate SHA-256 checksum of file."""
        sha256_hash = hashlib.sha256()
        file_obj.seek(0)
        for chunk in iter(lambda: file_obj.read(8192), b""):
            sha256_hash.update(chunk)
        file_obj.seek(0)
        return sha256_hash.hexdigest()

    def _parse_storage_key(self, storage_key: str) -> tuple[str, str]:
        """Parse storage key into bucket name and object key."""
        parts = storage_key.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid storage key format: {storage_key}")

        bucket_type = parts[0]
        object_key = parts[1]
        bucket_name = self.settings.get_bucket_name(bucket_type)

        return bucket_name, object_key

    async def upload_file(
        self,
        file_obj: IO[bytes],
        storage_key: str,
        content_type: str,
    ) -> dict[str, Any]:
        """Upload file to storage with checksum validation and multipart support."""
        bucket_name, object_key = self._parse_storage_key(storage_key)
        await self._ensure_bucket_exists(bucket_name)

        # Calculate checksum
        checksum = self._calculate_checksum(file_obj)

        # Prepare metadata
        upload_metadata = {
            "checksum-sha256": checksum,
            "uploaded-at": datetime.utcnow().isoformat(),
        }

        # Get file size
        file_obj.seek(0, 2)  # Seek to end
        file_size = file_obj.tell()
        file_obj.seek(0)  # Reset to beginning

        # Use multipart upload for files larger than 100MB
        multipart_threshold = 100 * 1024 * 1024  # 100MB
        if file_size > multipart_threshold:
            return await self._upload_multipart(
                file_obj,
                bucket_name,
                object_key,
                content_type,
                upload_metadata,
                storage_key,
                file_size,
                checksum,
            )
        else:
            return await self._upload_single_part(
                file_obj,
                bucket_name,
                object_key,
                content_type,
                upload_metadata,
                storage_key,
                file_size,
                checksum,
            )

    async def _upload_single_part(
        self,
        file_obj: IO[bytes],
        bucket_name: str,
        object_key: str,
        content_type: str,
        upload_metadata: dict[str, str],
        storage_key: str,
        file_size: int,
        checksum: str,
    ) -> dict[str, Any]:
        """Upload file using single-part upload."""
        async with self._get_s3_client() as s3:
            try:
                # Upload file
                await s3.put_object(
                    Bucket=bucket_name,
                    Key=object_key,
                    Body=file_obj,
                    ContentType=content_type,
                    Metadata=upload_metadata,
                )

                logger.info(
                    "File uploaded successfully",
                    storage_key=storage_key,
                    size=file_size,
                    checksum=checksum[:8],  # Log first 8 chars of checksum
                    method="single-part",
                )

                return {
                    "storage_key": storage_key,
                    "bucket": bucket_name,
                    "object_key": object_key,
                    "size": file_size,
                    "checksum": checksum,
                    "content_type": content_type,
                    "uploaded_at": upload_metadata["uploaded-at"],
                    "upload_method": "single-part",
                }

            except ClientError as e:
                logger.error(
                    "File upload failed",
                    storage_key=storage_key,
                    error=str(e),
                )
                raise

    async def _upload_multipart(
        self,
        file_obj: IO[bytes],
        bucket_name: str,
        object_key: str,
        content_type: str,
        upload_metadata: dict[str, str],
        storage_key: str,
        file_size: int,
        checksum: str,
    ) -> dict[str, Any]:
        """Upload file using multipart upload for large files."""
        part_size = 10 * 1024 * 1024  # 10MB per part
        parts = []

        async with self._get_s3_client() as s3:
            try:
                # Create multipart upload
                create_response = await s3.create_multipart_upload(
                    Bucket=bucket_name,
                    Key=object_key,
                    ContentType=content_type,
                    Metadata=upload_metadata,
                )
                upload_id = create_response["UploadId"]

                logger.info(
                    "Starting multipart upload",
                    storage_key=storage_key,
                    upload_id=upload_id,
                    parts_count=((file_size - 1) // part_size) + 1,
                )

                try:
                    part_number = 1
                    file_obj.seek(0)

                    # Upload parts
                    while True:
                        data = file_obj.read(part_size)
                        if not data:
                            break

                        part_response = await s3.upload_part(
                            Bucket=bucket_name,
                            Key=object_key,
                            PartNumber=part_number,
                            UploadId=upload_id,
                            Body=data,
                        )

                        parts.append(
                            {
                                "PartNumber": part_number,
                                "ETag": part_response["ETag"],
                            }
                        )

                        logger.debug(
                            "Uploaded part",
                            storage_key=storage_key,
                            part_number=part_number,
                            size=len(data),
                        )

                        part_number += 1

                    # Complete multipart upload
                    await s3.complete_multipart_upload(
                        Bucket=bucket_name,
                        Key=object_key,
                        UploadId=upload_id,
                        MultipartUpload={"Parts": parts},
                    )

                    logger.info(
                        "Multipart upload completed",
                        storage_key=storage_key,
                        size=file_size,
                        parts_count=len(parts),
                        checksum=checksum[:8],
                    )

                    return {
                        "storage_key": storage_key,
                        "bucket": bucket_name,
                        "object_key": object_key,
                        "size": file_size,
                        "checksum": checksum,
                        "content_type": content_type,
                        "uploaded_at": upload_metadata["uploaded-at"],
                        "upload_method": "multipart",
                        "parts_count": len(parts),
                        "upload_id": upload_id,
                    }

                except Exception:
                    # Abort multipart upload on failure
                    try:
                        await s3.abort_multipart_upload(
                            Bucket=bucket_name,
                            Key=object_key,
                            UploadId=upload_id,
                        )
                        logger.warning(
                            "Multipart upload aborted",
                            storage_key=storage_key,
                            upload_id=upload_id,
                        )
                    except Exception as abort_error:
                        logger.error(
                            "Failed to abort multipart upload",
                            storage_key=storage_key,
                            upload_id=upload_id,
                            error=str(abort_error),
                        )
                    raise

            except ClientError as e:
                logger.error(
                    "Multipart upload failed",
                    storage_key=storage_key,
                    error=str(e),
                )
                raise

    async def download_file(self, storage_key: str) -> bytes:
        """Download file from storage."""
        bucket_name, object_key = self._parse_storage_key(storage_key)

        async with self._get_s3_client() as s3:
            try:
                response = await s3.get_object(Bucket=bucket_name, Key=object_key)

                # Read file content
                content = await response["Body"].read()

                # Verify checksum if available
                metadata = response.get("Metadata", {})
                stored_checksum = metadata.get("checksum-sha256")
                if stored_checksum:
                    calculated_checksum = hashlib.sha256(content).hexdigest()
                    if calculated_checksum != stored_checksum:
                        logger.error(
                            "Checksum mismatch",
                            storage_key=storage_key,
                            stored=stored_checksum[:8],
                            calculated=calculated_checksum[:8],
                        )
                        raise ValueError("File checksum verification failed")

                logger.debug("File downloaded successfully", storage_key=storage_key)
                return bytes(content)

            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    logger.warning("File not found", storage_key=storage_key)
                    raise FileNotFoundError(f"File not found: {storage_key}") from e
                else:
                    logger.error("File download failed", storage_key=storage_key, error=str(e))
                    raise

    async def download_file_stream(  # type: ignore[override]
        self,
        storage_key: str,
        range_start: int | None = None,
        range_end: int | None = None,
    ) -> AsyncGenerator[bytes]:
        """Download file from storage as streaming bytes with optional range support."""
        bucket_name, object_key = self._parse_storage_key(storage_key)

        # Prepare range header if needed
        get_kwargs = {"Bucket": bucket_name, "Key": object_key}
        if range_start is not None or range_end is not None:
            range_header = self._build_range_header(range_start, range_end)
            get_kwargs["Range"] = range_header
            logger.debug(
                "Downloading file with range",
                storage_key=storage_key,
                range=range_header,
            )

        async with self._get_s3_client() as s3:
            try:
                response = await s3.get_object(**get_kwargs)

                # Stream file content in chunks
                content_length = response.get("ContentLength", 0)
                bytes_read = 0
                chunk_size = 8192  # 8KB chunks

                logger.debug(
                    "Starting file stream",
                    storage_key=storage_key,
                    content_length=content_length,
                )

                body = response["Body"]
                while True:
                    chunk = await body.read(chunk_size)
                    if not chunk:
                        break

                    bytes_read += len(chunk)
                    yield chunk

                logger.debug(
                    "File stream completed",
                    storage_key=storage_key,
                    bytes_streamed=bytes_read,
                )

            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    logger.warning("File not found for streaming", storage_key=storage_key)
                    raise FileNotFoundError(f"File not found: {storage_key}") from e
                elif e.response["Error"]["Code"] == "InvalidRange":
                    logger.warning("Invalid range request", storage_key=storage_key)
                    raise ValueError("Invalid range request") from e
                else:
                    logger.error("File stream failed", storage_key=storage_key, error=str(e))
                    raise

    def _build_range_header(self, range_start: int | None, range_end: int | None) -> str:
        """Build HTTP Range header for partial content requests."""
        if range_start is not None and range_end is not None:
            if range_start > range_end:
                raise ValueError("Range start cannot be greater than range end")
            return f"bytes={range_start}-{range_end}"
        elif range_start is not None:
            return f"bytes={range_start}-"
        elif range_end is not None:
            # Suffix-byte-range-spec (last N bytes)
            return f"bytes=-{range_end}"
        else:
            raise ValueError("At least one of range_start or range_end must be specified")

    async def generate_signed_url(
        self, storage_key: str, expiration: int = 3600, method: str = "GET"
    ) -> str:
        """Generate signed URL for file access with configurable HTTP method."""
        bucket_name, object_key = self._parse_storage_key(storage_key)

        # Map HTTP methods to S3 operations
        method_operations = {
            "GET": "get_object",
            "PUT": "put_object",
            "DELETE": "delete_object",
            "HEAD": "head_object",
        }

        if method.upper() not in method_operations:
            raise ValueError(f"Unsupported HTTP method: {method}")

        operation = method_operations[method.upper()]

        async with self._get_s3_client() as s3:
            try:
                url = await s3.generate_presigned_url(
                    operation,
                    Params={"Bucket": bucket_name, "Key": object_key},
                    ExpiresIn=expiration,
                )

                logger.debug(
                    "Signed URL generated",
                    storage_key=storage_key,
                    method=method.upper(),
                    expiration=expiration,
                )
                return str(url)

            except ClientError as e:
                logger.error(
                    "Signed URL generation failed",
                    storage_key=storage_key,
                    method=method.upper(),
                    error=str(e),
                )
                raise

    async def generate_upload_signed_url(
        self, storage_key: str, content_type: str, expiration: int = 3600
    ) -> dict[str, Any]:
        """Generate signed URL for direct file upload with metadata."""
        bucket_name, object_key = self._parse_storage_key(storage_key)
        await self._ensure_bucket_exists(bucket_name)

        # Prepare upload metadata
        upload_metadata = {
            "uploaded-at": datetime.utcnow().isoformat(),
        }

        async with self._get_s3_client() as s3:
            try:
                # Generate presigned POST for uploads (more secure than PUT)
                conditions = [
                    {"Content-Type": content_type},
                    ["content-length-range", 1, self.settings.storage.max_file_size],
                ]

                fields = {
                    "Content-Type": content_type,
                }

                # Add metadata fields
                for key, value in upload_metadata.items():
                    metadata_key = f"x-amz-meta-{key}"
                    fields[metadata_key] = value
                    conditions.append({metadata_key: value})

                response = await s3.generate_presigned_post(
                    Bucket=bucket_name,
                    Key=object_key,
                    Fields=fields,
                    Conditions=conditions,
                    ExpiresIn=expiration,
                )

                logger.debug(
                    "Upload signed URL generated",
                    storage_key=storage_key,
                    content_type=content_type,
                    expiration=expiration,
                )

                return {
                    "upload_url": response["url"],
                    "fields": response["fields"],
                    "storage_key": storage_key,
                    "bucket": bucket_name,
                    "object_key": object_key,
                    "expires_in": expiration,
                    "max_file_size": self.settings.storage.max_file_size,
                    "content_type": content_type,
                }

            except ClientError as e:
                logger.error(
                    "Upload signed URL generation failed",
                    storage_key=storage_key,
                    error=str(e),
                )
                raise

    async def delete_file(self, storage_key: str) -> bool:
        """Delete file from storage."""
        bucket_name, object_key = self._parse_storage_key(storage_key)

        async with self._get_s3_client() as s3:
            try:
                await s3.delete_object(Bucket=bucket_name, Key=object_key)
                logger.info("File deleted successfully", storage_key=storage_key)
                return True

            except ClientError as e:
                logger.error(
                    "File deletion failed",
                    storage_key=storage_key,
                    error=str(e),
                )
                return False

    async def delete_files(self, storage_keys: list[str]) -> dict[str, bool]:
        """Delete multiple files from storage."""
        results = {}

        # Group keys by bucket for efficient batch operations
        bucket_groups: dict[str, list[str]] = {}
        for storage_key in storage_keys:
            bucket_name, object_key = self._parse_storage_key(storage_key)
            if bucket_name not in bucket_groups:
                bucket_groups[bucket_name] = []
            bucket_groups[bucket_name].append(object_key)

        async with self._get_s3_client() as s3:
            for bucket_name, object_keys in bucket_groups.items():
                try:
                    # Prepare objects for deletion
                    delete_objects = [{"Key": key} for key in object_keys]

                    # Batch delete (up to 1000 objects at a time)
                    for i in range(0, len(delete_objects), 1000):
                        batch = delete_objects[i : i + 1000]
                        response = await s3.delete_objects(
                            Bucket=bucket_name,
                            Delete={"Objects": batch, "Quiet": False},
                        )

                        # Process results
                        for deleted in response.get("Deleted", []):
                            storage_key = f"{bucket_name.split('-', 1)[1]}/{deleted['Key']}"
                            results[storage_key] = True

                        for error in response.get("Errors", []):
                            storage_key = f"{bucket_name.split('-', 1)[1]}/{error['Key']}"
                            results[storage_key] = False
                            logger.error(
                                "File deletion error",
                                storage_key=storage_key,
                                error=error.get("Message"),
                            )

                except ClientError as e:
                    logger.error(
                        "Batch delete failed",
                        bucket=bucket_name,
                        count=len(object_keys),
                        error=str(e),
                    )
                    # Mark all as failed
                    for object_key in object_keys:
                        storage_key = f"{bucket_name.split('-', 1)[1]}/{object_key}"
                        results[storage_key] = False

        logger.info(
            "Batch delete completed",
            total=len(storage_keys),
            successful=sum(1 for success in results.values() if success),
            failed=sum(1 for success in results.values() if not success),
        )

        return results

    async def file_exists(self, storage_key: str) -> bool:
        """Check if file exists in storage."""
        bucket_name, object_key = self._parse_storage_key(storage_key)

        async with self._get_s3_client() as s3:
            try:
                await s3.head_object(Bucket=bucket_name, Key=object_key)
                return True
            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    return False
                else:
                    logger.error(
                        "File existence check failed",
                        storage_key=storage_key,
                        error=str(e),
                    )
                    raise

    async def list_files(self, prefix: str, limit: int | None = None) -> list[dict[str, Any]]:
        """List files with given prefix."""
        # Parse prefix to extract bucket info
        bucket_type = prefix.split("/")[0]
        bucket_name = self.settings.get_bucket_name(bucket_type)
        object_prefix = "/".join(prefix.split("/")[1:]) if "/" in prefix else ""

        files = []
        async with self._get_s3_client() as s3:
            try:
                paginator = s3.get_paginator("list_objects_v2")
                page_iterator = paginator.paginate(
                    Bucket=bucket_name,
                    Prefix=object_prefix,
                )

                async for page in page_iterator:
                    for obj in page.get("Contents", []):
                        storage_key = f"{bucket_type}/{obj['Key']}"
                        files.append(
                            {
                                "storage_key": storage_key,
                                "size": obj["Size"],
                                "last_modified": obj["LastModified"],
                                "etag": obj["ETag"].strip('"'),
                            }
                        )

                        if limit and len(files) >= limit:
                            return files

            except ClientError as e:
                logger.error(
                    "File listing failed",
                    prefix=prefix,
                    error=str(e),
                )
                raise

        return files

    async def get_file_metadata(self, storage_key: str) -> dict[str, Any] | None:
        """Get file metadata."""
        bucket_name, object_key = self._parse_storage_key(storage_key)

        async with self._get_s3_client() as s3:
            try:
                response = await s3.head_object(Bucket=bucket_name, Key=object_key)

                return {
                    "storage_key": storage_key,
                    "size": response["ContentLength"],
                    "content_type": response.get("ContentType"),
                    "last_modified": response["LastModified"],
                    "etag": response["ETag"].strip('"'),
                    "metadata": response.get("Metadata", {}),
                }

            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    return None
                else:
                    logger.error(
                        "File metadata retrieval failed",
                        storage_key=storage_key,
                        error=str(e),
                    )
                    raise

    async def health_check(self) -> bool:
        """Check storage connectivity."""
        try:
            # Try to list buckets as a health check
            async with self._get_s3_client() as s3:
                await s3.list_buckets()
                logger.debug("Storage health check passed")
                return True
        except (ClientError, NoCredentialsError, Exception) as e:
            logger.error("Storage health check failed", error=str(e))
            return False


async def init_storage() -> None:
    """Initialize storage client."""
    global _storage_client

    if _storage_client is not None:
        logger.warning("Storage client already initialized")
        return

    _storage_client = StorageClient()
    logger.info("Storage client initialized")


async def close_storage() -> None:
    """Close storage client connections."""
    global _storage_client

    if _storage_client is not None:
        # aioboto3 sessions close automatically
        _storage_client = None
        logger.info("Storage client closed")


def get_storage_client() -> StorageClient:
    """Get the current storage client."""
    if _storage_client is None:
        raise RuntimeError("Storage client not initialized. Call init_storage() first.")
    return _storage_client


@asynccontextmanager
async def get_storage() -> AsyncGenerator[StorageClient]:
    """Get storage client with automatic initialization."""
    if _storage_client is None:
        await init_storage()

    client = get_storage_client()
    try:
        yield client
    finally:
        # No explicit cleanup needed for aioboto3
        pass


def generate_storage_key(artifact_type: str, *path_parts: str) -> str:
    """Generate storage key with proper prefix organization."""
    # Clean path parts
    clean_parts = []
    for part in path_parts:
        # Remove leading/trailing slashes and ensure no empty parts
        clean_part = str(part).strip("/")
        if clean_part:
            clean_parts.append(clean_part)

    if not clean_parts:
        raise ValueError("Storage key must have at least one path part")

    return f"{artifact_type}/{'/'.join(clean_parts)}"


def parse_storage_key(storage_key: str) -> dict[str, str]:
    """Parse storage key into components."""
    parts = storage_key.split("/")
    if len(parts) < 2:
        raise ValueError(f"Invalid storage key format: {storage_key}")

    return {
        "artifact_type": parts[0],
        "path": "/".join(parts[1:]),
        "filename": parts[-1],
    }


class StorageLifecycleManager:
    """Manager for storage lifecycle operations like cleanup and retention."""

    def __init__(self, storage_client: StorageClient):
        """Initialize lifecycle manager with storage client."""
        self.storage_client = storage_client
        self.settings = storage_client.settings

    async def cleanup_expired_artifacts(
        self,
        max_age_days: int,
        artifact_types: list[str] | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Clean up artifacts older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        cleanup_results: dict[str, Any] = {
            "cutoff_date": cutoff_date.isoformat(),
            "max_age_days": max_age_days,
            "artifacts_scanned": 0,
            "artifacts_expired": 0,
            "artifacts_deleted": 0,
            "artifacts_failed": 0,
            "dry_run": dry_run,
            "deleted_files": [],
            "failed_files": [],
        }

        # Default artifact types if not specified
        if artifact_types is None:
            artifact_types = ["screenshots", "videos", "reports", "logs"]

        logger.info(
            "Starting expired artifacts cleanup",
            max_age_days=max_age_days,
            cutoff_date=cutoff_date.isoformat(),
            artifact_types=artifact_types,
            dry_run=dry_run,
        )

        for artifact_type in artifact_types:
            logger.debug("Processing artifact type", artifact_type=artifact_type)

            try:
                # List all files for this artifact type
                files = await self.storage_client.list_files(artifact_type)
                cleanup_results["artifacts_scanned"] += len(files)

                expired_files = []
                for file_info in files:
                    last_modified = file_info["last_modified"]

                    # Handle both datetime objects and ISO strings
                    if isinstance(last_modified, str):
                        last_modified = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))

                    # Remove timezone info for comparison
                    if last_modified.tzinfo is not None:
                        last_modified = last_modified.replace(tzinfo=None)

                    if last_modified < cutoff_date:
                        expired_files.append(file_info["storage_key"])
                        cleanup_results["artifacts_expired"] += 1

                if expired_files:
                    logger.info(
                        "Found expired artifacts",
                        artifact_type=artifact_type,
                        count=len(expired_files),
                    )

                    if not dry_run:
                        # Delete expired files in batches
                        delete_results = await self.storage_client.delete_files(expired_files)

                        for storage_key, success in delete_results.items():
                            if success:
                                cleanup_results["artifacts_deleted"] += 1
                                cleanup_results["deleted_files"].append(storage_key)
                            else:
                                cleanup_results["artifacts_failed"] += 1
                                cleanup_results["failed_files"].append(storage_key)

                    else:
                        # In dry run mode, just count what would be deleted
                        cleanup_results["deleted_files"].extend(expired_files)

            except Exception as e:
                logger.error(
                    "Error processing artifact type during cleanup",
                    artifact_type=artifact_type,
                    error=str(e),
                )
                continue

        logger.info(
            "Cleanup completed",
            scanned=cleanup_results["artifacts_scanned"],
            expired=cleanup_results["artifacts_expired"],
            deleted=cleanup_results["artifacts_deleted"],
            failed=cleanup_results["artifacts_failed"],
            dry_run=dry_run,
        )

        return cleanup_results

    async def enforce_retention_policy(
        self,
        retention_rules: dict[str, int],
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Enforce retention policies for different artifact types."""
        policy_results: dict[str, Any] = {
            "retention_rules": retention_rules,
            "dry_run": dry_run,
            "results_by_type": {},
            "total_scanned": 0,
            "total_deleted": 0,
            "total_failed": 0,
        }

        logger.info(
            "Starting retention policy enforcement",
            retention_rules=retention_rules,
            dry_run=dry_run,
        )

        for artifact_type, max_age_days in retention_rules.items():
            if max_age_days <= 0:
                logger.warning(
                    "Skipping invalid retention rule",
                    artifact_type=artifact_type,
                    max_age_days=max_age_days,
                )
                continue

            logger.info(
                "Applying retention policy",
                artifact_type=artifact_type,
                max_age_days=max_age_days,
            )

            try:
                cleanup_result = await self.cleanup_expired_artifacts(
                    max_age_days=max_age_days,
                    artifact_types=[artifact_type],
                    dry_run=dry_run,
                )

                policy_results["results_by_type"][artifact_type] = cleanup_result
                policy_results["total_scanned"] += cleanup_result["artifacts_scanned"]
                policy_results["total_deleted"] += cleanup_result["artifacts_deleted"]
                policy_results["total_failed"] += cleanup_result["artifacts_failed"]

            except Exception as e:
                logger.error(
                    "Error applying retention policy",
                    artifact_type=artifact_type,
                    error=str(e),
                )
                policy_results["results_by_type"][artifact_type] = {
                    "error": str(e),
                    "artifacts_scanned": 0,
                    "artifacts_deleted": 0,
                    "artifacts_failed": 0,
                }

        logger.info(
            "Retention policy enforcement completed",
            total_scanned=policy_results["total_scanned"],
            total_deleted=policy_results["total_deleted"],
            total_failed=policy_results["total_failed"],
            dry_run=dry_run,
        )

        return policy_results

    async def cleanup_suite_artifacts(
        self,
        suite_pattern: str,
        max_age_days: int | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Clean up all artifacts for test suites matching a pattern."""
        cleanup_results: dict[str, Any] = {
            "suite_pattern": suite_pattern,
            "max_age_days": max_age_days,
            "dry_run": dry_run,
            "artifacts_found": 0,
            "artifacts_deleted": 0,
            "artifacts_failed": 0,
            "deleted_files": [],
            "failed_files": [],
        }

        logger.info(
            "Starting suite artifacts cleanup",
            suite_pattern=suite_pattern,
            max_age_days=max_age_days,
            dry_run=dry_run,
        )

        # Search for files matching the suite pattern across all artifact types
        artifact_types = ["screenshots", "videos", "reports", "logs"]
        cutoff_date = None

        if max_age_days is not None:
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

        matching_files = []

        for artifact_type in artifact_types:
            try:
                # List files with the artifact type prefix
                files = await self.storage_client.list_files(artifact_type)

                for file_info in files:
                    storage_key = file_info["storage_key"]

                    # Check if the file path matches the suite pattern
                    if suite_pattern in storage_key:
                        # Apply age filter if specified
                        if cutoff_date is not None:
                            last_modified = file_info["last_modified"]

                            # Handle timezone-aware datetime objects
                            if isinstance(last_modified, str):
                                last_modified = datetime.fromisoformat(
                                    last_modified.replace("Z", "+00:00")
                                )

                            if last_modified.tzinfo is not None:
                                last_modified = last_modified.replace(tzinfo=None)

                            if last_modified < cutoff_date:
                                matching_files.append(storage_key)
                        else:
                            matching_files.append(storage_key)

            except Exception as e:
                logger.error(
                    "Error scanning artifact type for suite cleanup",
                    artifact_type=artifact_type,
                    suite_pattern=suite_pattern,
                    error=str(e),
                )
                continue

        cleanup_results["artifacts_found"] = len(matching_files)

        if matching_files:
            logger.info(
                "Found matching suite artifacts",
                suite_pattern=suite_pattern,
                count=len(matching_files),
            )

            if not dry_run:
                # Delete matching files
                delete_results = await self.storage_client.delete_files(matching_files)

                for storage_key, success in delete_results.items():
                    if success:
                        cleanup_results["artifacts_deleted"] += 1
                        cleanup_results["deleted_files"].append(storage_key)
                    else:
                        cleanup_results["artifacts_failed"] += 1
                        cleanup_results["failed_files"].append(storage_key)
            else:
                # In dry run mode, just list what would be deleted
                cleanup_results["deleted_files"] = matching_files

        logger.info(
            "Suite artifacts cleanup completed",
            suite_pattern=suite_pattern,
            found=cleanup_results["artifacts_found"],
            deleted=cleanup_results["artifacts_deleted"],
            failed=cleanup_results["artifacts_failed"],
            dry_run=dry_run,
        )

        return cleanup_results

    async def get_storage_usage_stats(
        self, artifact_types: list[str] | None = None
    ) -> dict[str, Any]:
        """Get storage usage statistics by artifact type."""
        if artifact_types is None:
            artifact_types = ["screenshots", "videos", "reports", "logs"]

        usage_stats: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "artifact_types": artifact_types,
            "total_files": 0,
            "total_size_bytes": 0,
            "by_type": {},
        }

        logger.info("Collecting storage usage statistics", artifact_types=artifact_types)

        for artifact_type in artifact_types:
            type_stats: dict[str, Any] = {
                "file_count": 0,
                "total_size_bytes": 0,
                "oldest_file": None,
                "newest_file": None,
            }

            try:
                files = await self.storage_client.list_files(artifact_type)
                type_stats["file_count"] = len(files)

                if files:
                    # Calculate total size and find oldest/newest files
                    total_size = sum(file_info["size"] for file_info in files)
                    type_stats["total_size_bytes"] = total_size

                    # Sort by modification time
                    sorted_files = sorted(files, key=lambda f: f["last_modified"])
                    type_stats["oldest_file"] = {
                        "storage_key": sorted_files[0]["storage_key"],
                        "last_modified": sorted_files[0]["last_modified"],
                        "size": sorted_files[0]["size"],
                    }
                    type_stats["newest_file"] = {
                        "storage_key": sorted_files[-1]["storage_key"],
                        "last_modified": sorted_files[-1]["last_modified"],
                        "size": sorted_files[-1]["size"],
                    }

                usage_stats["total_files"] += type_stats["file_count"]
                usage_stats["total_size_bytes"] += type_stats["total_size_bytes"]
                usage_stats["by_type"][artifact_type] = type_stats

                logger.debug(
                    "Artifact type statistics",
                    artifact_type=artifact_type,
                    file_count=type_stats["file_count"],
                    total_size_mb=type_stats["total_size_bytes"] // (1024 * 1024),
                )

            except Exception as e:
                logger.error(
                    "Error collecting statistics for artifact type",
                    artifact_type=artifact_type,
                    error=str(e),
                )
                usage_stats["by_type"][artifact_type] = {
                    "error": str(e),
                    "file_count": 0,
                    "total_size_bytes": 0,
                }

        logger.info(
            "Storage usage statistics collected",
            total_files=usage_stats["total_files"],
            total_size_mb=usage_stats["total_size_bytes"] // (1024 * 1024),
        )

        return usage_stats
