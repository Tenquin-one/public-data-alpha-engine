from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


LOCAL_SECRET_ENV_KEYS = frozenset(
    {"SEOUL_OPEN_DATA_KEY", "DATA_GO_KR_SERVICE_KEY", "KMA_API_HUB_KEY"}
)


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


def load_local_env(path: Path, *, allowed_keys: frozenset[str] = LOCAL_SECRET_ENV_KEYS) -> set[str]:
    """Load a small, project-local .env without overriding the process environment."""
    if not path.is_file():
        return set()
    loaded: set[str] = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"Invalid .env entry at line {line_number}")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if key not in allowed_keys:
            continue
        try:
            values = shlex.split(raw_value, comments=True, posix=True)
        except ValueError as exc:
            raise ValueError(f"Invalid .env value at line {line_number}") from exc
        value = " ".join(values)
        if key not in os.environ:
            os.environ[key] = value
            loaded.add(key)
    return loaded
