import hashlib
import json
import time
from json import JSONDecodeError
from logging import getLogger
from typing import List
from typing import Union
from urllib.parse import urlparse

import requests
from sqlalchemy import select

from abstract import AbstractExchange
from abstract import NoPriceFound
from abstract.abstract import CreateOrderError
from abstract.abstract import DepositAddressError
from abstract.abstract import WithdrawError
from db.base import Session
from db.models import Coin
from db.models import CoinNetworkExchange
from db.models import Exchange
from db.models import Pair
from db.models import PairExchange
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
    50000: "Exception error",
}


class CoinExAPI(AbstractExchange):
    NAME = "CoinEx"
    base_url = "https://api.coinex.com/v2"

    def __init__(self, config, connection, logger=None):
        self.connection = connection
        self.logger = logger or error_logger

        self.api_key = config["DIGIFINEX_API_KEY"]
        self.api_secret = config["DIGIFINEX_API_SECRET"]

        self.HEADERS = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "X-COINEX-KEY": self.api_key,
            "X-COINEX-SIGN": "",
            "X-COINEX-TIMESTAMP": "",
        }

    def gen_sign(self, method, request_path, body, timestamp) -> str:
        prepared_str = f"{method}{request_path}{body}{timestamp}{self.api_secret}"
        signed_str = hashlib.sha256(prepared_str.encode("utf-8")).hexdigest().lower()
        return signed_str

    def get_common_headers(self, signed_str, timestamp):
        headers = self.HEADERS.copy()
        headers["X-COINEX-SIGN"] = signed_str
        headers["X-COINEX-TIMESTAMP"] = timestamp
        return headers

    def sign_request(self, method: str, path: str, params: dict = None, body: str = "") -> dict:
        url = self.base_url + path
        req = urlparse(url)
        request_path = req.path

        timestamp = str(int(time.time() * 1000))
        if method.upper() == "GET":
            if params:
                query_params = []
                for item in params:
                    if params[item] is None:
                        continue
                    query_params.append(item + "=" + str(params[item]))
                query_string = "?{0}".format("&".join(query_params))
                request_path += query_string

            signed_str = self.gen_sign(
                method,
                request_path,
                body="",
                timestamp=timestamp,
            )
            response = requests.get(
                url,
                params=params or {},
                headers=self.get_common_headers(signed_str, timestamp),
            )

        else:
            signed_str = self.gen_sign(
                method,
                request_path,
                body=body,
                timestamp=timestamp,
            )
            response = requests.post(
                url,
                body,
                headers=self.get_common_headers(signed_str, timestamp),
            )

        if response.status_code != 200:
            raise ValueError(response.text)

        data = response.json()
        return data["data"]

    def public_request(self, method: str, path: str, params: dict = None) -> Union[dict, list]:
        url = self.base_url + path
        response = requests.request(method, url, params=params)
        data = response.json()
        return data["data"]

    def get_trading_pairs(self) -> List[TradingPair]:
        data = self.public_request("GET", "/spot/market")
        print(data)

        trading_pairs = [
            TradingPair(
                base_coin=pair["base_ccy"],
                quote_coin=pair["quote_ccy"],
                base_coin_precision=pair["base_ccy_precision"],
                quote_coin_precision=pair["quote_ccy_precision"],
                taker_fee=float(pair["taker_fee_rate"]),
                maker_fee=float(pair["maker_fee_rate"]),
                exchange=self.NAME,
            )
            for pair in data
            if pair["quote_ccy"] == "USDT"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        with Session() as session:
            coins = session.scalars(
                (
                    select(Coin.name.distinct())
                    .select_from(PairExchange)
                    .join(PairExchange.exchange)
                    .join(PairExchange.pair)
                    .join(Pair.base_coin)
                    .where(Exchange.name == self.NAME)
                ),
            )
        for coin_name in coins:
            data = self.public_request("GET", "/assets/deposit-withdraw-config", {"ccy": coin_name})
            yield CoinNetworkExchangeDC.from_coinex(coin_name, data["chains"])

    def get_price(self, pair: Pair, limit=50) -> tuple[list[list[str]], list[list[str]]]:
        params = {
            "market": pair.default_name,
            "limit": limit,
            "interval": "0",
        }
        data = self.public_request("GET", "/spot/depth", params)

        try:
            buy = data["depth"]["asks"]
            sell = data["depth"]["bids"]
        except KeyError as e:
            self.logger.error(f"[CoinEx] {pair.default_name} - error parsing {data = }")
            raise NoPriceFound() from e

        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=50):
        url = self.base_url + "/spot/depth"
        params = {
            "market": pair.default_name,
            "limit": limit,
            "interval": "0",
        }

        response = await self.connection.get(url, params=params)
        try:
            data = response.json()
        except JSONDecodeError as e:
            self.logger.error(f"[CoinEx] {pair.default_name} - {response.text}")
            raise NoPriceFound() from e

        try:
            buy = data["data"]["depth"]["asks"]
            sell = data["data"]["depth"]["bids"]
        except KeyError as e:
            self.logger.error(f"[CoinEx] {pair.default_name} - error parsing {data = }")
            raise NoPriceFound() from e

        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    def get_pair_trading_volume(self, pair: Pair) -> float:
        params = {
            "market": pair.default_name,
        }
        data = self.public_request("GET", "/spot/ticker", params=params)

        return float(data[0]["volume"])

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.coinex.com/en/exchange/{pair.dashed_name.lower()}"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.coinex.com/en/asset/deposit?type={cne.coin.name}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.coinex.com/en/asset/withdraw?type={cne.coin.name}"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        params = {
            "market": pair.default_name,
            "period": "1min",
            "limit": 10,
        }
        data = self.public_request("GET", "/spot/kline", params)
        if data["code"] != 0:
            self.logger.error(f"[CoinEx] {data['message']}")
            return 0

        opened = float(data[0]["open"])
        closed = float(data[-1]["close"])
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self, coin_name: str = "USDT") -> float:
        # path = "/assets/spot/balance"
        # resp = request("GET", base_url + path, {})
        # data = resp.json()
        # print(data)
        return 0

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        data = self.sign_request(
            "GET",
            "/assets/deposit-address",
            params={
                "ccy": cne.coin.name,
                "chain": cne.network.name,
            },
        )

        if data["code"] != 0:
            self.logger.error(f"[CoinEx] {data['msg']}")
            raise DepositAddressError() from None

        return DepositAddress(data["address"], data["memo"])

    def withdraw(
        self,
        cne: CoinNetworkExchange,
        ccy_quantity_to_withdraw: float,
        deposit_address: DepositAddress,
    ) -> None:
        if cne.withdraw_precision:
            amount = f"{ccy_quantity_to_withdraw:.{cne.withdraw_precision}}"
        else:
            amount = str(ccy_quantity_to_withdraw)

        path = "/assets/withdraw"
        body = {
            "ccy": cne.coin.name,
            "chain": cne.network.name,
            "to_address": deposit_address.address,
            "memo": deposit_address.memo,
            "amount": amount,
        }
        data = self.sign_request("POST", path, body=json.dumps(body))
        if err_msg := data["message"]:
            self.logger.error(f"[CoinEx] {err_msg}")
            raise WithdrawError(err_msg) from None

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
            "market": pair.default_name,
            "market_type": "SPOT",
            "side": "buy",
            "type": "fok",
            "amount": f"{ccy_quantity:.{ccy_precision}f}",
            "price": f"{price:.{price_precision}f}",
        }
        data = self.sign_request("POST", "/spot/order/new", body=json.dumps(body))
        if err_msg := data["message"]:
            self.logger.error(f"[CoinEx] {err_msg}")
            raise CreateOrderError(err_msg) from None
