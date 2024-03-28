from typing import Union

from aiogram import Bot
from retry import retry

from abstract.abstract import AbstractExchange
from db.models import CoinNetworkExchange
from db.models import Pair
from db.structs import Price
from tgbot.config import load_config
from tgbot.keyboards.bundle import get_bundle_keyboard
from tgbot.services.broadcaster import send_message


class PriceAnalyzer:
    BASE_SPREAD = 0.004  # 0.4%
    EXCHANGE_BUY_COMMISSION = 0.001  # 0.1%
    EXCHANGE_SELL_COMMISSION = 0.001  # 0.1%

    def __init__(
        self,
        buy_price,
        sell_price,
        withdraw_cne: CoinNetworkExchange,
        deposit_cne: Union[CoinNetworkExchange, None] = None,
        custom_liquid_limit: float = None,
    ):
        self.withdraw_cne = withdraw_cne
        self.deposit_cne = deposit_cne
        self.MAX_LIQUID_AMOUNT = custom_liquid_limit or withdraw_cne.exchange.max_liquid_amount

        self.exchange_commission = self.EXCHANGE_BUY_COMMISSION + self.EXCHANGE_SELL_COMMISSION
        self.buy_prices = buy_price
        self.sell_prices = sell_price
        self.coin_available_amount = 0
        self.to_use_usdt = 0
        self.base_profit = 0
        self.profit = 0
        self.spot_fee = 0
        self.network_fee = 0
        self.is_exhausted = False
        self.profit_sell_prices = set()
        self.spreads = []

        self.min_buy_price = 0
        self.max_buy_price = 0
        self.min_sell_price = 0
        self.max_sell_price = 0

        self.used_buy_orders = 0
        self.used_sell_orders = 0

        self.is_user_based = True

        self.user_based_coin_available_amount = 0
        self.user_based_to_use_usdt = 0
        self.user_based_base_profit = 0
        self.user_based_profit_sell_prices = set()
        self.user_based_spreads = []

        self.user_based_profit = 0
        self.user_based_spot_fee = 0
        self.user_based_network_fee = 0

        self.user_based_min_buy_price = 0
        self.user_based_max_buy_price = 0
        self.user_based_min_sell_price = 0
        self.user_based_max_sell_price = 0

        self.user_based_used_buy_orders = 0
        self.user_based_used_sell_orders = 0

    @property
    def total_fees(self) -> float:
        return self.spot_fee + self.network_fee

    @property
    def avg_sell_price(self):
        if self.profit_sell_prices:
            return sum(self.profit_sell_prices) / len(self.profit_sell_prices)
        return 0

    @property
    def avg_spread(self):
        if self.spreads:
            return sum(self.spreads) / len(self.spreads)
        return 0

    @property
    def user_based_total_fees(self) -> float:
        return self.user_based_spot_fee + self.user_based_network_fee

    @property
    def user_based_avg_sell_price(self):
        if self.user_based_profit_sell_prices:
            return sum(self.user_based_profit_sell_prices) / len(self.user_based_profit_sell_prices)
        return 0

    @property
    def user_based_avg_spread(self):
        if self.user_based_spreads:
            return sum(self.user_based_spreads) / len(self.user_based_spreads)
        return 0

    def set_user_based_data(self, buy_price: Price, sell_price: Price):
        self.user_based_coin_available_amount = self.coin_available_amount
        self.user_based_to_use_usdt = self.to_use_usdt
        self.user_based_base_profit = self.base_profit
        self.user_based_profit_sell_prices = self.profit_sell_prices
        self.user_based_spreads = self.spreads

        self.user_based_min_buy_price = self.min_buy_price
        self.user_based_max_buy_price = self.max_buy_price
        self.user_based_min_sell_price = self.min_sell_price
        self.user_based_max_sell_price = self.max_sell_price

        self.user_based_used_buy_orders = self.used_buy_orders
        self.user_based_used_sell_orders = self.used_sell_orders

        if buy_price.partial_exhausted:
            self.user_based_used_buy_orders += 1
        if sell_price.partial_exhausted:
            self.user_based_used_sell_orders += 1

    def run(self):
        # TODO: sell amount will be less than buy because of exchange commissions
        buy_p = None
        sell_p = None
        b_prices = self.buy_prices.copy()
        s_prices = self.sell_prices.copy()
        double_minus = False
        while b_prices and s_prices:
            if not buy_p or buy_p.amount_available == 0:
                buy_data = b_prices.pop(0)
                buy_p = Price(float(buy_data[0]), float(buy_data[1]))
            if not sell_p or sell_p.amount_available == 0:
                sell_data = s_prices.pop(0)
                sell_p = Price(float(sell_data[0]), float(sell_data[1]))

            price_diff = sell_p.price - buy_p.price
            spread = price_diff / buy_p.price
            coin_available_amount = min([buy_p.amount_available, sell_p.amount_available])

            if (
                self.is_user_based
                and self.coin_available_amount + coin_available_amount > self.MAX_LIQUID_AMOUNT / buy_p.price
            ):
                coin_available_amount = self.MAX_LIQUID_AMOUNT / buy_p.price - self.coin_available_amount
                double_minus = True

            if spread > self.BASE_SPREAD:
                self.base_profit += spread * coin_available_amount * sell_p.price
                self.coin_available_amount += coin_available_amount
                self.to_use_usdt += coin_available_amount * buy_p.price
                self.profit_sell_prices.add(sell_p.price)
                self.spreads.append(spread)

                if not self.min_buy_price:
                    self.min_buy_price = buy_p.price
                self.max_buy_price = buy_p.price

                if not self.min_sell_price:
                    self.min_sell_price = sell_p.price
                self.max_sell_price = sell_p.price

                if double_minus:
                    buy_p.amount_available -= coin_available_amount
                    sell_p.amount_available -= coin_available_amount
                    buy_p.partial_exhausted = sell_p.partial_exhausted = True
                    double_minus = False
                    self.set_user_based_data(buy_p, sell_p)
                    self.is_user_based = False

                elif buy_p.amount_available > sell_p.amount_available:
                    buy_p.amount_available -= sell_p.amount_available
                    sell_p.amount_available = 0
                    buy_p.partial_exhausted = True

                    self.used_sell_orders += 1
                elif buy_p.amount_available < sell_p.amount_available:
                    sell_p.amount_available -= buy_p.amount_available
                    buy_p.amount_available = 0
                    sell_p.partial_exhausted = True

                    self.used_buy_orders += 1
                else:
                    buy_p.amount_available = 0
                    sell_p.amount_available = 0

                    self.used_buy_orders += 1
                    self.used_sell_orders += 1

            else:
                break

        if not b_prices or not s_prices:
            self.is_exhausted = True

        if self.is_user_based:
            self.set_user_based_data(buy_p, sell_p)

        if buy_p.partial_exhausted:
            self.used_buy_orders += 1
        elif sell_p.partial_exhausted:
            self.used_sell_orders += 1

        if self.coin_available_amount:
            self.spot_fee = self.exchange_commission * self.coin_available_amount * self.avg_sell_price
            self.network_fee = self.withdraw_cne.withdraw_fee * self.avg_sell_price
            self.profit = self.base_profit - self.total_fees

            self.user_based_spot_fee = (
                self.exchange_commission * self.user_based_coin_available_amount * self.user_based_avg_sell_price
            )
            self.user_based_network_fee = self.network_fee
            self.user_based_profit = self.user_based_base_profit - self.user_based_total_fees

    @retry(tries=3, delay=1)
    async def report(
        self,
        base_exchange: AbstractExchange,
        pair_exchange: AbstractExchange,
        pair: Pair,
        bundle_id,
        network_speed,
    ):
        base_ex_spot_link = base_exchange.spot_link(pair)
        base_ex_withdraw_link = base_exchange.withdraw_link(self.withdraw_cne)
        pair_ex_spot_link = pair_exchange.spot_link(pair)
        pair_ex_deposit_link = pair_exchange.deposit_link(self.withdraw_cne)

        message = (
            f"<b>{base_exchange.NAME} -> {pair_exchange.NAME} | {self.user_based_to_use_usdt:.2f}$ +{self.user_based_profit:.2f}$ ({self.user_based_avg_spread * 100:.2f}%)</b>\n\n"
            f"{pair.dashed_name} | <b>{self.withdraw_cne.base_network.name}</b>\n\n"
            f"📕 {base_exchange.NAME} | <a href='{base_ex_spot_link}'>spot</a> | <a href='{base_ex_withdraw_link}'>withdraw</a>\n"
            f"📈 [ {round(self.user_based_min_buy_price, 12)}-{round(self.user_based_max_buy_price, 12)} ] | {self.user_based_used_buy_orders} orders\n\n"
            f"📗 {pair_exchange.NAME} | <a href='{pair_ex_spot_link}'>spot</a> | <a href='{pair_ex_deposit_link}'>deposit</a>\n"
            f"📈 [ {round(self.user_based_min_sell_price, 12)}-{round(self.user_based_max_sell_price, 12)} ] | {self.user_based_used_sell_orders} orders\n\n"
            f"‼️️ Spot Fee: <b>{self.user_based_spot_fee:.2f}$</b> | Network Fee: <b>{self.user_based_network_fee:.2f}$</b>"
        )
        if network_speed:
            message += f"\n🚀 Network Speed: {network_speed:.1f} - {network_speed + 2:.1f} minutes"

        config = load_config(".env")
        bot = Bot(token=config.tg_bot.token, parse_mode="HTML")
        for user_id in config.tg_bot.admin_ids:
            await send_message(
                bot,
                user_id,
                message,
                reply_markup=get_bundle_keyboard(
                    bundle_id,
                ),
                disable_web_page_preview=True,
            )

    def to_db(self):
        """Convert to ProfitBundleItem model object"""
        return {
            "is_exhausted": self.is_exhausted,
            # general info
            "to_use_usdt": self.to_use_usdt,
            "to_use_base_ccy": self.coin_available_amount,
            "avg_spread": self.avg_spread,
            "base_profit": self.base_profit,
            "total_fee": self.total_fees,
            "spot_fee": self.spot_fee,
            "network_fee": self.network_fee,
            "profit": self.profit,
            "base_exchange_max_price": self.max_buy_price,
            "base_exchange_min_price": self.min_buy_price,
            "pair_exchange_max_price": self.max_sell_price,
            "pair_exchange_min_price": self.min_sell_price,
            "used_buy_orders": self.used_buy_orders,
            "used_sell_orders": self.used_sell_orders,
            # user based info
            "user_based_to_use_usdt": self.user_based_to_use_usdt,
            "user_based_to_use_base_ccy": self.user_based_coin_available_amount,
            "user_based_avg_spread": self.user_based_avg_spread,
            "user_based_base_profit": self.user_based_base_profit,
            "user_based_total_fee": self.user_based_total_fees,
            "user_based_spot_fee": self.user_based_spot_fee,
            "user_based_network_fee": self.user_based_network_fee,
            "user_based_profit": self.user_based_profit,
            "user_based_base_exchange_max_price": self.user_based_max_buy_price,
            "user_based_base_exchange_min_price": self.user_based_min_buy_price,
            "user_based_pair_exchange_max_price": self.user_based_max_sell_price,
            "user_based_pair_exchange_min_price": self.user_based_min_sell_price,
            "user_based_used_buy_orders": self.user_based_used_buy_orders,
            "user_based_used_sell_orders": self.user_based_used_sell_orders,
        }
