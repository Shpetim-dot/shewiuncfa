"""Universal entrypoint for serverless hosts (Vercel) and for local runs.

Vercel imports whatever file it detects (index.py at the root, or api/index.py) and looks for
a callable named `app`. The application lives in the `app/` package, which may be next to this
file, one level up, or - in a flat upload - be the same directory with `cfa_core.py` next to it.
Both layouts are supported; if the code is genuinely missing, this module serves a readable
503 page instead of crashing the function with a stack trace.
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEARCH = [HERE, HERE.parent, Path.cwd()]


def _find_layout() -> tuple[Path | None, str | None]:
    for base in SEARCH:
        if (base / "app" / "main.py").is_file():
            return base, "package"
    for base in SEARCH:
        if (base / "cfa_core.py").is_file() and (base / "main.py").is_file():
            return base, "flat"
    return None, None


ROOT, LAYOUT = _find_layout()


def _fallback(reason: str):
    """Minimal ASGI app explaining the problem instead of a bare 500."""
    body = ('{"status":"error","detail":"' + reason.replace('"', "'") +
            '","fix":"deploy the whole repository: the app/ folder is required"}').encode()

    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 503,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    return app


if ROOT is None:
    app = _fallback("the application package was not found next to the entrypoint")
else:
    sys.path.insert(0, str(ROOT))
    if "app" not in sys.modules:
        pkg = types.ModuleType("app")
        pkg.__path__ = [str(ROOT / "app") if LAYOUT == "package" else str(ROOT)]
        pkg.__file__ = str((ROOT / "app" / "__init__.py")) if LAYOUT == "package" else str(ROOT / "__init__.py")
        sys.modules["app"] = pkg
    from app.main import app  # noqa: E402,F401  (the name hosts look for)

__all__ = ["app"]
