from pprint import pprint

import requests

api_key = ""
api_secret = ""

base_url = "https://sapi.xt.com"
# client = XTClientSDK()(accesskey=api_key, secretkey=api_secret)
# res = client.get_all_market_config()
# print(res)

# coin network exchange
# path = "/v4/public/wallet/support/currency"
# data = requests.get(base_url + path)
# data = data.json()
# for m in data["result"]:
#     if m["currency"] == "usdt":
#         pprint(m)


# trading pairs
# url = base_url + "/v4/public/symbol"
# data = requests.get(url)
# pprint(data.json())

# price
# url = base_url + "/v4/public/depth"
# params = {
#     "symbol": "btc_usdt",
#     "limit": 50
# }
# data = requests.get(url, params=params)
# data = data.json()
# pprint(data)
# bids = data["result"]["bids"]

# trading volume
# url = base_url + "/v4/public/ticker/24h"
# params = {
#     "symbol": "btc_usdt",
# }
# data = requests.get(url, params=params)
# pprint(data.json()["result"][0]["q"])

# chart change
# url = base_url + "/v4/public/kline"
# params = {
#     "symbol": "btc_usdt",
#     "interval": "1m",
#     "limit": 10
# }
# data = requests.get(url, params=params).json()
# opened = float(data["result"][-1]["o"])
# closed = float(data["result"][0]["c"])
# change = (closed - opened) / opened * 100
# pprint(data)
import time
# import urllib
import hmac
import hashlib
# def get_sign_params():
#     payload = {}
#     payload['accesskey'] = api_key
#     payload['nonce'] = str(int(time.time() * 1000))
#
#     # Need sorted
#     params = urllib.parse.urlencode(dict(sorted(payload.items(), key=lambda kv: (kv[0], kv[1]))))
#
#     payload['signature'] = signature
#     return payload


def create_signature(method: str, path: str, timestamp, params: dict = None, body: dict = None) -> str:
    signature_message = f"validate-algorithms=HmacSHA256&validate-appkey={api_key}&validate-recvwindow=60000&validate-timestamp={timestamp}"
    signature_message += f"#{method.upper()}#{path}"
    if params:
        ps = [f"{key}={value}" for key, value in dict(sorted(params.items())).items()]
        signature_message += f"#{'&'.join(ps)}"
    if body:
        signature_message += f"#{json.dumps(body)}"

    print(f"{signature_message = }")
    signature = hmac.new(api_secret.encode('utf-8'), signature_message.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature


#balance
# timestamp = str(int(time.time() * 1000))
# headers = {
#     "accept": "*/*",
#     "Content-Type": "application/json",
#     "validate-algorithms": "HmacSHA256",
#     "validate-appkey": api_key,
#     "validate-recvwindow": "60000",
#     "validate-timestamp": timestamp,
# }
# method = "GET"
# path = "/v4/balance"
# params = {
#     "currency": "usdt",
# }
import json
# # print(f"{json.dumps(headers, separators=(',', ':')) = }")
# # signature_message = json.dumps(headers, separators=(",", ":"))
# # signature_message += f"#{method}#{path}#"
# # signature_message += 'currency=usdt'
#
# signature = create_signature(method, path, timestamp, params)
# headers["validate-signature"] = signature
# # pprint(headers)
# data = requests.get(base_url + path, params=params, headers=headers)
# pprint(headers)
# pprint(data.json()["result"]["availableAmount"])

# deposit address
# timestamp = str(int(time.time() * 1000))
# headers = {
#     "accept": "*/*",
#     "Content-Type": "application/json",
#     "validate-algorithms": "HmacSHA256",
#     "validate-appkey": api_key,
#     "validate-recvwindow": "60000",
#     "validate-timestamp": timestamp,
# }
# method = "GET"
# path = "/v4/deposit/address"
# params = {
#     "currency": "usdt",
#     "chain": "Tron",
# }
# signature = create_signature(method, path, timestamp, params)
# headers["validate-signature"] = signature
# pprint(headers)
# response = requests.get(base_url + path, params=params, headers=headers)
# pprint(response.json()["result"])

# withdraw
# timestamp = str(int(time.time() * 1000))
# headers = {
#     "accept": "*/*",
#     "Content-Type": "application/json",
#     "validate-algorithms": "HmacSHA256",
#     "validate-appkey": api_key,
#     "validate-recvwindow": "60000",
#     "validate-timestamp": timestamp,
# }
# method = "POST"
# path = "/v4/withdraw"
# body = {
#     "currency": "usdt",
#     "chain": "Tron",
#     "amount": 2,
#     "address": "",
#     "memo": ""
# }
# signature = create_signature(method, path, timestamp, body=body)
# headers["validate-signature"] = signature
# # pprint(headers)
# response = requests.post(base_url + path, json=body, headers=headers)
# print(response.status_code, json.loads(response.text))
# pprint(response.json()["result"])

# create order
# ORDER_ERROR_MAPPING = {
#     "ORDER_001": "Platform rejection",
#     "ORDER_002": "insufficient funds",
#     "ORDER_003": "Trading Pair Suspended",
#     "ORDER_004": "no transaction",
#     "ORDER_005": "Order not exist",
#     "ORDER_006": "Too many open orders",
#     "ORDER_007": "The sub-account has no transaction authority",
#     "ORDER_008": "The order price or quantity precision is abnormal"
# }
#
# timestamp = str(int(time.time() * 1000))
# headers = {
#     "accept": "*/*",
#     "Content-Type": "application/json",
#     "validate-algorithms": "HmacSHA256",
#     "validate-appkey": api_key,
#     "validate-recvwindow": "60000",
#     "validate-timestamp": timestamp,
# }
# method = "POST"
# path = "/v4/order"
# body = {
#     "symbol": "btc_usdt",
#     "side": "BUY",
#     "type": "LIMIT",
#     "timeInForce": "FOK",
#     "bizType": "SPOT",
#     "price": "60000.17",
#     "quantity": "2"
# }
# signature = create_signature(method, path, timestamp, body=body)
# headers["validate-signature"] = signature
# # # pprint(headers)
# response = requests.post("https://sapi.xt.com/v4/order", json=body, headers=headers)
# # response = requests.post("https://sapi.xt.com/v4/order", json={})
# print(response.status_code, )
# res = json.loads(response.text)
# print(ORDER_ERROR_MAPPING[res["mc"]])
# pprint(response.json()["result"])
