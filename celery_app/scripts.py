from datetime import date
from datetime import timedelta

from celery_app.conf import app
from db.base import Session
from db.models import CoinNetworkExchange


@app.task
def uncheck_outdated_cne():
    with Session() as session:
        checked_lifetime = timedelta(days=7)
        (
            session.query(CoinNetworkExchange)
            .filter(
                CoinNetworkExchange.is_checked == True,
                CoinNetworkExchange.checked_at < date.today() - checked_lifetime,
            )
            .update({"is_checked": False})
        )
        session.commit()
