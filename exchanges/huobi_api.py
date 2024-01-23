from typing import List

from huobi.client.generic import GenericClient
from huobi.client.market import MarketClient
from huobi.constant import InstrumentStatus, DepthStep

from db.structs import CoinNetworkExchangeDC, TradingPair
from exchanges.abstract import AbstractExchange, NoPriceFound


class HuobiAPI(AbstractExchange):
    NAME = "Huobi"

    def __init__(self, config):
        self.client = GenericClient()
        self.price_client = MarketClient()

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.client.get_exchange_symbols()
        trading_pairs = [
            TradingPair(
                base_coin=pair.base_currency.upper(), quote_coin=pair.quote_currency.upper(), exchange=self.NAME
            )
            for pair in pairs_info
            if pair.state == "online"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        for coin_data in self.client.get_reference_currencies():
            if coin_data.instStatus == InstrumentStatus.NORMAL:
                yield CoinNetworkExchangeDC.from_huobi(coin_data)

    def get_price(self, pair, limit=20):
        try:
            depth = self.price_client.get_pricedepth(pair.huobi_name, DepthStep.STEP0, limit)
        except Exception:
            raise NoPriceFound()

        buy = [(ask.price, ask.amount) for ask in depth.asks]
        sell = [(bid.price, bid.amount) for bid in depth.bids]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell
