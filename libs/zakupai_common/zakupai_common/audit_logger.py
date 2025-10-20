import json
import logging
import sys
from datetime import datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname.lower(),
            "service": getattr(record, "service", "unknown"),
            "message": record.getMessage(),
            "procurement_type": getattr(record, "procurement_type", None),
            "compliance_flag": getattr(record, "compliance_flag", None),
            "logger": record.name,
        }
        for field in ("lot_id", "anti_dumping_percent", "endpoint"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(
            {k: v for k, v in payload.items() if v is not None}, ensure_ascii=False
        )


def get_audit_logger(service: str) -> logging.Logger:
    base_logger = logging.getLogger("audit")
    base_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    base_logger.handlers = [handler]
    base_logger.propagate = False

    class BoundAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            kwargs.setdefault("extra", {}).update(self.extra)
            return msg, kwargs

    return BoundAdapter(base_logger, {"service": service})
