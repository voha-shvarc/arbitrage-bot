from dataclasses import dataclass
from typing import List

from gate_api.models.currency import Currency
from huobi.constant import ChainDepositStatus, ChainWithdrawStatus
from huobi.model.generic import Chain, ReferenceCurrency


@dataclass
class NetworkExchange:
    name: str
    can_deposit: bool
    can_withdraw: bool
    withdraw_fee: [float, None]
    arrival_time: int
    # withdraw_min: float
    # withdraw_all_enable = True|False

    @classmethod
    def from_binance(cls, data):
        name = data["network"]
        can_deposit = data["depositEnable"]
        can_withdraw = data["withdrawEnable"]
        withdraw_fee = data["withdrawFee"]
        arrival_time = data["estimatedArrivalTime"]

        return cls(name, can_deposit, can_withdraw, withdraw_fee, arrival_time)

    @classmethod
    def from_bybit(cls, data):
        name = data["chain"]
        can_deposit = data["chainDeposit"] == "1"
        can_withdraw = data["chainWithdraw"] == "1"
        try:
            withdraw_fee = float(data["withdrawFee"])
        except ValueError:
            withdraw_fee = 0

        return cls(name, can_deposit, can_withdraw, withdraw_fee, 1)
        # arrival_time = data['estimatedArrivalTime']

    @classmethod
    def from_okx(cls, data):
        name = data["chain"].split("-")[1]
        can_deposit = data["canDep"]
        can_withdraw = data["canWd"]
        withdraw_fee = float(data["minFee"])

        return cls(name, can_deposit, can_withdraw, withdraw_fee, 1)

    @classmethod
    def from_gateio(cls, data: Currency):
        name = data.chain
        can_deposit = not data.deposit_disabled
        can_withdraw = not data.withdraw_disabled
        withdraw_fee = None

        return cls(name, can_deposit, can_withdraw, withdraw_fee, 1)

    @classmethod
    def from_huobi(cls, network: Chain):
        name = network.baseChain or network.chain
        can_deposit = network.depositStatus == ChainDepositStatus.ALLOWED
        can_withdraw = network.withdrawStatus == ChainWithdrawStatus.ALLOWED
        withdraw_fee = network.transactFeeWithdraw

        return cls(name.upper(), can_deposit, can_withdraw, withdraw_fee, 1)

    @classmethod
    def from_kucoin(cls, data):
        net_name = data["chainName"]
        can_deposit = data["isDepositEnabled"]
        can_withdraw = data["isWithdrawEnabled"]
        withdraw_fee = data["withdrawalMinFee"]

        return cls(net_name, can_deposit, can_withdraw, withdraw_fee, 1)

    @classmethod
    def from_bitget(cls, data):
        net_name = data["chain"]
        can_deposit = True if data["rechargeable"] == "true" else False
        can_withdraw = True if data["withdrawable"] == "true" else False
        withdraw_fee = float(data["withdrawFee"])

        return cls(net_name, can_deposit, can_withdraw, withdraw_fee, 1)


@dataclass
class CoinNetworkExchangeDC:
    coin_name: str
    exchange_name: str
    networks: List[NetworkExchange]

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
            "arrival_time": net.arrival_time,
        }
        return data

    @classmethod
    def from_binance(cls, data):
        coin_name = data["coin"]
        networks = [NetworkExchange.from_binance(network) for network in data["networkList"]]

        return cls(coin_name, "Binance", networks)

    @classmethod
    def from_bybit(cls, data):
        coin_name = data["coin"]
        networks = [NetworkExchange.from_bybit(network) for network in data["chains"]]

        return cls(coin_name, "ByBit", networks)

    @classmethod
    def from_okx(cls, data):
        coin_name = data["ccy"]
        networks = [NetworkExchange.from_okx(data)]

        return cls(coin_name, "OKX", networks)

    @classmethod
    def from_gateio(cls, data: Currency):
        coin_name = data.currency.split("_")[0]
        networks = []
        if data.chain:
            networks.append(NetworkExchange.from_gateio(data))

        return cls(coin_name, "GateIO", networks)

    @classmethod
    def from_huobi(cls, data: ReferenceCurrency):
        coin_name = data.currency
        networks = [
            NetworkExchange.from_huobi(network) for network in data.chains if network.withdrawFeeType == "fixed"
        ]

        return cls(coin_name.upper(), "Huobi", networks)

    @classmethod
    def from_kucoin(cls, data):
        coin_name = data["currency"]
        if data["chains"]:
            networks = [NetworkExchange.from_kucoin(chain_data) for chain_data in data["chains"]]
        else:
            networks = []

        return cls(coin_name, "KuCoin", networks)

    @classmethod
    def from_bitget(cls, data):
        coin_name = data["coinName"]
        networks = [NetworkExchange.from_bitget(chain_data) for chain_data in data["chains"]]

        return cls(coin_name, "Bitget", networks)


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
