from json import JSONDecodeError
from logging import getLogger
from typing import List

from huobi.client.account import AccountClient
from huobi.client.generic import GenericClient
from huobi.client.market import MarketClient
from huobi.constant import DepthStep
from huobi.constant import InstrumentStatus

from abstract import AbstractExchange
from abstract import NoPriceFound
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import CoinNetworkExchangeDC
from db.structs import TradingPair


error_log = getLogger("error")


class HuobiAPI(AbstractExchange):
    NAME = "Huobi"
    base_url = "https://api.huobi.pro"

    def __init__(self, config, connection):
        self.connection = connection

        api_key = config["HUOBI_API_KEY"]
        api_secret = config["HUOBI_API_SECRET"]

        self.client = GenericClient(api_key=api_key, secret_key=api_secret)
        self.price_client = MarketClient(api_key=api_key, secret_key=api_secret)
        self.account_client = AccountClient(api_key=api_key, secret_key=api_secret)

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.client.get_exchange_symbols()
        trading_pairs = [
            TradingPair(
                base_coin=pair.base_currency.upper(),
                quote_coin=pair.quote_currency.upper(),
                exchange=self.NAME,
            )
            for pair in pairs_info
            if pair.state == "online"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        for coin_data in self.client.get_reference_currencies():
            if coin_data.instStatus == InstrumentStatus.NORMAL:
                yield CoinNetworkExchangeDC.from_huobi(coin_data)

    def get_price(self, pair: Pair, limit=30) -> tuple[list[list[str]], list[list[str]]]:
        try:
            depth = self.price_client.get_pricedepth(pair.huobi_name, DepthStep.STEP0, limit)
        except Exception:
            raise NoPriceFound()

        buy = [[str(ask.price), str(ask.amount)] for ask in depth.asks]
        sell = [[str(bid.price), str(bid.amount)] for bid in depth.bids]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=20):
        url = self.base_url + "/market/depth"
        body = {
            "symbol": pair.huobi_name,
            "depth": limit,
            "type": DepthStep.STEP0,
        }
        response = await self.connection.get(url, params=body)
        try:
            data = response.json()
        except JSONDecodeError:
            error_log.error(f"[huobi] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        if data.get("err-msg") in ["invalid symbol", "request limit"]:
            error_log.error(f"[huobi] {pair.default_name} - {data['err-msg']}")
            raise NoPriceFound()

        try:
            buy = data["tick"]["asks"]
            sell = data["tick"]["bids"]
        except KeyError as e:
            error_log.error(f"[huobi] {pair.default_name} - error parsing data {data =}\n{e}")
            raise NoPriceFound()

        if not sell or not buy:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair) -> float:
        data = self.price_client.get_market_detail_merged(symbol=pair.huobi_name)
        return data.amount

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.htx.com/en-us/trade/{pair.underscored_name.lower()}?type=spot"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.htx.com/en-us/finance/deposit/{cne.coin.name.lower()}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.htx.com/en-us/finance/withdraw/{cne.coin.name.lower()}"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.price_client.get_candlestick(symbol=pair.huobi_name, period="1min", size=15)
        opened = response[-1].open
        closed = response[0].close
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self) -> float:
        response = self.account_client.get_account_asset_valuation("spot", "USD")
        return float(response.balance)
