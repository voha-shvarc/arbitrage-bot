import base64
import hmac
import time
from json.decoder import JSONDecodeError
from typing import List

from abstract import AbstractExchange
from abstract import NoPriceFound
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import CoinNetworkExchangeDC
from db.structs import TradingPair
from exchanges.bitget.v1.spot.market_api import MarketApi


class BitgetAPI(AbstractExchange):
    NAME = "Bitget"
    ALLOWED_STATUS = "online"
    base_url = "https://api.bitget.com"

    def __init__(self, config, connection):
        self.connection = connection

        self.api_key = config["BITGET_API_KEY"]
        self.api_secret = config["BITGET_API_SECRET"]
        self.api_passphrase = config["BITGET_API_PASSPHRASE"]
        self.client = MarketApi(api_key=self.api_key, api_secret_key=self.api_secret, passphrase=self.api_passphrase)

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

    def get_coin_exchange_networks(self):
        for coin_data in self.client.currencies(params={})["data"]:
            yield CoinNetworkExchangeDC.from_bitget(coin_data)

    def get_price(self, pair: Pair, limit=30) -> tuple[list[list[str]], list[list[str]]]:
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

    async def async_get_price(self, symbol, limit=30):
        url = self.base_url + "/api/spot/v1/market/depth"
        body = {
            "symbol": symbol.bitget_name,
            "limit": limit,
        }
        timestamp = self.get_timestamp()
        sign = self.sign(self.pre_hash(timestamp, "GET", url, ""))
        header = self.get_header(sign, timestamp)
        response = await self.connection.get(url, params=body, headers=header)
        try:
            data = response.json()
        except JSONDecodeError:
            import logging

            log = logging.getLogger("error")
            log.error(f"[bitget] - {response.text}")
            raise NoPriceFound()

        if not data.get("data"):
            raise NoPriceFound()

        buy = data["data"]["asks"]
        sell = data["data"]["bids"]
        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    def sign(self, message):
        mac = hmac.new(bytes(self.api_secret, encoding="utf8"), bytes(message, encoding="utf-8"), digestmod="sha256")
        d = mac.digest()
        return str(base64.b64encode(d), "utf8")

    @staticmethod
    def pre_hash(timestamp, method, request_path, body):
        return str(timestamp) + str.upper(method) + request_path + body

    @staticmethod
    def get_timestamp():
        return int(time.time() * 1000)

    def get_header(self, sign, timestamp):
        header = dict()
        header["Content-Type"] = "application/json"
        header["ACCESS-KEY"] = self.api_key
        header["ACCESS-SIGN"] = sign
        header["ACCESS-TIMESTAMP"] = str(timestamp)
        header["ACCESS-PASSPHRASE"] = self.api_passphrase
        return header

    def get_pair_trading_volume(self, pair) -> float:
        data = self.client.ticker({"symbol": pair.bitget_name})
        return float(data["data"]["baseVol"])

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.bitget.com/spot/{pair.default_name}"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        coin_id = cne.extra_info.get("coin_id")
        if not coin_id:
            link = "https://www.bitget.com/asset/recharge?coinId=2"
        else:
            link = f"https://www.bitget.com/asset/recharge?coinId={coin_id}"

        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        """Has static link"""
        link = "https://www.bitget.com/asset/withdraw"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        params = {
            "symbol": pair.bitget_name,
            "period": "1min",
            "limit": "15",
        }
        response = self.client.candles(params=params)
        opened = float(response["data"][0]["open"])
        closed = float(response["data"][-1]["close"])
        change = (closed - opened) / opened * 100
        return change
