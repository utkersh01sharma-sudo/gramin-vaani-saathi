"""Load every model before the first request needs it.

Each adapter loads lazily, which keeps management commands and tests fast. The
price is paid by whichever user happens to arrive first -- and it is not small:
measured on the 4070, the multilingual encoder plus the scheme index is ~8 s,
MuRIL ~2 s, Whisper ~4 s. A first-time user who asks "मुझे खेती के लिए पैसा
चाहिए" and waits ten seconds has learned that the voice button is broken.

So worker processes call warmup() at start. It is also what the latency
benchmark calls before timing anything, so its "warm" numbers mean all models
resident, not "everything except whichever model the first query touched".
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


def warmup(include_asr: bool = False) -> dict[str, int]:
    """Load models and run one tiny inference through each. Returns ms per model."""
    from ai.registry import get_embedder, get_nlu, get_scam

    timings: dict[str, int] = {}

    def timed(name, fn):
        started = time.perf_counter()
        try:
            fn()
        except Exception:  # noqa: BLE001 -- a missing model degrades, it does not stop the worker
            logger.exception("warmup: %s failed; it will fall back at request time", name)
        timings[name] = int((time.perf_counter() - started) * 1000)

    timed("intent", lambda: get_nlu().predict("मेरा बैलेंस बताओ", "hi"))
    timed("scam", lambda: get_scam().classify("Your OTP is 123456. Do not share it.", "en"))

    def schemes():
        from apps.schemes import retrieval

        retrieval.search("money for farming", get_embedder(), k=1)

    timed("embedder+scheme_index", schemes)

    if include_asr:
        from ai.registry import get_asr

        asr = get_asr()
        timed("asr", lambda: getattr(asr, "_load", lambda: None)())

    logger.info("warmup done: %s", timings)
    return timings
