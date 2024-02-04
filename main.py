import logging
import time

import asyncio
import httpx
from redis import Redis
from dotenv import dotenv_values

from analyze.analyzer import ExchangePairAnalyzer
from exchanges import OkxAPI, BybitAPI, BitgetAPI, HuobiAPI, BinanceAPI, KuCoinAPI, GateIOAPI

log_file = "error.log"
formatt = logging.Formatter("%(asctime)s - %(message)s")
log_er = logging.getLogger("error")
log_er.setLevel(logging.ERROR)
handler = logging.FileHandler(log_file)
handler.setFormatter(formatt)
log_er.addHandler(handler)

log_file = "processing.log"
log = logging.getLogger("output")
log.setLevel(logging.DEBUG)
handler = logging.FileHandler(log_file)
handler.setFormatter(formatt)
log.addHandler(handler)


EXCHANGES_MAPPING = {
    BinanceAPI.NAME: BinanceAPI,
    HuobiAPI.NAME: HuobiAPI,
    KuCoinAPI.NAME: KuCoinAPI,
    GateIOAPI.NAME: GateIOAPI,
    BitgetAPI.NAME: BitgetAPI,
    OkxAPI.NAME: OkxAPI,
    BybitAPI.NAME: BybitAPI,
}


def get_exchanges_combinations():
    pairs = list()
    circle_exchanges = list(EXCHANGES_MAPPING.keys())
    while len(circle_exchanges) > 1:
        base_exchange = circle_exchanges.pop(0)

        for pair_exchange in circle_exchanges:
            pairs.append(f"{base_exchange},{pair_exchange}")

    return pairs


def get_exchanges_api_from_redis(redis_client):
    if not redis_client.exists("exchange_pairs"):
        redis_client.lpush("exchange_pairs", *get_exchanges_combinations())

    pair = redis_client.brpop(["exchange_pairs"])[1]
    base_exchange_name, pair_exchange_name = pair.split(",")

    return EXCHANGES_MAPPING[base_exchange_name], EXCHANGES_MAPPING[pair_exchange_name]


async def main():
    config = dotenv_values(".env")
    redis_client = Redis(host=config["REDIS_HOST"], port=config["REDIS_PORT"], decode_responses=True)

    while True:
        start = time.time()
        connection = httpx.AsyncClient()
        base_exchange, pair_exchange = get_exchanges_api_from_redis(redis_client)
        log.info(f"Analyze {base_exchange.NAME}, {pair_exchange.NAME}")
        try:
            await ExchangePairAnalyzer(base_exchange(config, connection), pair_exchange(config, connection)).run()
        except Exception as e:
            log_er.exception(e)

        await connection.aclose()

        end = time.time()
        log.info(f"one cycle took {end - start} seconds")


if __name__ == "__main__":
    asyncio.run(main())
