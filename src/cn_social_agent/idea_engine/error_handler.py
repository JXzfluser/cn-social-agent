from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ErrorInfo:
    connector_id: str
    error_type: str
    message: str
    timestamp: datetime
    retry_count: int = 0
    last_retry: Optional[datetime] = None


class ErrorHandler:
    def __init__(self, max_retries: int = 3, retry_delay: int = 60):
        self._errors: dict[str, list[ErrorInfo]] = {}
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    def record_error(
        self,
        connector_id: str,
        error_type: str,
        message: str,
    ) -> None:
        if connector_id not in self._errors:
            self._errors[connector_id] = []

        error_info = ErrorInfo(
            connector_id=connector_id,
            error_type=error_type,
            message=message,
            timestamp=datetime.now(),
        )
        self._errors[connector_id].append(error_info)

        if len(self._errors[connector_id]) > 100:
            self._errors[connector_id] = self._errors[connector_id][-100:]

        logger.error(f"[{connector_id}] {error_type}: {message}")

    def should_retry(self, connector_id: str) -> bool:
        errors = self._errors.get(connector_id, [])
        if not errors:
            return True

        recent_errors = [
            e for e in errors
            if (datetime.now() - e.timestamp).seconds < self._retry_delay * 60
        ]

        return len(recent_errors) < self._max_retries

    def get_error_stats(self, connector_id: str) -> dict[str, Any]:
        errors = self._errors.get(connector_id, [])
        if not errors:
            return {"total": 0, "recent": 0, "last_error": None}

        recent = [
            e for e in errors
            if (datetime.now() - e.timestamp).seconds < 3600
        ]

        return {
            "total": len(errors),
            "recent": len(recent),
            "last_error": {
                "type": errors[-1].error_type,
                "message": errors[-1].message,
                "timestamp": errors[-1].timestamp.isoformat(),
            } if errors else None,
        }

    def clear_errors(self, connector_id: str) -> None:
        self._errors.pop(connector_id, None)


error_handler = ErrorHandler()
