from concurrent.futures import ThreadPoolExecutor

from redis import Redis
from rq import Queue

from src.api.config import get_api_settings
from src.api.worker_tasks import run_ats_optimize_job, run_resume_job


_local_executor = ThreadPoolExecutor(max_workers=2)


def enqueue_resume_job(job_id: str) -> str:
    settings = get_api_settings()

    if settings.redis_url:
        try:
            redis_connection = Redis.from_url(settings.redis_url)
            queue = Queue(name=settings.queue_name, connection=redis_connection, default_timeout=900)
            queue.enqueue("src.api.worker_tasks.run_resume_job", job_id)
            return "redis-rq"
        except Exception:
            # Keep local threaded fallback for development continuity.
            pass

    _local_executor.submit(run_resume_job, job_id)
    return "local-thread"


def enqueue_ats_optimize_job(job_id: str) -> str:
    settings = get_api_settings()

    if settings.redis_url:
        try:
            redis_connection = Redis.from_url(settings.redis_url)
            queue = Queue(name=settings.queue_name, connection=redis_connection, default_timeout=900)
            queue.enqueue("src.api.worker_tasks.run_ats_optimize_job", job_id)
            return "redis-rq"
        except Exception:
            pass

    _local_executor.submit(run_ats_optimize_job, job_id)
    return "local-thread"
