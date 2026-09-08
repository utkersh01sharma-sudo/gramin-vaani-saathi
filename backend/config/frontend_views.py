"""Serve the PWA shell from Django.

The frontend is plain HTML/CSS/ES modules with no build step, so Django can hand
it out directly. That is a deliberate choice, not a shortcut: a service worker
must be served from the origin root to claim a scope of "/", and one process
serving both the app and the API removes CORS and port juggling from the demo.

Anything that is not an API route falls through to index.html, which is what
lets the PWA route client-side and still deep-link.
"""
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse

FRONTEND_DIR = Path(settings.PROJECT_ROOT) / "frontend"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".mp3": "audio/mpeg",
}


def _resolve(relative: str) -> Path | None:
    """Resolve inside FRONTEND_DIR only. Rejects traversal outside the tree."""
    candidate = (FRONTEND_DIR / relative).resolve()
    root = FRONTEND_DIR.resolve()
    if root not in candidate.parents and candidate != root:
        return None
    return candidate if candidate.is_file() else None


def serve_frontend(request, path: str = ""):
    if not FRONTEND_DIR.is_dir():
        raise Http404("Frontend not built.")

    target = _resolve(path) if path else None
    if target is None:
        target = _resolve("index.html")
    if target is None:
        return HttpResponse(
            "frontend/index.html is missing.", status=501, content_type="text/plain"
        )

    response = FileResponse(
        target.open("rb"),
        content_type=CONTENT_TYPES.get(target.suffix, "application/octet-stream"),
    )
    if target.name in {"sw.js", "index.html"}:
        # The service worker and the shell must never be served stale, or a user
        # keeps running last week's app after a deploy.
        response["Cache-Control"] = "no-cache"
    return response
