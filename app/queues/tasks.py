import asyncio
import nest_asyncio

from celery import Task

from .worker import celery_app
from config.logger import logger
from config.database import get_db
from config.models import Datasource
from utils.crawler import crawl_urls_task_async
from config.settings import SETTINGS
from config.vector_db import vector_db
from datetime import datetime

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
def crawl_urls_task(
    self, knowledge_base_id: int, urls: list[str], datasource_ids: list[int]
) -> str:
    """Crawl URLs and update datasource status"""
    db = next(get_db())

    try:
        # ✅ Check if any datasource was deleted before starting
        active_datasource_ids = []
        for ds_id in datasource_ids:
            datasource = db.query(Datasource).filter(Datasource.id == ds_id).first()
            if datasource and datasource.deleted_at is None:
                active_datasource_ids.append(ds_id)
                datasource.status = "processing"
                db.commit()
            elif datasource and datasource.deleted_at is not None:
                logger.info(f"Datasource {ds_id} was deleted, skipping processing")
        
        # ✅ If all datasources were deleted, exit early
        if not active_datasource_ids:
            logger.info("All datasources were deleted, cancelling task")
            return "Task cancelled - all datasources deleted"

        # Crawl URLs
        file_path = asyncio.run(crawl_urls_task_async(urls))
        
        # ✅ Check again before expensive vector DB operation
        db_active_ids = []
        for ds_id in active_datasource_ids:
            datasource = db.query(Datasource).filter(Datasource.id == ds_id).first()
            if datasource and datasource.deleted_at is None:
                db_active_ids.append(ds_id)
            else:
                logger.info(f"Datasource {ds_id} deleted during crawling")
        
        if not db_active_ids:
            logger.info("All datasources deleted during crawling, skipping vector DB ingestion")
            return "Task cancelled - datasources deleted during processing"
        
        documents = vector_db.load_and_split(file_path)
        vector_db.ingest_documents(documents)

        # Update remaining active datasources to completed
        for ds_id in db_active_ids:
            datasource = db.query(Datasource).filter(Datasource.id == ds_id).first()
            if datasource and datasource.deleted_at is None:
                datasource.status = "completed"
                datasource.processed_at = datetime.now()
                db.commit()

        return "URLs crawled and ingested to Vector DB successfully!"

    except Exception as e:
        # Update all datasources to failed
        for ds_id in datasource_ids:
            datasource = db.query(Datasource).filter(Datasource.id == ds_id).first()
            if datasource:
                datasource.status = "failed"
                datasource.error_message = str(e)
                db.commit()
        raise e
    finally:
        db.close()


@celery_app.task(bind=True, base=BaseTask, name="tasks.upload_file_task")
def upload_file_task(
    self, knowledge_base_id: int, file_path: str, datasource_id: int
) -> str:
    """Upload file and update datasource status"""
    import os

    db = next(get_db())
    datasource = None

    try:
        # Get datasource and check if deleted
        datasource = db.query(Datasource).filter(Datasource.id == datasource_id).first()
        
        # ✅ Check if datasource was deleted before processing
        if not datasource or datasource.deleted_at is not None:
            logger.info(f"Datasource {datasource_id} was deleted, skipping processing")
            return "Task cancelled - datasource deleted"
        
        # Update to processing
        datasource.status = "processing"
        db.commit()

        # Process file (load and split)
        documents = vector_db.load_and_split(file_path)
        
        # ✅ Check again before expensive vector DB ingestion
        db.refresh(datasource)
        if datasource.deleted_at is not None:
            logger.info(f"Datasource {datasource_id} deleted during file processing")
            return "Task cancelled - datasource deleted during processing"
        
        vector_db.ingest_documents(documents)

        # ✅ Final check before marking as completed
        db.refresh(datasource)
        if datasource.deleted_at is None:
            datasource.status = "completed"
            datasource.processed_at = datetime.now()
            db.commit()
            return "File ingested to Vector DB successfully!"
        else:
            logger.info(f"Datasource {datasource_id} deleted after processing")
            return "Task completed but datasource was deleted"

    except Exception as e:
        # Update datasource to failed (only if not deleted)
        if datasource:
            db.refresh(datasource)
            if datasource.deleted_at is None:
                datasource.status = "failed"
                datasource.error_message = str(e)
                db.commit()
        raise e
    finally:
        # Clean up temporary files
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {file_path}: {e}")

        db.close()
