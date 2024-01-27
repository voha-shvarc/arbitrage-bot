import logging
import random

from dotenv import dotenv_values

from analyze.analyzer import ExchangePairAnalyzer
from exchanges import BinanceAPI, BybitAPI, OkxAPI, GateIOAPI, HuobiAPI, KuCoinAPI

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

EXCHANGES = [BinanceAPI, BybitAPI, OkxAPI, GateIOAPI, HuobiAPI, KuCoinAPI]


def main():
    config = dotenv_values(".env")
    while True:
        circle_exchanges = EXCHANGES.copy()
        while len(circle_exchanges) > 1:
            base_exchange = random.choice(circle_exchanges)
            circle_exchanges.remove(base_exchange)

            for pair_exchange in circle_exchanges:
                log.info(f"Analyze {base_exchange.NAME}, {pair_exchange.NAME}")
                analyzer = ExchangePairAnalyzer(base_exchange(config), pair_exchange(config))
                try:
                    analyzer.run()
                except Exception as e:
                    log_er.exception(e)


if __name__ == "__main__":
    main()
