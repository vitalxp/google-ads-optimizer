from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any


def check_http_url(url: str, *, timeout: float = 8.0) -> dict[str, Any]:
    """HEAD then GET. Returns ok=True only for HTTP 2xx."""
    target = str(url or "").strip()
    if not target:
        return {"ok": False, "url": target, "error": "URL is empty"}
    if not target.lower().startswith(("http://", "https://")):
        return {"ok": False, "url": target, "error": "URL must start with http:// or https://"}
    last_error = "request failed"
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(
            target,
            method=method,
            headers={"User-Agent": "AdsOptimizer-URLCheck/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = int(getattr(resp, "status", 200) or 200)
                final = str(resp.geturl() or target)
                ok = 200 <= code < 300
                return {
                    "ok": ok,
                    "url": target,
                    "final_url": final,
                    "status": code,
                    "error": None if ok else f"HTTP {code}",
                }
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if method == "HEAD" and exc.code in {403, 405}:
                continue
            return {
                "ok": False,
                "url": target,
                "final_url": target,
                "status": int(exc.code),
                "error": last_error,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)[:200]
            if method == "HEAD":
                continue
    return {"ok": False, "url": target, "error": last_error}


def require_working_url(url: str) -> dict[str, Any]:
    result = check_http_url(url)
    if not result.get("ok"):
        raise ValueError(
            f"Landing URL is not reachable ({result.get('error') or 'failed'}): {url}. "
            "Fix the page (HTTP 200) before publishing — Google rejects DESTINATION_NOT_WORKING."
        )
    return result
