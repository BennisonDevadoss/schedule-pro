from celery import Celery

from config.settings import SETTINGS

celery_app = Celery(
    "worker",
    broker=f"sqla+{str(SETTINGS.BROKER_HOST)}",
    backend=f"db+{SETTINGS.DATABASE_URL}",
    # broker=SETTINGS.REDIS_BASE_URL,
    # backend=SETTINGS.REDIS_BASE_URL,
)

celery_app.autodiscover_tasks(["queues"])

# If you need to set any other Celery options
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",
    task_routes={
        "tasks.crawl_urls_task": {"queue": "crawler"},
        "tasks.upload_file_task": {"queue": "document"},
    },
    # Increase task timeout to handle long-running embedding operations
    # task_soft_time_limit=600,  # 10 minutes soft limit
    # task_time_limit=900,  # 15 minutes hard limit
    # # Disable prefetching to avoid blocking other tasks
    # worker_prefetch_multiplier=1,
)

# PYTHONPATH=. celery -A queues.worker worker --loglevel=info -Q emails,priority_high,default

# # Worker only for emails
# PYTHONPATH=. celery -A worker.worker.celery_app worker --loglevel=info -Q emails

# # Worker for priority tasks
# PYTHONPATH=. celery -A worker.worker.celery_app worker --loglevel=info -Q priority_high

# # Worker for default
# PYTHONPATH=. celery -A worker.worker.celery_app worker --loglevel=info -Q default
