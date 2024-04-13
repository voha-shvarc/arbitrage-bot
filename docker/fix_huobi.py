BASE_PATH = "/usr/local"


def fix_encoding():
    file_path = f"{BASE_PATH}/lib/python3.11/site-packages/huobi/connection/impl/restapi_invoker.py"

    with open(file_path) as file:
        data = file.read()
        data = data.replace('json.loads(response.text, encoding="utf-8")', "json.loads(response.text)")
        with open(file_path, "w") as file_w:
            file_w.write(data)


def fix_balance_request():
    file_path = f"{BASE_PATH}/lib/python3.11/site-packages/huobi/service/account/get_balance.py"

    with open(file_path) as file:
        data = file.read()
        data = data.replace(
            "default_parse(data, AccountBalance, {})",
            "default_parse(data, AccountBalance, Balance)",
        )
        with open(file_path, "w") as file_w:
            file_w.write(data)


def fix_balance_model():
    file_path = f"{BASE_PATH}/lib/python3.11/site-packages/huobi/model/account/balance.py"

    with open(file_path) as file:
        data = file.read()
        data = data.replace("self.seqNum", "self.seq_num")
        with open(file_path, "w") as file_w:
            file_w.write(data)


if __name__ == "__main__":
    fix_encoding()
    fix_balance_request()
    fix_balance_model()
