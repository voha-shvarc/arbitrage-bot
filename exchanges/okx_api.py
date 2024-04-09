import base64
import datetime
import hmac
from json import JSONDecodeError
from logging import getLogger

from aiolimiter import AsyncLimiter
from okx.Account import AccountAPI
from okx.Funding import FundingAPI
from okx.MarketData import MarketAPI
from okx.PublicData import PublicAPI
from okx.Trade import TradeAPI
from retry import retry

from abstract import AbstractExchange
from abstract import NoPriceFound
from abstract.abstract import CreateOrderError
from abstract.abstract import DepositAddressError
from abstract.abstract import WithdrawError
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import CoinNetworkExchangeDC
from db.structs import DepositAddress
from db.structs import TradingPair


error_logger = getLogger("error")


class OkxAPI(AbstractExchange):
    NAME = "OKX"
    flag = "0"  # Production trading: 0, Demo trading: 1
    base_url = "https://www.okx.com"
    async_limiter = AsyncLimiter(3.2, 0.2)  # 16r/1s  max 20r/1s

    def __init__(self, config, connection, logger=None):
        self.connection = connection
        self.logger = logger or error_logger

        self.api_key = config["OKX_API_KEY"]
        self.api_secret = config["OKX_API_SECRET"]
        self.passphrase = config["OKX_API_PASSPHRASE"]

        self.public_data_client = PublicAPI(self.api_key, self.api_secret, self.passphrase, flag=self.flag, debug=False)
        self.market_client = MarketAPI(self.api_key, self.api_secret, self.passphrase, flag=self.flag, debug=False)
        self.funding_client = FundingAPI(self.api_key, self.api_secret, self.passphrase, flag=self.flag, debug=False)
        self.account_client = AccountAPI(self.api_key, self.api_secret, self.passphrase, flag=self.flag, debug=False)
        self.trade_client = TradeAPI(
            self.api_key,
            self.api_secret,
            self.passphrase,
            flag=self.flag,
            debug=False,
        )

    @retry(delay=1, tries=2)
    def get_trading_pairs(self) -> list:
        pairs_info = self.public_data_client.get_instruments(instType="SPOT")
        trading_pairs = [
            TradingPair(
                base_coin=pair["baseCcy"],
                quote_coin=pair["quoteCcy"],
                exchange=self.NAME,
                base_coin_precision=len(pair["lotSz"]) - 2 if pair["lotSz"] != "1" else 1,
                quote_coin_precision=len(pair["tickSz"]) - 2 if pair["tickSz"] != "1" else 1,
                maker_fee=0.0008,  # 0.08%
            )
            for pair in pairs_info["data"]
            if pair["quoteCcy"] == "USDT"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        for coin_data in self.funding_client.get_currencies()["data"]:
            yield CoinNetworkExchangeDC.from_okx(coin_data)

    @retry(delay=1, tries=2)
    def get_price(self, pair: Pair, limit=30) -> tuple[list[list[str, str]], list[list[str, str]]]:
        order_book = self.market_client.get_orderbook(instId=pair.dashed_name, sz=limit)
        if not order_book["data"]:
            raise NoPriceFound()
        buy = [ask[:2] for ask in order_book["data"][0]["asks"]]
        sell = [bid[:2] for bid in order_book["data"][0]["bids"]]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    @retry(delay=1, tries=2)
    async def async_get_price(self, pair: Pair, limit=30):
        url = self.base_url + "/api/v5/market/books"
        body = {
            "instId": pair.dashed_name,
            "sz": limit,
        }
        timestamp = self.get_timestamp()
        sign = self.sign(self.pre_hash(timestamp, "GET", url, ""))
        header = self.get_header(sign, timestamp)
        response = await self.connection.get(url, params=body, headers=header)
        try:
            data = response.json()
        except JSONDecodeError:
            self.logger.error(f"[okx] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        if data.get("code") in ["50011", "51001"]:  # too many requests or wrong instID
            self.logger.error(f"[okx] {pair.default_name} - {data['code']}")
            raise NoPriceFound()

        try:
            buy = data["data"][0]["asks"]
            sell = data["data"][0]["bids"]
        except (KeyError, IndexError) as e:
            self.logger.error(f"[okx] {pair.default_name} - error parsing data {data =}\n{e}")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    @staticmethod
    def get_timestamp():
        now = datetime.datetime.utcnow()
        t = now.isoformat("T", "milliseconds")
        return t + "Z"

    def sign(self, message):
        mac = hmac.new(bytes(self.api_secret, encoding="utf8"), bytes(message, encoding="utf-8"), digestmod="sha256")
        d = mac.digest()
        return base64.b64encode(d)

    @staticmethod
    def pre_hash(timestamp, method, request_path, body):
        return str(timestamp) + str.upper(method) + request_path + body

    def get_header(self, sign, timestamp):
        header = dict()
        header["Content-Type"] = "application/json"
        header["OK-ACCESS-KEY"] = self.api_key
        header["OK-ACCESS-SIGN"] = sign
        header["OK-ACCESS-TIMESTAMP"] = str(timestamp)
        header["OK-ACCESS-PASSPHRASE"] = self.passphrase
        header["x-simulated-trading"] = self.flag
        return header

    def get_pair_trading_volume(self, pair) -> float:
        data = self.market_client.get_ticker(instId=pair.dashed_name)
        return float(data["data"][0]["vol24h"])

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.okx.com/ua/trade-spot/{pair.dashed_name.lower()}"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        """Potentially can use network id or something (sub) to go directly to that one"""
        link = f"https://www.okx.com/ua/balance/recharge/{cne.coin.name.lower()}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.okx.com/ua/balance/withdrawal/{cne.coin.name.lower()}"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.market_client.get_candlesticks(pair.dashed_name, bar="1m", limit=10)
        opened = float(response["data"][-1][1])
        closed = float(response["data"][0][4])
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self) -> float:
        response = self.account_client.get_account_balance(ccy="USDT")
        try:
            balance = float(response["data"][0]["details"][0]["availBal"])
        except (KeyError, IndexError):
            balance = 0

        return balance

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        try:
            data = self.funding_client.get_deposit_address(cne.coin.name)
            for net in data["data"]:
                if net["chain"] == cne.plain_network_name:
                    return DepositAddress(net["addr"], net.get("tag") or net.get("memo"))
        except Exception as e:
            self.logger.error(f"[okx] deposit address error - {e}")
            raise DepositAddressError() from e
        else:
            raise DepositAddressError()

    def create_order(
        self,
        pair: Pair,
        ccy_quantity: float,
        ccy_precision: int,
        price: float,
        price_precision: int,
        spot_fee: float,
    ):
        body = {
            "instId": pair.dashed_name,
            "tdMode": "cash",
            "side": "buy",
            "ordType": "fok",
            "sz": f"{ccy_quantity:.{ccy_precision}f}",
            "px": f"{price:.{price_precision}f}",
        }
        res = self.trade_client.place_order(**body)
        if res["code"] != "0":
            self.logger.error(f"[okx] error creating order {res['data'][0]['sMsg']}. {body = }")
            raise CreateOrderError(res["data"][0]["sMsg"])

    def withdraw(
        self,
        cne: CoinNetworkExchange,
        ccy_quantity_to_withdraw: float,
        deposit_address: DepositAddress,
    ) -> None:
        ccy_quantity_to_withdraw -= cne.withdraw_fee
        if cne.withdraw_precision:
            amount = f"{ccy_quantity_to_withdraw:.{cne.withdraw_precision}}"
        else:
            amount = str(ccy_quantity_to_withdraw)

        if deposit_address.memo:
            address = f"{deposit_address.address}:{deposit_address.memo}"
        else:
            address = deposit_address.address

        body = {
            "ccy": cne.coin.name,
            "chain": cne.plain_network_name,
            "amt": amount,  # doesn't include fee
            "dest": "4",  # on-chain withdraw
            "toAddr": address,  # includes address and tag if present
            "fee": cne.withdraw_fee,
        }
        response = self.funding_client.withdrawal(**body)
        if response["code"] != "0":
            msg = response["msg"]
            self.logger.error(f"[okx] {msg = }; {body =}")
            raise WithdrawError(msg)
