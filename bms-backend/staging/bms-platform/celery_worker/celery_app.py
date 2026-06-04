from celery import Celery
from app.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    
    app = Celery(
        "bms-platform",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
    )
    
    return app

app = create_celery_app()