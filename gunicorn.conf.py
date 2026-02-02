import os

bind = os.getenv("BIND", "0.0.0.0:8000")
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_class = "gthread"
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
