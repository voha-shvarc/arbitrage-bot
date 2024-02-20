from typing import List

from binance.spot import Spot

from abstract import AbstractExchange, NoPriceFound
from db.structs import CoinNetworkExchangeDC, TradingPair


class BinanceAPI(AbstractExchange):
    """For testing use different keys. more here https://testnet.binance.vision/"""

    NAME = "Binance"
    NOT_ALLOWED_STATUS = "BREAK"
    base_url = "https://api.binance.com"

    def __init__(self, config, connection):
        self.connection = connection

        self.api_key = config["BINANCE_API_KEY"]
        api_secret = config["BINANCE_API_SECRET"]
        self.client = Spot(api_key=self.api_key, api_secret=api_secret)

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.client.exchange_info(permissions=["SPOT"])
        trading_pairs = [
            TradingPair(base_coin=pair["baseAsset"], quote_coin=pair["quoteAsset"], exchange=self.NAME)
            for pair in pairs_info["symbols"]
            if self._is_valid_pair(pair)
        ]
        return trading_pairs

    def _is_valid_pair(self, coin_data):
        return (
            coin_data["isSpotTradingAllowed"]
            and coin_data["quoteAsset"] == "USDT"
            and coin_data["status"] != self.NOT_ALLOWED_STATUS
        )

    def get_coin_exchange_networks(self):
        for coin_data in self.client.coin_info():
            yield CoinNetworkExchangeDC.from_binance(coin_data)

    def get_price(self, pair, limit=30):
        order_book = self.client.depth(symbol=pair.default_name, limit=limit)
        buy = order_book["asks"]
        sell = order_book["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, symbol, limit=30):
        url = self.base_url + "/api/v3/depth"
        body = {
            "symbol": symbol.default_name,
            "limit": limit,
        }
        headers = {
            "Content-Type": "application/json;charset=utf-8",
            "User-Agent": "binance-connector-python/3.3.1",
            "X-MBX-APIKEY": self.api_key,
        }
        response = await self.connection.get(url, params=body, headers=headers)
        data = response.json()

        buy = data["asks"]
        sell = data["bids"]
        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair) -> float:
        data = self.client.ticker_24hr(symbol=pair.default_name)
        return float(data["volume"])
