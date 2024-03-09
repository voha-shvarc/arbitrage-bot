import base64
import hashlib
import hmac
import time
from typing import List

from kucoin.client import MarketData

from abstract import AbstractExchange
from abstract import NoPriceFound
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import CoinNetworkExchangeDC
from db.structs import TradingPair


class KuCoinAPI(AbstractExchange):
    NAME = "KuCoin"
    base_url = "https://api.kucoin.com"

    def __init__(self, config, connection):
        self.connection = connection

        self.api_key = config["KUCOIN_API_KEY"]
        self.api_secret = config["KUCOIN_API_SECRET"]
        self.api_passphrase = config["KUCOIN_API_PASSPHRASE"]
        self.client = MarketData(self.api_key, self.api_secret, self.api_passphrase)

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

    def get_price(self, pair: Pair, limit=20) -> tuple[list[list[str]], list[list[str]]]:
        # the sdk depth is 100. but need only 20
        order_book = self.client._request(
            "GET",
            "/api/v3/market/orderbook/level2_20",
            params={"symbol": pair.dashed_name},
        )
        buy = order_book["asks"]
        sell = order_book["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, symbol, limit=20):
        url = self.base_url + "/api/v3/market/orderbook/level2_20"
        uri_path = f"/api/v3/market/orderbook/level2_20?symbol={symbol.dashed_name}"
        body = {
            "symbol": symbol.dashed_name,
        }
        now_time = int(time.time()) * 1000
        sign = self.sign(self.pre_hash(now_time, "GET", uri_path))

        passphrase = base64.b64encode(
            hmac.new(self.api_secret.encode("utf-8"), self.api_passphrase.encode("utf-8"), hashlib.sha256).digest(),
        )
        headers = self.get_header(sign, now_time, passphrase)

        response = await self.connection.get(url, params=body, headers=headers)
        data = response.json()

        if data.get("code") == "400002":  # invalid timestamp error
            raise NoPriceFound()

        buy = data["data"]["asks"]
        sell = data["data"]["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    def sign(self, message):
        mac = hmac.new(self.api_secret.encode("utf-8"), message.encode("utf-8"), digestmod="sha256")
        d = mac.digest()
        return base64.b64encode(d)

    @staticmethod
    def pre_hash(timestamp, method, request_path):
        return str(timestamp) + str.upper(method) + request_path

    @staticmethod
    def get_timestamp():
        return int(time.time()) * 1000

    def get_header(self, sign, timestamp, passphrase):
        header = dict()
        header["Content-Type"] = "application/json"
        header["KC-API-KEY"] = self.api_key
        header["KC-API-SIGN"] = sign
        header["KC-API-TIMESTAMP"] = str(timestamp)
        header["KC-API-PASSPHRASE"] = passphrase
        header["KC-API-KEY-VERSION"] = "2"
        header["User-Agent"] = "kucoin-python-sdk/1.0.0"
        return header

    def get_coin_exchange_networks(self):
        for coin_data in self.client._request("GET", "/api/v3/currencies"):
            yield CoinNetworkExchangeDC.from_kucoin(coin_data)

    def get_pair_trading_volume(self, pair) -> float:
        data = self.client.get_24h_stats(symbol=pair.dashed_name)
        return float(data["vol"])

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.kucoin.com/trade/{pair.dashed_name}"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.kucoin.com/assets/coin/{cne.coin.name}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.kucoin.com/assets/withdraw/{cne.coin.name}"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.client.get_kline(symbol=pair.dashed_name, kline_type="1min")
        opened = float(response[14][1])
        closed = float(response[0][2])
        change = (closed - opened) / opened * 100
        return change
