from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def slug(value: str, limit: int = 80) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣]+", "-", value).strip("-").lower()
    return (cleaned or "item")[:limit]


def redact_secret(value: str, secret: str | None) -> str:
    return value.replace(secret, "REDACTED") if secret else value


def json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_relative_to(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(root.resolve())
    return resolved
