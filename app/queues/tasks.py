import asyncio
import nest_asyncio

from celery import Task

from .worker import celery_app
from config.logger import logger
from utils.crawler import crawl_urls_task_async
from config.settings import SETTINGS
from config.vector_db import vector_db

# Enable nested event loops for Celery workers
# This allows async operations (like GoogleGenerativeAI embeddings) to work in Celery tasks
nest_asyncio.apply()


class BaseTask(Task):
    autoretry_for = (Exception,)  # Retry for all unhandled exceptions
    retry_kwargs = {"max_retries": SETTINGS.MAX_RETRIES, "countdown": 10}
    retry_backoff = True  # Exponential backoff
    retry_jitter = True  # Add random jitter to avoid thundering herd
    default_retry_delay = 10  # seconds

    def on_success(self, retval, task_id, args, kwargs) -> None:
        logger.info(f"[{task_id}] ✅ Task completed successfully.")
        super().on_success(retval, task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:
        logger.error(f"[{task_id}] ❌ Task failed with error: {exc}")
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo) -> None:
        logger.warning(f"[{task_id}] 🔁 Task is being retried due to: {exc}")
        super().on_retry(exc, task_id, args, kwargs, einfo)


@celery_app.task(bind=True, base=BaseTask, name="tasks.crawl_urls_task")
def crawl_urls_task(self, collection_name: str, urls: list[str]) -> None:
    file_path = asyncio.run(crawl_urls_task_async(urls))  # 👈 wrap async logic
    documents = vector_db.load_and_split(file_path)
    vector_db.ingest_documents(documents)
    return "Website is been ingested to Vector DB successfully!!!"


@celery_app.task(bind=True, base=BaseTask, name="tasks.upload_file_task")
def upload_file_task(self, collection_name: str, file_path: str) -> str:
    documents = vector_db.load_and_split(file_path)
    vector_db.ingest_documents(documents)
    return "File is been ingested to Vector DB successfully!!!"
