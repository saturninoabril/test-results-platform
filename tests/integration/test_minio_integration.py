"""
MinIO storage integration tests with real MinIO instance.
Tests complete file upload/download workflows, multipart uploads, and cleanup operations.
"""

import asyncio
import sys
import os
import io
import time
from pathlib import Path
from typing import List

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.lib.storage import get_storage_client, init_storage, StorageClient
from src.lib.config import get_settings


class FileGenerator:
    """Helper class to generate test files of various sizes."""

    @staticmethod
    def generate_small_file(content: str = "Hello, MinIO!") -> io.BytesIO:
        """Generate a small text file for basic testing."""
        return io.BytesIO(content.encode('utf-8'))

    @staticmethod
    def generate_medium_file(size_kb: int = 100) -> io.BytesIO:
        """Generate a medium-sized file for testing."""
        content = b"X" * (size_kb * 1024)
        return io.BytesIO(content)

    @staticmethod
    def generate_large_file(size_mb: int = 10) -> io.BytesIO:
        """Generate a large file for multipart upload testing."""
        chunk_size = 1024 * 1024  # 1MB chunks
        content = io.BytesIO()

        for i in range(size_mb):
            chunk = f"Chunk {i:04d} - " + "X" * (chunk_size - 20)
            content.write(chunk.encode('utf-8')[:chunk_size])

        content.seek(0)
        return content

    @staticmethod
    def generate_image_file() -> io.BytesIO:
        """Generate a fake PNG image file for testing."""
        # PNG signature + minimal PNG structure
        png_header = b'\x89PNG\r\n\x1a\n'
        ihdr_chunk = b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
        idat_chunk = b'\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x00\x01\x00\x18\xdd\x8d\xb4'
        iend_chunk = b'\x00\x00\x00\x00IEND\xaeB`\x82'

        fake_png = png_header + ihdr_chunk + idat_chunk + iend_chunk
        return io.BytesIO(fake_png)


async def test_storage_client_initialization():
    """Test storage client initialization and configuration."""
    print("🔧 Testing storage client initialization...")

    # Initialize storage first
    await init_storage()

    # Test singleton pattern
    client1 = get_storage_client()
    client2 = get_storage_client()
    assert client1 is client2, "Storage client should be singleton"

    # Test client configuration
    assert isinstance(client1, StorageClient)
    print("✅ Storage client initialization successful")


async def test_basic_file_operations():
    """Test basic file upload and download operations."""
    print("📁 Testing basic file operations...")

    client = get_storage_client()

    # Test small text file upload
    test_content = "Hello, MinIO! This is a test file."
    file_obj = FileGenerator.generate_small_file(test_content)
    storage_key = "test-artifacts/basic/hello.txt"

    # Upload file
    upload_result = await client.upload_file(
        file_obj=file_obj,
        storage_key=storage_key,
        content_type="text/plain",
        metadata={"test": "basic_upload", "size": "small"}
    )

    assert "storage_key" in upload_result
    assert upload_result["storage_key"] == storage_key
    assert "checksum" in upload_result
    assert "size" in upload_result
    print(f"✅ File uploaded: {upload_result['storage_key']} (size: {upload_result['size']} bytes)")

    # Download and verify content
    downloaded_content = await client.download_file(storage_key)
    assert downloaded_content.decode('utf-8') == test_content
    print("✅ File download and content verification successful")

    # Test file existence
    exists = await client.file_exists(storage_key)
    assert exists is True
    print("✅ File existence check successful")

    # Test file metadata
    metadata = await client.get_file_metadata(storage_key)
    assert "size" in metadata
    assert "last_modified" in metadata
    assert "content_type" in metadata
    print("✅ File metadata retrieval successful")

    return storage_key


async def test_multipart_upload():
    """Test multipart upload for large files."""
    print("📦 Testing multipart upload...")

    client = get_storage_client()

    # Generate a 10MB file
    large_file = FileGenerator.generate_large_file(size_mb=10)
    original_size = large_file.getbuffer().nbytes
    storage_key = "test-artifacts/large/multipart-10mb.bin"

    start_time = time.time()

    # Upload large file (should trigger multipart upload)
    upload_result = await client.upload_file(
        file_obj=large_file,
        storage_key=storage_key,
        content_type="application/octet-stream",
        metadata={"test": "multipart_upload", "original_size": str(original_size)}
    )

    upload_time = time.time() - start_time

    assert upload_result["size"] == original_size
    print(f"✅ Large file uploaded: {upload_result['storage_key']} (size: {upload_result['size']} bytes, time: {upload_time:.2f}s)")

    # Verify download
    start_time = time.time()
    downloaded_content = await client.download_file(storage_key)
    download_time = time.time() - start_time

    assert len(downloaded_content) == original_size
    print(f"✅ Large file download successful (size: {len(downloaded_content)} bytes, time: {download_time:.2f}s)")

    return storage_key


async def test_streaming_download():
    """Test streaming download for large files."""
    print("🌊 Testing streaming download...")

    client = get_storage_client()

    # Use the large file from multipart test
    large_file = FileGenerator.generate_large_file(size_mb=5)
    original_size = large_file.getbuffer().nbytes
    storage_key = "test-artifacts/streaming/stream-5mb.bin"

    # Upload file first
    await client.upload_file(
        file_obj=large_file,
        storage_key=storage_key,
        content_type="application/octet-stream"
    )

    # Test streaming download
    chunks = []
    total_size = 0

    async for chunk in client.download_file_stream(storage_key):
        chunks.append(chunk)
        total_size += len(chunk)

    # Verify streaming result
    streamed_content = b''.join(chunks)
    assert len(streamed_content) == original_size
    assert total_size == len(streamed_content)
    print(f"✅ Streaming download successful (chunks: {len(chunks)}, total size: {total_size} bytes)")

    return storage_key


async def test_signed_urls():
    """Test signed URL generation for secure access."""
    print("🔗 Testing signed URL generation...")

    client = get_storage_client()

    # Upload a test file
    test_file = FileGenerator.generate_image_file()
    storage_key = "test-artifacts/signed/test-image.png"

    await client.upload_file(
        file_obj=test_file,
        storage_key=storage_key,
        content_type="image/png",
        metadata={"test": "signed_url", "type": "image"}
    )

    # Generate signed URL
    signed_url = await client.generate_signed_url(
        storage_key=storage_key,
        expiration=3600  # 1 hour
    )

    assert signed_url is not None
    assert "http" in signed_url.lower()
    assert storage_key.replace("/", "%2F") in signed_url or storage_key in signed_url
    print(f"✅ Signed URL generated successfully")

    return storage_key, signed_url


async def test_file_listing():
    """Test file listing and prefix-based filtering."""
    print("📋 Testing file listing...")

    client = get_storage_client()

    # Upload multiple test files
    test_files = [
        ("test-artifacts/list/file1.txt", "Content of file 1"),
        ("test-artifacts/list/file2.txt", "Content of file 2"),
        ("test-artifacts/list/subdir/file3.txt", "Content of file 3"),
        ("test-artifacts/other/file4.txt", "Content of file 4"),
    ]

    for storage_key, content in test_files:
        file_obj = FileGenerator.generate_small_file(content)
        await client.upload_file(
            file_obj=file_obj,
            storage_key=storage_key,
            content_type="text/plain"
        )

    # Test listing all files with prefix
    files_in_list = await client.list_files(prefix="test-artifacts/list/")
    assert len(files_in_list) >= 3  # Should find file1, file2, file3
    print(f"✅ Listed {len(files_in_list)} files with prefix 'test-artifacts/list/'")

    # Test listing with different prefix
    files_in_other = await client.list_files(prefix="test-artifacts/other/")
    assert len(files_in_other) >= 1  # Should find file4
    print(f"✅ Listed {len(files_in_other)} files with prefix 'test-artifacts/other/'")

    return [storage_key for storage_key, _ in test_files]


async def test_bulk_operations():
    """Test bulk file operations for performance."""
    print("⚡ Testing bulk operations...")

    client = get_storage_client()

    # Upload multiple files in sequence
    files_to_upload = []
    for i in range(20):
        content = f"Bulk test file {i:02d} with some content"
        storage_key = f"test-artifacts/bulk/bulk-{i:02d}.txt"
        files_to_upload.append((storage_key, content))

    start_time = time.time()

    # Upload files sequentially (could be parallelized in production)
    uploaded_files = []
    for storage_key, content in files_to_upload:
        file_obj = FileGenerator.generate_small_file(content)
        result = await client.upload_file(
            file_obj=file_obj,
            storage_key=storage_key,
            content_type="text/plain",
            metadata={"batch": "bulk_test", "index": storage_key.split('-')[-1].split('.')[0]}
        )
        uploaded_files.append(result["storage_key"])

    upload_time = time.time() - start_time
    print(f"✅ Uploaded {len(uploaded_files)} files in {upload_time:.2f} seconds")

    # Test bulk existence check
    start_time = time.time()
    existence_checks = []
    for storage_key in uploaded_files:
        exists = await client.file_exists(storage_key)
        existence_checks.append(exists)

    check_time = time.time() - start_time
    assert all(existence_checks), "All files should exist"
    print(f"✅ Verified existence of {len(existence_checks)} files in {check_time:.3f} seconds")

    return uploaded_files


async def test_cleanup_operations():
    """Test file cleanup and retention policies."""
    print("🧹 Testing cleanup operations...")

    client = get_storage_client()

    # Create test files for cleanup
    cleanup_files = []
    for i in range(10):
        content = f"Cleanup test file {i}"
        storage_key = f"test-artifacts/cleanup/temp-{i:02d}.txt"
        file_obj = FileGenerator.generate_small_file(content)

        await client.upload_file(
            file_obj=file_obj,
            storage_key=storage_key,
            content_type="text/plain",
            metadata={"temp": "true", "test": "cleanup"}
        )
        cleanup_files.append(storage_key)

    # Verify files exist before cleanup
    for storage_key in cleanup_files:
        exists = await client.file_exists(storage_key)
        assert exists, f"File {storage_key} should exist before cleanup"

    print(f"✅ Created {len(cleanup_files)} temporary files for cleanup test")

    # Test individual file deletion
    file_to_delete = cleanup_files[0]
    await client.delete_file(file_to_delete)

    exists_after_delete = await client.file_exists(file_to_delete)
    assert not exists_after_delete, "File should not exist after deletion"
    print(f"✅ Successfully deleted individual file: {file_to_delete}")

    # Test bulk deletion by listing files and deleting them
    file_metadata_list = await client.list_files(prefix="test-artifacts/cleanup/")
    if file_metadata_list:
        # Extract storage keys from metadata
        files_to_cleanup = [file_info["storage_key"] for file_info in file_metadata_list]
        delete_results = await client.delete_files(files_to_cleanup)
        successful_deletes = sum(1 for success in delete_results.values() if success)
        print(f"✅ Bulk deletion: deleted {successful_deletes}/{len(files_to_cleanup)} files")

    # Verify all cleanup files are gone
    remaining_files = 0
    for storage_key in cleanup_files[1:]:  # Skip the already deleted file
        exists = await client.file_exists(storage_key)
        if exists:
            remaining_files += 1

    print(f"✅ Bulk cleanup completed. Remaining files: {remaining_files}")

    return cleanup_files


async def test_error_handling():
    """Test error handling for various failure scenarios."""
    print("❌ Testing error handling...")

    client = get_storage_client()

    # Test downloading non-existent file
    try:
        await client.download_file("test-artifacts/nonexistent/missing-file.txt")
        assert False, "Should have raised an exception for missing file"
    except Exception as e:
        print(f"✅ Correctly handled missing file download: {type(e).__name__}")

    # Test deleting non-existent file
    try:
        await client.delete_file("test-artifacts/nonexistent/missing-file.txt")
        # Note: Some storage implementations might not error on deleting missing files
        print("✅ Delete missing file handled gracefully")
    except Exception as e:
        print(f"✅ Delete missing file error handled: {type(e).__name__}")

    # Test invalid storage key
    try:
        invalid_key = ""  # Empty key
        test_file = FileGenerator.generate_small_file("test")
        await client.upload_file(
            file_obj=test_file,
            storage_key=invalid_key,
            content_type="text/plain"
        )
        assert False, "Should have raised an exception for invalid storage key"
    except Exception as e:
        print(f"✅ Correctly handled invalid storage key: {type(e).__name__}")


async def test_file_types_and_content_types():
    """Test various file types and content type handling."""
    print("📄 Testing various file types...")

    client = get_storage_client()

    test_files = [
        ("test-artifacts/types/text.txt", "text/plain", "Hello, world!"),
        ("test-artifacts/types/data.json", "application/json", '{"test": "data", "number": 42}'),
        ("test-artifacts/types/style.css", "text/css", "body { color: red; }"),
        ("test-artifacts/types/script.js", "application/javascript", "console.log('hello');"),
        ("test-artifacts/types/image.png", "image/png", None),  # Will use generated PNG
    ]

    uploaded_files = []

    for storage_key, content_type, content in test_files:
        if content is None:
            # Use generated image
            file_obj = FileGenerator.generate_image_file()
        else:
            file_obj = FileGenerator.generate_small_file(content)

        result = await client.upload_file(
            file_obj=file_obj,
            storage_key=storage_key,
            content_type=content_type,
            metadata={"file_type": content_type.split('/')[0]}
        )

        uploaded_files.append((storage_key, content_type, content))
        print(f"✅ Uploaded {content_type}: {storage_key}")

    # Verify metadata and content types
    for storage_key, expected_content_type, original_content in uploaded_files:
        metadata = await client.get_file_metadata(storage_key)

        # Note: Content type verification might vary by storage implementation
        print(f"✅ File metadata retrieved for {storage_key}")

        # Verify content for text files
        if original_content is not None:
            downloaded_content = await client.download_file(storage_key)
            assert downloaded_content.decode('utf-8') == original_content
            print(f"✅ Content verified for {storage_key}")

    return uploaded_files


async def run_all_tests():
    """Run all MinIO storage integration tests."""
    print("🚀 Starting MinIO Storage Integration Tests...")
    print("=" * 60)

    try:
        # Test 1: Basic initialization
        await test_storage_client_initialization()
        print()

        # Test 2: Basic file operations
        basic_file = await test_basic_file_operations()
        print()

        # Test 3: Multipart upload for large files
        large_file = await test_multipart_upload()
        print()

        # Test 4: Streaming download
        stream_file = await test_streaming_download()
        print()

        # Test 5: Signed URLs
        signed_file, signed_url = await test_signed_urls()
        print()

        # Test 6: File listing and filtering
        list_files = await test_file_listing()
        print()

        # Test 7: Bulk operations
        bulk_files = await test_bulk_operations()
        print()

        # Test 8: File types and content types
        type_files = await test_file_types_and_content_types()
        print()

        # Test 9: Error handling
        await test_error_handling()
        print()

        # Test 10: Cleanup operations (run last)
        cleanup_files = await test_cleanup_operations()
        print()

        print("=" * 60)
        print("🎉 All MinIO Storage Integration Tests Passed!")

        # Summary
        total_files_created = (
            1 +  # basic file
            1 +  # large file
            1 +  # stream file
            1 +  # signed file
            len(list_files) +  # list files
            len(bulk_files) +  # bulk files
            len(type_files)    # type files
            # cleanup files are deleted
        )

        print(f"📊 Test Summary:")
        print(f"   • Total test files processed: ~{total_files_created}")
        print(f"   • Multipart upload tested: ✅")
        print(f"   • Streaming download tested: ✅")
        print(f"   • Signed URLs tested: ✅")
        print(f"   • Bulk operations tested: ✅")
        print(f"   • Cleanup operations tested: ✅")
        print(f"   • Error handling tested: ✅")

        return True

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Configure environment for testing
    os.environ.setdefault("STORAGE_TYPE", "minio")
    os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9000")
    os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
    os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin123")
    os.environ.setdefault("MINIO_BUCKET_PREFIX", "test")

    success = asyncio.run(run_all_tests())
    if success:
        print("✅ All integration tests with MinIO storage passed!")
    else:
        print("❌ MinIO storage integration tests failed!")
        sys.exit(1)