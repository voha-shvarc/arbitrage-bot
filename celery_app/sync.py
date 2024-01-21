from dotenv import dotenv_values
from sqlalchemy import or_, and_

from celery_app.conf import app
from db.base import Session
from db.models import Exchange, PairExchange, Coin
from db.models import Network
from db.models import Pair, CoinNetworkExchange
from db.utils import get_or_create
from exchanges import BinanceAPI, BybitAPI, OkxAPI, GateIOAPI, HuobiAPI

config = dotenv_values(".env")

EXCHANGES = {BinanceAPI, BybitAPI, OkxAPI, GateIOAPI, HuobiAPI}


@app.task
def sync_coin_exchange_networks():
    with Session() as session:
        for exchange_api in EXCHANGES:
            print(f"Syncing {exchange_api.NAME}...")
            exchange_api = exchange_api(config)
            exchange, created = get_or_create(session, Exchange, name=exchange_api.NAME)
            for cen_dataclass in exchange_api.get_coin_exchange_networks():
                coin, created = get_or_create(session, Coin, name=cen_dataclass.coin_name)
                for i, network_dataclass in enumerate(cen_dataclass.networks):
                    network, created = get_or_create(session, Network, name=network_dataclass.name)

                    coin_network_exchange = (session.query(CoinNetworkExchange.id)
                                             .filter(CoinNetworkExchange.exchange_id == exchange.id)
                                             .filter(CoinNetworkExchange.coin_id == coin.id)
                                             .filter(CoinNetworkExchange.network_id == network.id)
                                             .one_or_none())

                    new = CoinNetworkExchange(**cen_dataclass.to_db(exchange, coin, network, i))
                    if not coin_network_exchange:
                        session.add(new)
                    else:
                        new.id = coin_network_exchange.id
                        session.merge(new)
        session.commit()

    with Session() as session:
        subq = session.query(CoinNetworkExchange.id) \
            .join(CoinNetworkExchange.coin) \
            .join(CoinNetworkExchange.exchange) \
            .join(CoinNetworkExchange.network) \
            .filter(
                or_(
                    and_(Exchange.name == "GateIO", Coin.name == "GTC"),
                    and_(Network.name == 'BSC', Coin.name == 'BABYDOGE'),
                    and_(Exchange.name == "GateIO", Coin.name == "PEPE2")
                )
            )
        session.query(CoinNetworkExchange).filter(CoinNetworkExchange.id.in_(subq)).update({"can_withdraw": False}, synchronize_session=False)

        session.query(CoinNetworkExchange) \
            .filter(CoinNetworkExchange.withdraw_fee == None) \
            .update({"can_withdraw": False, "withdraw_fee": 0}, synchronize_session=False)

        session.commit()


@app.task
def sync_pairs():
    with Session() as session:
        quote_coin, created = get_or_create(session, Coin, name="USDT")
        for exchange_api in EXCHANGES:
            print(f"Syncing {exchange_api.NAME}...")
            exchange_api = exchange_api(config)

            exchange, created = get_or_create(session, Exchange, name=exchange_api.NAME)
            pairs = exchange_api.get_trading_pairs()
            base_coins = {pair.base_coin for pair in pairs}

            existing_base_coins = session.query(Coin.name) \
                .join(Pair, Coin.id == Pair.base_coin_id) \
                .join(PairExchange) \
                .filter(PairExchange.exchange_id == exchange.id) \
                .all()

            solution_temporary = [coin.name for coin in existing_base_coins]
            diff_coins = base_coins.difference(solution_temporary)
            for new_coin in diff_coins:
                base_coin, created = get_or_create(session, Coin, name=new_coin)
                pair, _ = get_or_create(session, Pair, base_coin_id=base_coin.id, quote_coin_id=quote_coin.id)
                pair_exchange, _ = get_or_create(session, PairExchange, pair_id=pair.id, exchange_id=exchange.id)

        session.commit()
