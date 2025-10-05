import json

from zakupai_common.audit import AuditLogger


def test_audit_logger(tmp_path):
    """Test that AuditLogger creates logs correctly"""
    log_dir = tmp_path / "logs"
    audit = AuditLogger(str(log_dir))
    audit.log_request("test", "input", "output")
    log_file = log_dir / "audit.log.jsonl"
    assert log_file.exists(), "Log file should be created"
    with open(log_file) as f:
        entry = json.loads(f.readline())
        assert entry["service"] == "test", "Service name should match"
        assert "timestamp" in entry, "Entry should have timestamp"
        assert entry["input_data"] == "input", "Input data should match"
        assert entry["output_data"] == "output", "Output data should match"


def test_audit_logger_truncation(tmp_path):
    """Test that long data is truncated to 500 chars"""
    log_dir = tmp_path / "logs"
    audit = AuditLogger(str(log_dir))
    long_input = "x" * 1000
    long_output = "y" * 1000
    audit.log_request("test", long_input, long_output)
    log_file = log_dir / "audit.log.jsonl"
    with open(log_file) as f:
        entry = json.loads(f.readline())
        assert len(entry["input_data"]) == 500, "Input should be truncated to 500 chars"
        assert (
            len(entry["output_data"]) == 500
        ), "Output should be truncated to 500 chars"


def test_audit_logger_custom_hash(tmp_path):
    """Test that custom prompt hash is used when provided"""
    log_dir = tmp_path / "logs"
    audit = AuditLogger(str(log_dir))
    custom_hash = "custom_test_hash"
    audit.log_request("test", "input", "output", custom_hash)
    log_file = log_dir / "audit.log.jsonl"
    with open(log_file) as f:
        entry = json.loads(f.readline())
        assert entry["prompt_hash"] == custom_hash, "Custom hash should be used"
