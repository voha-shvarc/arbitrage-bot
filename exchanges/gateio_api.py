from typing import List

from gate_api import Configuration, ApiClient, SpotApi

from db.structs import CoinNetworkExchangeDC, TradingPair
from abstract import AbstractExchange, NoPriceFound


class GateIOAPI(AbstractExchange):
    NAME = "GateIO"

    def __init__(self, config):
        api_config = ApiClient(Configuration())
        self.spot_client = SpotApi(api_config)

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

    def get_price(self, pair, limit=20):
        res = self.spot_client.list_order_book(pair.gateio_name)
        buy = res.asks
        sell = res.bids
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell
