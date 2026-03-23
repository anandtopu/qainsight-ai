import os
import tempfile
import pytest
from pathlib import Path

from app.core.config import settings
from app.db.storage import LocalStorageProvider

@pytest.fixture
def temp_storage_path(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", tmpdir)
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
        yield tmpdir

@pytest.mark.asyncio
async def test_local_storage_provider(temp_storage_path):
    provider = LocalStorageProvider()
    
    bucket = "test-bucket"
    key = "test-folder/test-file.txt"
    content = b"Hello Storage!"

    # Test put_object
    await provider.put_object(key=key, content=content, bucket=bucket)
    
    # Verify file was written
    expected_path = Path(temp_storage_path) / bucket / key
    assert expected_path.exists()
    assert expected_path.read_bytes() == content

    # Test get_object_content
    retrieved_content = await provider.get_object_content(key=key, bucket=bucket)
    assert retrieved_content == content

    # Test list_objects
    objects = await provider.list_objects(prefix="test-folder", bucket=bucket)
    assert len(objects) == 1
    assert objects[0]["Key"] == "test-folder/test-file.txt"
    assert objects[0]["Size"] == len(content)

    # Test stream_object
    chunks = []
    async for chunk in provider.stream_object(key=key, bucket=bucket):
        chunks.append(chunk)
    assert b"".join(chunks) == content

    # Test get_presigned_url
    url = await provider.get_presigned_url(key=key, bucket=bucket)
    assert url == f"file://{expected_path.resolve()}"
