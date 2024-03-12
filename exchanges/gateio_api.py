from json import JSONDecodeError
from logging import getLogger
from typing import List

from gate_api import ApiClient
from gate_api import Configuration
from gate_api import SpotApi
from gate_api import WalletApi

from abstract import AbstractExchange
from abstract import NoPriceFound
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import CoinNetworkExchangeDC
from db.structs import TradingPair


error_log = getLogger("error")


class GateIOAPI(AbstractExchange):
    NAME = "GateIO"
    base_url = "https://api.gateio.ws"

    def __init__(self, config, connection):
        self.connection = connection

        api_key = config["GATEIO_API_KEY"]
        secret_key = config["GATEIO_API_SECRET"]
        api_config = ApiClient(Configuration(key=api_key, secret=secret_key))
        self.spot_client = SpotApi(api_config)
        self.account_client = WalletApi(api_config)

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.spot_client.list_currency_pairs()
        trading_pairs = [
            TradingPair(base_coin=pair.base, quote_coin=pair.quote, exchange=self.NAME)
            for pair in pairs_info
            if pair.quote == "USDT" and pair.trade_status == "tradable"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        for coin_data in self.spot_client.list_currencies():
            if not coin_data.delisted:
                yield CoinNetworkExchangeDC.from_gateio(coin_data)

    def get_price(self, pair: Pair, limit=30) -> tuple[list[list[str]], list[list[str]]]:
        res = self.spot_client.list_order_book(pair.underscored_name)
        buy = res.asks
        sell = res.bids
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=30):
        url = self.base_url + "/api/v4/spot/order_book"
        body = {
            "currency_pair": pair.underscored_name,
            "limit": limit,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = await self.connection.get(url, params=body, headers=headers)
        try:
            data = response.json()
        except JSONDecodeError:
            error_log.error(f"[gateio] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        try:
            buy = data["asks"]
            sell = data["bids"]
        except KeyError as e:
            error_log.error(f"[gateio] {pair.default_name} - error parsing data {data =}\n{e}")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()

        return data["asks"], data["bids"]

    def get_pair_trading_volume(self, pair: Pair) -> float:
        data = self.spot_client.list_tickers(currency_pair=pair.underscored_name)
        return float(data[0].base_volume)

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.gate.io/trade/{pair.underscored_name}"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.gate.io/ru/myaccount/deposit/{cne.coin.name}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.gate.io/ru/myaccount/withdraw/{cne.coin.name}"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.spot_client.list_candlesticks(
            currency_pair=pair.underscored_name,
            interval="1m",
            limit=3,
        )
        opened = float(response[0][5])
        closed = float(response[0][2])
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self) -> float:
        balance = self.account_client.get_total_balance()
        return float(balance.total.amount)
