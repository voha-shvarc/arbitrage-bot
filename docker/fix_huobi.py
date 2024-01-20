file_path = "/usr/local/lib/python3.11/site-packages/huobi/connection/impl/restapi_invoker.py"

with open(file_path) as file:
    data = file.read()
    data = data.replace('json.loads(response.text, encoding="utf-8")',
                        'json.loads(response.text)')
    with open(file_path, "w") as file_w:
        file_w.write(data)
