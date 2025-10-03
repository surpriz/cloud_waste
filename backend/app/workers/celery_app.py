"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Create Celery application
celery_app = Celery(
    "cloudwaste",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL),
    include=["app.workers.tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
)

# Celery Beat schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    "daily-scan-all-accounts": {
        "task": "app.workers.tasks.scheduled_scan_all_accounts",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2:00 AM UTC
    },
}

if __name__ == "__main__":
    celery_app.start()
