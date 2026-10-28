import os

from celery import Celery
from celery.signals import worker_process_init

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("gramin_vaani")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_process_init.connect
def _warm_models(**_kwargs):
    """Load every model when a worker process starts, not on its first task.

    AI_WARMUP=0 skips it (CI, or a worker that only runs non-ML tasks).
    """
    if os.environ.get("AI_WARMUP", "1") == "0":
        return
    from ai.warmup import warmup

    warmup(include_asr=True)
