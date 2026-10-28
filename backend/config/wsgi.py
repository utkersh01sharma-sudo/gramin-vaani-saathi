"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

application = get_wsgi_application()

# With CELERY_TASK_ALWAYS_EAGER (the default) models run inside the web
# process, so it needs warming too. In a background thread, so the server
# accepts connections immediately; the first few requests may still wait.
if os.environ.get("AI_WARMUP") == "1":
    import threading

    from ai.warmup import warmup

    threading.Thread(target=warmup, name="ai-warmup", daemon=True).start()
