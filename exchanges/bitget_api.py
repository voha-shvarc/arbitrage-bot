from typing import List

from .bitget.v1.spot.market_api import MarketApi

from abstract import AbstractExchange, NoPriceFound
from db.structs import CoinNetworkExchangeDC, TradingPair


class BitgetAPI(AbstractExchange):
    NAME = "Bitget"
    ALLOWED_STATUS = "online"

    def __init__(self, config):
        api_key = config["BITGET_API_KEY"]
        api_secret = config["BITGET_API_SECRET"]
        api_passphrase = config["BITGET_API_PASSPHRASE"]
        self.client = MarketApi(api_key=api_key, api_secret_key=api_secret, passphrase=api_passphrase)

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.client.products(params={})
        trading_pairs = [
            TradingPair(base_coin=pair["baseCoin"], quote_coin=pair["quoteCoin"], exchange=self.NAME)
            for pair in pairs_info["data"]
            if self._is_valid_pair(pair)
        ]
        return trading_pairs

    def _is_valid_pair(self, pair_data):
        return pair_data["quoteCoin"] == "USDT" and pair_data["status"] == self.ALLOWED_STATUS

    def get_price(self, pair, limit=20):
        data = {
            "symbol": pair.bitget_name,
            "limit": limit,
        }
        order_book = self.client.depth(params=data)

        buy = order_book["data"]["asks"]
        sell = order_book["data"]["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    def get_coin_exchange_networks(self):
        for coin_data in self.client.currencies(params={})["data"]:
            yield CoinNetworkExchangeDC.from_bitget(coin_data)
