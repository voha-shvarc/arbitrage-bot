from dotenv import dotenv_values
from sqlalchemy import and_
from sqlalchemy import or_

from celery_app.conf import app
from db.base import Session
from db.models import Coin
from db.models import CoinNetworkExchange
from db.models import Exchange
from db.models import Network
from db.models import Pair
from db.models import PairExchange
from db.utils import get_or_create
from exchanges import BinanceAPI
from exchanges import BitgetAPI
from exchanges import BybitAPI
from exchanges import GateIOAPI
from exchanges import HuobiAPI
from exchanges import KuCoinAPI
from exchanges import OkxAPI
from exchanges import WhitebitAPI


config = dotenv_values(".env")

EXCHANGES = {BinanceAPI, BybitAPI, OkxAPI, GateIOAPI, HuobiAPI, KuCoinAPI, BitgetAPI, WhitebitAPI}


@app.task
def sync_coin_exchange_networks():
    with Session() as session:
        for exchange_api in EXCHANGES:
            print(f"Syncing {exchange_api.NAME}...")
            exchange_api = exchange_api(config, {})
            exchange, created = get_or_create(session, Exchange, name=exchange_api.NAME)
            for cen_dataclass in exchange_api.get_coin_exchange_networks():
                coin, created = get_or_create(session, Coin, name=cen_dataclass.coin_name)
                for i, network_dataclass in enumerate(cen_dataclass.networks):
                    network, created = get_or_create(session, Network, name=network_dataclass.name)

                    coin_network_exchange = (
                        session.query(CoinNetworkExchange.id)
                        .filter(CoinNetworkExchange.exchange_id == exchange.id)
                        .filter(CoinNetworkExchange.coin_id == coin.id)
                        .filter(CoinNetworkExchange.network_id == network.id)
                        .one_or_none()
                    )

                    new = CoinNetworkExchange(**cen_dataclass.to_db(exchange, coin, network, i))
                    if not coin_network_exchange:
                        session.add(new)
                    else:
                        new.id = coin_network_exchange.id
                        session.merge(new)

        _run_networks_mapping(session)

        subq = (
            session.query(CoinNetworkExchange.id)
            .join(CoinNetworkExchange.coin)
            .join(CoinNetworkExchange.exchange)
            .join(CoinNetworkExchange.base_network)
            .filter(
                or_(
                    and_(Exchange.name == "GateIO", Coin.name == "GTC"),
                    and_(Exchange.name == "ByBit", Coin.name == "VPAD"),
                    and_(Exchange.name == "ByBit", Coin.name == "NGL"),  # different from other exchanges
                    and_(
                        Exchange.name.in_(["ByBit", "Binance", "OKX"]),
                        Network.name == "Chiliz",
                    ),  # different contract addresses for this chain
                    and_(Exchange.name == "ByBit", Coin.name == "GPT"),  # differs from okx and gateio
                    and_(Exchange.name == "Bitget", Coin.name == "ALT"),  # differs from binance and gateio
                    Coin.name == "BABYDOGE",  # a lot of additional commission
                    Coin.name == "LSD",  # different coins
                    Coin.name == "PEPE2",  # kucoin asks not to deposit it, has different contract addresses
                    Coin.name == "BIFI",  # different coins
                    Coin.name == "RED",  # different coins
                    Coin.name == "LUNC",  # takes additional 0.5% for smart c and 0.5% as exchange fee
                ),
            )
        )
        session.query(CoinNetworkExchange).filter(CoinNetworkExchange.id.in_(subq)).update(
            {"can_withdraw": False, "can_deposit": False},
            synchronize_session=False,
        )

        session.commit()


@app.task
def sync_pairs():
    with Session() as session:
        quote_coin, created = get_or_create(session, Coin, name="USDT")
        for exchange_api in EXCHANGES:
            print(f"Syncing {exchange_api.NAME}...")
            exchange_api = exchange_api(config, {})

            exchange, created = get_or_create(session, Exchange, name=exchange_api.NAME)
            pairs = exchange_api.get_trading_pairs()
            base_coins = {pair.base_coin for pair in pairs}

            existing_base_coins = (
                session.query(Coin.name)
                .join(Pair, Coin.id == Pair.base_coin_id)
                .join(PairExchange)
                .filter(PairExchange.exchange_id == exchange.id)
                .all()
            )

            solution_temporary = [coin.name for coin in existing_base_coins]
            diff_coins = base_coins.difference(solution_temporary)
            for new_coin in diff_coins:
                base_coin, created = get_or_create(session, Coin, name=new_coin)
                pair, _ = get_or_create(session, Pair, base_coin_id=base_coin.id, quote_coin_id=quote_coin.id)
                pair_exchange, _ = get_or_create(session, PairExchange, pair_id=pair.id, exchange_id=exchange.id)

        session.commit()


def _run_networks_mapping(session: Session):
    data = {
        "Avalanche": ["AVAX", "XAVAX", "Avalanche X", "X-Chain", "XCHAIN"],
        "AVAXC": [
            "AVAXC",
            "AVAX_C",
            "Avalanche C",
            "CCHAINAVAX",
            "CAVAX",
            "AVAXCCHAIN",
            "C-Chain",
            "AVAX C-Chain",
            "CCHAIN",
        ],
        "Manta": ["Manta", "MANTA"],
        "Bitcoin": ["BTC", "Bitcoin", "BRC20"],
        "Bitcoin Cash": ["BCH", "BitcoinCash"],
        "Bitcoin SV": ["BSV", "Bitcoin SV"],
        "Cardano": ["ADA", "Cardano"],
        "Cosmos": ["ATOM", "Cosmos", "ATOM1"],
        "Dogecoin": ["DOGE", "Dogecoin"],
        "Ethereum": ["ETH", "ERC20", "Ethereum"],
        "Ethereum Classic": ["ETC", "Ethereum Classic"],
        "Litecoin": ["LTC", "Litecoin"],
        "Polygon": ["MATIC", "Polygon", "MATIC1", "POLYGON"],
        "Ripple": ["XRP", "Ripple"],
        "Solana": ["SOL", "Solana", "SOLANA"],
        "Stellar": ["XLM", "Stellar Lumens"],
        "Tron": ["TRX", "TRX1", "TRC20"],
        "Zcash": ["ZEC", "Zcash"],
        "Arbitrum": ["ARB", "ARBI", "Arbitrum One", "ARBEVM", "ARBIETH", "ARBITRUM"],
        "ARBINOVA": ["ARBINOVA", "ARBNOVA"],
        "Optimism": ["OP", "Optimism", "OPETH", "OPTETH", "OPTIMISM", "Optimism (V2)"],
        "Fantom": ["FTM", "Fantom"],
        "Algorand": ["ALGO", "Algorand", "ALGOUSDT"],
        "Aptos": ["APT", "Aptos"],
        "Arweave": ["AR", "Arweave"],
        "Chiliz": ["CHZ", "Chiliz Chain"],
        "Astar": ["ASTR", "Astar"],
        "Klaytn": ["KLAY", "Klaytn"],
        "CFX": ["CFX", "CFX_EVM"],
        "Casper": ["CSPR", "Casper"],
        "Cortex": ["CTXC", "CTXC1", "Cortex"],
        "Dash": ["DASH", "Digital Cash"],
        "Decred": ["DCR", "Decred"],
        "Digibyte": ["DGB", "Digibyte"],
        "Polkadot": ["DOT", "Polkadot"],
        "Elrond": ["EGLD", "Elrond"],
        "Filecoin": ["FIL", "Filecoin"],
        "Flare": ["FLR", "Flare"],
        "Moonbeam": ["GLMR", "Moonbeam"],
        "Hedera": ["HBAR", "Hedera"],
        "HyperCash": ["HC", "HyperCash"],
        "Dfinity": ["ICP", "Dfinity"],
        "ICON": ["ICX", "ICON"],
        "MIOTA": ["IOTA", "MIOTA"],
        "Kadena": ["KDA", "Kadena"],
        "Kusama": ["KSM", "Kusama"],
        "Lisk": ["LSK", "Lisk", "LSK1"],
        "Terra": ["LUNA", "Terra", "LUNANEW", "TERRA"],
        "Terra Classic": ["LUNC", "Terra Classic"],
        "Mina": ["MINA", "Mina"],
        "Moonriver": ["MOVR", "Moonriver"],
        "NEO": ["NEO", "NEO1"],
        "NEO3": ["NEO3", "N3"],
        "Ontology": ["ONT", "ONT2", "ONG", "Ontology"],
        "Quantum": ["QTUM", "Quantum"],
        "Ronin": ["RON", "Ronin"],
        "Ravencoin": ["RVN", "Ravencoin"],
        "Siacoin": ["SC", "Siacoin"],
        "Theta": ["THETA", "Theta", "THETA1"],
        "Tezos": ["XTZ", "Tezos"],
        "Zilliqa": ["ZIL", "Zilliqa", "ZIL1"],
        "Chia": ["XCH", "Chia"],
        "New Economy Movement": ["XEM", "NEM"],
        "Nano": ["NANO", "Nano"],
        "Starknet": ["STARKNET", "Starknet"],
        "zkSyncEra": ["zkSync Era", "ZKSYNCERA"],
        "Base": ["BASE", "Base", "BASEEVM", "BASEETH"],
        "Linea": ["LINEA", "Linea", "LINEAETH"],
        "XYM": ["XYM", "XYM1"],
        "XMR": ["XMR", "XMR1"],
        "XEC": ["XEC", "XEC1"],
        "WTC": ["WTC", "WTC1"],
        "WEMIX": ["WEMIX", "WEMIX1"],
        "WICC": ["WICC", "WICC1"],
        "WAX": ["Wax", "WAXP", "WAX", "WAX1"],
        "VSYS": ["VSYS", "VSYSTEMS"],
        "Calestia": ["Calestia", "CALESTIA", "TIA"],
        "TENET": ["TENET", "TENET1"],
        "SXP": ["SXP", "SXP1"],
        "STX": ["STX", "l"],
        "METIS": ["Metis", "METIS"],
        "STEP": ["STEP", "Step Network"],
        "cro": ["CRO", "CRO2", "Crypto"],
        "cru": ["CRU", "CRU1"],
        "dbc": ["DBC", "DBC1"],
        "ae": ["AE", "AE1"],
        "band": ["BAND", "BAND2"],
        "btt": ["BTT", "BTT2"],
        "elf": ["AELF", "ELF", "ELF1"],
        "em": ["EM1", "Eminer"],
        "enj": ["ENJ", "ENJ1", "Enjin Relay Chain"],
        "eos": ["EOS", "EOS1"],
        "fitfi": ["FITFI", "FITFI1"],
        "fsn": ["FSN", "FSN1"],
        "ht": ["HT", "HT2"],
        "icx": ["ICON", "ICX1"],
        "iost": ["IOST", "IOST1"],
        "iota": ["IOTA1", "MIOTA"],
        "iris": ["IRIS", "IRIS1"],
        "kava": ["KAVA", "KAVA10"],
        "kda": ["KDA2", "Kadena"],
        "lamb": ["LAMB", "LAMB1"],
        "nas": ["NAS", "NAS1"],
        "nuls": ["NULS", "NULS1"],
        "one": ["Harmony", "ONE", "ONE1"],
        "polyx": ["POLY1", "POLYX"],
        "seele": ["SEELE", "SEELE2"],
        "smt": ["SMT", "SMT2"],
        "BSC": ["BSC", "BNB1", "BEP20"],
        "BNB": ["BNB", "BEP2"],
    }

    for base_network, networks in data.items():
        base_net, created = get_or_create(session, Network, name=base_network)
        network_ids = session.query(Network.id).filter(Network.name.in_(networks))

        session.query(CoinNetworkExchange).filter(CoinNetworkExchange.network_id.in_(network_ids)).update(
            {"base_network_id": base_net.id},
            synchronize_session=False,
        )
