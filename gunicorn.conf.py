import multiprocessing
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def env_int(name, default):
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


cpu_cores = multiprocessing.cpu_count()
if cpu_cores >= 4:
    default_workers = min(cpu_cores * 2 + 1, 12)
    default_threads = 2
else:
    default_workers = max(cpu_cores * 2 + 1, 2)
    default_threads = 1


workers = env_int("GUNICORN_WORKERS", default_workers)
threads = env_int("GUNICORN_THREADS", default_threads)
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "sync")
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
timeout = env_int("GUNICORN_TIMEOUT", 120)
graceful_timeout = env_int("GUNICORN_GRACEFUL_TIMEOUT", 120)
keepalive = env_int("GUNICORN_KEEPALIVE", 5)
max_requests = env_int("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = env_int("GUNICORN_MAX_REQUESTS_JITTER", 200)
accesslog = os.getenv("GUNICORN_ACCESSLOG", str(LOG_DIR / "gunicorn.access"))
errorlog = os.getenv("GUNICORN_ERRORLOG", str(LOG_DIR / "gunicorn.err"))
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
pidfile = os.getenv("GUNICORN_PIDFILE", str(BASE_DIR / "gunicorn.pid"))
preload_app = os.getenv("GUNICORN_PRELOAD", "true").lower() in ("1", "true", "yes", "on")
reload = os.getenv("GUNICORN_RELOAD", "false").lower() in ("1", "true", "yes", "on")
