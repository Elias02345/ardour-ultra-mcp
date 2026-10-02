import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        value = {"level": record.levelname, "logger": record.name, "event": record.getMessage()}
        for field in ["command", "success", "duration_ms", "error_type"]:
            if hasattr(record, field):
                value[field] = getattr(record, field)
        if record.exc_info:
            value["exception"] = self.formatException(record.exc_info)
        return json.dumps(value, ensure_ascii=True)


def configure_logging(debug: bool = False) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING, handlers=[handler], force=True
    )
