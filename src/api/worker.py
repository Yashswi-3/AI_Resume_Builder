from redis import Redis
from rq import Connection, Worker

from src.api.config import get_api_settings


def main() -> None:
    settings = get_api_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is not configured. Set REDIS_URL to run worker mode.")

    connection = Redis.from_url(settings.redis_url)
    with Connection(connection):
        worker = Worker([settings.queue_name])
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
