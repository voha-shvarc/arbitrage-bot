import requests
from pprint import pp


# base_url = "https://api.crypto.com/exchange/v1"
base_url = "https://api.crypto.com/v2"

# trading pairs
# base_url = "https://api.crypto.com/exchange/v1"
# path = "/public/get-instruments"
# response = requests.get(base_url + path)
# data = response.json()["result"]
# for pair_info in data["data"]:
#     base_coin = data["base_ccy"]
#     quote_coin = data["quote_ccy"]
#     base_coin_pre = data["quantity_decimals"]
#     quote_coin_pre = data["quote_decimals"]
# pp(data)

# cne
# path = "/private/get-currency-networks"
# response = requests.post(base_url + path, json={})
# data = response.json()
# pp(data)
# need api key


# price
# path = "/public/get-book"
# params = {
#     "instrument_name": "BTC_USDT",
#     "depth": "50"
# }
# response = requests.get(base_url + path, params=params)
# data = response.json()["result"]
# bids = data["data"][0]["bids"]
# asks = data["data"][0]["asks"]
# print(f"{bids = }")
# print(f"{asks = }")
# pp(data)

# trading volume
# path = "/public/get-ticker"
# params = {
#     "instrument_name": "BTC_USDT"
# }
# response = requests.get(base_url + path, params)
# data = response.json()["result"]
# volume = float(data["data"][0]["v"])
# print(volume)
# pp(data)

# chart change
# path = "/public/get-candlestick"
# params = {
#     "instrument_name": "BTC_USDT",
#     "timeframe": "1h",
# }
# response = requests.get(base_url + path, params)
# data = response.json()["result"]["data"]
# opened = float(data[-10]["o"])
# closed = float(data[-1]["c"])
#
# change = (closed - opened) / opened * 100
# print(change)
# pp(data)

# balance
# path = "/private/get-account-summary"
# params = {
#     "currency": "USDT"
# }
# response = requests.post(base_url + path, json=params)
# data = response.json()
# pp(data)

# deposit address
# path = "/private/get-deposit-address"
# params = {
#     "currency": "USDT"
# }
# response = requests.post(base_url + path, json=params)
# data = response.json()
# pp(data)

# create order
# path = "/private/create-order"
# body = {
#     "instrument_name": "BTC_USDT",
#     "side": "BUY",
#     "type": "LIMIT",
#     "price": "",
#     "quantity": "",
#     "time_in_force": "FILL_OR_KILL"
# }
# response = requests.post(base_url + path, json=body)
# data = response.json()
# pp(data)