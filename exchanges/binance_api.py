from typing import List

from binance.spot import Spot

from db.structs import CoinNetworkExchangeDC, TradingPair
from abstract import AbstractExchange, NoPriceFound


class BinanceAPI(AbstractExchange):
    """For testing use different keys. more here https://testnet.binance.vision/"""

    NAME = "Binance"
    NOT_ALLOWED_STATUS = "BREAK"

    def __init__(self, config):
        api_key = config["BINANCE_API_KEY"]
        api_secret = config["BINANCE_API_SECRET"]
        self.client = Spot(api_key=api_key, api_secret=api_secret)

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

    def get_price(self, pair, limit=20):
        order_book = self.client.depth(symbol=pair.default_name, limit=limit)
        buy = order_book["asks"]
        sell = order_book["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    def get_coin_exchange_networks(self):
        coins_data = self.client.coin_info()

        for coin_data in coins_data:
            yield CoinNetworkExchangeDC.from_binance(coin_data)
