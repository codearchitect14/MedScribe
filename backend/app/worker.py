from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("medscribe", broker=settings.redis_url, backend=settings.redis_url)

# Nightly analytics rollup (plan.md Phase 7): runs at 02:00 UTC, well after
# a normal clinic day ends anywhere reasonable, rolling up "yesterday" for
# every active organization. Run `celery -A app.worker beat` alongside the
# worker to actually fire this on schedule; POST /analytics/rollup triggers
# the same task on demand without waiting for it.
celery_app.conf.beat_schedule = {
    "nightly-analytics-rollup": {
        "task": "compute_analytics_rollups",
        "schedule": crontab(hour=2, minute=0),
    },
}
celery_app.conf.timezone = "UTC"

# Import side effect: registers the task with celery_app so both the worker
# and `beat_schedule` above (which references it by name) can find it.
from app.tasks import analytics_rollup, bulk_reprocess  # noqa: E402,F401
