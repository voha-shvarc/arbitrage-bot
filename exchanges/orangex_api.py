import requests
from pprint import pp


api_key = "fd8f2bf2"
api_secret = "27f64a48b54b33484b97ab8a"
base_url = "https://api.orangex.com/api/v1"

access_token = "K5bDKdkeNUBNyLFZJqp1HbT++sa9oh2qn3yqJn7HBadHUzznyyOlDFx/SE3ukgXI6bdRBrdjm3IoYhJpemQazWMQPijMQANn7vSL6JW0/8cDIDuROSdUsaYWY9PETRRFB7DjbmJeUse5O8XuQoNFNB2UOcmTQ0qw8VxyoTmVdO4="
refresh_token = "a9ABJY9N4TVFu4Hho2/hUiHFuNzcP9zaqU1u9PrMKk9kn1R4CCgylkVP0pNmpBaWYC510mlrzxLdXPwZKXDrhyzoOx9lfxx6O+G/jv6cKII="

# auth
import hmac
import hashlib
import time
timestamp = str(time.time() * 1000)
string_to_sing = f"{api_key}\n{timestamp}\n"
sign = hmac.new(api_secret.encode("utf-8"), string_to_sing.encode("utf-8"), hashlib.sha256).hexdigest()

path = "/public/auth"
body = {
    "jsonrpc": "2.0",
    "method": path,
    "params": {
        "grant_type": "client_signature",
        "client_id": api_key,
        "signature": sign,
        "nonce": "dfsfa",
        "timestamp": timestamp
    }
}

response = requests.post(base_url + path, json=body)
data = response.json()
pp(data)


# get trading pairs
# path = "/public/get_instruments"
# body = {
#     "jsonrpc": "2.0",
#     "method": path,
#     "params": {
#         "currency": "SPOT",
#         "kind": "spot"
#     }
# }
# response = requests.post(base_url + path, json=body)
# data = response.json()
# for pair_info in data["result"]:
#     base = pair_info["base_currency"]
#     quote = pair_info["quote_currency"]
#     base_p = len(pair_info["min_qty"]) - 2
#     quote_p = len(pair_info["tick_size"]) - 2
#     print(base, quote, base_p, quote_p)
# pp(data)

# cne
# path = "/public/get_coin_config"
# body = {
#     "jsonrpc": "2.0",
#     "method": path,
#     "params": {
#
#     }
# }
# response = requests.post(base_url + path, json=body)
# data = response.json()
# for currency_info in data["result"]:
#     coin_name = currency_info["coin_type"]

# price
# path = "/public/get_order_book"
# body = {
#     "jsonrpc": "2.0",
#     "method": path,
#     "params": {
#         "instrument_name": "BTC-USDT-SPOT",
#     }
# }
# response = requests.post(base_url + path, json=body)
# data = response.json()
# asks = data["result"]["asks"]
# bids = data["result"]["bids"]
# print(asks, bids)
# pp(data)

# trading volume
# path = "/public/tickers"
# body = {
#     "jsonrpc": "2.0",
#     "method": path,
#     "params": {
#         "instrument_name": "BTC-USDT-SPOT"
#     }
# }
# response = requests.post(base_url + path, json=body)
# data = response.json()
# volume = float(data["result"][0]["stats"]["volume"])
# print(volume)


# chart change
# import time
# path = "/public/get_tradingview_chart_data"
# now_time = int(time.time())
# body = {
#     "jsonrpc": "2.0",
#     "method": path,
#     "params": {
#         "instrument_name": "BTC-USDT",
#         "resolution": "1",
#         "start_timestamp": str((now_time - 600) * 1000),
#         "end_timestamp": str(now_time * 1000),
#     }
# }
# response = requests.post(base_url + path, json=body)
# data = response.json()
# opened = float(data["result"][0]["open"])
# closed = float(data["result"][-1]["close"])
# print(opened, closed)
# pp(data)

headers = {
    "Authorization": f"bearer {access_token}"
}
# balance
# path = "/private/get_assets_info"
# body = {
#     "jsonrpc": "2.0",
#     "method": path,
#     "params": {
#         "asset_type": ["SPOT"],
#         "coin_type": ["USDT"]
#     }
# }
# response = requests.post(base_url + path, json=body, headers=headers)
# data = response.json()
# balance = float(data["result"]["SPOT"]["details"][0]["available"])
# print(balance)
# pp(data)

# withdraw
# path = "/private/withdraw"
# body = {
#     "jsonrpc": "2.0",
#     "method": path,
#     "params": {
#         "coin_type": "USDT",
#         "main_chain": "ETH",
#         "address": "jfksajfalsj",
#         "amount": "100",
#     }
# }
#
# response = requests.post(base_url + path, json=body, headers=headers)
# data = response.json()
# pp(data)
import hashlib
import json
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


class OrangeXAPI(AbstractExchange):
    NAME = "OrangeX"
    base_url = "https://api.orangex.com/api/v1"

    def __init__(self, config, connection, logger=None):
        self.connection = connection
        self.logger = logger or error_logger

        self.api_key = config["ORANGEX_API_KEY"]
        self.api_secret = config["ORANGEX_API_SECRET"]

        self.headers = {
            "Authorization": f"bearer {1}"
        }

    def public_request(self, path, params=None, **kwargs):
        body = {
            "jsonrpc": "2.0",
            "method": path,
            "params": params or {}
        }
        url = self.base_url + path
        response = requests.post(url, json=body, **kwargs)
        data = response.json()
        return data["result"]

    def get_trading_pairs(self) -> List[TradingPair]:
        params = {
            "currency": "SPOT",
            "kind": "spot",
        }
        data = self.public_request("/public/get_instruments", params)

        trading_pairs = [
            TradingPair(
                base_coin=pair["quote_currency"],
                quote_coin=pair["base_currency"],
                base_coin_precision=max(len(pair["min_trade_amount"]) - 2, 1),
                quote_coin_precision=max(len(pair["tick_size"]) - 2, 1),
                exchange=self.NAME,
            )
            for pair in data
            if pair["base_currency"] == "USDT" and pair["is_active"]
        ]
        return trading_pairs

    def get_coin_exchange_networks(self):
        data = self.public_request("/public/get_coin_config")
        for coin_data in data:
            yield CoinNetworkExchangeDC.from_orangex(coin_data)

    def get_price(self, pair: Pair, limit=50) -> tuple[list[list[str]], list[list[str]]]:
        params = {
            "instrument_name": f"{pair.dashed_name}-SPOT",
            "depth": limit,
        }
        data = self.public_request("/public/get_order_book", params)

        try:
            buy = data["asks"]
            sell = data["bids"]
        except KeyError:
            self.logger.error(f"[OrangeX] {pair.default_name} - error parsing {data = }")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell

    async def async_get_price(self, pair: Pair, limit=50):
        params = {
            "instrument_name": f"{pair.dashed_name}-SPOT",
            "depth": limit,
        }
        url = self.base_url + "/public/get_order_book"
        data = await self.connection.get(url, params=params)

        try:
            buy = data["asks"]
            sell = data["bids"]
        except KeyError:
            self.logger.error(f"[OrangeX] {pair.default_name} - error parsing {data = }")
            raise NoPriceFound()

        if not buy or not sell:
            raise NoPriceFound()

        return buy, sell

    def get_pair_trading_volume(self, pair: Pair) -> float:
        params = {
            "instrument_name": f"{pair.dashed_name}-SPOT"
        }
        data = self.public_request("/public/tickers", params=params)

        return float(data[0]["stats"]["volume"])

    @classmethod
    def spot_link(cls, pair: Pair) -> str:
        link = f"https://www.orangex.com/spot/{pair.dashed_name}-SPOT"
        return link

    @classmethod
    def deposit_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.orangex.com/account/wallet/deposit?coin={cne.coin.name}&at=SPOT"
        return link

    @classmethod
    def withdraw_link(cls, cne: CoinNetworkExchange) -> str:
        link = f"https://www.orangex.com/account/wallet/withdraw?coin={cne.coin.name}&at=SPOT"
        return link

    def get_pair_chart_change(self, pair: Pair) -> float:
        now_time = int(time.time())
        params = {
            "instrument_name": "BTC-USDT",
            "resolution": "1",
            "start_timestamp": str((now_time - 600) * 1000),
            "end_timestamp": str(now_time * 1000),

        }
        data = self.public_request("/public/get_tradingview_chart_data", params)

        opened = float(data[0]["open"])
        closed = float(data[-1]["close"])
        change = (closed - opened) / opened * 100
        return change

    def get_balance(self, coin_name: str = "USDT") -> float:
        params = {
            "asset_type": ["SPOT"],
            "coin_type": [coin_name]
        }
        data = self.public_request("/private/get_assets_info", params, headers=self.headers)

        return float(data["SPOT"]["details"][0]["available"])

    def get_deposit_address(self, cne: CoinNetworkExchange) -> DepositAddress:
        raise DepositAddressError() from None

    def withdraw(self, cne: CoinNetworkExchange, deposit_address: DepositAddress) -> None:
        raise WithdrawError() from None

    def create_order(self, pair: Pair, ccy_quantity: float, ccy_precision: int, price: float, price_precision: int):
        params = {
            "instrument_name": f"{pair.dashed_name}-SPOT",
            "type": "limit",
            "time_in_force": "fill_or_kill",
            "amount": f"{ccy_quantity:.{ccy_precision}f}",
            "price": f"{price:.{price_precision}f}",
        }
        self.public_request("/private/buy", params, headers=self.headers)
