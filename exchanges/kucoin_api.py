from typing import List

from kucoin.client import MarketData

from abstract import AbstractExchange, NoPriceFound
from db.structs import CoinNetworkExchangeDC, TradingPair


class KuCoinAPI(AbstractExchange):
    NAME = "KuCoin"

    def __init__(self, config):
        api_key = config["KUCOIN_API_KEY"]
        api_secret = config["KUCOIN_API_SECRET"]
        api_passphrase = config["KUCOIN_API_PASSPHRASE"]
        self.client = MarketData(api_key, api_secret, api_passphrase)

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.client.get_symbol_list_v2()
        trading_pairs = [
            TradingPair(base_coin=pair["baseCurrency"], quote_coin=pair["quoteCurrency"], exchange=self.NAME)
            for pair in pairs_info
            if self._is_valid_pair(pair)
        ]
        return trading_pairs

    @staticmethod
    def _is_valid_pair(coin_data):
        return coin_data["enableTrading"] and coin_data["quoteCurrency"] == "USDT"

    def get_price(self, pair, limit=20):
        # the sdk depth is 100. but need only 20
        order_book = self.client._request(
            "GET", "/api/v3/market/orderbook/level2_20", params={"symbol": pair.dashed_name}
        )
        buy = order_book["asks"]
        sell = order_book["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    def get_coin_exchange_networks(self):
        for coin_data in self.client._request("GET", "/api/v3/currencies"):
            yield CoinNetworkExchangeDC.from_kucoin(coin_data)

    def get_pair_trading_volume(self, pair) -> float:
        data = self.client.get_24h_stats(symbol=pair.dashed_name)
        return float(data["vol"])
