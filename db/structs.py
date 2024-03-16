from dataclasses import dataclass
from typing import Any
from typing import List
from typing import Union

from gate_api.models.currency import Currency
from huobi.constant import ChainDepositStatus
from huobi.constant import ChainWithdrawStatus
from huobi.model.generic import Chain
from huobi.model.generic import ReferenceCurrency


@dataclass
class NetworkExchange:
    name: str
    can_deposit: bool
    can_withdraw: bool
    withdraw_fee: float
    confirmations_needed: Union[int, float, None] = None
    plain_name: Union[str, None] = None

    @classmethod
    def from_binance(cls, data):
        name = data["network"]
        can_deposit = data["depositEnable"]
        can_withdraw = data["withdrawEnable"]
        withdraw_fee = data["withdrawFee"]
        confirmations_needed = data["minConfirm"]

        return cls(name, can_deposit, can_withdraw, withdraw_fee, confirmations_needed)

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

        return cls(name, can_deposit, can_withdraw, withdraw_fee, confirmations_needed)

    @classmethod
    def from_okx(cls, data):
        name = data["chain"].split("-")[1]
        can_deposit = data["canDep"]
        can_withdraw = data["canWd"]
        withdraw_fee = float(data["minFee"])
        confirmations_needed = int(data["minDepArrivalConfirm"])

        return cls(name, can_deposit, can_withdraw, withdraw_fee, confirmations_needed, plain_name=data["chain"])

    @classmethod
    def from_gateio(cls, data: Currency):
        name = data.chain
        can_deposit = not data.deposit_disabled
        can_withdraw = not data.withdraw_disabled

        return cls(name, can_deposit, can_withdraw, 0)

    @classmethod
    def from_huobi(cls, network: Chain):
        name = network.baseChain or network.chain
        can_deposit = network.depositStatus == ChainDepositStatus.ALLOWED
        can_withdraw = network.withdrawStatus == ChainWithdrawStatus.ALLOWED
        withdraw_fee = network.transactFeeWithdraw
        confirmations_needed = network.numOfFastConfirmations

        return cls(
            name.upper(), can_deposit, can_withdraw, withdraw_fee, confirmations_needed, plain_name=network.chain
        )

    @classmethod
    def from_kucoin(cls, data):
        net_name = data["chainName"]
        plain_name = data["chainId"]
        can_deposit = data["isDepositEnabled"]
        can_withdraw = data["isWithdrawEnabled"]
        withdraw_fee = data["withdrawalMinFee"]
        confirmations_needed = data["preConfirms"]

        return cls(net_name, can_deposit, can_withdraw, withdraw_fee, confirmations_needed, plain_name)

    @classmethod
    def from_bitget(cls, data):
        net_name = data["chain"]
        can_deposit = True if data["rechargeable"] == "true" else False
        can_withdraw = True if data["withdrawable"] == "true" else False
        withdraw_fee = float(data["withdrawFee"])
        confirmations_needed = int(data["depositConfirm"])

        return cls(net_name, can_deposit, can_withdraw, withdraw_fee, confirmations_needed)

    @classmethod
    def from_bingx(cls, data: dict):
        net_name = data["network"]
        can_deposit = data["depositEnable"]
        can_withdraw = data["withdrawEnable"]
        withdraw_fee = float(data["withdrawFee"])
        confirmations_needed = data["minConfirm"]

        return cls(net_name, can_deposit, can_withdraw, withdraw_fee, confirmations_needed)

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

        return cls(net_name, can_deposit, can_withdraw, withdraw_fee, confirmations_needed, plain_name)


@dataclass
class CoinNetworkExchangeDC:
    coin_name: str
    exchange_name: str
    networks: List[NetworkExchange]
    extra_info: dict[str:Any]

    def to_db(self, exchange, coin, network, network_id):
        net = self.networks[network_id]
        data = {
            "exchange_id": exchange.id,
            "coin_id": coin.id,
            "network_id": network.id,
            "base_network_id": network.id,
            "can_deposit": net.can_deposit,
            "can_withdraw": net.can_withdraw,
            "withdraw_fee": net.withdraw_fee,
            "extra_info": self.extra_info,
            "confirmations_needed": net.confirmations_needed,
            "plain_network_name": net.plain_name,
        }
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

    @classmethod
    def from_gateio(cls, data: Currency):
        coin_name = data.currency.split("_")[0]
        networks = []
        if data.chain:
            networks.append(NetworkExchange.from_gateio(data))

        return cls(coin_name, "GateIO", networks, {})

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
            networks = [NetworkExchange.from_kucoin(chain_data) for chain_data in data["chains"]]
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
                withdraw_fee=0,
                confirmations_needed=confirmations,
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


@dataclass
class TradingPair:
    base_coin: str
    quote_coin: str
    exchange: str

    def to_standard(self):
        return f"{self.base_coin}{self.quote_coin}"

    def to_dashed(self):
        return f"{self.base_coin}-{self.quote_coin}"


@dataclass
class Price:
    price: float
    amount_available: float
    partial_exhausted: bool = False


@dataclass
class DepositAddress:
    address: str
    memo: Union[str, None]
