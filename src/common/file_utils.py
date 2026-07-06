from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


INVALID_FILENAME_CHARS = r'[<>:"/\\|?*]'


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def timestamp_for_run() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sanitize_filename(value: str, fallback: str = "untitled") -> str:
    cleaned = re.sub(INVALID_FILENAME_CHARS, "_", value).strip()
    cleaned = cleaned.rstrip(".")
    return cleaned or fallback


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=json_default),
        encoding="utf-8",
    )


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def find_latest_run_dir(outputs_root: Path, exclude: Path | None = None) -> Path | None:
    candidates = []
    for pattern in ("output_*", "run_*"):
        for path in outputs_root.glob(pattern):
            if not path.is_dir():
                continue
            if exclude and path.resolve() == exclude.resolve():
                continue
            candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda path: (path.stat().st_mtime_ns, path.name))
    for path in reversed(candidates):
        if path.name.startswith("output_"):
            return path
    return candidates[-1]


def find_latest_run_dir_with_marker(
    outputs_root: Path, marker: Path, exclude: Path | None = None
) -> Path | None:
    candidates = []
    for pattern in ("output_*", "run_*"):
        for path in outputs_root.glob(pattern):
            if not path.is_dir():
                continue
            if exclude and path.resolve() == exclude.resolve():
                continue
            if not (path / marker).exists():
                continue
            candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda path: (path.stat().st_mtime_ns, path.name))
    for path in reversed(candidates):
        if path.name.startswith("output_"):
            return path
    return candidates[-1]
