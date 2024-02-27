from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, ARRAY
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import JSONB

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
    name = Column(String(50), index=True, nullable=False)
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
    base_network_id = Column(ForeignKey("networks.id"), index=True)

    arrival_time = Column(Integer)
    withdraw_fee = Column(Float, default=0, server_default="0")
    can_withdraw = Column(Boolean, default=False, server_default="false", index=True, nullable=False)
    can_deposit = Column(Boolean, default=False, server_default="false", index=True, nullable=False)
    extra_info = Column(JSONB, server_default="{}", nullable=False)

    created_at = db_created()
    updated_at = db_updated()

    exchange = relationship("Exchange", uselist=False)
    coin = relationship("Coin", uselist=False)
    network = relationship("Network", uselist=False, foreign_keys=[network_id])
    base_network = relationship("Network", uselist=False, foreign_keys=[base_network_id])


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
    def dashed_name(self):
        return f"{self.base_coin.name}-{self.quote_coin.name}"

    @property
    def underscored_name(self):
        return f"{self.base_coin.name}_{self.quote_coin.name}"

    @property
    def slashed_name(self):
        return f"{self.base_coin.name}/{self.quote_coin.name}"

    @property
    def huobi_name(self):
        return f"{self.base_coin.name.lower()}{self.quote_coin.name.lower()}"

    @property
    def bitget_name(self):
        return f"{self.base_coin.name}{self.quote_coin.name}_SPBL"


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

    base_exchange_trading_volume = Column(Float)
    pair_exchange_trading_volume = Column(Float)
    synced = Column(Boolean(), default=False, server_default="False", index=True)
    status = Column(
        String(20),
        default=BundleStatus.in_progress,
        server_default=BundleStatus.in_progress,
        index=True,
    )

    buy_price_snapshot = Column(ARRAY(String(50)))

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

    is_exhausted = Column(Boolean, default=False, server_default="false")

    # general info
    to_use_usdt = Column(Float)
    to_use_base_ccy = Column(Float)
    avg_spread = Column(Float)
    base_profit = Column(Float)
    total_fee = Column(Float)
    spot_fee = Column(Float, server_default="0")
    network_fee = Column(Float, server_default="0")
    profit = Column(Float)

    base_exchange_max_price = Column(Float, server_default="0")
    base_exchange_min_price = Column(Float, server_default="0")
    pair_exchange_max_price = Column(Float, server_default="0")
    pair_exchange_min_price = Column(Float, server_default="0")

    used_buy_orders = Column(Integer, server_default="0")
    used_sell_orders = Column(Integer, server_default="0")

    # user based info
    user_based_to_use_usdt = Column(Float, server_default="0")
    user_based_to_use_base_ccy = Column(Float, server_default="0")
    user_based_avg_spread = Column(Float, server_default="0")
    user_based_base_profit = Column(Float, server_default="0")
    user_based_total_fee = Column(Float, server_default="0")
    user_based_spot_fee = Column(Float, server_default="0")
    user_based_network_fee = Column(Float, server_default="0")
    user_based_profit = Column(Float, server_default="0")

    user_based_base_exchange_max_price = Column(Float, server_default="0")
    user_based_base_exchange_min_price = Column(Float, server_default="0")
    user_based_pair_exchange_max_price = Column(Float, server_default="0")
    user_based_pair_exchange_min_price = Column(Float, server_default="0")

    user_based_used_buy_orders = Column(Integer, server_default="0")
    user_based_used_sell_orders = Column(Integer, server_default="0")

    created_at = db_created()
    updated_at = db_updated()

    profit_bundle = relationship("ProfitBundle", backref=backref("items"), uselist=False)

    @property
    def percent_of_base_trading_vol(self):
        if self.profit_bundle.base_exchange_trading_volume:
            return self.to_use_base_ccy / self.profit_bundle.base_exchange_trading_volume
        else:
            return 0

    @property
    def percent_of_pair_trading_vol(self):
        if self.profit_bundle.pair_exchange_trading_volume:
            return self.to_use_base_ccy / self.profit_bundle.pair_exchange_trading_volume
        else:
            return 0

    @property
    def user_based_percent_of_base_trading_vol(self):
        if self.profit_bundle.base_exchange_trading_volume:
            return self.user_based_to_use_base_ccy / self.profit_bundle.base_exchange_trading_volume
        else:
            return 0

    @property
    def user_based_percent_of_pair_trading_vol(self):
        if self.profit_bundle.pair_exchange_trading_volume:
            return self.user_based_to_use_base_ccy / self.profit_bundle.pair_exchange_trading_volume
        else:
            return 0
