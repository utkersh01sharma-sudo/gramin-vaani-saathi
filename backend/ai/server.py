"""A standalone model server: the other end of AI_BACKEND=remote.

    python backend/ai/server.py --port 9000

Hosts the same local adapters the web process would otherwise load, behind a
small JSON-over-HTTP interface. Running the models here instead of in every web
or Celery process is the scaling story: GPU memory is paid once per model
server rather than once per worker, web replicas become small and CPU-only, and
the model tier scales on its own (more servers behind a load balancer).

Standard library only -- no FastAPI, no extra dependency to install on the GPU
box. ThreadingHTTPServer handles concurrent requests; PyTorch inference
releases the GIL, so threads are adequate for a demo-scale deployment.

Endpoints (all JSON unless noted):

    GET  /health                       -> which models are loaded
    POST /v1/nlu   {text, language}    -> IntentPrediction
    POST /v1/scam  {text, language}    -> ScamVerdict + headline/advice
    POST /v1/asr   raw audio body      -> Transcript
                   headers X-Language, X-Filename

If AI_REMOTE_KEY is set, every request must carry it in X-Model-Key. The
server should still sit on a private network; the key stops accidents, not an
attacker who can already reach the box.
"""
from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import sys
import tempfile
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
# This process IS the model tier: it must never forward to itself.
os.environ["AI_BACKEND"] = "local"

import django  # noqa: E402

django.setup()

from ai.registry import get_asr, get_nlu, get_scam  # noqa: E402
from ai.warmup import warmup  # noqa: E402

logger = logging.getLogger("ai.server")
MAX_JSON = 64 * 1024
MAX_AUDIO = 8 * 1024 * 1024
KEY = os.environ.get("AI_REMOTE_KEY", "")


class Handler(BaseHTTPRequestHandler):
    server_version = "VaaniModelServer/1.0"

    def log_message(self, fmt, *args):  # route through logging, not stderr
        logger.info("%s %s", self.address_string(), fmt % args)

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorised(self) -> bool:
        if not KEY:
            return True
        return hmac.compare_digest(self.headers.get("X-Model-Key", ""), KEY)

    def _body(self, limit: int) -> bytes | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > limit:
            return None
        return self.rfile.read(length)

    def do_GET(self):  # noqa: N802
        if self.path != "/health":
            return self._send(404, {"detail": "not found"})
        nlu = get_nlu()
        scam = get_scam()
        self._send(200, {
            "ok": True,
            "nlu": getattr(nlu, "active_backend", getattr(nlu, "name", "")),
            "scam": getattr(scam, "active_backend", getattr(scam, "name", "")),
        })

    def do_POST(self):  # noqa: N802
        if not self._authorised():
            return self._send(401, {"detail": "bad model key"})
        try:
            if self.path == "/v1/asr":
                return self._asr()
            raw = self._body(MAX_JSON)
            if raw is None:
                return self._send(413, {"detail": "body missing or too large"})
            data = json.loads(raw)
            text, language = str(data.get("text", ""))[:2000], data.get("language", "hi")
            if self.path == "/v1/nlu":
                nlu = get_nlu()
                pred = nlu.predict(text, language)
                return self._send(200, {**asdict(pred),
                                        "backend": getattr(nlu, "active_backend", nlu.name)})
            if self.path == "/v1/scam":
                scam = get_scam()
                verdict = scam.classify(text, language)
                return self._send(200, {**asdict(verdict), **scam.explain(verdict, language),
                                        "backend": scam.active_backend})
            return self._send(404, {"detail": "not found"})
        except (ValueError, json.JSONDecodeError) as exc:
            return self._send(400, {"detail": str(exc)})
        except Exception:  # noqa: BLE001
            logger.exception("model server error on %s", self.path)
            return self._send(500, {"detail": "internal error"})

    def _asr(self):
        raw = self._body(MAX_AUDIO)
        if raw is None:
            return self._send(413, {"detail": "audio missing or too large"})
        suffix = Path(self.headers.get("X-Filename", "clip.webm")).suffix[:8] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(raw)
            path = handle.name
        try:
            transcript = get_asr().transcribe(path, self.headers.get("X-Language") or None)
            return self._send(200, asdict(transcript))
        finally:
            os.unlink(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Gramin Vaani Saathi model server")
    ap.add_argument("--host", default=os.environ.get("AI_SERVER_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("AI_SERVER_PORT", "9000")))
    ap.add_argument("--no-warmup", action="store_true")
    ap.add_argument("--asr", action="store_true", help="also load Whisper at start")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if not args.no_warmup:
        warmup(include_asr=args.asr)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    logger.info("model server on http://%s:%d", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
