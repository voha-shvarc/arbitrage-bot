from celery import Celery

app = Celery('tasks', include=['celery_app.sync', 'celery_app.tasks'], broker='redis://redis:6379')


app.conf.beat_schedule = {
    "sync_pairs": {
        "task": "celery_app.sync.sync_pairs",
        "schedule": 60 * 9,  # every 9 minutes
    },
    "sync_coin_exchange_networks": {
        "task": "celery_app.sync.sync_coin_exchange_networks",
        "schedule": 60 * 5,  # every 5 minutes
    },
    "send_analytics": {
        "task": "celery_app.tasks.send_analytics",
        "schedule": 60 * 13,  # every 13 minutes
    },
}
