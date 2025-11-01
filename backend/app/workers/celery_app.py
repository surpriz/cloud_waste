"""Celery application configuration."""

import asyncio

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

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
    beat_schedule_filename="/tmp/celerybeat-schedule",  # Celery Beat schedule file
)


# Celery Beat schedule
# Check every hour if any accounts need to be scanned based on their schedule
celery_app.conf.beat_schedule = {
    "check-scheduled-scans": {
        "task": "app.workers.tasks.check_and_trigger_scheduled_scans",
        "schedule": crontab(minute=0),  # Every hour at minute 0
    },
    "cleanup-unverified-accounts": {
        "task": "app.workers.tasks.cleanup_unverified_accounts",
        "schedule": crontab(hour=3, minute=0),  # Every day at 3:00 AM UTC
    },
    "update-pricing-cache": {
        "task": "app.workers.tasks.update_pricing_cache",
        "schedule": crontab(hour=2, minute=0),  # Every day at 2:00 AM UTC
    },
}

if __name__ == "__main__":
    celery_app.start()
