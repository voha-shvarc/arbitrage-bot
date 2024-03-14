from json import JSONDecodeError
from logging import getLogger
from typing import List

from bingX.spot import Spot

from abstract import AbstractExchange
from abstract import NoPriceFound
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import CoinNetworkExchangeDC
from db.structs import TradingPair


error_log = getLogger("error")


class BingxAPI(AbstractExchange):
    NAME = "Bingx"

    def __init__(self, config, connection):
        self.connection = connection

        api_key = config["BINGX_API_KEY"]
        api_secret = config["BINGX_API_SECRET"]
        self.client = Spot(api_key, api_secret)

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.client.symbols()
        trading_pairs = [
            TradingPair(
                base_coin=pair["symbol"].split("-")[0],
                quote_coin=pair["symbol"].split("-")[1],
                exchange=self.NAME,
            )
            for pair in pairs_info["symbols"]
            if pair["symbol"].split("-")[1] == "USDT"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        for coin_data in self.client.get("/openApi/wallets/v1/capital/config/getall")["data"]:
            yield CoinNetworkExchangeDC.from_bingx(coin_data)

    def get_price(self, pair: Pair, limit=30) -> tuple[list[list[str]], list[list[str]]]:
        response = self.client.depth(symbol=pair.dashed_name, limit=limit)
        buy = response["asks"]
        sell = response["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=30):
        path = "/openApi/spot/v1/market/depth"
        params = {"symbol": pair.dashed_name, "limit": limit}
        url = f"{self.client.base_url}{path}?{self.client._handle_params(params, path, 'GET')}"

        response = await self.connection.get(url, headers=self.client.headers)
        try:
            data = response.json()
        except JSONDecodeError:
            error_log.error(f"[bingx] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        try:
            buy = data["data"]["asks"]
            sell = data["data"]["bids"]
        except KeyError as e:
            error_log.error(f"[bingx] {pair.default_name} - error parsing data {data =}\n{e}")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair: Pair) -> float:
        response = self.client.get(
            "/openApi/spot/v1/ticker/24hr",
            params={"symbol": pair.dashed_name},
        )
        return response["data"][0]["volume"]

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://bingx.com/en-us/spot/{pair.default_name}"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = "https://bingx.com/en-us/assets/recharge"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = "https://bingx.com/en-us/assets/withdraw/"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.client.get(
            "/openApi/spot/v2/market/kline",
            params={"symbol": "BTC-USDT", "interval": "1m", "limit": 15},
        )
        opened = response["data"][-1][1]
        closed = response["data"][0][4]
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self) -> float:
        """data = client.assets()"""
        return 0
