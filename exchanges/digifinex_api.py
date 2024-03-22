import hashlib
from itertools import groupby
from urllib.parse import urlencode
import hmac
import time
from json import JSONDecodeError
from logging import getLogger
from typing import List

import requests

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

ERROR_MAPPING = {
    10001: "Wrong request method, please check it's a GET or POST request",
    10002: "Invalid ApiKey",
    10003: "Sign doesn't match",
    10004: "Illegal request parameters",
    10005: "Request frequency exceeds the limit",
    10006: "Unauthorized to execute this request",
    10007: "IP address Unauthorized",
    10008: "Timestamp for this request is invalid",
    10009: "Unexist endpoint or misses ACCESS-KEY, please check endpoint URL",
    10011: "ApiKey expired. Please go to client side to re-create an ApiKey.",
    20002: "Trade of this trading pair is suspended",
    20007: "Price precision error",
    20008: "Amount precision error",
    20009: "Amount is less than the minimum requirement",
    20010: "Cash Amount is less than the minimum requirement",
    20011: "Insufficient balance",
    20012: "Invalid trade type (valid value: buy/sell)",
    20013: "No order info found",
    20014: "Invalid date (Valid format: 2018-07-25)",
    20015: "Date exceeds the limit",
    20018: "Your have been banned for API trading by the system",
    20019: "Wrong trading pair symbol, correct format:'base_quote', e.g. 'btc_usdt'",
    20020: "You have violated the API trading rules and temporarily banned for trading. At present, we have certain restrictions on the user's transaction rate and withdrawal rate.",
    20021: "Invalid currency",
    20022: "The ending timestamp must be larger than the starting timestamp",
    20023: "Invalid transfer type",
    20024: "Invalid amount",
    20025: "This currency is not transferable at the moment",
    20026: "Transfer amount exceed your balance",
    20027: "Abnormal account status",
    20028: "Blacklist for transfer",
    20029: "Transfer amount exceed your daily limit",
    20030: "You have no position on this trading pair",
    20032: "Withdrawal limited",
    20033: "Wrong Withdrawal ID",
    20034: "Withdrawal service of this crypto has been closed",
    20035: "Withdrawal limit",
    20036: "Withdrawal cancellation failed",
    20037: "The withdrawal address, Tag or chain type is not included in the withdrawal management list",
    20038: "The withdrawal address is not on the white list",
    20039: "Can't be canceled in current status",
    20040: "Withdraw too frequently; limitation: 3 times a minute, 100 times a day",
    20041: "Beyond the daily withdrawal limit",
    20042: "Current trading pair does not support API trading",
    50000: "Exception error"
}


class DigiFinexAPI(AbstractExchange):
    NAME = "DigiFinex"
    base_url = "https://openapi.digifinex.com/v3"

    def __init__(self, config, connection, logger=None):
        self.connection = connection
        self.logger = logger or error_logger

        self.api_key = config["DIGIFINEX_API_KEY"]
        self.api_secret = config["DIGIFINEX_API_SECRET"]

    def create_signature(self, data) -> str:
        query_string = urlencode(data)
        m = hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        s = m.hexdigest()
        return s

    def sign_request(self, method: str, path: str, params: dict = None, body: dict = None):
        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-TIMESTAMP": str(int(time.time())),
            "ACCESS-SIGN": self.create_signature(params or body or {}),
        }
        return requests.request(method, self.base_url + path, params=params, json=body, headers=headers)

    def public_request(self, method: str, path: str, params: dict = None):
        url = self.base_url + path
        return requests.request(method, url, params=params)

    def get_trading_pairs(self) -> List[TradingPair]:
        response = self.public_request("GET", "/spot/symbols")
        data = response.json()

        trading_pairs = [
            TradingPair(
                base_coin=pair["base_asset"].upper(),
                quote_coin=pair["quote_asset"].upper(),
                base_coin_precision=pair["amount_precision"],
                quote_coin_precision=pair["price_precision"],
                exchange=self.NAME,
            )
            for pair in data["symbol_list"]
            if pair["quote_asset"] == "USDT" and pair["status"] == "TRADING"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        response = self.public_request("GET", "/currencies")
        data = response.json()["data"]
        sorted_chains = sorted(data, key=lambda x: x["currency"])
        grouped_by_currency = groupby(sorted_chains, key=lambda x: x["currency"])

        for coin_name, chains_data in grouped_by_currency:
            yield CoinNetworkExchangeDC.from_digifinex(coin_name, chains_data)

    def get_price(self, pair: Pair, limit=50) -> tuple[list[list[str]], list[list[str]]]:
        params = {"symbol": pair.underscored_name.lower(), "limit": limit}
        response = self.public_request("GET", "/order_book", params)

        try:
            data = response.json()
            if data["code"] != 0:
                msg = ERROR_MAPPING[data["code"]]
                self.logger.error(f"[DigiFinex] {msg}")
                raise NoPriceFound()
        except JSONDecodeError:
            self.logger.error(f"[DigiFinex] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        try:
            buy = data["asks"]
            sell = data["bids"]
        except KeyError:
            self.logger.error(f"[DigiFinex] {pair.default_name} - error parsing {data = }")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=50):
        url = self.base_url + "/order_book"
        params = {"symbol": pair.underscored_name.lower(), "limit": limit}

        response = await self.connection.get(url, params=params)
        try:
            data = response.json()
            if data["code"] != 0:
                msg = ERROR_MAPPING[data["code"]]
                self.logger.error(f"[DigiFinex] {msg}")
                raise NoPriceFound()
        except JSONDecodeError:
            self.logger.error(f"[DigiFinex] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        try:
            buy = data["asks"]
            sell = data["bids"]
        except KeyError:
            self.logger.error(f"[DigiFinex] {pair.default_name} - error parsing {data = }")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    def get_pair_trading_volume(self, pair: Pair) -> float:
        params = {
            "symbol": pair.underscored_name.lower(),
        }
        response = self.public_request("GET", "/ticker", params=params)
        data = response.json()
        if data["code"] != 0:
            msg = ERROR_MAPPING[data["code"]]
            self.logger.error(f"[DigiFinex] {msg}")
            return 0

        return data["ticker"][0]["vol"]

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.digifinex.com/ru-ru/trade/{pair.slashed_name}"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.digifinex.com/ru-ru/charge/deposit/{cne.coin.name}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.digifinex.com/ru-ru/withdraw/{cne.coin.name}"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.public_request(
            "GET",
            "/kline",
            {"symbol": pair.underscored_name.lower(), "period": "1"},
        )
        data = response.json()
        if data["code"] != 0:
            msg = ERROR_MAPPING[data["code"]]
            self.logger.error(f"[DigiFinex] {msg}")
            return 0

        opened = data["data"][-10][-1]
        closed = data["data"][-1]["c"]
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self, coin_name: str = "usdt") -> float:
        params = {"currency": coin_name.lower()}
        response = self.sign_request("GET", "/spot/assets", params)
        try:
            data = response.json()
            if data["code"] != 0:
                msg = ERROR_MAPPING[data["code"]]
                self.logger.error(f"[DigiFinex] {msg}")
                raise WithdrawError(msg) from None

        except JSONDecodeError as e:
            self.logger.error(f"[DigiFinex] Error getting balance for {coin_name}. {response.text}")
            raise WithdrawError("Couldn't get balance") from e

        return float(data["result"]["availableAmount"])

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        try:
            response = self.sign_request(
                "GET",
                "/deposit/address",
                params={
                    "currency": cne.coin.name.lower(),
                },
            )
        except Exception as e:
            self.logger.error(f"[DigiFinex] deposit address error - {e}")
            raise DepositAddressError() from e

        try:
            data = response.json()
            if data["code"] != 0:
                msg = ERROR_MAPPING[data["code"]]
                self.logger.error(f"[DigiFinex] {msg}")
                raise DepositAddressError() from None

        except JSONDecodeError as e:
            self.logger.error(f"[xt] deposit address error. couldn't parse response. {response.text}")
            raise DepositAddressError() from e
        except KeyError as e:
            self.logger.error(f"[xt] deposit address error. couldn't parse response. {data}")
            raise DepositAddressError() from e
        else:
            for deposit_info in data["data"]:
                if deposit_info["chain"] == cne.network.name:
                    return DepositAddress(deposit_info["address"], deposit_info["addressTag"])

            raise DepositAddressError() from None

    def create_order(self, pair: Pair, ccy_quantity: float, ccy_precision: int, price: float, price_precision: int):
        body = {
            "market": "spot",
            "symbol": "btc_usdt",
            "type": "buy",
            "amount": f"{ccy_quantity:.{ccy_precision}f}",
            "price": f"{price:.{price_precision}f}",
        }
        response = self.sign_request("POST", "/spot/order/new", body=body)

        try:
            data = response.json()
            if data["code"] != 0:
                msg = ERROR_MAPPING[data["code"]]
                self.logger.error(f"[DigiFinex] {msg}")
                raise CreateOrderError(msg) from None

        except JSONDecodeError as e:
            self.logger.error(f"[DigiFinex] couldn't parse response. {response.text}. {body = }")
            raise CreateOrderError("Couldn't parse response. Check logs") from e
