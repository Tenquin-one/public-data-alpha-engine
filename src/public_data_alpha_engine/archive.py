from __future__ import annotations

import io
import json
import re
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


_NAMESPACE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def validate_namespace(namespace: str) -> str:
    """Keep every seed inside one predictable data-branch subtree."""
    if not _NAMESPACE.fullmatch(namespace):
        raise ValueError(f"invalid archive namespace: {namespace!r}")
    return namespace


def namespace_path(output_root: Path, kind: str, namespace: str, *parts: str | Path) -> Path:
    if kind not in {"bundles", "runs", "state"}:
        raise ValueError(f"invalid archive kind: {kind!r}")
    validate_namespace(namespace)
    return output_root / kind / namespace / Path(*parts)


def read_json_state(path: Path, *, namespace: str | None = None) -> dict[str, Any]:
    if not path.exists():
        value: dict[str, Any] = {"version": 1}
        if namespace:
            value["namespace"] = validate_namespace(namespace)
        return value
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"state must be an object: {path}")
    if namespace and value.get("namespace", namespace) != namespace:
        raise ValueError(f"state namespace mismatch: {path}")
    return value


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def schedule_health(
    state: dict[str, Any],
    now: datetime,
    *,
    cadence_seconds: int,
    gap_threshold_multiplier: float = 2.5,
) -> dict[str, Any]:
    previous_value = state.get("updated_at")
    if not isinstance(previous_value, str):
        return {
            "status": "NO_BASELINE",
            "cadence_seconds": cadence_seconds,
            "previous_run_at": None,
            "elapsed_seconds": None,
            "late_by_seconds": 0,
            "missed_intervals": 0,
        }
    try:
        previous = datetime.fromisoformat(previous_value)
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=UTC)
        previous = previous.astimezone(UTC)
    except ValueError:
        return {
            "status": "INVALID_BASELINE",
            "cadence_seconds": cadence_seconds,
            "previous_run_at": previous_value,
            "elapsed_seconds": None,
            "late_by_seconds": 0,
            "missed_intervals": 0,
        }
    elapsed = max(0, round((now - previous).total_seconds()))
    threshold = cadence_seconds * gap_threshold_multiplier
    return {
        "status": "WARNING" if elapsed > threshold else "OK",
        "cadence_seconds": cadence_seconds,
        "previous_run_at": previous.isoformat(),
        "elapsed_seconds": elapsed,
        "late_by_seconds": max(0, elapsed - cadence_seconds),
        "missed_intervals": max(0, elapsed // cadence_seconds - 1),
    }


def add_bytes(archive: tarfile.TarFile, name: str, content: bytes, mtime: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mtime = mtime
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(content))
