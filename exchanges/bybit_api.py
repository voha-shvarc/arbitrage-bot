from typing import List

from pybit.unified_trading import HTTP

from abstract import AbstractExchange, NoPriceFound
from db.structs import CoinNetworkExchangeDC, TradingPair


import logging


error_log = logging.getLogger("error")
class BybitAPI(AbstractExchange):
    NAME = "ByBit"
    base_url = "https://api.bybit.com"

    def __init__(self, config, connection):
        self.connection = connection

        api_key = config["BYBIT_API_KEY"]
        api_secret = config["BYBIT_API_SECRET"]
        self.session = HTTP(api_key=api_key, api_secret=api_secret, testnet=False)

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.session.get_instruments_info(category="spot")
        trading_pairs = [
            TradingPair(base_coin=pair["baseCoin"], quote_coin=pair["quoteCoin"], exchange=self.NAME)
            for pair in pairs_info["result"]["list"]
            if pair["quoteCoin"] == "USDT"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        # TODO: maybe check coin for presence in db
        for coin_data in self.session.get_coin_info()["result"]["rows"]:
            try:
                yield CoinNetworkExchangeDC.from_bybit(coin_data)
            except IndexError:
                continue

    def get_price(self, pair, limit=20):
        res = self.session.get_orderbook(symbol=pair.default_name, limit=limit, category="spot")
        buy = res["result"]["a"]
        sell = res["result"]["b"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, symbol, limit=20):
        url = self.base_url + "/v5/market/orderbook"
        body = {
            "symbol": symbol.default_name,
            "limit": limit,
            "category": "spot",
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = await self.connection.get(url, params=body, headers=headers)
        try:
            data = response.json()
        except Exception:
            error_log.info(f"[bybit] - {response}")
            raise NoPriceFound()

        try:
            buy = data['result']['a']
            sell = data['result']['b']
        except KeyError as e:
            error_log.info(f"[bybit] eror response - {data}")
            raise NoPriceFound()
        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair) -> float:
        data = self.session.get_tickers(symbol=pair.default_name, category="spot")
        return float(data["result"]["list"][0]["volume24h"])
