"""Bounded public-cache refresh. Never reads private account records."""
import logging
import threading
from datetime import timedelta
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from .models import FeedState
from .discovery import refresh
_guard = threading.Lock()
_log = logging.getLogger(__name__)

def _run():
    close_old_connections()
    try:
        result = refresh(min_interval=170)
        _log.info("Public job refresh completed: %s", result)
    except Exception:
        _log.exception("Public job refresh failed; previous cache retained")
    finally:
        close_old_connections()
        _guard.release()

def maybe_refresh():
    if not settings.AUTO_JOB_REFRESH:
        return False
    state = FeedState.objects.filter(key='refresh').first()
    if state and state.attempted and timezone.now()-state.attempted < timedelta(minutes=170):
        return False
    if not _guard.acquire(blocking=False):
        return False
    try:
        threading.Thread(target=_run, name='public-job-refresh', daemon=True).start()
    except Exception:
        _guard.release()
        raise
    return True
