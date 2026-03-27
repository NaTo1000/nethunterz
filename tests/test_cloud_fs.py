"""Tests for cloud filesystem and provider sync modules."""
from __future__ import annotations

import pytest

from cloud.cloud_fs import (
    CloudFilesystem,
    SyncConfig,
    SyncProvider,
    ConflictStrategy,
    SyncEntry,
    BLCKJACK_FOLDER_STRUCTURE,
)
from cloud.gdrive_sync import GDriveSync, GDriveConfig
from cloud.onedrive_sync import OneDriveSync, OneDriveConfig
from cloud.vps_sync import VPSSync, VPSConfig


# ---------------------------------------------------------------------------
# CloudFilesystem tests
# ---------------------------------------------------------------------------

def test_cloud_fs_initialisation():
    fs = CloudFilesystem(simulation=True)
    status = fs.get_status()
    assert status["provider"] == SyncProvider.GOOGLE_DRIVE.value
    assert status["simulation"] is True
    assert status["indexed_files"] == 0


def test_cloud_fs_create_blckjack_structure(tmp_path):
    fs = CloudFilesystem(simulation=True)
    created = fs.create_blckjack_structure(tmp_path)
    assert len(created) == len(BLCKJACK_FOLDER_STRUCTURE)
    for d in created:
        assert d.exists()
        assert d.is_dir()


def test_cloud_fs_index_file(tmp_path):
    fs = CloudFilesystem(simulation=True)
    f = tmp_path / "config.json"
    f.write_bytes(b'{"key": "value"}')
    entry = fs.index_file(f)
    assert entry.local_path == str(f)
    assert len(entry.sha256) == 64
    assert entry.size_bytes == len(b'{"key": "value"}')
    assert not entry.synced


def test_cloud_fs_get_delta_all_new(tmp_path):
    fs = CloudFilesystem(simulation=True)
    for i in range(3):
        f = tmp_path / f"file_{i}.bin"
        f.write_bytes(b"data" * (i + 1))
        fs.index_file(f)
    delta = fs.get_delta()
    assert len(delta) == 3


def test_cloud_fs_get_delta_no_changes(tmp_path):
    fs = CloudFilesystem(simulation=True)
    f = tmp_path / "test.bin"
    f.write_bytes(b"test data")
    entry = fs.index_file(f)
    # Simulate already-synced remote index
    fs._remote_index[str(f)] = entry
    delta = fs.get_delta()
    assert len(delta) == 0


def test_cloud_fs_encrypt_decrypt_roundtrip():
    fs = CloudFilesystem(simulation=True)
    plaintext = b"BLCKjACK secret configuration data"
    encrypted = fs.encrypt_file(plaintext)
    assert encrypted != plaintext
    decrypted = fs.decrypt_file(encrypted)
    assert decrypted == plaintext


def test_cloud_fs_conflict_local_wins():
    fs = CloudFilesystem(
        config=SyncConfig(conflict_strategy=ConflictStrategy.LOCAL_WINS),
        simulation=True,
    )
    local = SyncEntry("local.bin", "remote/local.bin", "sha_a", 100, last_modified=2.0)
    remote = SyncEntry("local.bin", "remote/local.bin", "sha_b", 100, last_modified=1.0)
    winner = fs.resolve_conflict(local, remote)
    assert winner is local


def test_cloud_fs_conflict_remote_wins():
    fs = CloudFilesystem(
        config=SyncConfig(conflict_strategy=ConflictStrategy.REMOTE_WINS),
        simulation=True,
    )
    local = SyncEntry("local.bin", "remote/local.bin", "sha_a", 100, last_modified=2.0)
    remote = SyncEntry("local.bin", "remote/local.bin", "sha_b", 100, last_modified=1.0)
    winner = fs.resolve_conflict(local, remote)
    assert winner is remote


def test_cloud_fs_conflict_newest_wins():
    fs = CloudFilesystem(
        config=SyncConfig(conflict_strategy=ConflictStrategy.NEWEST_WINS),
        simulation=True,
    )
    local = SyncEntry("local.bin", "remote/local.bin", "sha_a", 100, last_modified=5.0)
    remote = SyncEntry("local.bin", "remote/local.bin", "sha_b", 100, last_modified=3.0)
    winner = fs.resolve_conflict(local, remote)
    assert winner is local


@pytest.mark.asyncio
async def test_cloud_fs_sync_once(tmp_path):
    fs = CloudFilesystem(simulation=True)
    fs.create_blckjack_structure(tmp_path)
    f = tmp_path / "BLCKjACK" / "logs" / "test.log"
    f.write_bytes(b"log data" * 10)
    fs.index_file(f)

    stats = await fs.sync_once()
    assert stats.files_uploaded == 1
    assert stats.bytes_transferred > 0
    assert stats.errors == 0


@pytest.mark.asyncio
async def test_cloud_fs_sync_skips_unchanged(tmp_path):
    fs = CloudFilesystem(simulation=True)
    f = tmp_path / "config.bin"
    f.write_bytes(b"config")
    entry = fs.index_file(f)
    fs._remote_index[str(f)] = entry  # Mark as already synced
    stats = await fs.sync_once()
    assert stats.files_uploaded == 0


# ---------------------------------------------------------------------------
# GDriveSync tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gdrive_authenticate_simulation():
    gd = GDriveSync(simulation=True)
    result = await gd.authenticate()
    assert result is True
    assert gd._authenticated is True


def test_gdrive_get_auth_url():
    gd = GDriveSync(config=GDriveConfig(client_id="test_client"))
    url = gd.get_auth_url()
    assert url.startswith("https://accounts.google.com/")
    assert "test_client" in url


@pytest.mark.asyncio
async def test_gdrive_create_folder_structure():
    gd = GDriveSync(simulation=True)
    await gd.authenticate()
    folders = await gd.create_folder_structure()
    assert len(folders) >= 7
    assert "BLCKjACK" in folders


@pytest.mark.asyncio
async def test_gdrive_upload():
    gd = GDriveSync(simulation=True)
    await gd.authenticate()
    file_id = await gd.upload("BLCKjACK/logs/test.log", b"log content")
    assert file_id is not None
    assert "sim_file" in file_id


@pytest.mark.asyncio
async def test_gdrive_download():
    gd = GDriveSync(simulation=True)
    await gd.authenticate()
    data = await gd.download("sim_file_001")
    assert data is not None
    assert len(data) > 0


@pytest.mark.asyncio
async def test_gdrive_list_folder():
    gd = GDriveSync(simulation=True)
    await gd.authenticate()
    items = await gd.list_folder("BLCKjACK/logs")
    assert isinstance(items, list)
    assert len(items) >= 1


def test_gdrive_status():
    gd = GDriveSync(simulation=True)
    status = gd.get_status()
    assert status["simulation"] is True
    assert status["authenticated"] is False


# ---------------------------------------------------------------------------
# OneDriveSync tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_onedrive_authenticate_simulation():
    od = OneDriveSync(simulation=True)
    result = await od.authenticate()
    assert result is True
    assert od._authenticated is True


def test_onedrive_get_auth_url():
    od = OneDriveSync(config=OneDriveConfig(client_id="ms_client"))
    url = od.get_auth_url()
    assert url.startswith("https://login.microsoftonline.com/")


@pytest.mark.asyncio
async def test_onedrive_create_folder_structure():
    od = OneDriveSync(simulation=True)
    await od.authenticate()
    folders = await od.create_folder_structure()
    assert len(folders) >= 7


@pytest.mark.asyncio
async def test_onedrive_upload():
    od = OneDriveSync(simulation=True)
    await od.authenticate()
    item_id = await od.upload("BLCKjACK/firmware_backups/fw.bin", b"firmware_data")
    assert item_id is not None


@pytest.mark.asyncio
async def test_onedrive_upload_large():
    od = OneDriveSync(simulation=True)
    await od.authenticate()
    large_data = b"X" * 1_000_000
    item_id = await od.upload_large("BLCKjACK/model_data/model.bin", large_data)
    assert item_id is not None


@pytest.mark.asyncio
async def test_onedrive_download():
    od = OneDriveSync(simulation=True)
    await od.authenticate()
    data = await od.download("sim_od_item_001")
    assert data is not None


# ---------------------------------------------------------------------------
# VPSSync tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vps_connect_simulation():
    vps = VPSSync(simulation=True)
    result = await vps.connect()
    assert result is True
    assert vps._connected is True


@pytest.mark.asyncio
async def test_vps_disconnect():
    vps = VPSSync(simulation=True)
    await vps.connect()
    await vps.disconnect()
    assert vps._connected is False


def test_vps_generate_install_script():
    vps = VPSSync(simulation=True)
    script = vps.generate_install_script()
    assert "BLCKjACK" in script
    assert "docker-compose" in script
    assert "#!/usr/bin/env bash" in script


def test_vps_generate_docker_compose():
    vps = VPSSync(simulation=True)
    compose = vps.generate_docker_compose()
    assert "blckjack-cloud" in compose
    assert "aes256" in compose


@pytest.mark.asyncio
async def test_vps_run_install_script():
    vps = VPSSync(simulation=True)
    await vps.connect()
    result = await vps.run_install_script()
    assert result is True


@pytest.mark.asyncio
async def test_vps_upload():
    vps = VPSSync(simulation=True)
    await vps.connect()
    result = await vps.upload(b"config data", "configurations/config.json")
    assert result is True
    assert len(vps._uploaded_paths) == 1


@pytest.mark.asyncio
async def test_vps_download():
    vps = VPSSync(simulation=True)
    await vps.connect()
    data = await vps.download("logs/test.log")
    assert data is not None
    assert len(data) > 0


@pytest.mark.asyncio
async def test_vps_list_directory():
    vps = VPSSync(simulation=True)
    await vps.connect()
    items = await vps.list_directory("logs")
    assert isinstance(items, list)
    assert len(items) >= 1


def test_vps_status():
    vps = VPSSync(config=VPSConfig(host="192.168.1.100", port=2222), simulation=True)
    status = vps.get_status()
    assert status["host"] == "192.168.1.100"
    assert status["port"] == 2222
    assert status["simulation"] is True
    assert status["connected"] is False
