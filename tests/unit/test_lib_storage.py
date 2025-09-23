"""
Unit tests for storage library foundation.
Tests storage client initialization, configuration, and utility functions.
"""

import hashlib
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.lib.storage import (
    StorageClient,
    StorageLifecycleManager,
    _storage_client,
    close_storage,
    generate_storage_key,
    get_storage,
    get_storage_client,
    init_storage,
    parse_storage_key,
)


class TestStorageClient:
    """Test StorageClient class."""

    def test_init(self):
        """Test client initialization."""
        client = StorageClient()
        assert client.settings is not None
        assert client._session is None
        assert client._bucket_cache == {}

    def test_calculate_checksum(self):
        """Test checksum calculation."""
        client = StorageClient()
        test_data = b"Hello, World!"
        file_obj = BytesIO(test_data)

        checksum = client._calculate_checksum(file_obj)
        expected_checksum = hashlib.sha256(test_data).hexdigest()

        assert checksum == expected_checksum
        assert file_obj.tell() == 0  # Should reset to beginning

    def test_parse_storage_key_valid(self):
        """Test valid storage key parsing."""
        client = StorageClient()

        bucket_name, object_key = client._parse_storage_key("screenshots/test/file.png")

        # Should extract bucket type and construct bucket name
        assert object_key == "test/file.png"
        assert "screenshots" in bucket_name

    def test_parse_storage_key_invalid(self):
        """Test invalid storage key parsing."""
        client = StorageClient()

        with pytest.raises(ValueError, match="Invalid storage key format"):
            client._parse_storage_key("invalid_key_no_slash")

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test session creation and reuse."""
        client = StorageClient()

        # First call creates session
        session1 = await client._get_session()
        assert session1 is not None
        assert client._session is session1

        # Second call reuses session
        session2 = await client._get_session()
        assert session2 is session1

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_get_s3_client_minio(self, mock_session_class):
        """Test S3 client creation for MinIO."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        # Get S3 client
        async with client._get_s3_client() as s3_client:
            assert s3_client is mock_client

        # Verify MinIO-specific configuration
        mock_session.client.assert_called_once()
        call_args = mock_session.client.call_args
        assert call_args[0][0] == "s3"  # First positional arg
        assert "endpoint_url" in call_args[1]  # Should have endpoint_url for MinIO

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_get_s3_client_s3(self, mock_session_class):
        """Test S3 client creation for AWS S3."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        # Override storage type to S3
        with patch.object(client.settings.storage, "type", "s3"):
            async with client._get_s3_client() as s3_client:
                assert s3_client is mock_client

        # Verify S3-specific configuration (no endpoint_url)
        mock_session.client.assert_called_once()
        call_args = mock_session.client.call_args
        assert call_args[0][0] == "s3"  # First positional arg
        assert "endpoint_url" not in call_args[1]  # Should not have endpoint_url for S3


class TestStorageUtilities:
    """Test storage utility functions."""

    def test_generate_storage_key_valid(self):
        """Test valid storage key generation."""
        key = generate_storage_key("screenshots", "suite123", "test.png")
        assert key == "screenshots/suite123/test.png"

    def test_generate_storage_key_clean_paths(self):
        """Test storage key generation with path cleaning."""
        key = generate_storage_key("videos", "/suite123/", "//test.mp4//")
        assert key == "videos/suite123/test.mp4"

    def test_generate_storage_key_empty_parts(self):
        """Test storage key generation with empty path parts."""
        with pytest.raises(ValueError, match="Storage key must have at least one path part"):
            generate_storage_key("screenshots")

    def test_parse_storage_key_valid(self):
        """Test valid storage key parsing."""
        result = parse_storage_key("screenshots/suite123/test.png")

        assert result == {
            "artifact_type": "screenshots",
            "path": "suite123/test.png",
            "filename": "test.png",
        }

    def test_parse_storage_key_complex(self):
        """Test complex storage key parsing."""
        result = parse_storage_key("reports/project/suite/subsuite/report.html")

        assert result == {
            "artifact_type": "reports",
            "path": "project/suite/subsuite/report.html",
            "filename": "report.html",
        }

    def test_parse_storage_key_invalid(self):
        """Test invalid storage key parsing."""
        with pytest.raises(ValueError, match="Invalid storage key format"):
            parse_storage_key("invalid")


class TestStorageLifecycle:
    """Test storage lifecycle management."""

    @pytest.mark.asyncio
    async def test_init_storage_first_time(self):
        """Test first-time storage initialization."""
        # Ensure clean state
        global _storage_client
        original_client = _storage_client
        _storage_client = None

        try:
            await init_storage()
            client = get_storage_client()
            assert isinstance(client, StorageClient)
        finally:
            _storage_client = original_client

    @pytest.mark.asyncio
    async def test_init_storage_already_initialized(self):
        """Test storage initialization when already initialized."""
        # Mock existing client
        import src.lib.storage as storage_module

        original_client = storage_module._storage_client
        mock_client = MagicMock()
        storage_module._storage_client = mock_client

        try:
            with patch("src.lib.storage.logger") as mock_logger:
                await init_storage()
                mock_logger.warning.assert_called_once_with("Storage client already initialized")

            # Should not change existing client
            assert get_storage_client() is mock_client
        finally:
            storage_module._storage_client = original_client

    @pytest.mark.asyncio
    async def test_close_storage(self):
        """Test storage client closing."""
        import src.lib.storage as storage_module

        original_client = storage_module._storage_client
        storage_module._storage_client = MagicMock()

        try:
            await close_storage()
            assert storage_module._storage_client is None
        finally:
            storage_module._storage_client = original_client

    def test_get_storage_client_not_initialized(self):
        """Test getting storage client when not initialized."""
        import src.lib.storage as storage_module

        original_client = storage_module._storage_client
        storage_module._storage_client = None

        try:
            with pytest.raises(RuntimeError, match="Storage client not initialized"):
                get_storage_client()
        finally:
            storage_module._storage_client = original_client

    @pytest.mark.asyncio
    async def test_get_storage_context_manager(self):
        """Test storage context manager."""
        global _storage_client
        original_client = _storage_client
        _storage_client = None

        try:
            async with get_storage() as client:
                assert isinstance(client, StorageClient)
                assert get_storage_client() is client
        finally:
            _storage_client = original_client


class TestHealthCheck:
    """Test storage health check."""

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_health_check_success(self, mock_session_class):
        """Test successful health check."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_client.list_buckets.return_value = {"Buckets": []}
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        result = await client.health_check()
        assert result is True
        mock_client.list_buckets.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_health_check_failure(self, mock_session_class):
        """Test failed health check."""
        # Mock session and client with failure
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_client.list_buckets.side_effect = Exception("Connection failed")
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        result = await client.health_check()
        assert result is False


class TestFileUploadOperations:
    """Test file upload operations."""

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_upload_file_success(self, mock_session_class):
        """Test successful file upload."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_client.head_bucket.side_effect = [True]  # Bucket exists
        mock_client.put_object.return_value = None
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session
        client._bucket_cache["dev-screenshots"] = True  # Cache bucket exists

        # Test file data
        test_data = b"This is a test file content"
        file_obj = BytesIO(test_data)

        result = await client.upload_file(file_obj, "screenshots/suite123/test.png", "image/png")

        # Verify result
        assert result["storage_key"] == "screenshots/suite123/test.png"
        assert result["size"] == len(test_data)
        assert result["content_type"] == "image/png"
        assert "checksum" in result
        assert "uploaded_at" in result

        # Verify S3 upload was called
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args.kwargs
        assert "Body" in call_kwargs
        assert call_kwargs["ContentType"] == "image/png"
        assert "Metadata" in call_kwargs

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_upload_file_bucket_creation(self, mock_session_class):
        """Test file upload with bucket creation."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        # First call: bucket doesn't exist (404), second call: create bucket succeeds
        mock_client.head_bucket.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadBucket")
        mock_client.create_bucket.return_value = None
        mock_client.put_object.return_value = None
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        # Test file data
        test_data = b"Test content"
        file_obj = BytesIO(test_data)

        result = await client.upload_file(file_obj, "videos/suite456/test.mp4", "video/mp4")

        # Verify bucket creation was attempted
        mock_client.head_bucket.assert_called_once()
        mock_client.create_bucket.assert_called_once()
        mock_client.put_object.assert_called_once()

        # Verify result
        assert result["storage_key"] == "videos/suite456/test.mp4"
        assert result["content_type"] == "video/mp4"

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_upload_file_invalid_storage_key(self, mock_session_class):
        """Test file upload with invalid storage key."""
        client = StorageClient()

        test_data = b"Test content"
        file_obj = BytesIO(test_data)

        with pytest.raises(ValueError, match="Invalid storage key format"):
            await client.upload_file(file_obj, "invalid_key", "text/plain")

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_upload_file_client_error(self, mock_session_class):
        """Test file upload with client error."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_client.head_bucket.side_effect = [True]  # Bucket exists
        mock_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "PutObject"
        )
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session
        client._bucket_cache["dev-reports"] = True

        test_data = b"Test content"
        file_obj = BytesIO(test_data)

        with pytest.raises(ClientError):
            await client.upload_file(file_obj, "reports/test.html", "text/html")

    def test_calculate_checksum_consistency(self):
        """Test checksum calculation is consistent."""
        client = StorageClient()
        test_data = b"Hello, World! This is a test."

        file_obj1 = BytesIO(test_data)
        checksum1 = client._calculate_checksum(file_obj1)

        file_obj2 = BytesIO(test_data)
        checksum2 = client._calculate_checksum(file_obj2)

        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA-256 hex string length

    def test_parse_storage_key_components(self):
        """Test storage key parsing for upload operations."""
        client = StorageClient()

        bucket_name, object_key = client._parse_storage_key("screenshots/project1/suite2/test.png")

        assert object_key == "project1/suite2/test.png"
        assert bucket_name.endswith("-screenshots")

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_upload_multipart_large_file(self, mock_session_class):
        """Test multipart upload for large files."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_client.head_bucket.side_effect = [True]  # Bucket exists
        mock_client.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
        mock_client.upload_part.return_value = {"ETag": "test-etag"}
        mock_client.complete_multipart_upload.return_value = None
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session
        client._bucket_cache["dev-videos"] = True

        # Create a large file (>100MB)
        large_file_size = 150 * 1024 * 1024  # 150MB
        test_data = b"x" * large_file_size
        file_obj = BytesIO(test_data)

        result = await client.upload_file(file_obj, "videos/suite789/large.mp4", "video/mp4")

        # Verify multipart upload was used
        assert result["upload_method"] == "multipart"
        assert result["parts_count"] == 15  # 150MB / 10MB per part
        assert result["upload_id"] == "test-upload-id"
        assert result["size"] == large_file_size

        # Verify S3 calls
        mock_client.create_multipart_upload.assert_called_once()
        assert mock_client.upload_part.call_count == 15
        mock_client.complete_multipart_upload.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_upload_single_part_small_file(self, mock_session_class):
        """Test single-part upload for small files."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_client.head_bucket.side_effect = [True]  # Bucket exists
        mock_client.put_object.return_value = None
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session
        client._bucket_cache["dev-screenshots"] = True

        # Create a small file (<100MB)
        small_file_size = 50 * 1024 * 1024  # 50MB
        test_data = b"y" * small_file_size
        file_obj = BytesIO(test_data)

        result = await client.upload_file(file_obj, "screenshots/suite456/small.png", "image/png")

        # Verify single-part upload was used
        assert result["upload_method"] == "single-part"
        assert result["size"] == small_file_size

        # Verify S3 calls
        mock_client.put_object.assert_called_once()
        # Should not call multipart methods
        mock_client.create_multipart_upload.assert_not_called()
        mock_client.upload_part.assert_not_called()
        mock_client.complete_multipart_upload.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_upload_multipart_failure_and_abort(self, mock_session_class):
        """Test multipart upload failure and abort."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_client.head_bucket.side_effect = [True]  # Bucket exists
        mock_client.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
        # First part succeeds, second part fails
        mock_client.upload_part.side_effect = [
            {"ETag": "test-etag"},
            ClientError({"Error": {"Code": "InternalError"}}, "UploadPart"),
        ]
        mock_client.abort_multipart_upload.return_value = None
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session
        client._bucket_cache["dev-videos"] = True

        # Create a large file that will trigger multipart
        large_file_size = 120 * 1024 * 1024  # 120MB
        test_data = b"z" * large_file_size
        file_obj = BytesIO(test_data)

        with pytest.raises(ClientError):
            await client.upload_file(file_obj, "videos/suite999/failed.mp4", "video/mp4")

        # Verify multipart upload was attempted and aborted
        mock_client.create_multipart_upload.assert_called_once()
        mock_client.upload_part.assert_called()  # Called at least once
        mock_client.abort_multipart_upload.assert_called_once_with(
            Bucket="dev-videos",
            Key="suite999/failed.mp4",
            UploadId="test-upload-id",
        )


class TestFileDownloadOperations:
    """Test file download operations."""

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_download_file_success(self, mock_session_class):
        """Test successful file download."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        test_content = b"Hello, World! This is test content."
        mock_body = AsyncMock()
        mock_body.read.return_value = test_content

        mock_client.get_object.return_value = {
            "Body": mock_body,
            "Metadata": {"checksum-sha256": hashlib.sha256(test_content).hexdigest()},
            "ContentLength": len(test_content),
        }
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        result = await client.download_file("screenshots/test123/file.png")

        # Verify result
        assert result == test_content

        # Verify S3 call
        mock_client.get_object.assert_called_once_with(
            Bucket="dev-screenshots", Key="test123/file.png"
        )

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_download_file_not_found(self, mock_session_class):
        """Test file download when file doesn't exist."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        with pytest.raises(FileNotFoundError, match="File not found: videos/missing.mp4"):
            await client.download_file("videos/missing.mp4")

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_download_file_checksum_mismatch(self, mock_session_class):
        """Test file download with checksum verification failure."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        test_content = b"Hello, World!"
        mock_body = AsyncMock()
        mock_body.read.return_value = test_content

        # Provide wrong checksum
        wrong_checksum = hashlib.sha256(b"different content").hexdigest()
        mock_client.get_object.return_value = {
            "Body": mock_body,
            "Metadata": {"checksum-sha256": wrong_checksum},
        }
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        with pytest.raises(ValueError, match="File checksum verification failed"):
            await client.download_file("reports/corrupted.html")

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_download_file_stream_success(self, mock_session_class):
        """Test successful file streaming download."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        test_content = b"This is a large file content for streaming test"
        chunk_size = 8192
        chunks = [test_content[i : i + chunk_size] for i in range(0, len(test_content), chunk_size)]

        mock_body = AsyncMock()
        mock_body.read = AsyncMock(side_effect=chunks + [b""])  # End with empty bytes

        mock_client.get_object.return_value = {
            "Body": mock_body,
            "ContentLength": len(test_content),
        }
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        # Stream the file
        streamed_content = b""
        async for chunk in client.download_file_stream("videos/large.mp4"):
            streamed_content += chunk

        # Verify result
        assert streamed_content == test_content

        # Verify S3 call
        mock_client.get_object.assert_called_once_with(Bucket="dev-videos", Key="large.mp4")

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_download_file_stream_with_range(self, mock_session_class):
        """Test file streaming download with range request."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        full_content = b"0123456789" * 100  # 1000 bytes
        range_start = 100
        range_end = 199
        range_content = full_content[range_start : range_end + 1]

        mock_body = AsyncMock()
        mock_body.read = AsyncMock(side_effect=[range_content, b""])

        mock_client.get_object.return_value = {
            "Body": mock_body,
            "ContentLength": len(range_content),
        }
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        # Stream the file with range
        streamed_content = b""
        async for chunk in client.download_file_stream(
            "videos/large.mp4", range_start=range_start, range_end=range_end
        ):
            streamed_content += chunk

        # Verify result
        assert streamed_content == range_content

        # Verify S3 call with range
        mock_client.get_object.assert_called_once_with(
            Bucket="dev-videos", Key="large.mp4", Range="bytes=100-199"
        )

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_download_file_stream_invalid_range(self, mock_session_class):
        """Test file streaming with invalid range request."""
        # Test the range validation that happens before S3 call
        client = StorageClient()

        with pytest.raises(ValueError, match="Range start cannot be greater than range end"):
            async for _chunk in client.download_file_stream(
                "videos/test.mp4", range_start=1000, range_end=100
            ):
                pass

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_download_file_stream_s3_invalid_range(self, mock_session_class):
        """Test file streaming with S3 invalid range response."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "InvalidRange"}}, "GetObject"
        )
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        with pytest.raises(ValueError, match="Invalid range request"):
            async for _chunk in client.download_file_stream(
                "videos/test.mp4", range_start=50, range_end=100
            ):
                pass

    def test_build_range_header(self):
        """Test range header building."""
        client = StorageClient()

        # Test full range
        assert client._build_range_header(0, 499) == "bytes=0-499"

        # Test start only
        assert client._build_range_header(500, None) == "bytes=500-"

        # Test end only (suffix)
        assert client._build_range_header(None, 500) == "bytes=-500"

        # Test invalid range
        with pytest.raises(ValueError, match="Range start cannot be greater than range end"):
            client._build_range_header(500, 100)

        # Test no range specified
        with pytest.raises(ValueError, match="At least one of range_start or range_end"):
            client._build_range_header(None, None)

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_generate_signed_url_success(self, mock_session_class):
        """Test successful signed URL generation."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        test_url = "https://test-bucket.s3.amazonaws.com/test-key?signature=abc123"
        mock_client.generate_presigned_url.return_value = test_url
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        result = await client.generate_signed_url("screenshots/test.png", expiration=7200)

        # Verify result
        assert result == test_url

        # Verify S3 call
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "dev-screenshots", "Key": "test.png"},
            ExpiresIn=7200,
        )

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_generate_signed_url_different_methods(self, mock_session_class):
        """Test signed URL generation for different HTTP methods."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_client.generate_presigned_url.return_value = "https://example.com/signed-url"
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session

        # Test different methods
        methods = ["GET", "PUT", "DELETE", "HEAD"]
        operations = ["get_object", "put_object", "delete_object", "head_object"]

        for method, expected_op in zip(methods, operations, strict=False):
            mock_client.reset_mock()
            await client.generate_signed_url("files/test.txt", method=method)

            mock_client.generate_presigned_url.assert_called_once()
            call_args = mock_client.generate_presigned_url.call_args
            assert call_args[0][0] == expected_op

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_generate_signed_url_unsupported_method(self, mock_session_class):
        """Test signed URL generation with unsupported HTTP method."""
        client = StorageClient()

        with pytest.raises(ValueError, match="Unsupported HTTP method: PATCH"):
            await client.generate_signed_url("files/test.txt", method="PATCH")

    @pytest.mark.asyncio
    @patch("src.lib.storage.aioboto3.Session")
    async def test_generate_upload_signed_url_success(self, mock_session_class):
        """Test successful upload signed URL generation."""
        # Mock session and client
        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_client.head_bucket.side_effect = [True]  # Bucket exists
        test_response = {
            "url": "https://test-bucket.s3.amazonaws.com/",
            "fields": {
                "key": "test.png",
                "Content-Type": "image/png",
                "x-amz-meta-uploaded-at": "2025-09-14T12:00:00",
            },
        }
        mock_client.generate_presigned_post.return_value = test_response
        mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_session.client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        client = StorageClient()
        client._session = mock_session
        client._bucket_cache["dev-screenshots"] = True

        result = await client.generate_upload_signed_url("screenshots/test.png", "image/png", 3600)

        # Verify result structure
        assert result["upload_url"] == test_response["url"]
        assert result["fields"] == test_response["fields"]
        assert result["storage_key"] == "screenshots/test.png"
        assert result["content_type"] == "image/png"
        assert result["expires_in"] == 3600

        # Verify S3 call
        mock_client.generate_presigned_post.assert_called_once()


class TestStorageLifecycleManager:
    """Test storage lifecycle management operations."""

    @pytest.fixture
    def mock_storage_client(self):
        """Create a mock storage client for lifecycle tests."""
        client = MagicMock(spec=StorageClient)
        client.settings = MagicMock()  # Add mock settings
        return client

    @pytest.fixture
    def lifecycle_manager(self, mock_storage_client):
        """Create lifecycle manager with mock storage client."""
        return StorageLifecycleManager(mock_storage_client)

    @pytest.mark.asyncio
    async def test_cleanup_expired_artifacts_dry_run(self, lifecycle_manager, mock_storage_client):
        """Test expired artifacts cleanup in dry run mode."""
        # Mock file listing
        old_date = datetime.utcnow() - timedelta(days=10)
        new_date = datetime.utcnow() - timedelta(days=1)

        mock_files = [
            {
                "storage_key": "screenshots/suite1/old.png",
                "size": 1024,
                "last_modified": old_date,
                "etag": "abc123",
            },
            {
                "storage_key": "screenshots/suite2/new.png",
                "size": 2048,
                "last_modified": new_date,
                "etag": "def456",
            },
        ]

        mock_storage_client.list_files.return_value = mock_files

        result = await lifecycle_manager.cleanup_expired_artifacts(
            max_age_days=5, artifact_types=["screenshots"], dry_run=True
        )

        # Verify results
        assert result["artifacts_scanned"] == 2
        assert result["artifacts_expired"] == 1
        assert result["artifacts_deleted"] == 0  # Dry run
        assert result["dry_run"] is True
        assert "screenshots/suite1/old.png" in result["deleted_files"]
        assert "screenshots/suite2/new.png" not in result["deleted_files"]

        # Verify no delete was called
        mock_storage_client.delete_files.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_expired_artifacts_real_run(self, lifecycle_manager, mock_storage_client):
        """Test expired artifacts cleanup with actual deletion."""
        # Mock file listing
        old_date = datetime.utcnow() - timedelta(days=10)

        mock_files = [
            {
                "storage_key": "videos/suite1/old.mp4",
                "size": 1024000,
                "last_modified": old_date,
                "etag": "video123",
            }
        ]

        mock_storage_client.list_files.return_value = mock_files
        mock_storage_client.delete_files.return_value = {"videos/suite1/old.mp4": True}

        result = await lifecycle_manager.cleanup_expired_artifacts(
            max_age_days=5, artifact_types=["videos"], dry_run=False
        )

        # Verify results
        assert result["artifacts_scanned"] == 1
        assert result["artifacts_expired"] == 1
        assert result["artifacts_deleted"] == 1
        assert result["artifacts_failed"] == 0
        assert result["dry_run"] is False
        assert result["deleted_files"] == ["videos/suite1/old.mp4"]

        # Verify delete was called
        mock_storage_client.delete_files.assert_called_once_with(["videos/suite1/old.mp4"])

    @pytest.mark.asyncio
    async def test_cleanup_expired_artifacts_with_failures(
        self, lifecycle_manager, mock_storage_client
    ):
        """Test cleanup handling delete failures."""
        old_date = datetime.utcnow() - timedelta(days=10)

        mock_files = [
            {
                "storage_key": "reports/suite1/old.html",
                "size": 5120,
                "last_modified": old_date,
                "etag": "report123",
            },
            {
                "storage_key": "reports/suite2/old.xml",
                "size": 3072,
                "last_modified": old_date,
                "etag": "report456",
            },
        ]

        mock_storage_client.list_files.return_value = mock_files
        mock_storage_client.delete_files.return_value = {
            "reports/suite1/old.html": True,
            "reports/suite2/old.xml": False,  # Failed
        }

        result = await lifecycle_manager.cleanup_expired_artifacts(
            max_age_days=5, artifact_types=["reports"], dry_run=False
        )

        # Verify results
        assert result["artifacts_deleted"] == 1
        assert result["artifacts_failed"] == 1
        assert result["deleted_files"] == ["reports/suite1/old.html"]
        assert result["failed_files"] == ["reports/suite2/old.xml"]

    @pytest.mark.asyncio
    async def test_cleanup_expired_artifacts_iso_string_dates(
        self, lifecycle_manager, mock_storage_client
    ):
        """Test cleanup with ISO string dates."""
        old_date_str = (datetime.utcnow() - timedelta(days=10)).isoformat() + "Z"

        mock_files = [
            {
                "storage_key": "logs/suite1/old.log",
                "size": 1024,
                "last_modified": old_date_str,  # ISO string with Z
                "etag": "log123",
            }
        ]

        mock_storage_client.list_files.return_value = mock_files

        result = await lifecycle_manager.cleanup_expired_artifacts(
            max_age_days=5, artifact_types=["logs"], dry_run=True
        )

        # Should parse ISO date and find it expired
        assert result["artifacts_expired"] == 1
        assert "logs/suite1/old.log" in result["deleted_files"]

    @pytest.mark.asyncio
    async def test_enforce_retention_policy(self, lifecycle_manager, mock_storage_client):
        """Test retention policy enforcement."""
        # Mock different files for different artifact types
        screenshot_files = [
            {
                "storage_key": "screenshots/old.png",
                "size": 1024,
                "last_modified": datetime.utcnow() - timedelta(days=10),
                "etag": "abc",
            }
        ]

        video_files = [
            {
                "storage_key": "videos/old.mp4",
                "size": 5120,
                "last_modified": datetime.utcnow() - timedelta(days=20),
                "etag": "def",
            }
        ]

        def mock_list_files(artifact_type):
            if artifact_type == "screenshots":
                return screenshot_files
            elif artifact_type == "videos":
                return video_files
            else:
                return []

        mock_storage_client.list_files.side_effect = mock_list_files
        mock_storage_client.delete_files.return_value = {"screenshots/old.png": True}

        retention_rules = {
            "screenshots": 7,  # 7 days
            "videos": 30,  # 30 days
        }

        result = await lifecycle_manager.enforce_retention_policy(retention_rules, dry_run=False)

        # Verify results
        assert result["total_scanned"] == 2
        assert result["total_deleted"] == 1  # Only screenshot expired
        assert "screenshots" in result["results_by_type"]
        assert "videos" in result["results_by_type"]

        # Screenshot should be expired and deleted
        screenshot_result = result["results_by_type"]["screenshots"]
        assert screenshot_result["artifacts_expired"] == 1
        assert screenshot_result["artifacts_deleted"] == 1

        # Video should not be expired (20 days < 30 days)
        video_result = result["results_by_type"]["videos"]
        assert video_result["artifacts_expired"] == 0

    @pytest.mark.asyncio
    async def test_enforce_retention_policy_invalid_rules(self, lifecycle_manager):
        """Test retention policy with invalid rules."""
        retention_rules = {
            "screenshots": 0,  # Invalid
            "videos": -5,  # Invalid
            "reports": 30,  # Valid
        }

        result = await lifecycle_manager.enforce_retention_policy(retention_rules, dry_run=True)

        # Should only process valid rule
        assert "reports" in result["results_by_type"]
        assert "screenshots" not in result["results_by_type"]
        assert "videos" not in result["results_by_type"]

    @pytest.mark.asyncio
    async def test_cleanup_suite_artifacts(self, lifecycle_manager, mock_storage_client):
        """Test cleanup of artifacts for specific test suite."""
        mock_files = [
            {
                "storage_key": "screenshots/suite123/test1.png",
                "size": 1024,
                "last_modified": datetime.utcnow() - timedelta(days=1),
                "etag": "abc",
            },
            {
                "storage_key": "videos/suite123/test1.mp4",
                "size": 5120,
                "last_modified": datetime.utcnow() - timedelta(days=2),
                "etag": "def",
            },
            {
                "storage_key": "screenshots/suite456/test1.png",
                "size": 1024,
                "last_modified": datetime.utcnow() - timedelta(days=1),
                "etag": "ghi",
            },
        ]

        def mock_list_files(artifact_type):
            return [f for f in mock_files if f["storage_key"].startswith(artifact_type)]

        mock_storage_client.list_files.side_effect = mock_list_files
        mock_storage_client.delete_files.return_value = {
            "screenshots/suite123/test1.png": True,
            "videos/suite123/test1.mp4": True,
        }

        result = await lifecycle_manager.cleanup_suite_artifacts(
            suite_pattern="suite123", dry_run=False
        )

        # Verify results
        assert result["artifacts_found"] == 2  # Only suite123 files
        assert result["artifacts_deleted"] == 2
        assert result["artifacts_failed"] == 0
        assert "screenshots/suite123/test1.png" in result["deleted_files"]
        assert "videos/suite123/test1.mp4" in result["deleted_files"]
        assert "screenshots/suite456/test1.png" not in result["deleted_files"]

    @pytest.mark.asyncio
    async def test_cleanup_suite_artifacts_with_age_filter(
        self, lifecycle_manager, mock_storage_client
    ):
        """Test suite cleanup with age filtering."""
        old_date = datetime.utcnow() - timedelta(days=10)
        new_date = datetime.utcnow() - timedelta(days=1)

        # Screenshots files only
        screenshot_files = [
            {
                "storage_key": "screenshots/suite123/old.png",
                "size": 1024,
                "last_modified": old_date,
                "etag": "abc",
            },
            {
                "storage_key": "screenshots/suite123/new.png",
                "size": 1024,
                "last_modified": new_date,
                "etag": "def",
            },
        ]

        def mock_list_files(artifact_type):
            if artifact_type == "screenshots":
                return screenshot_files
            else:
                return []  # No files in other types

        mock_storage_client.list_files.side_effect = mock_list_files

        result = await lifecycle_manager.cleanup_suite_artifacts(
            suite_pattern="suite123", max_age_days=5, dry_run=True
        )

        # Should only match old file (age filter applied)
        assert result["artifacts_found"] == 1
        assert "screenshots/suite123/old.png" in result["deleted_files"]
        assert "screenshots/suite123/new.png" not in result["deleted_files"]

    @pytest.mark.asyncio
    async def test_get_storage_usage_stats(self, lifecycle_manager, mock_storage_client):
        """Test storage usage statistics collection."""
        screenshot_files = [
            {
                "storage_key": "screenshots/test1.png",
                "size": 1024,
                "last_modified": datetime.utcnow() - timedelta(days=1),
                "etag": "abc",
            },
            {
                "storage_key": "screenshots/test2.png",
                "size": 2048,
                "last_modified": datetime.utcnow() - timedelta(days=2),
                "etag": "def",
            },
        ]

        video_files = [
            {
                "storage_key": "videos/test1.mp4",
                "size": 10240,
                "last_modified": datetime.utcnow() - timedelta(days=3),
                "etag": "ghi",
            }
        ]

        def mock_list_files(artifact_type):
            if artifact_type == "screenshots":
                return screenshot_files
            elif artifact_type == "videos":
                return video_files
            else:
                return []

        mock_storage_client.list_files.side_effect = mock_list_files

        result = await lifecycle_manager.get_storage_usage_stats(
            artifact_types=["screenshots", "videos"]
        )

        # Verify results
        assert result["total_files"] == 3
        assert result["total_size_bytes"] == 13312  # 1024 + 2048 + 10240

        # Check screenshots stats
        screenshots_stats = result["by_type"]["screenshots"]
        assert screenshots_stats["file_count"] == 2
        assert screenshots_stats["total_size_bytes"] == 3072  # 1024 + 2048
        assert screenshots_stats["oldest_file"]["storage_key"] == "screenshots/test2.png"
        assert screenshots_stats["newest_file"]["storage_key"] == "screenshots/test1.png"

        # Check videos stats
        videos_stats = result["by_type"]["videos"]
        assert videos_stats["file_count"] == 1
        assert videos_stats["total_size_bytes"] == 10240

    @pytest.mark.asyncio
    async def test_get_storage_usage_stats_with_error(self, lifecycle_manager, mock_storage_client):
        """Test storage usage statistics with listing error."""

        def mock_list_files(artifact_type):
            if artifact_type == "screenshots":
                raise Exception("Access denied")
            else:
                return []

        mock_storage_client.list_files.side_effect = mock_list_files

        result = await lifecycle_manager.get_storage_usage_stats(
            artifact_types=["screenshots", "videos"]
        )

        # Should handle error gracefully
        assert result["total_files"] == 0
        assert "screenshots" in result["by_type"]
        assert result["by_type"]["screenshots"]["error"] == "Access denied"
        assert result["by_type"]["screenshots"]["file_count"] == 0

    def test_lifecycle_manager_initialization(self):
        """Test lifecycle manager initialization."""
        mock_client = MagicMock(spec=StorageClient)
        mock_client.settings = MagicMock()
        manager = StorageLifecycleManager(mock_client)

        assert manager.storage_client is mock_client
        assert manager.settings is mock_client.settings


@pytest.fixture(autouse=True)
def cleanup_storage_state():
    """Ensure clean storage state for each test."""
    global _storage_client
    original_client = _storage_client
    yield
    _storage_client = original_client
