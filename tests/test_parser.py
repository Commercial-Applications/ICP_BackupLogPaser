import os
from datetime import datetime, timezone
from pathlib import Path
import pytest
from virtnbd_parser import (
    parse_timestamp,
    determine_status,
    backup_level_from_filename,
    parse_log,
    build_line_protocol,
    vm_from_log,
    load_processed_logs,
    mark_log_as_processed,
    PROCESSED_LOGS_FILE
)
import requests

def test_parse_timestamp():
    line = "[2026-05-24 16:38:27] INFO lib common"
    expected = datetime(2026, 5, 24, 6, 38, 27, tzinfo=timezone.utc)
    assert parse_timestamp(line) == expected

    assert parse_timestamp("No timestamp here") is None

def test_determine_status():
    assert determine_status(0, 0, 0) == ("success", 0)
    assert determine_status(1, 0, 0) == ("failed", 2)
    assert determine_status(0, 1, 0) == ("failed", 2)
    assert determine_status(0, 0, 1) == ("warning", 1)
    assert determine_status(1, 1, 1) == ("failed", 2)

def test_backup_level_from_filename():
    assert backup_level_from_filename(Path("backup.full.123.log")) == "full"
    assert backup_level_from_filename(Path("backup.inc.123.log")) == "incremental"
    assert backup_level_from_filename(Path("other.log")) == "unknown"

def test_vm_from_log():
    parsed = {"vm": "my-vm", "output_path": "/path/to/vm1"}
    assert vm_from_log(parsed) == "my-vm"

    parsed = {"vm": "", "output_path": "/path/to/vm1"}
    assert vm_from_log(parsed) == "vm1"

    parsed = {"vm": "", "output_path": ""}
    assert vm_from_log(parsed) == "unknown"
    assert vm_from_log(parsed, fallback="none") == "none"

def test_parse_log_real_file():
    log_path = Path("tests/files/backup.full.05242026163826.log")
    if not log_path.exists():
        pytest.skip("Sample log file not found")
    
    result = parse_log(log_path)
    assert result["vm"] == "2404-TestServer"
    assert result["version"] == "2.38"
    assert result["backup_level"] == "full"
    assert result["total_saved_data_gib"] == 30.2
    assert result["error_count"] == 0
    assert result["warning_count"] == 0
    assert result["start_time"] == datetime(2026, 5, 24, 6, 38, 27, tzinfo=timezone.utc)
    assert result["end_time"] == datetime(2026, 5, 24, 6, 40, 5, tzinfo=timezone.utc)
    assert result["duration_sec"] == 98

def test_build_line_protocol():
    parsed = {
        "vm": "test-vm",
        "version": "1.0",
        "backup_level": "full",
        "output_path": "/tmp",
        "attached_disks": 1,
        "concurrent_processes": 1,
        "error_count": 0,
        "warning_count": 0,
        "error_message": "",
        "checkpoint_error": "",
        "backup_start_failed": 0,
        "checkpoint_name": "cp1",
        "parent_checkpoint": "",
        "total_saved_data_gib": 10.5,
        "start_time": datetime(2026, 5, 24, 10, 0, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 5, 24, 10, 5, 0, tzinfo=timezone.utc),
        "duration_sec": 300,
    }
    log_file = Path("test.log")
    line = build_line_protocol("myhost", "test-vm", log_file, 0, parsed)
    
    assert "backup_run,host=myhost,vm=test-vm,backup_level=full,program=virtnbdbackup" in line
    assert 'status="success"' in line
    assert "status_code=0i" in line
    assert "total_saved_data_gib=10.5" in line
    assert "week_number=21i" in line
    assert "year=2026i" in line

def test_state_management(tmp_path, monkeypatch):
    # Use a temporary file for processed logs
    test_file = tmp_path / ".processed_logs"
    monkeypatch.setattr("virtnbd_parser.PROCESSED_LOGS_FILE", test_file)
    
    # Initially empty
    assert load_processed_logs() == set()
    
    # Mark one
    mark_log_as_processed("log1.log")
    assert load_processed_logs() == {"log1.log"}
    
    # Mark another
    mark_log_as_processed("log2.log")
    assert load_processed_logs() == {"log1.log", "log2.log"}

def test_write_to_influx_mock(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 204
    
    from virtnbd_parser import write_to_influx
    write_to_influx("test line")
    
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0].startswith("http")
    assert kwargs["data"] == "test line"
    assert "Authorization" in kwargs["headers"]
