import hashlib
import hmac
import time
from json import JSONDecodeError
from logging import getLogger
from typing import List
from urllib.parse import quote
from urllib.parse import urlencode

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


error_log = getLogger("error")


class MexcAPI(AbstractExchange):
    NAME = "Mexc"
    base_url = "https://api.mexc.com"

    def __init__(self, config, connection):
        self.connection = connection

        self.api_key = config["MEXC_API_KEY"]
        self.api_secret = config["MEXC_API_SECRET"]

    def _sign_v3(self, req_time, sign_params=None):
        if sign_params:
            sign_params = urlencode(sign_params, quote_via=quote)
            to_sign = "{}&timestamp={}".format(sign_params, req_time)
        else:
            to_sign = "timestamp={}".format(req_time)
        sign = hmac.new(self.api_secret.encode("utf-8"), to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        return sign

    def sign_request(self, method, url, params=None):
        url = self.base_url + url
        req_time = int(1000 * time.time())
        if params:
            params["signature"] = self._sign_v3(req_time=req_time, sign_params=params)
        else:
            params = {
                "signature": self._sign_v3(req_time=req_time),
            }
        params["timestamp"] = req_time
        headers = {
            "x-mexc-apikey": self.api_key,
            "Content-Type": "application/json",
        }
        return requests.request(method, url, params=params, headers=headers)

    def public_request(self, method, url, params=None):
        url = self.base_url + url
        return requests.request(method, url, params=params)

    def get_trading_pairs(self) -> List[TradingPair]:
        response = self.public_request("GET", "/api/v3/exchangeInfo")
        data = response.json()
        trading_pairs = [
            TradingPair(
                base_coin=pair["baseAsset"],
                quote_coin=pair["quoteAsset"],
                exchange=self.NAME,
            )
            for pair in data["symbols"]
            if pair["quoteAsset"] == "USDT" and pair["status"] == "ENABLED" and pair["isSpotTradingAllowed"]
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        for coin_data in self.sign_request("GET", "/api/v3/capital/config/getall").json():
            yield CoinNetworkExchangeDC.from_mexc(coin_data)

    def get_price(self, pair: Pair, limit=50) -> tuple[list[list[str]], list[list[str]]]:
        response = self.public_request("GET", "/api/v3/depth", {"symbol": pair.default_name, "limit": limit})
        data = response.json()
        buy = data["asks"]
        sell = data["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=50):
        url = self.base_url + "/api/v3/depth"
        params = {"symbol": pair.default_name, "limit": limit}

        response = await self.connection.get(url, params=params)
        try:
            data = response.json()
        except JSONDecodeError:
            error_log.error(f"[mexc] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        try:
            buy = data["asks"]
            sell = data["bids"]
        except KeyError:
            error_log.error(f"[mexc] {pair.default_name} - error parsing {data = }")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair: Pair) -> float:
        response = self.public_request("GET", "/api/v3/ticker/24hr", params={"symbol": pair.default_name})
        data = response.json()
        return float(data["volume"])

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.mexc.com/ru-RU/exchange/{pair.underscored_name}"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.mexc.com/assets/deposit/{cne.coin.name}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.mexc.com/assets/withdraw/{cne.coin.name}"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.public_request(
            "GET",
            "/api/v3/klines",
            {"symbol": pair.default_name, "interval": "1m", "limit": 10},
        )
        data = response.json()
        opened = float(data[0][1])
        closed = float(data[-1][4])
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self, coin_name: str = "USDT") -> float:
        response = self.sign_request("GET", "/api/v3/account")
        try:
            data = response.json()
        except JSONDecodeError as e:
            error_log.error(f"[mexc] Error getting balance for {coin_name}. {response.text}")
            raise WithdrawError("Couldn't get balance") from e
        for balance_data in data["balances"]:
            if balance_data["asset"] == coin_name:
                balance = float(balance_data["free"])
                return balance

        raise WithdrawError(f"No available balance for {coin_name}")

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        try:
            response = self.sign_request(
                "POST",
                "/api/v3/capital/deposit/address",
                params={
                    "coin": cne.coin.name,
                    "network": cne.plain_network_name or cne.network.name,
                },
            )
            data = response.json()
            address = DepositAddress(data["address"], data.get("memo"))
        except JSONDecodeError as e:
            error_log.error(f"[mexc] deposit address error. couldn't parse response. {response.text}")
            raise DepositAddressError() from e
        except Exception as e:
            error_log.error(f"[mexc] deposit address error - {e}")
            raise DepositAddressError() from e
        else:
            return address

    def withdraw(self, cne: CoinNetworkExchange, deposit_address: DepositAddress) -> None:
        amount = self.get_balance(cne.coin.name)
        body = {
            "coin": cne.coin.name,
            "network": cne.plain_network_name,
            "address": deposit_address.address,
            "amount": str(amount),
        }
        if deposit_address.memo:
            body["memo"] = deposit_address.memo

        try:
            response = self.sign_request(
                "POST",
                "/api/v3/capital/withdraw/apply",
                params=body,
            )
        except Exception as e:
            error_log.exception(e)
            raise WithdrawError(f"[mexc]Unknown exception, {e}") from e

        try:
            data = response.json()
        except JSONDecodeError as e:
            error_log.exception(e)
            raise WithdrawError(f"[mexc]Couldn't parse response, {response.text}") from e

        if msg := data.get("code"):
            raise WithdrawError(msg)

    def create_order(self, pair: Pair, ccy_quantity: float, price: float):
        body = {
            "symbol": pair.default_name,
            "side": "BUY",
            "type": "LIMIT",
            "quantity": ccy_quantity,
            "price": price,
        }
        response = self.sign_request("POST", "/api/v3/order", body)

        try:
            data = response.json()
        except JSONDecodeError as e:
            error_log.error(f"[mexc] couldn't parse response. {response.text}")
            raise CreateOrderError("Couldn't parse response. Check logs") from e
        if err_msg := data.get("msg"):
            raise CreateOrderError(err_msg)
