from json import JSONDecodeError
from logging import getLogger
from typing import List

from binance.error import ClientError
from binance.spot import Spot

from abstract import AbstractExchange
from abstract import NoPriceFound
from abstract.abstract import CreateOrderError
from abstract.abstract import DepositAddressError
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import CoinNetworkExchangeDC
from db.structs import DepositAddress
from db.structs import TradingPair


error_log = getLogger("error")


class BinanceAPI(AbstractExchange):
    """For testing use different keys. more here https://testnet.binance.vision/"""

    NAME = "Binance"
    NOT_ALLOWED_STATUS = "BREAK"
    base_url = "https://api.binance.com"

    def __init__(self, config, connection):
        self.connection = connection

        self.api_key = config["BINANCE_API_KEY"]
        api_secret = config["BINANCE_API_SECRET"]
        self.client = Spot(api_key=self.api_key, api_secret=api_secret)

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.client.exchange_info(permissions=["SPOT"])
        trading_pairs = [
            TradingPair(base_coin=pair["baseAsset"], quote_coin=pair["quoteAsset"], exchange=self.NAME)
            for pair in pairs_info["symbols"]
            if self._is_valid_pair(pair)
        ]
        return trading_pairs

    def _is_valid_pair(self, coin_data):
        return (
            coin_data["isSpotTradingAllowed"]
            and coin_data["quoteAsset"] == "USDT"
            and coin_data["status"] != self.NOT_ALLOWED_STATUS
        )

    def get_coin_exchange_networks(self):
        for coin_data in self.client.coin_info():
            yield CoinNetworkExchangeDC.from_binance(coin_data)

    def get_price(self, pair: Pair, limit=30) -> tuple[list[list[str]], list[list[str]]]:
        order_book = self.client.depth(symbol=pair.default_name, limit=limit)
        buy = order_book["asks"]
        sell = order_book["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=30):
        url = self.base_url + "/api/v3/depth"
        body = {
            "symbol": pair.default_name,
            "limit": limit,
        }
        headers = {
            "Content-Type": "application/json;charset=utf-8",
            "User-Agent": "binance-connector-python/3.3.1",
            "X-MBX-APIKEY": self.api_key,
        }
        response = await self.connection.get(url, params=body, headers=headers)
        try:
            data = response.json()
        except JSONDecodeError:
            error_log.error(f"[binance] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        try:
            buy = data["asks"]
            sell = data["bids"]
        except KeyError as e:
            error_log.error(f"[binance] {pair.default_name} - error parsing data {data =}\n{e}")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair) -> float:
        data = self.client.ticker_24hr(symbol=pair.default_name)
        return float(data["volume"])

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.binance.com/en/trade/{pair.underscored_name}?type=spot"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.binance.com/en/my/wallet/account/main/deposit/crypto/{cne.coin.name}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.binance.com/en/my/wallet/account/main/withdrawal/crypto/{cne.coin.name}"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.client.rolling_window_ticker(symbol=pair.default_name, windowSize="15m")
        return float(response["priceChangePercent"])

    def get_balance(self) -> float:
        response = self.client.user_asset(asset="USDT")
        try:
            balance = float(response[0]["free"])
        except (KeyError, IndexError):
            balance = 0

        return balance

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        try:
            data = self.client.deposit_address(coin=cne.coin.name, network=cne.network.name)
            address = DepositAddress(data["address"], data["tag"])
        except Exception as e:
            error_log.error(f"[binance] deposit address error - {e}")
            raise DepositAddressError() from e
        else:
            return address

    def create_order(self, pair: Pair, ccy_quantity: float, price: float):
        body = {
            "symbol": pair.default_name,
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "FOK",
            "quantity": ccy_quantity,
            "price": price,
        }
        try:
            self.client.new_order(**body)
        except ClientError as e:
            error_log.exception(f"[binance] create order error - {e}. {body = }")
            raise CreateOrderError(str(e)) from e
