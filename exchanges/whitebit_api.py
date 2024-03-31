from json import JSONDecodeError
from logging import getLogger
from typing import List

from whitebit import MainAccountClient
from whitebit import TradeAccountClient
from whitebit import TradeMarketClient
from whitebit.client import _create_uri

from abstract import AbstractExchange
from abstract import NoPriceFound
from abstract.abstract import DepositAddressError
from abstract.abstract import WithdrawStatus
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import CoinNetworkExchangeDC
from db.structs import DepositAddress
from db.structs import TradingPair


error_logger = getLogger("error")


class WhitebitAPI(AbstractExchange):
    NAME = "Whitebit"
    base_url = "https://whitebit.com"
    withdraw_status = WithdrawStatus.disabled

    def __init__(self, config, connection, logger=None):
        self.connection = connection
        self.logger = logger or error_logger

        api_key = config["WHITEBIT_API_KEY"]
        api_secret = config["WHITEBIT_API_SECRET"]
        self.account_client = MainAccountClient(api_key, api_secret)
        self.trade_account_client = TradeAccountClient(api_key, api_secret)
        self.market_client = TradeMarketClient(api_key, api_secret)

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.market_client.get_markets_info()
        trading_pairs = [
            TradingPair(
                base_coin=pair["stock"],
                quote_coin=pair["money"],
                exchange=self.NAME,
                base_coin_precision=int(pair["stockPrec"]),
                quote_coin_precision=int(pair["moneyPrec"]),
            )
            for pair in pairs_info["result"]
            if pair["money"] == "USDT"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        for coin_name, coin_data in self.market_client.get_assets().items():
            if coin_data.get("confirmations"):
                yield CoinNetworkExchangeDC.from_whitebit(coin_name, coin_data)

    def get_price(self, pair: Pair, limit=30) -> tuple[list[list[str]], list[list[str]]]:
        response = self.market_client.get_order_book(pair.underscored_name, limit=str(limit))
        buy = response["asks"]
        sell = response["bids"]
        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    async def async_get_price(self, pair: Pair, limit=30):
        url = self.base_url + f"/api/v4/public/orderbook/{pair.underscored_name}"
        url += _create_uri({"limit": str(limit)})

        headers = {
            "User-Agent": "python-whitebit-sdk",
            "Content-Type": "application/json",
        }
        response = await self.connection.get(url, headers=headers)
        try:
            data = response.json()
        except JSONDecodeError:
            self.logger.error(f"[whitebit] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        try:
            buy = data["asks"]
            sell = data["bids"]
        except KeyError as e:
            self.logger.error(f"[whitebit] {pair.default_name} - error parsing data {data = }\n{e}")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair: Pair) -> float:
        response = self.market_client.get_kline(market=pair.underscored_name, interval="30m", limit="48")
        total = sum([float(volume[5]) for volume in response["result"]])
        return total

    def get_pair_chart_change(self, pair) -> float:
        response = self.market_client.get_kline(market=pair.underscored_name, interval="1m", limit="10")
        opened = float(response["result"][0][1])
        closed = float(response["result"][-1][2])
        change = (closed - opened) / opened * 100
        return change

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://whitebit.com/trade/{pair.dashed_name}?type=spot&tab=open-orders"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://whitebit.com/deposit?ticker={cne.coin.name}&method=address&network={cne.network.name}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://whitebit.com/withdraw?ticker={cne.coin.name}&network={cne.network.name}"
        return link

    def get_balance(self, coin_name: str = "USDT") -> float:
        data = self.trade_account_client.get_balance(coin_name)
        return float(data["available"])

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        uri = "/api/v4/main-account/address"
        try:
            data = self.account_client._request(
                "POST",
                uri=uri,
                params={"ticker": cne.coin.name, "network": cne.network.name},
                auth=True,
            )
            address = DepositAddress(data["account"]["address"], data["account"].get("memo"))
        except Exception as e:
            self.logger.error(f"[bybit] deposit address error - {e}")
            raise DepositAddressError() from e
        else:
            return address
