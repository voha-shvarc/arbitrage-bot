from decimal import Decimal
from decimal import ROUND_DOWN
from decimal import ROUND_HALF_EVEN
from json import JSONDecodeError
from logging import getLogger
from typing import List

from aiolimiter import AsyncLimiter
from huobi.client.account import AccountClient
from huobi.client.generic import GenericClient
from huobi.client.market import MarketClient
from huobi.client.trade import TradeClient
from huobi.client.wallet import WalletClient
from huobi.constant import DepthStep
from huobi.constant import InstrumentStatus
from huobi.constant.definition import AccountBalanceUpdateType
from huobi.constant.definition import OrderType
from huobi.exception.huobi_api_exception import HuobiApiException

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


class HuobiAPI(AbstractExchange):
    NAME = "Huobi"
    ACCOUNT_ID = 58372812
    base_url = "https://api.huobi.pro"
    async_limiter = AsyncLimiter(9.5, 0.2)  # 47.5r/1s

    def __init__(self, config, connection, logger=None):
        self.connection = connection
        self.logger = logger or error_logger

        api_key = config["HUOBI_API_KEY"]
        api_secret = config["HUOBI_API_SECRET"]

        self.client = GenericClient(api_key=api_key, secret_key=api_secret)
        self.price_client = MarketClient(api_key=api_key, secret_key=api_secret)
        self.account_client = AccountClient(api_key=api_key, secret_key=api_secret)
        self.wallet_client = WalletClient(api_key=api_key, secret_key=api_secret)
        self.trade_client = TradeClient(api_key=api_key, secret_key=api_secret)

    def get_trading_pairs(self) -> List[TradingPair]:
        pairs_info = self.client.get_exchange_symbols()
        trading_pairs = [
            TradingPair(
                base_coin=pair_info.base_currency.upper(),
                quote_coin=pair_info.quote_currency.upper(),
                exchange=self.NAME,
                base_coin_precision=pair_info.amount_precision,
                quote_coin_precision=pair_info.price_precision,
                taker_fee=0.002,  # 0.2%
                maker_fee=0.002,  # 0.2%
            )
            for pair_info in pairs_info
            if pair_info.state == "online"
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        for coin_data in self.client.get_reference_currencies():
            if coin_data.instStatus == InstrumentStatus.NORMAL:
                yield CoinNetworkExchangeDC.from_huobi(coin_data)

    def get_price(self, pair: Pair, limit=30) -> tuple[list[list[str]], list[list[str]]]:
        try:
            depth = self.price_client.get_pricedepth(pair.huobi_name, DepthStep.STEP0, limit)
        except Exception:
            raise NoPriceFound()

        buy = [[str(ask.price), str(ask.amount)] for ask in depth.asks]
        sell = [[str(bid.price), str(bid.amount)] for bid in depth.bids]
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=20):
        url = self.base_url + "/market/depth"
        body = {
            "symbol": pair.huobi_name,
            "depth": limit,
            "type": DepthStep.STEP0,
        }
        response = await self.connection.get(url, params=body)
        try:
            data = response.json()
        except JSONDecodeError:
            self.logger.error(f"[huobi] {pair.default_name} - {response.text}")
            raise NoPriceFound()

        if data.get("err-msg") in ["invalid symbol", "request limit"]:
            self.logger.error(f"[huobi] {pair.default_name} - {data['err-msg']}")
            raise NoPriceFound()

        try:
            buy = data["tick"]["asks"]
            sell = data["tick"]["bids"]
        except KeyError as e:
            self.logger.error(f"[huobi] {pair.default_name} - error parsing data {data =}\n{e}")
            raise NoPriceFound()

        if not sell or not buy:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair) -> float:
        data = self.price_client.get_market_detail_merged(symbol=pair.huobi_name)
        return data.amount

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.htx.com/en-us/trade/{pair.underscored_name.lower()}?type=spot"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.htx.com/en-us/finance/deposit/{cne.coin.name.lower()}"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.htx.com/en-us/finance/withdraw/{cne.coin.name.lower()}"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        response = self.price_client.get_candlestick(symbol=pair.huobi_name, period="1min", size=10)
        opened = response[-1].open
        closed = response[0].close
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self, coin_name: str = "USDT") -> float:
        account_balance = self.account_client.get_balance(self.ACCOUNT_ID)
        for balance in account_balance.list:
            if balance.currency == coin_name.lower() and balance.type == AccountBalanceUpdateType.TRADE:
                return float(balance.balance)

        raise WithdrawError(f"No available balance for {coin_name}")

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        try:
            data = self.wallet_client.get_account_deposit_address(cne.coin.name.lower())
            for net in data:
                if net.chain == cne.plain_network_name:
                    return DepositAddress(net.address, net.addressTag)
        except Exception as e:
            self.logger.error(f"[huobi] deposit address error - {e}")
            raise DepositAddressError() from e
        else:
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
        price = Decimal(price).quantize(Decimal(f"1e-{price_precision}"), rounding=ROUND_HALF_EVEN)
        body = {
            "symbol": pair.huobi_name,
            "account_id": self.ACCOUNT_ID,
            "order_type": OrderType.BUY_LIMIT_FOK if is_buy else OrderType.SELL_LIMIT,
            "amount": float(qty),
            "price": float(price),
        }
        try:
            self.trade_client.create_spot_order(**body)
        except HuobiApiException as e:
            self.logger.exception(f"[huobi] create order error - {e}. {body = }")
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
            "currency": cne.coin.name.lower(),
            "chain": cne.plain_network_name,
            "address": deposit_address.address,
            "address_tag": deposit_address.memo or "",
            "amount": amount,
            "fee": cne.withdraw_fee,
        }
        try:
            self.wallet_client.post_create_withdraw(**body)
        except HuobiApiException as e:
            self.logger.error(f"[huobi] {e.error_message = }, {body = }")
            raise WithdrawError(e.error_message) from e
