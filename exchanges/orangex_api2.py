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
import secrets

# nonce = secrets.token_urlsafe()[:6]
# timestamp = str(int(time.time() * 1000 + 200))
# string_to_sing = f"{api_key}\n{timestamp}\n{nonce}\n"
# sign = hmac.new(api_secret.encode("utf-8"), string_to_sing.encode("utf-8"), hashlib.sha256).hexdigest()
# print(string_to_sing)
# path = "/public/auth"
# body = {
#     "jsonrpc": "2.0",
#     "method": path,
#     "params": {
#         "grant_type": "client_signature",
#         "client_id": api_key,
#         "signature": sign.upper(),
#         "nonce": nonce,
#         "timestamp": timestamp
#     }
# }
# print(body)
#
# response = requests.post(base_url + path, json=body)
# data = response.json()
# pp(data)


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
#     base = pair_info["quote_currency"]
#     quote = pair_info["base_currency"]
#     base_p = max(len(pair_info["min_trade_amount"]) - 2, 1)
#     quote_p = max(len(pair_info["tick_size"]) - 2, 1)
#     # print(base, quote, pair_info["is_active"], base_p, pair_info["min_trade_amount"], quote_p, pair_info["tick_size"])
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
# pp(data["result"])
# for currency_info in data["result"]:
#     coin_name = currency_info["coin_type"]

# price
# path = "/public/get_order_book"
# body = {
#     "jsonrpc": "2.0",
#     "method": path,
#     "params": {
#         "instrument_name": "BTC-USDT-SPOT",
#         "depth": 50
#     }
# }
# response = requests.post(base_url + path, json=body)
# data = response.json()
# asks = data["result"]["asks"]
# bids = data["result"]["bids"]
# print(f"{asks = }")
# print(f"{bids = }")
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
# pp(data)
#
# balance = float(data["result"]["SPOT"]["details"][0]["available"])
# print(balance)


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

# create order
# path = "/private/buy"
# body = {
#     "jsonrpc": "2.0",
#     "method": path,
#     "params": {
#         "instrument_name": "BTC-USDT-SPOT",
#         "type": "limit",
#         "time_in_force": "fill_or_kill",
#         "price": "1",
#         "amount": "100"
#     }
# }
# response = requests.post(base_url + path, json=body, headers=headers)
# data = response.json()
# pp(data)
