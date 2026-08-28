from celery import Celery

from .config import settings

celery_app = Celery(
    "revguard_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Tracking + visibility for long-running QA tasks (30-120s)
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=580,
    # Worker fairness for long tasks
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Queues
    task_default_queue="revguard_default",
)

# Ensure our tasks modules are discovered
celery_app.autodiscover_tasks(["app.worker", "app.explore_worker", "app.graph_worker"])
