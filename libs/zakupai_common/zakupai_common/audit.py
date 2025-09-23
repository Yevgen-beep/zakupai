import hashlib
import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AuditLogger:
    def __init__(self, log_dir="/logs", retention_days=1095):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, "audit.log.jsonl")
        self.retention_days = retention_days

    def log_request(
        self, service: str, input_data: str, output_data: str, prompt_hash: str = None
    ):
        if not prompt_hash:
            prompt_hash = hashlib.sha256(
                (input_data + output_data).encode()
            ).hexdigest()
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": service,
            "input_data": input_data[:500],
            "output_data": output_data[:500],
            "prompt_hash": prompt_hash,
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        self._rotate_logs()

    def _rotate_logs(self):
        """Удаляет записи старше retention_days"""
        if not os.path.exists(self.log_file):
            return
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
        lines = []
        with open(self.log_file) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    ts = datetime.fromisoformat(data["timestamp"].replace("Z", ""))
                    if ts >= cutoff:
                        lines.append(line)
                except Exception as e:
                    logger.warning(f"Failed to parse audit log line: {e}")
                    continue
        with open(self.log_file, "w") as f:
            f.writelines(lines)

    def sync_to_s3(self, bucket: str, prefix: str):
        print(
            f"Syncing to S3 bucket={bucket}, prefix={prefix}"
        )  # TODO: асинхронная загрузка
