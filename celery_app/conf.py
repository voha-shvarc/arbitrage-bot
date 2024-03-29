import os

from celery import Celery
from dotenv import load_dotenv


load_dotenv()

app = Celery(
    "tasks",
    include=["celery_app.sync", "celery_app.tasks"],
    broker=f"redis://default:{os.getenv('REDIS_PASSWORD')}@{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}",
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
    # "send_analytics": {
    #     "task": "celery_app.tasks.send_analytics",
    #     "schedule": 60 * 10,  # every 10 minutes
    # },
}
