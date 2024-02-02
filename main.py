import logging

from dotenv import dotenv_values
from redis import Redis

from analyze.analyzer import ExchangePairAnalyzer
from exchanges import BinanceAPI, BybitAPI, OkxAPI, GateIOAPI, HuobiAPI, KuCoinAPI, BitgetAPI

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
    BybitAPI.NAME: BybitAPI,
    HuobiAPI.NAME: HuobiAPI,
    GateIOAPI.NAME: GateIOAPI,
    OkxAPI.NAME: OkxAPI,
    KuCoinAPI.NAME: KuCoinAPI,
    BitgetAPI.NAME: BitgetAPI,
}


def get_exchanges_combinations():
    pairs = set()
    circle_exchanges = list(EXCHANGES_MAPPING.keys())
    while len(circle_exchanges) > 1:
        base_exchange = circle_exchanges.pop(0)

        for pair_exchange in circle_exchanges:
            pairs.add(f"{base_exchange},{pair_exchange}")

    return pairs


def get_exchanges_api_from_redis(redis_client):
    if not redis_client.exists("exchange_pairs"):
        redis_client.lpush("exchange_pairs", *get_exchanges_combinations())

    pair = redis_client.brpop(["exchange_pairs"])[1]
    base_exchange_name, pair_exchange_name = pair.split(",")

    return EXCHANGES_MAPPING[base_exchange_name], EXCHANGES_MAPPING[pair_exchange_name]


def main():
    config = dotenv_values(".env")
    redis_client = Redis(host=config["REDIS_HOST"], port=config["REDIS_PORT"], decode_responses=True)

    while True:
        base_exchange, pair_exchange = get_exchanges_api_from_redis(redis_client)
        log.info(f"Analyze {base_exchange.NAME}, {pair_exchange.NAME}")

        analyzer = ExchangePairAnalyzer(base_exchange(config), pair_exchange(config))
        try:
            analyzer.run()
        except Exception as e:
            log_er.exception(e)
        finally:
            redis_client.lpush("exchange_pairs", f"{base_exchange.NAME},{pair_exchange.NAME}")


if __name__ == "__main__":
    main()
