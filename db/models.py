from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship, backref

from .base import Base
from .utils import db_created, db_updated


class BundleStatus:
    in_progress = "In progress"
    done = "Done"


class Coin(Base):
    __tablename__ = "coins"

    id = Column(Integer, primary_key=True)
    name = Column(String(30), nullable=False)
    created_at = db_created()
    updated_at = db_updated()


class Network(Base):
    __tablename__ = "networks"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    created_at = db_created()
    updated_at = db_updated()


class Exchange(Base):
    __tablename__ = "exchanges"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    created_at = db_created()
    updated_at = db_updated()


class CoinNetworkExchange(Base):
    __tablename__ = "coin_network_exchange"

    id = Column(Integer, primary_key=True)
    exchange_id = Column(ForeignKey("exchanges.id"), index=True)
    coin_id = Column(ForeignKey("coins.id"), index=True)
    network_id = Column(ForeignKey("networks.id"), index=True)

    arrival_time = Column(Integer)
    withdraw_fee = Column(Float, default=0, server_default="0")
    can_withdraw = Column(Boolean, default=False, server_default="false", index=True, nullable=False)
    can_deposit = Column(Boolean, default=False, server_default="false", index=True, nullable=False)
    created_at = db_created()
    updated_at = db_updated()

    coin = relationship("Coin", uselist=False)
    network = relationship("Network", uselist=False)
    exchange = relationship("Exchange", uselist=False)


class Pair(Base):
    __tablename__ = "pairs"

    id = Column(Integer, primary_key=True)
    base_coin_id = Column(ForeignKey("coins.id"), index=True)
    quote_coin_id = Column(ForeignKey("coins.id"), index=True)
    created_at = db_created()
    updated_at = db_updated()

    base_coin = relationship("Coin", uselist=False, foreign_keys=[base_coin_id])
    quote_coin = relationship("Coin", uselist=False, foreign_keys=[quote_coin_id])

    @property
    def default_name(self):
        return f"{self.base_coin.name}{self.quote_coin.name}"

    @property
    def okx_name(self):
        return f"{self.base_coin.name}-{self.quote_coin.name}"

    @property
    def gateio_name(self):
        return f"{self.base_coin.name}_{self.quote_coin.name}"

    @property
    def huobi_name(self):
        return f"{self.base_coin.name.lower()}{self.quote_coin.name.lower()}"


class PairExchange(Base):
    __tablename__ = "pair_exchanges"

    id = Column(Integer, primary_key=True)
    pair_id = Column(ForeignKey("pairs.id"), index=True)
    exchange_id = Column(ForeignKey("exchanges.id"), index=True)
    created_at = db_created()
    updated_at = db_updated()

    pair = relationship("Pair", uselist=False)
    exchange = relationship("Exchange", uselist=False)


class ProfitBundle(Base):
    __tablename__ = "profit_bundles"

    id = Column(Integer, primary_key=True)
    pair_id = Column(ForeignKey("pairs.id"), index=True)
    coin_network_exchange_id = Column(ForeignKey("coin_network_exchange.id"), index=True)
    base_exchange_id = Column(ForeignKey("exchanges.id"), index=True)
    pair_exchange_id = Column(ForeignKey("exchanges.id"), index=True)
    synced = Column(Boolean(), default=False, server_default="False", index=True)
    status = Column(
        String(20),
        default=BundleStatus.in_progress,
        server_default=BundleStatus.in_progress,
        index=True,
    )
    created_at = db_created()
    updated_at = db_updated()

    pair = relationship("Pair", uselist=False)
    coin_network_exchange = relationship("CoinNetworkExchange", uselist=False)
    base_exchange = relationship("Exchange", uselist=False, foreign_keys=[base_exchange_id])
    pair_exchange = relationship("Exchange", uselist=False, foreign_keys=[pair_exchange_id])


class ProfitBundleItem(Base):
    __tablename__ = "profit_bundles_items"

    id = Column(Integer, primary_key=True)
    profit_bundle_id = Column(ForeignKey("profit_bundles.id"))
    to_use_usdt = Column(Float)
    avg_spread = Column(Float)
    base_profit = Column(Float)
    total_fee = Column(Float)
    profit = Column(Float)
    created_at = db_created()
    updated_at = db_updated()

    profit_bundle = relationship("ProfitBundle", backref=backref("items"), uselist=False)
