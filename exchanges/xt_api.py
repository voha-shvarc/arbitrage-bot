import hashlib
import hmac
import json
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
from abstract.abstract import WithdrawStatus
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import CoinNetworkExchangeDC
from db.structs import DepositAddress
from db.structs import TradingPair


error_logger = getLogger("error")

ERROR_MAPPING = {
    "ORDER_001": "Platform rejection",
    "ORDER_002": "insufficient funds",
    "ORDER_003": "Trading Pair Suspended",
    "ORDER_004": "no transaction",
    "ORDER_005": "Order not exist",
    "ORDER_006": "Too many open orders",
    "ORDER_007": "The sub-account has no transaction authority",
    "ORDER_008": "The order price or quantity precision is abnormal",
    "DEPOSIT_001": "Deposit is not open",
    "DEPOSIT_002": "The current account security level is low, please bind any two security verifications in mobile phone/email/Google Authenticator before deposit",
    "DEPOSIT_003": "The format of address is incorrect, please enter again",
    "DEPOSIT_004": "The address is already exists, please enter again",
    "DEPOSIT_005": "Can not find the address of offline wallet",
    "DEPOSIT_006": "No deposit address, please try it later",
    "DEPOSIT_007": "Address is being generated, please try it later",
    "DEPOSIT_008": "Deposit is not available",
    "WITHDRAW_001": "Withdraw is not open",
    "WITHDRAW_002": "The withdrawal address is invalid",
    "WITHDRAW_003": "The current account security level is low, please bind any two security verifications in mobile phone/email/Google Authenticator before withdraw",
    "WITHDRAW_004": "The withdrawal address is not added",
    "WITHDRAW_005": "The withdrawal address cannot be empty",
    "WITHDRAW_006": "Memo cannot be empty",
    "WITHDRAW_008": "Risk control is triggered, withdraw of this currency is not currently supported",
    "WITHDRAW_009": "Withdraw failed, some assets in this withdraw are restricted by T+1 withdraw",
    "WITHDRAW_010": "The precision of withdrawal is invalid",
    "WITHDRAW_011": "free balance is not enough",
    "WITHDRAW_012": "Withdraw failed, your remaining withdrawal limit today is not enough",
    "WITHDRAW_013": "Withdraw failed, your remaining withdrawal limit today is not enough, the withdrawal amount can be increased by completing a higher level of real-name authentication",
    "WITHDRAW_014": "This withdrawal address cannot be used in the internal transfer function, please cancel the internal transfer function before submitting",
    "WITHDRAW_015": "The withdrawal amount is not enough to deduct the handling fee",
    "WITHDRAW_016": "This withdrawal address is already exists",
    "WITHDRAW_017": "This withdrawal has been processed and cannot be canceled",
    "WITHDRAW_018": "Memo must be a number",
    "WITHDRAW_019": "Memo is incorrect, please enter again",
    "WITHDRAW_020": "Your withdrawal amount has reached the upper limit for today, please try it tomorrow",
    "WITHDRAW_021": "Your withdrawal amount has reached the upper limit for today, you can only withdraw up to {0} this time",
    "WITHDRAW_022": "Withdrawal amount must be greater than {0}",
    "WITHDRAW_023": "Withdrawal amount must be less than {0}",
    "WITHDRAW_024": "Withdraw is not supported",
    "WITHDRAW_025": "Please create a FIO address in the deposit page",
    "FUND_001": "Duplicate request (a bizId can only be requested once)",
    "FUND_002": "Insufficient account balance",
    "COMMON_001": "The user does not exist",
    "COMMON_002": "System busy, please try it later",
    "COMMON_003": "Operation failed, please try it later",
    "CURRENCY_001": "Information of currency is abnormal",
}


class XTAPI(AbstractExchange):
    NAME = "XT"
    base_url = "https://sapi.xt.com"
    withdraw_status = WithdrawStatus.enabled

    def __init__(self, config, connection, logger=None):
        self.connection = connection
        self.logger = logger or error_logger

        self.api_key = config["XT_API_KEY"]
        self.api_secret = config["XT_API_SECRET"]

    def create_signature(self, method: str, path: str, timestamp, params: dict = None, body: dict = None) -> str:
        signature_message = f"validate-algorithms=HmacSHA256&validate-appkey={self.api_key}&validate-recvwindow=60000&validate-timestamp={timestamp}"
        signature_message += f"#{method.upper()}#{path}"
        if params:
            ps = [f"{key}={value}" for key, value in dict(sorted(params.items())).items()]
            signature_message += f"#{'&'.join(ps)}"

        signature = hmac.new(self.api_secret.encode("utf-8"), signature_message.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature

    def sign_request(self, method: str, path: str, params: dict = None, body: dict = None):
        timestamp = str(int(time.time() * 1000))
        headers = {
            "accept": "*/*",
            "Content-Type": "application/json",
            "validate-algorithms": "HmacSHA256",
            "validate-appkey": self.api_key,
            "validate-recvwindow": "60000",
            "validate-timestamp": timestamp,
            "validate-signature": self.create_signature(method, path, params, body),
        }
        return requests.request(method, self.base_url + path, params=params, json=body, headers=headers)

    def public_request(self, method, path, params=None):
        url = self.base_url + path
        return requests.request(method, url, params=params)

    def get_trading_pairs(self) -> List[TradingPair]:
        response = self.public_request("GET", "/v4/public/symbol")
        data = response.json()
        if data is None:
            error_response = json.loads(response.text)
            msg = ERROR_MAPPING[error_response.get("mc")]
            self.logger.error(f"[xt] {msg}")
            return []

        trading_pairs = [
            TradingPair(
                base_coin=pair["baseCurrency"].upper(),
                quote_coin=pair["quoteCurrency"].upper(),
                base_coin_precision=pair["quantityPrecision"],
                quote_coin_precision=pair["pricePrecision"],
                exchange=self.NAME,
                taker_fee=0.002,  # 0.2%
                maker_fee=0.002,  # 0.2%
            )
            for pair in data["result"]["symbols"]
            if pair["quoteCurrency"] == "usdt" and pair["state"] == "ONLINE" and pair["tradingEnabled"]
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        response = self.public_request("GET", "/v4/public/wallet/support/currency")
        data = response.json()["result"]
        for coin_data in data:
            yield CoinNetworkExchangeDC.from_xt(coin_data)

    def get_price(self, pair: Pair, limit=50) -> tuple[list[list[str]], list[list[str]]]:
        params = {"symbol": pair.underscored_name.lower(), "limit": limit}
        response = self.public_request("GET", "/v4/public/depth", params)

        try:
            data = response.json()
            if data is None:
                error_response = json.loads(response.text)
                msg = ERROR_MAPPING[error_response.get("mc")]
                self.logger.error(f"[xt] {msg}")
                raise NoPriceFound()

        except JSONDecodeError as e:
            self.logger.error(f"[xt] {pair.default_name} - {response.text}")
            raise NoPriceFound() from e

        try:
            buy = data["result"]["asks"]
            sell = data["result"]["bids"]
        except KeyError as e:
            self.logger.error(f"[xt] {pair.default_name} - error parsing {data = }")
            raise NoPriceFound() from e

        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=50):
        url = self.base_url + "/v4/public/depth"
        params = {"symbol": pair.underscored_name.lower(), "limit": limit}

        response = await self.connection.get(url, params=params)
        try:
            data = response.json()
            if data is None:
                error_response = json.loads(response.text)
                msg = ERROR_MAPPING[error_response.get("mc")]
                self.logger.error(f"[xt] {msg}")
                raise NoPriceFound()

        except JSONDecodeError as e:
            self.logger.error(f"[xt] {pair.default_name} - {response.text}")
            raise NoPriceFound() from e

        try:
            buy = data["result"]["asks"]
            sell = data["result"]["bids"]
        except KeyError as e:
            self.logger.error(f"[xt] {pair.default_name} - error parsing {data = }")
            raise NoPriceFound() from e

        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair: Pair) -> float:
        params = {
            "symbol": pair.underscored_name.lower(),
        }
        response = self.public_request("GET", "/v4/public/ticker/24h", params=params)
        data = response.json()
        if data is None:
            error_response = json.loads(response.text)
            msg = ERROR_MAPPING[error_response.get("mc")]
            self.logger.error(f"[xt] {msg}")
            return 0

        return float(data["result"][0]["q"])

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.xt.com/en/trade/{pair.underscored_name.lower()}"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.xt.com/wallet/account/common/deposit?currency={cne.coin.name.lower()}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.xt.com/wallet/account/common/withdrawal?currency={cne.coin.name.lower()}"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.public_request(
            "GET",
            "/v4/public/kline",
            {"symbol": pair.underscored_name.lower(), "interval": "1m", "limit": 10},
        )
        data = response.json()
        opened = float(data["result"][-1]["o"])
        closed = float(data["result"][0]["c"])
        if data is None:
            error_response = json.loads(response.text)
            msg = ERROR_MAPPING[error_response.get("mc")]
            self.logger.error(f"[xt] {msg}")
            return 0

        change = (closed - opened) / opened * 100
        return change

    def get_balance(self, coin_name: str = "usdt") -> float:
        # params = {"currency": coin_name.lower()}
        # response = self.sign_request("GET", "/v4/balance", params)
        # try:
        #     data = response.json()
        #     if data is None:
        #         error_response = json.loads(response.text)
        #         msg = ERROR_MAPPING[error_response.get("mc")]
        #         self.logger.error(f"[xt] {msg}")
        #         raise WithdrawError(f"[xt] {msg}") from None
        #
        # except JSONDecodeError as e:
        #     self.logger.error(f"[xt] Error getting balance for {coin_name}. {response.text}")
        #     raise WithdrawError("Couldn't get balance") from e
        #
        # return float(data["result"]["availableAmount"])
        return 0

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        try:
            response = self.sign_request(
                "POST",
                "/v4/deposit/address",
                params={
                    "currency": cne.coin.name.lower(),
                    "network": cne.network.name,
                },
            )
        except Exception as e:
            self.logger.error(f"[xt] deposit address error - {e}")
            raise DepositAddressError() from e

        try:
            data = response.json()
            if data is None:
                error_response = json.loads(response.text)
                msg = ERROR_MAPPING[error_response.get("mc")]
                self.logger.error(f"[xt] {msg}")
                raise DepositAddressError() from None

            address = DepositAddress(data["result"]["address"], data["result"].get("memo"))

        except JSONDecodeError as e:
            self.logger.error(f"[xt] deposit address error. couldn't parse response. {response.text}")
            raise DepositAddressError() from e
        except KeyError as e:
            self.logger.error(f"[xt] deposit address error. couldn't parse response. {data}")
            raise DepositAddressError() from e
        else:
            return address

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

        body = {
            "currency": cne.coin.name.lower(),
            "chain": cne.network.name,
            "amount": amount,
            "address": deposit_address.address,
        }
        if deposit_address.memo:
            body["memo"] = deposit_address.memo

        try:
            response = self.sign_request("POST", "/v4/withdraw", body=body)
        except Exception as e:
            self.logger.exception(e)
            raise WithdrawError(f"[xt] Unknown exception, {e}") from e

        try:
            data = response.json()
            if data is None:
                error_response = json.loads(response.text)
                msg = ERROR_MAPPING[error_response.get("mc")]
                self.logger.error(f"[xt] {msg}")
                raise WithdrawError(f"{msg}")

        except JSONDecodeError as e:
            self.logger.exception(e)
            raise WithdrawError(f"Couldn't parse response, {response.text}") from e

    def create_order(self, pair: Pair, ccy_quantity: float, ccy_precision: int, price: float, price_precision: int):
        body = {
            "symbol": pair.underscored_name.lower(),
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "FOK",
            "bizType": "SPOT",
            "quantity": f"{ccy_quantity:.{ccy_precision}f}",
            "price": f"{price:.{price_precision}f}",
        }
        response = self.sign_request("POST", "/v4/order", body=body)

        try:
            data = response.json()
            if data is None:
                error_response = json.loads(response.text)
                msg = ERROR_MAPPING[error_response.get("mc")]
                self.logger.error(f"[xt] {msg}")
                raise CreateOrderError(f"[xt] {msg}")

        except JSONDecodeError as e:
            self.logger.error(f"[xt] couldn't parse response. {response.text}. {body = }")
            raise CreateOrderError("Couldn't parse response. Check logs") from e
