import base64
import hashlib
import hmac
import time
from json import JSONDecodeError
from logging import getLogger
from typing import List

from kucoin.client import MarketData
from kucoin.client import TradeData
from kucoin.client import UserData

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


error_log = getLogger("error")


class KuCoinAPI(AbstractExchange):
    NAME = "KuCoin"
    base_url = "https://api.kucoin.com"

    def __init__(self, config, connection):
        self.connection = connection

        self.api_key = config["KUCOIN_API_KEY"]
        self.api_secret = config["KUCOIN_API_SECRET"]
        self.api_passphrase = config["KUCOIN_API_PASSPHRASE"]
        self.client = MarketData(self.api_key, self.api_secret, self.api_passphrase)
        self.account_client = UserData(self.api_key, self.api_secret, self.api_passphrase)
        self.trade_client = TradeData(self.api_key, self.api_secret, self.api_passphrase)

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

    async def async_get_price(self, pair, limit=20):
        url = self.base_url + "/api/v3/market/orderbook/level2_20"
        uri_path = f"/api/v3/market/orderbook/level2_20?symbol={pair.dashed_name}"
        body = {
            "symbol": pair.dashed_name,
        }
        now_time = int(time.time()) * 1000
        sign = self.sign(self.pre_hash(now_time, "GET", uri_path))

        passphrase = base64.b64encode(
            hmac.new(self.api_secret.encode("utf-8"), self.api_passphrase.encode("utf-8"), hashlib.sha256).digest(),
        )
        headers = self.get_header(sign, now_time, passphrase)

        response = await self.connection.get(url, params=body, headers=headers)
        try:
            data = response.json()
        except JSONDecodeError:
            error_log.error(f"[kucoin] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        if data.get("code") == "400002":  # invalid timestamp error
            raise NoPriceFound()

        try:
            buy = data["data"]["asks"]
            sell = data["data"]["bids"]
        except KeyError as e:
            error_log.error(f"[kucoin] {pair.default_name} - error parsing data {data =}\n{e}")
            raise NoPriceFound()

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

    def get_balance(self, coin_name: str = "USDT") -> float:
        response = self.account_client.get_account_list(currency=coin_name, account_type="trade")
        try:
            balance = float(response[0]["balance"])
        except (KeyError, IndexError) as e:
            error_log.exception(f"[kucoin] error getting balance: {coin_name}, {e}")
            raise WithdrawError(f"No available balance for {coin_name}") from e
        else:
            return balance

    def transfer(self, coin_name: str, amount: str, from_account: str = "trade", to_account: str = "main"):
        try:
            self.account_client.inner_transfer(coin_name, from_account, to_account, amount)
        except Exception as e:
            error_log.exception(f"[kucoin] transfer error: {e}")
            raise WithdrawError(f"Couldn't transfer from {from_account} to {to_account}. {e}") from e

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        try:
            data = self.account_client.get_deposit_addressv2(cne.coin.name, cne.plain_network_name)
            if isinstance(data, dict):
                data = self.account_client.create_deposit_address(cne.coin.name, cne.plain_network_name)
            else:
                data = data[0]
            address = DepositAddress(data["address"], data["memo"])
        except Exception as e:
            error_log.error(f"[kucoin] deposit address error - {e}")
            raise DepositAddressError() from e
        else:
            return address

    def withdraw(self, cne: CoinNetworkExchange, deposit_address: DepositAddress) -> None:
        amount = self.get_balance(cne.coin.name)
        self.transfer(cne.coin.name, str(amount))
        body = {
            "currency": cne.coin.name,
            "chain": cne.network.plain_network_name,
            "address": deposit_address.address,
            "amount": amount,
            "isInner": False,
            "feeDeductType": "INTERNAL",
        }
        if deposit_address.memo:
            body["memo"] = deposit_address.memo

        try:
            self.account_client.apply_withdrawal(**body)
        except Exception as e:
            raise WithdrawError(f"[kucoin] error submitting withdrawal {e}") from e

    def create_order(self, pair: Pair, ccy_quantity: float, price: float):
        try:
            self.trade_client.create_limit_order(
                symbol=pair.dashed_name,
                side="buy",
                type="limit",
                price=str(price),
                size=str(ccy_quantity),
                timeInForce="FOK",
            )
        except Exception as e:
            error_log.exception(f"[kucoin] create order error - {e}")
            raise CreateOrderError(str(e)) from e
