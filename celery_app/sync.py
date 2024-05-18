from dotenv import dotenv_values
from sqlalchemy import and_
from sqlalchemy import or_
from sqlalchemy import update
from sqlalchemy.orm import joinedload

from celery_app.conf import app
from db.base import Session
from db.models import Coin
from db.models import CoinNetworkExchange
from db.models import Exchange
from db.models import Network
from db.models import Pair
from db.models import PairExchange
from db.utils import get_or_create
from exchanges import EXCHANGES_MAPPING
from exchanges import KuCoinAPI
from exchanges import WhitebitAPI
from utils import grouper


config = dotenv_values(".env")


@app.task
def sync_coin_exchange_networks():
    """
    IP Whitelist
    Binance
    ByBit
    BingX
    KuCoin (everyone need to be whitelisted)
    Bitget
    """
    with Session() as session:
        for exchange_name, exchange_api in EXCHANGES_MAPPING.items():
            print(f"Syncing {exchange_name}...")
            exchange_api = exchange_api(config, {})
            exchange, _ = get_or_create(session, Exchange, name=exchange_name)

            existing_coins_mapping = {coin.name: coin.id for coin in session.query(Coin)}
            existing_networks_mapping = {network.name: network.id for network in session.query(Network)}

            for cne_dataclass in exchange_api.get_coin_exchange_networks():
                if cne_dataclass.coin_name in existing_coins_mapping:
                    coin_id = existing_coins_mapping[cne_dataclass.coin_name]
                else:
                    coin, _ = get_or_create(session, Coin, name=cne_dataclass.coin_name)
                    coin_id = coin.id

                for i, network_dataclass in enumerate(cne_dataclass.networks):
                    if network_dataclass.name in existing_networks_mapping:
                        network_id = existing_networks_mapping[network_dataclass.name]
                    else:
                        network, _ = get_or_create(session, Network, name=network_dataclass.name)
                        network_id = network.id

                    coin_network_exchange = (
                        session.query(CoinNetworkExchange.id)
                        .filter(CoinNetworkExchange.exchange_id == exchange.id)
                        .filter(CoinNetworkExchange.coin_id == coin_id)
                        .filter(CoinNetworkExchange.network_id == network_id)
                        .first()
                    )

                    new = CoinNetworkExchange(**cne_dataclass.to_db(exchange, coin_id, network_id, i))
                    if not coin_network_exchange:
                        session.add(new)
                    else:
                        new.id = coin_network_exchange.id
                        session.merge(new)

            # commit per exchange results
            session.commit()

        _run_networks_mapping(session)

        subq = (
            session.query(CoinNetworkExchange.id)
            .join(CoinNetworkExchange.coin)
            .join(CoinNetworkExchange.exchange)
            .join(CoinNetworkExchange.base_network)
            .filter(
                or_(
                    and_(Exchange.name == "ByBit", Coin.name == "VPAD"),
                    and_(Exchange.name == "ByBit", Coin.name == "NGL"),  # different from other exchanges
                    and_(Exchange.name == "ByBit", Coin.name == "GPT"),  # differs from okx and gateio
                    and_(Exchange.name == "ByBit", Coin.name == "TOMS"),  # on bybit available only in corea
                    and_(Exchange.name == "Bitget", Coin.name == "ALT"),  # differs from binance and gateio
                    and_(Exchange.name == "Bitget", Coin.name == "PMPY"),  # takes additional 7% for smart c
                    and_(Exchange.name == "Bingx", Coin.name == "TORN"),
                    and_(Exchange.name == "Bingx", Coin.name == "NGL"),
                    and_(Exchange.name == "KuCoin", Coin.name == "ARC"),
                    and_(Exchange.name == "Huobi", Coin.name == "GAME"),
                    and_(
                        Exchange.name.in_(["ByBit", "Binance", "OKX"]),
                        Network.name == "Chiliz",
                    ),  # different contract addresses for this chain
                    Coin.name == "PIT",  # 8% of additional fee
                    Coin.name == "BABYDOGE",  # a lot of additional commission
                    Coin.name == "LSD",  # different coins
                    Coin.name == "PEPE2",  # kucoin asks not to deposit it, has different contract addresses
                    Coin.name == "BIFI",  # different coins
                    Coin.name == "RED",  # different coins
                    Coin.name == "LUNC",  # takes additional 0.5% for smart c and 0.5% as exchange fee
                    Coin.name == "PLT",  # different coins
                    Coin.name == "TABOO",  # takes additional 4% for smart c
                    Coin.name == "BRISE",  # takes additional 10% for smart c
                    Coin.name == "10SET",  # additional 8% for smart c
                    Coin.name == "TRUMP",  # additional 1% fee
                    Coin.name == "LOOP",  # additional 10% fee
                    Coin.name == "QUACK",  # additional 12% fee
                    Coin.name == "FLOKICEO",
                    # after mex and bingx integration
                    and_(Exchange.name == "Mexc", Network.name == "Solana"),
                    and_(Exchange.name == "Mexc", Coin.name == "KT"),
                    and_(Exchange.name == "Mexc", Coin.name == "STC"),
                    and_(Exchange.name == "Mexc", Coin.name == "CO"),
                    and_(Exchange.name == "Mexc", Coin.name == "SOLS"),
                    and_(Exchange.name == "Mexc", Coin.name == "RAM"),
                    and_(Exchange.name == "Mexc", Coin.name == "FROG"),
                    and_(Exchange.name == "Mexc", Coin.name == "ARBI"),
                    and_(Exchange.name == "Mexc", Coin.name == "WALLET"),
                    and_(Exchange.name == "Mexc", Coin.name == "CAPS"),
                    and_(Exchange.name == "Mexc", Coin.name == "PAY"),
                    and_(Exchange.name == "Mexc", Coin.name == "TIME"),
                    and_(Exchange.name == "Mexc", Coin.name == "FIS"),
                    and_(Exchange.name == "Mexc", Coin.name == "GMT"),
                    and_(Exchange.name == "Mexc", Coin.name == "MAX"),
                    and_(Exchange.name == "Mexc", Coin.name == "PAW"),
                    and_(Exchange.name == "Mexc", Coin.name == "VT"),
                    and_(Exchange.name == "Mexc", Coin.name == "SQUAD"),
                    and_(Exchange.name == "Mexc", Coin.name == "PUMP"),
                    and_(Exchange.name == "Mexc", Coin.name == "IMPT"),
                    and_(Exchange.name == "Mexc", Coin.name == "AOG"),
                    and_(Exchange.name.in_(["Mexc", "KuCoin"]), Coin.name == "HERO"),
                    and_(Exchange.name.in_(["Poloniex", "KuCoin"]), Coin.name == "AI"),
                    and_(Exchange.name == "Poloniex", Coin.name == "AC"),
                    and_(Exchange.name == "Poloniex", Coin.name == "BOBO"),
                    and_(Exchange.name == "Poloniex", Coin.name == "CLOSEDAI"),
                    and_(Exchange.name == "Poloniex", Coin.name == "AGI"),
                    and_(Exchange.name == "Poloniex", Coin.name == "DYP"),
                    and_(Exchange.name == "Poloniex", Coin.name == "MEOW"),
                    and_(Exchange.name == "Poloniex", Coin.name == "MILK"),
                    and_(Exchange.name == "Poloniex", Coin.name == "GPU"),
                    and_(Exchange.name == "Poloniex", Coin.name == "KNOB"),
                    and_(Exchange.name == "Poloniex", Coin.name == "WSB"),
                    and_(Exchange.name == "Poloniex", Coin.name == "NGL"),
                    and_(Exchange.name == "Poloniex", Coin.name == "DMT"),
                    and_(Exchange.name == "Poloniex", Coin.name == "APU"),
                    and_(Exchange.name == "Poloniex", Coin.name == "KAI"),
                    and_(Exchange.name == "XT", Coin.name == "AC"),
                    and_(Exchange.name == "XT", Coin.name == "TITAN"),
                    and_(Exchange.name == "XT", Coin.name == "MTO"),
                    and_(Exchange.name == "GateIO", Coin.name == "SMT"),
                    and_(Exchange.name == "GateIO", Coin.name == "GTC"),
                    and_(Exchange.name == "GateIO", Coin.name == "GDT"),
                    and_(Exchange.name == "GateIO", Coin.name == "GAME"),
                    and_(Exchange.name == "GateIO", Coin.name == "DERP"),
                    and_(Exchange.name == "GateIO", Coin.name == "FREE"),
                    and_(Exchange.name == "GateIO", Coin.name == "GEM"),
                    and_(Exchange.name == "GateIO", Coin.name == "OMNI"),
                    and_(Exchange.name == "GateIO", Coin.name == "AXL"),
                ),
            )
        )
        session.query(CoinNetworkExchange).filter(CoinNetworkExchange.id.in_(subq)).update(
            {"can_withdraw": False, "can_deposit": False},
            synchronize_session=False,
        )

        session.commit()


def _run_networks_mapping(session: Session):
    data = {
        "Avalanche": ["AVAX", "XAVAX", "Avalanche X", "X-Chain", "XCHAIN", "AVAX XCHAIN", "AVA"],
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
            "AVAX-C",
            "AVAX CCHAIN",
            "AVAX_CCHAIN",
            "AVA_C",
        ],
        "DYM": ["DYM", "DYMEVM"],
        "Manta": ["Manta", "MANTA", "MANTAETH"],
        "Bitcoin": ["BTC", "Bitcoin", "BRC20", "ARC20", "BTC_BRC20", "BTC_ARC20"],
        "Bitcoin Cash": ["BCH", "BitcoinCash", "BCHN"],
        "Bitcoin SV": ["BSV", "Bitcoin SV"],
        "Cardano": ["ADA", "Cardano"],
        "Cosmos": ["ATOM", "Cosmos", "ATOM1", "COSMOS"],
        "Dogecoin": ["DOGE", "Dogecoin"],
        "Ethereum": ["ETH", "ERC20", "Ethereum"],
        "Ethereum Classic": ["ETC", "Ethereum Classic"],
        "Litecoin": ["LTC", "Litecoin"],
        "Polygon": [
            "MATIC",
            "Polygon",
            "MATIC1",
            "POLYGON",
            "MATICPOLY",
        ],
        "Ripple": ["XRP", "Ripple"],
        "Solana": ["SOL", "Solana", "SOLANA", "SOL-SOL"],
        "Stellar": ["XLM", "Stellar Lumens"],
        "Tron": ["TRX", "TRX1", "TRC20"],
        "Zcash": ["ZEC", "Zcash"],
        "Arbitrum": ["ARB", "ARBI", "Arbitrum One", "ARBEVM", "ARBIETH", "ARBITRUM", "ETHARB"],
        "ARBINOVA": ["ARBINOVA", "ARBNOVA"],
        "Optimism": ["OP", "Optimism", "OPETH", "OPTETH", "OPTIMISM", "Optimism (V2)", "ETHOP", "OPT"],
        "Fantom": ["FTM", "Fantom", "FANTOM"],
        "Algorand": ["ALGO", "Algorand", "ALGOUSDT"],
        "Aptos": ["APT", "Aptos"],
        "Arweave": ["AR", "Arweave"],
        "Chiliz": ["CHZ", "Chiliz Chain"],
        "Astar": ["ASTR", "Astar"],
        "Klaytn": ["KLAY", "Klaytn", "KLAYTN"],
        "CFX": ["CFX", "CFX_EVM"],
        "Casper": ["CSPR", "Casper"],
        "Cortex": ["CTXC", "CTXC1", "Cortex"],
        "Dash": ["DASH", "Digital Cash"],
        "Decred": ["DCR", "Decred"],
        "Digibyte": ["DGB", "Digibyte"],
        "Polkadot": ["DOT", "Polkadot", "POLKADOT"],
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
        "Terra Classic": ["LUNC", "Terra Classic", "TERRA_CLASSIC"],
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
        "Starknet": ["STARKNET", "Starknet", "STARK"],
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
        "enj": ["ENJ", "ENJ1", "Enjin Relay Chain", "Enjin"],
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
        "BSC": ["BSC", "BNB1", "BEP20", "BNB Smart Chain"],
        "BNB": ["BNB", "BEP2"],
        "NEAR": ["NEAR", "NEAR Protocol"],
    }

    for base_network, networks in data.items():
        base_net, created = get_or_create(session, Network, name=base_network)
        network_ids = session.query(Network.id).filter(Network.name.in_(networks))

        session.query(CoinNetworkExchange).filter(CoinNetworkExchange.network_id.in_(network_ids)).update(
            {"base_network_id": base_net.id},
            synchronize_session=False,
        )


@app.task
def sync_pairs():
    """
    Biget statuses: halt(offline), gray(listing coming), online. No info about api, only UI
    Bingx: some have turned off UI but enabled api
    Bybit: only status Trading for ui and api combined
    Gateio: tradable, untradable, sellable(listing coming), boughtable(not present)
    Huobi: online, offline(delisted), suspend(paused), pre-online(listing coming)
    KuCoin: enableTrading True/False. didn't find False values
    Mexc: status = 'ENABLED' for UI, isSpotTradingAllowed for API
    OKX: live, suspend, preopen. Found only live
    Poloniex: normal, post_only(listing coming), pause
    Whitebit: tradesEnabled True/False. didn't find False values
    XT: state: ONLINE/OFFLINE, offline is either delisted or listing coming.
     tradingEnabled is always True even if it shouldn't be.
     opendapiEnabled is reasonable for API True/False
    Binance: isSpotTradingAllowed should be for API, but didn't find False values. status TRADING/BREAK
    """
    with Session() as session:
        session.execute(update(PairExchange).values(api_enabled=False, ui_enabled=False))

        quote_coin, _ = get_or_create(session, Coin, name="USDT")
        pairs_mapping = {pair.base_coin.name: pair for pair in session.query(Pair).options(joinedload(Pair.base_coin))}
        for exchange_name, exchange_api in EXCHANGES_MAPPING.items():
            print(f"Syncing {exchange_name}...")
            exchange_api = exchange_api(config, {})
            exchange, _ = get_or_create(session, Exchange, name=exchange_name)

            for pair_data in exchange_api.get_trading_pairs():
                if pair := pairs_mapping.get(pair_data.base_coin):
                    pair = pair
                else:
                    base_coin, _ = get_or_create(session, Coin, name=pair_data.base_coin)
                    pair, _ = get_or_create(session, Pair, base_coin_id=base_coin.id, quote_coin_id=quote_coin.id)
                from sqlalchemy import select

                pair_exchange = session.scalar(
                    select(PairExchange).where(
                        PairExchange.pair_id == pair.id,
                        PairExchange.exchange_id == exchange.id,
                    ),
                )

                new = PairExchange(**pair_data.to_db(pair.id, exchange.id))
                if not pair_exchange:
                    session.add(new)
                else:
                    new.id = pair_exchange.id
                    session.merge(new)

        session.commit()


@app.task
def sync_spot__withdraw_fees():
    """Sync kucoin spot fees and whitebit withdraw fees"""
    mapping = {}
    kucoin_api = KuCoinAPI(config, {})
    print(f"Syncing {kucoin_api.NAME}...")
    with Session() as session:
        pairs = (
            session.query(PairExchange)
            .join(PairExchange.exchange)
            .filter(Exchange.name == KuCoinAPI.NAME)
            .options(
                joinedload(PairExchange.pair),
                joinedload(PairExchange.pair).joinedload(Pair.base_coin),
                joinedload(PairExchange.pair).joinedload(Pair.quote_coin),
            )
            .all()
        )
        for group in grouper(10, pairs):
            symbols = ",".join([pair_exchange.pair.dashed_name for pair_exchange in group if pair_exchange is not None])
            data = kucoin_api.account_client.get_actual_fee(symbols=symbols)
            mapping.update(
                {
                    symbol["symbol"]: {
                        "maker_fee": float(symbol["makerFeeRate"]),
                        "taker_fee": float(symbol["takerFeeRate"]),
                    }
                    for symbol in data
                },
            )

        update_mapping = [
            {
                "id": pair_exchange.id,
                "taker_fee": mapping[pair_exchange.pair.dashed_name]["taker_fee"],
                "maker_fee": mapping[pair_exchange.pair.dashed_name]["maker_fee"],
            }
            for pair_exchange in pairs
        ]

        session.bulk_update_mappings(PairExchange, update_mapping)
        session.flush()
        session.commit()

    mapping = {}
    whitebit_api = WhitebitAPI(config, {})
    print(f"Syncing {whitebit_api.NAME}...")
    with Session() as session:
        data = whitebit_api.account_client.get_fee()
        for ccy_info in data:
            withdraw_fee = ccy_info["withdraw"]["fixed"]
            mapping[ccy_info["ticker"]] = float(withdraw_fee)

        coins = (
            session.query(Coin.name, CoinNetworkExchange.id)
            .select_from(Coin)
            .join(CoinNetworkExchange)
            .join(CoinNetworkExchange.exchange)
            .filter(Exchange.name == WhitebitAPI.NAME)
        )
        update_mapping = [
            {
                "id": cne_id,
                "withdraw_fee": mapping[coin_name],
            }
            for coin_name, cne_id in coins
            if mapping.get(coin_name)
        ]

        session.bulk_update_mappings(CoinNetworkExchange, update_mapping)
        session.flush()
        session.commit()
