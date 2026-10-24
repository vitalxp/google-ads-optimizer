from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"


def ensure_env_file(path: Path = ENV_PATH) -> Path:
    if path.exists():
        return path
    if ENV_EXAMPLE.exists():
        path.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        path.write_text("", encoding="utf-8")
    return path


def read_env(path: Path = ENV_PATH) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data


def _format_value(value: str) -> str:
    text = str(value)
    if any(ch in text for ch in " \t#\"'"):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def upsert_env(updates: dict[str, str], path: Path = ENV_PATH) -> Path:
    """Create or update keys in .env without dropping other lines."""
    ensure_env_file(path)
    clean = {str(k).strip(): "" if v is None else str(v).strip() for k, v in updates.items() if k}
    lines = path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if stripped and not stripped.startswith("#") and "=" in raw:
            key = raw.split("=", 1)[0].strip()
            if key in clean:
                out.append(f"{key}={_format_value(clean[key])}")
                seen.add(key)
                continue
        out.append(raw)
    for key, value in clean.items():
        if key not in seen:
            out.append(f"{key}={_format_value(value)}")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return path
