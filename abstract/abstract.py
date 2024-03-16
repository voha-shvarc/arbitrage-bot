from abc import ABC
from abc import abstractmethod
from typing import List

from db.base import Session
from db.models import CoinNetworkExchange
from db.models import Exchange
from db.models import Pair
from db.structs import DepositAddress
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
    async def get_price(self, pair: Pair, limit=10) -> tuple[list[list[str]], list[list[str]]]:
        pass

    @abstractmethod
    def get_pair_trading_volume(self, pair: Pair) -> float:
        pass

    @classmethod
    def get_db_id(cls) -> int:
        with Session() as session:
            exchange_id = session.query(Exchange.id).filter(Exchange.name == cls.NAME).scalar()
        return exchange_id

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        raise NotImplementedError()

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        raise NotImplementedError()

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        raise NotImplementedError()

    def get_pair_chart_change(self, pair: Pair) -> float:
        """Returns pair chart change for the last 15 minutes in percents"""
        raise NotImplementedError()

    def get_balance(self) -> float:
        raise NotImplementedError()

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        raise NotImplementedError()

    def withdraw(self, cne: CoinNetworkExchange, deposit_address: DepositAddress) -> bool:
        raise NotImplementedError()


class NoPriceFound(Exception):
    pass


class DepositAddressError(Exception):
    pass


class WithdrawError(Exception):
    pass
