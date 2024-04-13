import os

from celery import Celery
from dotenv import load_dotenv


load_dotenv()

app = Celery(
    "tasks",
    include=["celery_app.sync", "celery_app.tasks"],
    broker=f"redis://{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}",
)


app.conf.beat_schedule = {
    "sync_pairs": {
        "task": "celery_app.sync.sync_pairs",
        "schedule": 60 * 30,  # every 30 minutes
    },
    "sync_coin_exchange_networks": {
        "task": "celery_app.sync.sync_coin_exchange_networks",
        "schedule": 60 * 19,  # every 19 minutes
    },
    "sync_spot__withdraw_fees": {
        "task": "celery_app.sync.sync_spot__withdraw_fees",
        "schedule": 60 * 60 * 24,  # every 24 hours
    },
    "uncheck_outdated_cne": {
        "task": "celery_app.scripts.uncheck_outdated_cne",
        "schedule": 60 * 60 * 24,  # every 24 hours
    },
}
