from abc import ABC
from abc import abstractmethod
from typing import List

from aiolimiter import AsyncLimiter

from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import DepositAddress
from db.structs import TradingPair


class WithdrawStatus:
    enabled = ""
    whitelist = "📝"
    disabled = "🛠"


class DepositStatus:
    enabled = ""
    disabled = "📪"


class AbstractExchange(ABC):
    NAME = None
    async_limiter = AsyncLimiter(20, 0.2)  # 100r/1s
    withdraw_status = WithdrawStatus.whitelist
    deposit_status = DepositStatus.enabled

    @abstractmethod
    def get_trading_pairs(self) -> List[TradingPair]:
        raise NotImplementedError()

    @abstractmethod
    def get_coin_exchange_networks(self):
        raise NotImplementedError()

    @abstractmethod
    def get_price(self, pair: Pair, limit=30) -> tuple[list[list[str]], list[list[str]]]:
        raise NotImplementedError()

    @abstractmethod
    async def async_get_price(self, pair: Pair, limit=10) -> tuple[list[list[str]], list[list[str]]]:
        raise NotImplementedError()

    @abstractmethod
    def get_pair_trading_volume(self, pair: Pair) -> float:
        raise NotImplementedError()

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

    def withdraw(self, cne: CoinNetworkExchange, ccy_quantity: float, deposit_address: DepositAddress) -> bool:
        raise NotImplementedError()

    def create_order(
        self,
        pair: Pair,
        ccy_quantity: float,
        ccy_precision: int,
        price: float,
        price_precision: int,
        spot_fee: float,
    ):
        raise NotImplementedError()


class NoPriceFound(Exception):
    pass


class DepositAddressError(Exception):
    pass


class WithdrawError(Exception):
    pass


class CreateOrderError(Exception):
    pass
