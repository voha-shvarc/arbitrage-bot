from abc import ABC, abstractmethod
from typing import List

from db.base import Session
from db.models import Exchange
from db.structs import TradingPair


class AbstractExchange(ABC):
    NAME = None

    @abstractmethod
    def get_trading_pairs(self) -> List[TradingPair]:
        pass

    @abstractmethod
    def get_coin_exchange_networks(self):
        pass

    @abstractmethod
    def get_price(self, pair, limit=10):
        pass

    @property
    def db_id(self):
        with Session() as session:
            exchange_id = session.query(Exchange.id).filter(Exchange.name == self.NAME).scalar()
        return exchange_id


class NoPriceFound(Exception):
    pass
