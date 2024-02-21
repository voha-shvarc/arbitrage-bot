from typing import List

from huobi.client.generic import GenericClient
from huobi.client.market import MarketClient
from huobi.constant import InstrumentStatus, DepthStep

from abstract import AbstractExchange, NoPriceFound
from db.structs import CoinNetworkExchangeDC, TradingPair


class HuobiAPI(AbstractExchange):
    NAME = "Huobi"
    base_url = "https://api.huobi.pro"

    def __init__(self, config, connection):
        self.connection = connection

        self.client = GenericClient()
        self.price_client = MarketClient(init_log=True)

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

    def get_price(self, pair, limit=30):
        try:
            depth = self.price_client.get_pricedepth(pair.huobi_name, DepthStep.STEP0, limit)
        except Exception:
            raise NoPriceFound()

        buy = [(ask.price, ask.amount) for ask in depth.asks]
        sell = [(bid.price, bid.amount) for bid in depth.bids]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, symbol, limit=20):
        url = self.base_url + "/market/depth"
        body = {
            "symbol": symbol.huobi_name,
            "depth": limit,
            "type": DepthStep.STEP0,
        }
        response = await self.connection.get(url, params=body)
        data = response.json()

        if data.get("err-msg") in ["invalid symbol", "request limit"]:
            raise NoPriceFound()

        buy = data["tick"]["asks"]
        sell = data["tick"]["bids"]
        if not sell or not buy:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair) -> float:
        data = self.price_client.get_market_detail_merged(symbol=pair.huobi_name)
        return data.amount
