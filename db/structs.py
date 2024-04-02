from dataclasses import dataclass
from typing import Any
from typing import List
from typing import Union

from huobi.constant import ChainDepositStatus
from huobi.constant import ChainWithdrawStatus
from huobi.model.generic import Chain
from huobi.model.generic import ReferenceCurrency


@dataclass
class NetworkExchange:
    name: str
    can_deposit: bool
    can_withdraw: bool
    withdraw_min: float
    withdraw_fee: float
    withdraw_max: float = None
    deposit_min: float = None
    withdraw_precision: int = None
    confirmations_needed: int = None
    plain_name: str = None

    @classmethod
    def from_binance(cls, data):
        name = data["network"]
        can_deposit = data["depositEnable"]
        can_withdraw = data["withdrawEnable"]
        withdraw_fee = data["withdrawFee"]
        confirmations_needed = data["minConfirm"]
        withdraw_min = float(data["withdrawMin"])
        withdraw_max = float(data["withdrawMax"])
        withdraw_precision = len(data["withdrawIntegerMultiple"]) - 2 if data["withdrawIntegerMultiple"] != "1" else 1

        return cls(
            name=name,
            can_deposit=can_deposit,
            can_withdraw=can_withdraw,
            withdraw_fee=withdraw_fee,
            withdraw_min=withdraw_min,
            withdraw_max=withdraw_max,
            withdraw_precision=withdraw_precision,
            confirmations_needed=confirmations_needed,
        )

    @classmethod
    def from_bybit(cls, data):
        name = data["chain"]
        can_deposit = data["chainDeposit"] == "1"
        can_withdraw = data["chainWithdraw"] == "1"
        try:
            withdraw_fee = float(data["withdrawFee"])
        except ValueError:
            withdraw_fee = 0

        try:
            confirmations_needed = int(data["confirmation"])
        except ValueError:
            confirmations_needed = 0

        withdraw_min = float(data["withdrawMin"]) if data["withdrawMin"] else None
        withdraw_precision = int(data["minAccuracy"])

        return cls(
            name=name,
            can_deposit=can_deposit,
            can_withdraw=can_withdraw,
            withdraw_fee=withdraw_fee,
            withdraw_min=withdraw_min,
            withdraw_precision=withdraw_precision,
            confirmations_needed=confirmations_needed,
        )

    @classmethod
    def from_okx(cls, data):
        name = data["chain"].split("-")[1]
        can_deposit = data["canDep"]
        can_withdraw = data["canWd"]
        withdraw_fee = float(data["minFee"])
        confirmations_needed = int(data["minDepArrivalConfirm"])
        withdraw_max = float(data["maxWd"])
        withdraw_min = float(data["minWd"])
        deposit_min = float(data["minDep"])
        withdraw_precision = int(data["wdTickSz"])

        return cls(
            name=name,
            can_deposit=can_deposit,
            can_withdraw=can_withdraw,
            withdraw_fee=withdraw_fee,
            withdraw_min=withdraw_min,
            withdraw_max=withdraw_max,
            deposit_min=deposit_min,
            withdraw_precision=withdraw_precision,
            confirmations_needed=confirmations_needed,
            plain_name=data["chain"],
        )

    # @classmethod
    # def from_gateio(cls, data: Currency):
    #     name = data.chain
    #     can_deposit = not data.deposit_disabled
    #     can_withdraw = not data.withdraw_disabled
    #
    #     return cls(name, can_deposit, can_withdraw, 0)

    @classmethod
    def from_huobi(cls, network: Chain):
        name = network.baseChain or network.chain
        can_deposit = network.depositStatus == ChainDepositStatus.ALLOWED
        can_withdraw = network.withdrawStatus == ChainWithdrawStatus.ALLOWED
        withdraw_fee = network.transactFeeWithdraw
        confirmations_needed = network.numOfFastConfirmations
        withdraw_max = network.maxWithdrawAmt
        withdraw_min = network.minWithdrawAmt
        deposit_min = network.minDepositAmt
        withdraw_precision = network.withdrawPrecision

        return cls(
            name=name.upper(),
            can_deposit=can_deposit,
            can_withdraw=can_withdraw,
            withdraw_fee=withdraw_fee,
            withdraw_min=withdraw_min,
            withdraw_max=withdraw_max,
            deposit_min=deposit_min,
            withdraw_precision=withdraw_precision,
            confirmations_needed=confirmations_needed,
            plain_name=network.chain,
        )

    @classmethod
    def from_kucoin(cls, withdraw_precision: int, data: dict):
        net_name = data["chainName"]
        plain_name = data["chainId"]
        can_deposit = data["isDepositEnabled"]
        can_withdraw = data["isWithdrawEnabled"]
        withdraw_fee = data["withdrawalMinFee"]
        confirmations_needed = data["preConfirms"]
        withdraw_min = float(data["withdrawalMinSize"])
        deposit_min = float(data["depositMinSize"]) if data["depositMinSize"] else None

        return cls(
            name=net_name,
            can_deposit=can_deposit,
            can_withdraw=can_withdraw,
            withdraw_fee=withdraw_fee,
            withdraw_min=withdraw_min,
            deposit_min=deposit_min,
            withdraw_precision=withdraw_precision,
            confirmations_needed=confirmations_needed,
            plain_name=plain_name,
        )

    @classmethod
    def from_bitget(cls, data):
        net_name = data["chain"]
        can_deposit = True if data["rechargeable"] == "true" else False
        can_withdraw = True if data["withdrawable"] == "true" else False
        withdraw_fee = float(data["withdrawFee"])
        confirmations_needed = int(data["depositConfirm"])
        withdraw_min = float(data["minWithdrawAmount"])
        deposit_min = float(data["minDepositAmount"])

        return cls(
            name=net_name,
            can_deposit=can_deposit,
            can_withdraw=can_withdraw,
            withdraw_fee=withdraw_fee,
            withdraw_min=withdraw_min,
            deposit_min=deposit_min,
            confirmations_needed=confirmations_needed,
        )

    @classmethod
    def from_bingx(cls, data: dict):
        net_name = data["network"]
        can_deposit = data["depositEnable"]
        can_withdraw = data["withdrawEnable"]
        withdraw_fee = float(data["withdrawFee"])
        confirmations_needed = data["minConfirm"]
        withdraw_min = float(data["withdrawMin"])
        withdraw_max = float(data["withdrawMax"])
        deposit_min = float(data["depositMin"])

        return cls(
            name=net_name,
            can_deposit=can_deposit,
            can_withdraw=can_withdraw,
            withdraw_fee=withdraw_fee,
            withdraw_min=withdraw_min,
            withdraw_max=withdraw_max,
            deposit_min=deposit_min,
            confirmations_needed=confirmations_needed,
        )

    @classmethod
    def from_mexc(cls, data: dict):
        plain_name = None
        net_name = data["network"]
        short_name_index = net_name.find("(")
        if short_name_index != -1:
            plain_name = net_name
            net_name = net_name[short_name_index + 1 : -1]

        can_deposit = data["depositEnable"]
        can_withdraw = data["withdrawEnable"]
        withdraw_fee = float(data["withdrawFee"])
        confirmations_needed = data["minConfirm"]
        withdraw_min = float(data["withdrawMin"])
        withdraw_max = float(data["withdrawMax"])

        return cls(
            name=net_name,
            can_deposit=can_deposit,
            can_withdraw=can_withdraw,
            withdraw_fee=withdraw_fee,
            withdraw_min=withdraw_min,
            withdraw_max=withdraw_max,
            confirmations_needed=confirmations_needed,
            plain_name=plain_name,
        )

    @classmethod
    def from_poloniex(cls, data: dict):
        net_name = data["blockchain"]
        plain_name = data["coin"]
        can_deposit = data["depositEnable"]
        can_withdraw = data["withdrawalEnable"]
        withdraw_fee = float(data["withdrawFee"])
        confirmations_needed = data["minConfirm"]
        withdraw_min = float(data["withdrawMin"])
        withdraw_precision = int(data["decimals"])

        return cls(
            name=net_name,
            can_deposit=can_deposit,
            can_withdraw=can_withdraw,
            withdraw_fee=withdraw_fee,
            withdraw_min=withdraw_min,
            withdraw_precision=withdraw_precision,
            confirmations_needed=confirmations_needed,
            plain_name=plain_name,
        )


@dataclass
class CoinNetworkExchangeDC:
    coin_name: str
    exchange_name: str
    networks: List[NetworkExchange]
    extra_info: dict[str:Any]

    def to_db(self, exchange, coin_id: int, network_id: int, network_index: int) -> dict:
        net = self.networks[network_index]
        data = {
            "exchange_id": exchange.id,
            "coin_id": coin_id,
            "network_id": network_id,
            "base_network_id": network_id,
            "can_deposit": net.can_deposit,
            "can_withdraw": net.can_withdraw,
            "extra_info": self.extra_info,
            "confirmations_needed": net.confirmations_needed,
            "plain_network_name": net.plain_name,
            "withdraw_min": net.withdraw_min,
            "withdraw_max": net.withdraw_max,
            "deposit_min": net.deposit_min,
            "withdraw_precision": net.withdraw_precision,
        }
        if net.withdraw_fee:
            data["withdraw_fee"] = net.withdraw_fee

        return data

    @classmethod
    def from_binance(cls, data):
        coin_name = data["coin"]
        networks = [NetworkExchange.from_binance(network) for network in data["networkList"]]

        return cls(coin_name, "Binance", networks, {})

    @classmethod
    def from_bybit(cls, data):
        coin_name = data["coin"]
        networks = [NetworkExchange.from_bybit(network) for network in data["chains"]]

        return cls(coin_name, "ByBit", networks, {})

    @classmethod
    def from_okx(cls, data):
        coin_name = data["ccy"]
        networks = [NetworkExchange.from_okx(data)]

        return cls(coin_name, "OKX", networks, {})

    # @classmethod
    # def from_gateio(cls, data: Currency):
    #     coin_name = data.currency.split("_")[0]
    #     networks = []
    #     if data.chain:
    #         networks.append(NetworkExchange.from_gateio(data))
    #
    #     return cls(coin_name, "GateIO", networks, {})

    @classmethod
    def from_huobi(cls, data: ReferenceCurrency):
        coin_name = data.currency
        networks = [
            NetworkExchange.from_huobi(network) for network in data.chains if network.withdrawFeeType == "fixed"
        ]

        return cls(coin_name.upper(), "Huobi", networks, {})

    @classmethod
    def from_kucoin(cls, data):
        coin_name = data["currency"]
        if data["chains"]:
            networks = [NetworkExchange.from_kucoin(data["precision"], chain_data) for chain_data in data["chains"]]
        else:
            networks = []

        return cls(coin_name, "KuCoin", networks, {})

    @classmethod
    def from_bitget(cls, data):
        coin_name = data["coinName"]
        extra_info = {"coin_id": data["coinId"]}
        networks = [NetworkExchange.from_bitget(chain_data) for chain_data in data["chains"]]

        return cls(coin_name, "Bitget", networks, extra_info)

    @classmethod
    def from_whitebit(cls, coin_name: str, data: dict):
        networks = [
            NetworkExchange(
                net_name,
                can_deposit=net_name in data["networks"].get("deposits", []),
                can_withdraw=net_name in data["networks"].get("withdraws", []),
                confirmations_needed=confirmations,
                withdraw_max=float(data["max_withdraw"]) if data["max_withdraw"] != "0" else None,
                withdraw_min=float(data["min_withdraw"]) if data["min_withdraw"] != "0" else None,
                deposit_min=float(data["min_deposit"]) if data["min_deposit"] != "0" else None,
                withdraw_precision=data["currency_precision"],
                withdraw_fee=0,
            )
            for net_name, confirmations in data["confirmations"].items()
        ]

        return cls(coin_name, "Whitebit", networks, {})

    @classmethod
    def from_bingx(cls, data: dict):
        coin_name = data["name"]
        networks = [NetworkExchange.from_bingx(net_data) for net_data in data["networkList"]]

        return cls(coin_name, "Bingx", networks, {})

    @classmethod
    def from_mexc(cls, data: dict):
        coin_name = data["coin"]
        networks = [NetworkExchange.from_mexc(net_data) for net_data in data["networkList"]]

        return cls(coin_name, "Mexc", networks, {})

    @classmethod
    def from_poloniex(cls, data: dict):
        coin_name = data["coin"]
        networks = [NetworkExchange.from_poloniex(net_data) for net_data in data["networkList"]]

        return cls(coin_name, "Poloniex", networks, {})


@dataclass
class TradingPair:
    base_coin: str
    quote_coin: str
    base_coin_precision: int
    quote_coin_precision: int
    exchange: str
    taker_fee: float = 0.001  # 0.1%
    maker_fee: float = 0.001  # 0.1%

    def to_standard(self):
        return f"{self.base_coin}{self.quote_coin}"

    def to_dashed(self):
        return f"{self.base_coin}-{self.quote_coin}"

    def to_db(self):
        data = {
            "base_coin_precision": self.base_coin_precision,
            "quote_coin_precision": self.quote_coin_precision,
            "taker_fee": self.taker_fee,
            "maker_fee": self.maker_fee,
        }
        return data


@dataclass
class Price:
    amount_available: float
    price: float = None
    partial_exhausted: bool = False


@dataclass
class DepositAddress:
    address: str
    memo: Union[str, None] = None


@dataclass
class ExchangeLiquidity:
    exchange_id: int
    name: str
    current_limit: float
    balance: float


@dataclass
class ProfitBookOrder:
    spread: float
    coin_amount: float
    buy_price: float
    sell_price: float
