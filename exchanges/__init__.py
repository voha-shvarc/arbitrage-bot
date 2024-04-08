from .binance_api import BinanceAPI
from .bingx_api import BingxAPI
from .bitget_api import BitgetAPI
from .bybit_api import BybitAPI
from .huobi_api import HuobiAPI
from .kucoin_api import KuCoinAPI
from .mexc_api import MexcAPI
from .okx_api import OkxAPI
from .poloniex_api import PoloniexAPI
from .whitebit_api import WhitebitAPI
from .xt_api import XTAPI


EXCHANGES_MAPPING = {
    BinanceAPI.NAME: BinanceAPI,
    BybitAPI.NAME: BybitAPI,
    HuobiAPI.NAME: HuobiAPI,
    KuCoinAPI.NAME: KuCoinAPI,
    WhitebitAPI.NAME: WhitebitAPI,
    BitgetAPI.NAME: BitgetAPI,
    BingxAPI.NAME: BingxAPI,
    OkxAPI.NAME: OkxAPI,
    PoloniexAPI.NAME: PoloniexAPI,
    MexcAPI.NAME: MexcAPI,
    XTAPI.NAME: XTAPI,
}
