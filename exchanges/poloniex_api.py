from json import JSONDecodeError
from logging import getLogger
from typing import List

from abstract import AbstractExchange
from abstract.abstract import CreateOrderError
from abstract.abstract import NoPriceFound
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import CoinNetworkExchangeDC
from db.structs import DepositAddress
from db.structs import TradingPair
from exchanges.polosdk import RestClient
from exchanges.polosdk.rest.accounts import Accounts
from exchanges.polosdk.rest.markets import Markets
from exchanges.polosdk.rest.orders import Orders
from exchanges.polosdk.rest.request import Request
from exchanges.polosdk.rest.wallets import Wallets


error_logger = getLogger("error")


class PoloniexAPI(AbstractExchange):
    NAME = "Poloniex"
    ACCOUNT_ID = 292397646520455168
    base_url = "https://api.poloniex.com"

    def __init__(self, config, connection, logger=None):
        self.connection = connection
        self.logger = logger or error_logger

        api_key = config["POLONIEX_API_KEY"]
        api_secret = config["POLONIEX_API_SECRET"]
        self.market_client = Markets()
        self.orders_client = Orders(api_key, api_secret)
        self.account_client = Accounts(api_key, api_secret)
        self.wallet_client = Wallets(api_key, api_secret)
        self.rest_client = RestClient(api_key, api_secret)
        self.request = Request(api_key, api_secret)

    def get_trading_pairs(self) -> List[TradingPair]:
        response = self.rest_client.get_markets()
        trading_pairs = [
            TradingPair(
                base_coin=pair_info["baseCurrencyName"],
                quote_coin=pair_info["quoteCurrencyName"],
                base_coin_precision=int(pair_info["symbolTradeLimit"]["amountScale"]),
                quote_coin_precision=int(pair_info["symbolTradeLimit"]["priceScale"]),
                exchange=self.NAME,
            )
            for pair_info in response
            if pair_info["state"] == "NORMAL"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        response = self.request("GET", "/v2/currencies")
        for coin_data in response:
            if not coin_data["delisted"] and coin_data["tradeEnable"]:
                yield CoinNetworkExchangeDC.from_poloniex(coin_data)

    def get_price(self, pair: Pair, limit=50) -> tuple[list[list[str]], list[list[str]]]:
        response = self.market_client.get_orderbook(pair.underscored_name, limit=limit)
        buy = response["asks"]
        sell = response["bids"]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=30):
        path = f"/markets/{pair.underscored_name}/orderBook"
        params = {"limit": limit}
        headers = {
            "content-type": "application/json",
        }
        url = self.base_url + path

        response = await self.connection.get(url, params=params, headers=headers)
        try:
            data = response.json()
        except JSONDecodeError:
            self.logger.error(f"[poloniex] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        if "code" in data and data["code"]:
            self.logger.error(f"[poloniex] {pair.default_name} - {data['code']}, {data['msg']}")
            raise NoPriceFound()

        try:
            buy = data["data"]["asks"]
            sell = data["data"]["bids"]
        except KeyError as e:
            self.logger.error(f"[poloniex] {pair.default_name} - error parsing data {data =}\n{e}")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair: Pair) -> float:
        response = self.market_client.get_ticker24h(pair.underscored_name)
        return float(response["quantity"])

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.market_client.get_candles(pair.underscored_name, interval="MINUTE_1", limit=10)
        opened = float(response[0][2])
        closed = float(response[-1][2])
        change = (opened - closed) / opened * 100
        return change

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://poloniex.com/trade/{pair.underscored_name}/?type=spot"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://poloniex.com/wallet/deposit/{cne.coin.name}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://poloniex.com/wallet/withdraw/{cne.coin.name}"
        return link

    def get_balance(self, coin_name: str = "USDT") -> float:
        # res = account_client.get_account_balances()
        return 0

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        response = self.wallet_client.create_address(cne.plain_network_name)
        return DepositAddress(response[cne.coin.name])

    def withdraw(self, cne: CoinNetworkExchange, deposit_address: DepositAddress) -> bool:
        amount = self.get_balance(cne.coin.name)
        body = {
            "currency": cne.coin.name,
            "network": cne.network.name,  # blockchain name
            "amount": amount,
            "address": deposit_address.address,
        }
        if deposit_address.memo:
            body["addressTag"] = deposit_address.memo

        response = self.request("POST", "v2/wallets/withdraw", params=body)
        self.logger.error(f"[poloniex withdraw] - {response}")

    def create_order(self, pair: Pair, ccy_quantity: float, ccy_precision: int, price: float, price_precision: int):
        body = {
            "symbol": pair.underscored_name,
            "time_in_force": "FOK",
            "type": "LIMIT",
            "side": "BUY",
            "quantity": f"{ccy_quantity:.{ccy_precision}f}",
            "price": f"{price:.{price_precision}f}",
        }
        response = self.orders_client.create(**body)

        try:
            data = response.json()
        except JSONDecodeError as e:
            self.logger.error(f"[poloniex] couldn't parse response. {response.text}. {body = }")
            raise CreateOrderError("Couldn't parse response. Check logs") from e
        if err_msg := data.get("msg"):
            self.logger.error(f"[poloniex] error creating order. {err_msg}. {body = }")
            raise CreateOrderError(err_msg)
