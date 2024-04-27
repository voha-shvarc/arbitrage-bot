from decimal import Decimal
from decimal import ROUND_DOWN
from json import JSONDecodeError
from logging import getLogger
from typing import List

from aiolimiter import AsyncLimiter
from gate_api import ApiClient
from gate_api import Configuration
from gate_api import SpotApi
from gate_api import WalletApi
from gate_api.api.withdrawal_api import WithdrawalApi
from gate_api.exceptions import GateApiException

from abstract import AbstractExchange
from abstract import NoPriceFound
from abstract.abstract import CanceledOrderError
from abstract.abstract import CreateOrderError
from abstract.abstract import DepositAddressError
from abstract.abstract import WithdrawError
from abstract.abstract import WithdrawStatus
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import CoinNetworkExchangeDC
from db.structs import DepositAddress
from db.structs import TradingPair


error_log = getLogger("error")


class GateIOAPI(AbstractExchange):
    NAME = "GateIO"
    base_url = "https://api.gateio.ws"
    withdraw_status = WithdrawStatus.whitelist
    async_limiter = AsyncLimiter(2.8, 0.2)  # 14r/1s  max? 20r/1s

    def __init__(self, config, connection, logger=None):
        self.connection = connection
        self.logger = logger or error_log

        api_key = config["GATEIO_API_KEY"]
        secret_key = config["GATEIO_API_SECRET"]
        api_config = ApiClient(Configuration(key=api_key, secret=secret_key))
        self.spot_client = SpotApi(api_config)
        self.withdraw_client = WithdrawalApi(api_config)
        self.account_client = WalletApi(api_config)

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.spot_client.list_currency_pairs()
        trading_pairs = [
            TradingPair(
                base_coin=pair.base,
                quote_coin=pair.quote,
                exchange=self.NAME,
                base_coin_precision=pair.amount_precision,
                quote_coin_precision=pair.precision,
                taker_fee=float(pair.fee) / 2 / 100,
                maker_fee=float(pair.fee) / 2 / 100,
            )
            for pair in pairs_info
            if pair.quote == "USDT" and pair.trade_status == "tradable"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        for coin_data in self.spot_client.list_currencies():
            if not coin_data.delisted:
                yield CoinNetworkExchangeDC.from_gateio(coin_data)

    def get_price(self, pair: Pair, limit=30) -> tuple[list[list[str]], list[list[str]]]:
        res = self.spot_client.list_order_book(pair.underscored_name)
        buy = res.asks
        sell = res.bids
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=30):
        url = self.base_url + "/api/v4/spot/order_book"
        body = {
            "currency_pair": pair.underscored_name,
            "limit": limit,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = await self.connection.get(url, params=body, headers=headers)
        try:
            data = response.json()
        except JSONDecodeError as e:
            error_log.error(f"[gateio] {pair.default_name} - {response.text}")
            raise NoPriceFound() from e

        try:
            buy = data["asks"]
            sell = data["bids"]
        except KeyError as e:
            error_log.error(f"[gateio] {pair.default_name} - error parsing data {data =}\n{e}")
            raise NoPriceFound() from e

        if not buy or not sell:
            raise NoPriceFound()

        return data["asks"], data["bids"]

    def get_pair_trading_volume(self, pair: Pair) -> float:
        data = self.spot_client.list_tickers(currency_pair=pair.underscored_name)
        return float(data[0].base_volume)

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.gate.io/trade/{pair.underscored_name}"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.gate.io/ru/myaccount/deposit/{cne.coin.name}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.gate.io/ru/myaccount/withdraw/{cne.coin.name}"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.spot_client.list_candlesticks(
            currency_pair=pair.underscored_name,
            interval="1m",
            limit=3,
        )
        opened = float(response[0][5])
        closed = float(response[0][2])
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self, coin_name: str = "USDT") -> float:
        spot_accounts = self.spot_client.list_spot_accounts(currency=coin_name)
        return float(spot_accounts[0].available)

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        try:
            data = self.account_client.get_deposit_address(cne.coin.name)
        except GateApiException as e:
            self.logger.error(f"[gateio] {e.message = }; {e.body = }")
            raise DepositAddressError() from e

        for chain in data.multichain_addresses:
            if chain.chain == cne.network.name:
                return DepositAddress(chain.address, chain.payment_id)

        self.logger.error("[gateio] no deposit address was found")
        raise DepositAddressError()

    def create_order(
        self,
        pair: Pair,
        ccy_quantity: float,
        ccy_precision: int,
        price: float,
        price_precision: int,
        spot_fee: float,
        is_buy: bool = True,
    ):
        qty = Decimal(ccy_quantity).quantize(Decimal(f"1e-{ccy_precision}"), rounding=ROUND_DOWN)
        price = Decimal(price).quantize(Decimal(f"1e-{price_precision}"), rounding=ROUND_DOWN)
        body = {
            "currency_pair": pair.underscored_name,
            "type": "limit",
            "account": "spot",
            "side": "buy" if is_buy else "sell",
            "amount": str(qty),
            "price": str(price),
            "time_in_force": "fok" if is_buy else "gtc",
        }
        try:
            self.spot_client.create_order(body)
        except GateApiException as e:
            self.logger.error(f"[gateio] {e.message}")
            if e.label == "FOK_NOT_FILL":
                raise CanceledOrderError() from e
            else:
                raise CreateOrderError(e.message) from e

    def withdraw(
        self,
        cne: CoinNetworkExchange,
        ccy_quantity_to_withdraw: float,
        deposit_address: DepositAddress,
    ) -> None:
        if cne.withdraw_precision:
            amount = Decimal(ccy_quantity_to_withdraw).quantize(Decimal(f"1e-{cne.withdraw_precision}"), rounding=ROUND_DOWN)
        else:
            amount = ccy_quantity_to_withdraw

        body = {
            "currency": cne.coin.name,
            "address": deposit_address.address,
            "amount": str(amount),
            "memo": deposit_address.memo,
            "chain": cne.network.name,
        }
        try:
            self.withdraw_client.withdraw(body)
        except GateApiException as e:
            self.logger.error(f"[gateio] {e.message}")
            raise WithdrawError(e.message) from e
