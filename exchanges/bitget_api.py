import base64
import hmac
import time
from json import JSONDecodeError
from logging import getLogger
from typing import List

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
from exchanges.bitget.exceptions import BitgetAPIException
from exchanges.bitget.v1.spot.account_api import AccountApi
from exchanges.bitget.v1.spot.market_api import MarketApi
from exchanges.bitget.v1.spot.order_api import OrderApi
from exchanges.bitget.v1.spot.wallet_api import WalletApi


error_logger = getLogger("error")


class BitgetAPI(AbstractExchange):
    NAME = "Bitget"
    ALLOWED_STATUS = "online"
    base_url = "https://api.bitget.com"

    def __init__(self, config, connection, logger=None):
        self.connection = connection
        self.logger = logger or error_logger

        self.api_key = config["BITGET_API_KEY"]
        self.api_secret = config["BITGET_API_SECRET"]
        self.api_passphrase = config["BITGET_API_PASSPHRASE"]
        self.client = MarketApi(api_key=self.api_key, api_secret_key=self.api_secret, passphrase=self.api_passphrase)
        self.account_client = AccountApi(
            api_key=self.api_key,
            api_secret_key=self.api_secret,
            passphrase=self.api_passphrase,
        )
        self.wallet_client = WalletApi(
            api_key=self.api_key,
            api_secret_key=self.api_secret,
            passphrase=self.api_passphrase,
        )
        self.order_client = OrderApi(
            api_key=self.api_key,
            api_secret_key=self.api_secret,
            passphrase=self.api_passphrase,
        )

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.client.products(params={})
        trading_pairs = [
            TradingPair(
                base_coin=pair["baseCoin"],
                quote_coin=pair["quoteCoin"],
                exchange=self.NAME,
                base_coin_precision=int(pair["quantityScale"]),
                quote_coin_precision=int(pair["priceScale"]),
                taker_fee=float(pair["takerFeeRate"]),
                maker_fee=float(pair["makerFeeRate"]),
            )
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

    async def async_get_price(self, pair: Pair, limit=30):
        url = self.base_url + "/api/spot/v1/market/depth"
        body = {
            "symbol": pair.bitget_name,
            "limit": limit,
        }
        timestamp = self.get_timestamp()
        sign = self.sign(self.pre_hash(timestamp, "GET", url, ""))
        header = self.get_header(sign, timestamp)
        response = await self.connection.get(url, params=body, headers=header)
        try:
            data = response.json()
        except JSONDecodeError:
            self.logger.error(f"[bitget] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        try:
            buy = data["data"]["asks"]
            sell = data["data"]["bids"]
        except (KeyError, TypeError) as e:
            self.logger.error(f"[bitget] {pair.default_name} - error parsing data {data = }; {response.text}\n{e}")
            raise NoPriceFound()

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
        coin_id = cne.extra_info.get("coin_id")
        if not coin_id:
            link = "https://www.bitget.com/asset/withdraw?coinId=2"
        else:
            link = f"https://www.bitget.com/asset/withdraw?coinId={coin_id}"

        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        params = {
            "symbol": pair.bitget_name,
            "period": "1min",
            "limit": "10",
        }
        response = self.client.candles(params=params)
        opened = float(response["data"][0]["open"])
        closed = float(response["data"][-1]["close"])
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self) -> float:
        params = {
            "coin": "USDT",
        }
        response = self.account_client.assetsLite(params=params)
        try:
            balance = float(response["data"][0]["available"])
        except (KeyError, IndexError):
            balance = 0

        return balance

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        try:
            response = self.wallet_client.depositAddress(params={"coin": cne.coin.name, "chain": cne.network.name})
            address = DepositAddress(response["data"]["address"], response["data"]["tag"])
        except Exception as e:
            self.logger.error(f"[bitget] deposit address error - {e}")
            raise DepositAddressError() from e
        else:
            return address

    def create_order(self, pair: Pair, ccy_quantity: float, ccy_precision: int, price: float, price_precision: int):
        body = {
            "symbol": pair.bitget_name,
            "side": "buy",
            "orderType": "limit",
            "force": "fok",
            "quantity": f"{ccy_quantity:.{ccy_precision}f}",
            "price": f"{price:.{price_precision}f}",
        }
        try:
            self.order_client.placeOrder(params=body)
        except BitgetAPIException as e:
            self.logger.exception(f"[bitget] create order error - {e}. {body = }")
            raise CreateOrderError(str(e)) from e

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
            "coin": cne.coin.name,
            "chain": cne.network.name,
            "address": deposit_address.address,
            "tag": deposit_address.memo or "",
            "amount": amount,
        }

        try:
            self.wallet_client.withdrawal(body)
        except BitgetAPIException as e:
            self.logger.error(f"[bitget] {e.message = }, {body = }")
            raise WithdrawError(e.message) from e
