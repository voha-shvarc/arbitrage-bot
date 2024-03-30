from json import JSONDecodeError
from logging import getLogger
from typing import List

from bingX.api import API
from bingX.error import ClientError
from bingX.spot import Spot

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


class BingxAPI(AbstractExchange):
    NAME = "Bingx"
    withdraw_status = WithdrawStatus.enabled

    def __init__(self, config, connection, logger=None):
        self.connection = connection
        self.logger = logger or error_logger

        api_key = config["BINGX_API_KEY"]
        api_secret = config["BINGX_API_SECRET"]
        self.client = Spot(api_key, api_secret)
        self.api_client = API(api_key, api_secret, base_url="https://open-api.bingx.com")

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.client.symbols()
        trading_pairs = [
            TradingPair(
                base_coin=pair["symbol"].split("-")[0],
                quote_coin=pair["symbol"].split("-")[1],
                exchange=self.NAME,
                base_coin_precision=self.__step_to_precision(pair["stepSize"]),
                quote_coin_precision=self.__step_to_precision(pair["tickSize"]),
            )
            for pair in pairs_info["symbols"]
            if pair["symbol"].split("-")[1] == "USDT"
        ]
        return trading_pairs

    @staticmethod
    def __step_to_precision(step: float) -> int:
        precision = str(step)
        if "1e-" in precision:
            return int(precision[-2:])
        else:
            return len(precision) - 2

    def get_coin_exchange_networks(self):
        for coin_data in self.client.get("/openApi/wallets/v1/capital/config/getall")["data"]:
            yield CoinNetworkExchangeDC.from_bingx(coin_data)

    def get_price(self, pair: Pair, limit=30) -> tuple[list[list[str]], list[list[str]]]:
        response = self.client.depth(symbol=pair.dashed_name, limit=limit)
        buy = response["asks"]
        sell = response["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=30):
        path = "/openApi/spot/v1/market/depth"
        params = {"symbol": pair.dashed_name, "limit": limit}
        url = f"{self.client.base_url}{path}?{self.client._handle_params(params, path, 'GET')}"

        response = await self.connection.get(url, headers=self.client.headers)
        try:
            data = response.json()
        except JSONDecodeError:
            self.logger.error(f"[bingx] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        if "code" in data and data["code"]:
            self.logger.error(f"[bingx] {pair.default_name} - {data['code']}, {data['msg']}")
            raise NoPriceFound()

        try:
            buy = data["data"]["asks"]
            sell = data["data"]["bids"]
        except KeyError as e:
            self.logger.error(f"[bingx] {pair.default_name} - error parsing data {data =}\n{e}")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair: Pair) -> float:
        response = self.client.get(
            "/openApi/spot/v1/ticker/24hr",
            params={"symbol": pair.dashed_name},
        )
        return response["data"][0]["volume"]

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://bingx.com/en-us/spot/{pair.default_name}"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = "https://bingx.com/en-us/assets/recharge"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = "https://bingx.com/en-us/assets/withdraw/"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.client.get(
            "/openApi/spot/v2/market/kline",
            params={"symbol": "BTC-USDT", "interval": "1m", "limit": 10},
        )
        opened = response["data"][-1][1]
        closed = response["data"][0][4]
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self, coin_name: str = "USDT") -> float:
        data = self.client.assets()
        for balance_data in data["balances"]:
            if balance_data["asset"] == coin_name:
                balance = float(balance_data["free"])
                return balance

        raise WithdrawError(f"No available balance for {coin_name}")

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        try:
            data = self.api_client.get("/openApi/wallets/v1/capital/deposit/address", params={"coin": cne.coin.name})
            for network_data in data["data"]["data"]:
                if network_data["network"] == cne.network.name:
                    address = network_data["address"]
                    if address == "0494d7654faf6ac77cabf002aab0e1ba5534404c":
                        address = f"0x{address}"
                    address = DepositAddress(address, network_data.get("tag"))
                    return address
        except Exception as e:
            self.logger.error(f"[bingx] deposit address error - {e}")
            raise DepositAddressError(str(e)) from e
        else:
            self.logger.error(f"[bingx] empty deposit address data - {data}")
            raise DepositAddressError(f"empty deposit address data - {data}")

    def withdraw(self, cne: CoinNetworkExchange, deposit_address: DepositAddress) -> None:
        amount = self.get_balance(cne.coin.name)
        body = {
            "coin": cne.coin.name,
            "network": cne.network.name,
            "address": deposit_address.address,
            "amount": amount,
            "walletType": "1",
        }
        if deposit_address.memo:
            body["addressTag"] = deposit_address.memo

        try:
            data = self.api_client.post("/openApi/wallets/v1/capital/withdraw/apply", params=body)
        except Exception as e:
            self.logger.exception(e)
            raise WithdrawError(f"[bingx] unknown exception {e}") from e

        if data["code"] != 0:
            msg = data["msg"]
            self.logger.error(f"[bingx] error creating order - {data['msg']}")
            raise WithdrawError(msg)

    def create_order(self, pair: Pair, ccy_quantity: float, ccy_precision: int, price: float, price_precision: int):
        body = {
            "symbol": pair.dashed_name,
            "side": "BUY",
            "type": "LIMIT",
            "quantity": f"{ccy_quantity:.{ccy_precision}f}",
            "price": f"{price:.{price_precision}f}",
        }
        try:
            self.client.place_order(**body)
        except ClientError as e:
            self.logger.exception(f"[bingx] create order error - {e}. {body = }")
            raise CreateOrderError(str(e)) from e
