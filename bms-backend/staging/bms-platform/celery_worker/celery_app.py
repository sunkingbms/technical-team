from celery import Celery
from celery.schedules import crontab
from app.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()

    app = Celery(
        "bms-platform",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["celery_worker.tasks.zendesk_jobs"],
    )

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
    )

    app.conf.beat_schedule = {
        "zendesk-create-jobs": {
            "task": "zendesk.create_jobs",
            "schedule": crontab(minute="*/5"),
        },
        "zendesk-check-job-status": {
            "task": "zendesk.check_job_status",
            "schedule": crontab(minute="*/2"),
        },
    }

    return app


app = create_celery_app()
