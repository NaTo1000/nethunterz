"""
Tests for Cloud Filesystem Integration.
"""
import pytest
from cloud import CloudConfig, CloudFilesystem, CloudProvider


@pytest.fixture
def google_drive_fs():
    return CloudFilesystem.setup_google_drive(root_path="/test_nethunterz")


@pytest.fixture
def onedrive_fs():
    return CloudFilesystem.setup_onedrive(root_path="/test_nethunterz")


@pytest.fixture
def vps_fs():
    return CloudFilesystem.setup_vps(
        host="localhost",
        username="test",
        key_path="/tmp/test.key",
        root_path="/test_nethunterz",
    )


# ── Factory Tests ─────────────────────────────────────────────────────────────

def test_google_drive_factory(google_drive_fs):
    assert google_drive_fs.config.provider == CloudProvider.GOOGLE_DRIVE
    assert google_drive_fs.config.root_path == "/test_nethunterz"


def test_onedrive_factory(onedrive_fs):
    assert onedrive_fs.config.provider == CloudProvider.ONEDRIVE


def test_vps_factory(vps_fs):
    assert vps_fs.config.provider == CloudProvider.VPS_SFTP


def test_encryption_enabled_by_default(google_drive_fs):
    assert google_drive_fs.config.encryption_enabled is True


# ── Connection Tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_google_drive(google_drive_fs):
    result = await google_drive_fs.connect()
    assert result is True
    assert google_drive_fs._connected is True


@pytest.mark.asyncio
async def test_connect_onedrive(onedrive_fs):
    result = await onedrive_fs.connect()
    assert result is True


# ── Install Tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_install_google_drive(google_drive_fs):
    result = await google_drive_fs.install()
    assert result is True


@pytest.mark.asyncio
async def test_install_vps(vps_fs):
    result = await vps_fs.install()
    assert result is True


# ── Upload Tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_file(google_drive_fs):
    await google_drive_fs.connect()
    data = b"test data content"
    cloud_file = await google_drive_fs.upload_file(
        "/tmp/test.txt", data, "operations"
    )
    assert cloud_file.size_bytes == len(data)
    assert cloud_file.encrypted is True
    assert len(cloud_file.checksum) == 64


@pytest.mark.asyncio
async def test_upload_increments_stats(google_drive_fs):
    await google_drive_fs.connect()
    await google_drive_fs.upload_file("/tmp/f1.txt", b"data1")
    await google_drive_fs.upload_file("/tmp/f2.txt", b"data2")
    stats = google_drive_fs.get_stats()
    assert stats["files_uploaded"] == 2


@pytest.mark.asyncio
async def test_upload_without_encryption():
    config = CloudConfig(
        provider=CloudProvider.GOOGLE_DRIVE,
        encryption_enabled=False,
        root_path="/test",
    )
    fs = CloudFilesystem(config)
    await fs.connect()
    cf = await fs.upload_file("/tmp/plain.txt", b"plain data")
    assert cf.encrypted is False


# ── Encryption Tests ──────────────────────────────────────────────────────────

def test_encryption_layer(google_drive_fs):
    data = b"sensitive data"
    encrypted = google_drive_fs.encryption.encrypt(data)
    decrypted = google_drive_fs.encryption.decrypt(encrypted)
    assert decrypted == data


def test_checksum_consistency(google_drive_fs):
    data = b"test data"
    c1 = google_drive_fs.encryption.compute_checksum(data)
    c2 = google_drive_fs.encryption.compute_checksum(data)
    assert c1 == c2
    assert len(c1) == 64


# ── Stats Tests ───────────────────────────────────────────────────────────────

def test_initial_stats(google_drive_fs):
    stats = google_drive_fs.get_stats()
    assert stats["files_uploaded"] == 0
    assert stats["total_bytes"] == 0
    assert stats["provider"] == "google_drive"
    assert stats["encrypted"] is True
