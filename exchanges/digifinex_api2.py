import requests
import json
from pprint import pprint

api_key = ""
api_secret = ""


base_url = "https://openapi.digifinex.com/v3"


# trading pairs
# path = "/spot/symbols"
# response = requests.get(base_url + path)
# data = response.json()
# for pair_info in data["symbol_list"]:
#     if pair_info["status"] == "TRADING" and pair_info["quote_asset"] == "USDT":
#         base = pair_info["base_asset"]
#         quote = pair_info["quote_asset"]
#         base_pre = pair_info["amount_precision"]
#         price_pre = pair_info["price_precision"]
#         print(base, quote, base_pre, price_pre)

from itertools import groupby

#cne
# path = "/currencies"
# response = requests.get(base_url + path)
# data = response.json()["data"]
# s = sorted(data, key=lambda x: x["currency"])
# l = groupby(s, key=lambda x: x["currency"])
# for cur, group in l:
#     print(cur, list(group))
# pprint(data)


# price
# path = "/order_book"
# params = {"symbol": "btc_usdtt", "limit": 50}
# response = requests.get(base_url + path, params=params)
# data = response.json()
# asks = data["asks"]
# bids = data["bids"]
# pprint(data)

# pair trading volume
# path = "/ticker"
# params = {"symbol": "btc_usdt"}
# response = requests.get(base_url + path, params=params)
# data = response.json()
# volume = data["ticker"][0]["vol"]  # already float
# pprint(volume)


# chart change
# path = "/kline"
# params = {"symbol": "btc_usdt", "period": "60"}
# response = requests.get(base_url + path, params=params)
# data = response.json()
# opened = data["data"][-24][-1]
# closed = data["data"][-1][2]
# change = (closed - opened) / opened * 100
# print(change)
# pprint(data)

from urllib.parse import urlencode
import hmac
import hashlib
import time


def _generate_accesssign(data):
    query_string = urlencode(data)
    m = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
    s = m.hexdigest()
    print("data-origin:", data)
    print("query_string:", query_string)
    print("sign:", s)
    return s


# get balance
# path = "/spot/assets"
# headers = {
#     "ACCESS-KEY": api_key,
#     "ACCESS-TIMESTAMP": str(int(time.time())),
#     "ACCESS-SIGN": _generate_accesssign(None or {}),
# }
# response = requests.get(base_url + path, headers=headers)
# data = response.json()
# pprint(data)


# get deposit address
# path = "/deposit/address"
# params = {"currency": "usdt"}
# headers = {
#     "ACCESS-KEY": api_key,
#     "ACCESS-TIMESTAMP": str(int(time.time())),
#     "ACCESS-SIGN": _generate_accesssign(params),
# }
# response = requests.get(base_url + path, params=params, headers=headers)
# data = response.json()
# for deposit_info in data["data"]:
#     if deposit_info["chain"] == "BEP20":
#         address = deposit_info["address"]
#         memo = deposit_info["addressTag"]
#         print(address, memo)
#
# pprint(data)


# create new order
# path = "/spot/order/new"
# body = {
#     "market": "spot",
#     "symbol": "btc_usdt",
#     "type": "buy",
#     "amount": "100",
#     "price": "100"
# }
# headers = {
#     "ACCESS-KEY": api_key,
#     "ACCESS-TIMESTAMP": str(int(time.time())),
#     "ACCESS-SIGN": _generate_accesssign(body),
# }
# response = requests.post(base_url + path, data=body, headers=headers)
# data = response.json()
# pprint(data)
