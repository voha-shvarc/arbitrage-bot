from okx.Funding import FundingAPI
from okx.MarketData import MarketAPI
from okx.PublicData import PublicAPI
from retry import retry

from db.structs import CoinNetworkExchangeDC, TradingPair
from exchanges.abstract import AbstractExchange, NoPriceFound


class OkxAPI(AbstractExchange):
    NAME = "OKX"

    def __init__(self, config):
        flag = "0"  # Production trading: 0, Demo trading: 1
        api_key = config["OKX_API_KEY"]
        api_secret = config["OKX_API_SECRET"]
        passphrase = config["OKX_API_PASSPHRASE"]

        self.public_data_client = PublicAPI(api_key, api_secret, passphrase, flag=flag, debug=False)
        self.market_client = MarketAPI(api_key, api_secret, passphrase, flag=flag, debug=False)
        self.funding_client = FundingAPI(api_key, api_secret, passphrase, flag=flag, debug=False)

    @retry(delay=1, tries=2)
    def get_trading_pairs(self) -> list:
        pairs_info = self.public_data_client.get_instruments(instType="SPOT")
        trading_pairs = [TradingPair(base_coin=pair['baseCcy'], quote_coin=pair['quoteCcy'], exchange=self.NAME)
                         for pair in pairs_info['data'] if pair['instId'].endswith("USDT")]
        return trading_pairs

    def get_coin_exchange_networks(self):
        # todo: there's option to speed up transaction by setting more fee amount
        # todo: also minimal withdraw amount should also be considered as well as max withdraw amount
        # todo: also minimal and max deposits
        for coin_data in self.funding_client.get_currencies()["data"]:
            yield CoinNetworkExchangeDC.from_okx(coin_data)

    @retry(delay=1, tries=2)
    def get_price(self, pair, limit=20):
        order_book = self.market_client.get_orderbook(instId=pair.okx_name, sz=limit)
        if not order_book['data']:
            raise NoPriceFound()
        buy = order_book['data'][0]['asks']
        sell = order_book['data'][0]['bids']
        if not buy or not sell:
            raise NoPriceFound()
        return buy, sell
