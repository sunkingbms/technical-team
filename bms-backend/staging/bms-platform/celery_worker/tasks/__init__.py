# Celery tasks package — import all task modules here so Celery autodiscovers them.
from celery_worker.tasks import zendesk_jobs  # noqa: F401
