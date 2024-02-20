import base64
import datetime
import hmac

from okx.Funding import FundingAPI
from okx.MarketData import MarketAPI
from okx.PublicData import PublicAPI
from retry import retry

from abstract import AbstractExchange, NoPriceFound
from db.structs import CoinNetworkExchangeDC, TradingPair


class OkxAPI(AbstractExchange):
    NAME = "OKX"
    flag = "0"  # Production trading: 0, Demo trading: 1
    base_url = "https://www.okx.com"

    def __init__(self, config, connection):
        self.connection = connection

        self.api_key = config["OKX_API_KEY"]
        self.api_secret = config["OKX_API_SECRET"]
        self.passphrase = config["OKX_API_PASSPHRASE"]

        self.public_data_client = PublicAPI(self.api_key, self.api_secret, self.passphrase, flag=self.flag, debug=False)
        self.market_client = MarketAPI(self.api_key, self.api_secret, self.passphrase, flag=self.flag, debug=False)
        self.funding_client = FundingAPI(self.api_key, self.api_secret, self.passphrase, flag=self.flag, debug=False)

    @retry(delay=1, tries=2)
    def get_trading_pairs(self) -> list:
        pairs_info = self.public_data_client.get_instruments(instType="SPOT")
        trading_pairs = [
            TradingPair(base_coin=pair["baseCcy"], quote_coin=pair["quoteCcy"], exchange=self.NAME)
            for pair in pairs_info["data"]
            if pair["instId"].endswith("USDT")
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        # todo: there's option to speed up transaction by setting more fee amount
        # todo: also minimal withdraw amount should also be considered as well as max withdraw amount
        # todo: also minimal and max deposits
        for coin_data in self.funding_client.get_currencies()["data"]:
            yield CoinNetworkExchangeDC.from_okx(coin_data)

    @retry(delay=1, tries=2)
    def get_price(self, pair, limit=30):
        order_book = self.market_client.get_orderbook(instId=pair.dashed_name, sz=limit)
        if not order_book["data"]:
            raise NoPriceFound()
        buy = order_book["data"][0]["asks"]
        sell = order_book["data"][0]["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    @retry(delay=1, tries=2)
    async def async_get_price(self, symbol, limit=30):
        url = self.base_url + "/api/v5/market/books"
        body = {
            "instId": symbol.dashed_name,
            "sz": limit,
        }
        timestamp = self.get_timestamp()
        sign = self.sign(self.pre_hash(timestamp, "GET", url, ""))
        header = self.get_header(sign, timestamp)
        response = await self.connection.get(url, params=body, headers=header)
        data = response.json()

        if data.get("code") == "50011":  # too many requests
            raise NoPriceFound()

        buy = data['data'][0]['asks']
        sell = data['data'][0]['bids']
        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    @staticmethod
    def get_timestamp():
        now = datetime.datetime.utcnow()
        t = now.isoformat("T", "milliseconds")
        return t + "Z"

    def sign(self, message):
        mac = hmac.new(bytes(self.api_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        return base64.b64encode(d)

    @staticmethod
    def pre_hash(timestamp, method, request_path, body):
        return str(timestamp) + str.upper(method) + request_path + body

    def get_header(self, sign, timestamp):
        header = dict()
        header['Content-Type'] = "application/json"
        header['OK-ACCESS-KEY'] = self.api_key
        header['OK-ACCESS-SIGN'] = sign
        header['OK-ACCESS-TIMESTAMP'] = str(timestamp)
        header['OK-ACCESS-PASSPHRASE'] = self.passphrase
        header['x-simulated-trading'] = self.flag
        return header

    def get_pair_trading_volume(self, pair) -> float:
        data = self.market_client.get_ticker(instId=pair.dashed_name)
        return float(data["data"][0]["vol24h"])
