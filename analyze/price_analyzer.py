import json
import os

from retry import retry
from telebot import TeleBot

from db.models import CoinNetworkExchange
from db.structs import Price


class PriceAnalyzer:
    BASE_SPREAD = 0.004  # 0.4%
    EXCHANGE_BUY_COMMISSION = 0.001  # 0.1%
    EXCHANGE_SELL_COMMISSION = 0.001  # 0.1%

    def __init__(self, buy_price, sell_price, network: CoinNetworkExchange):
        self.exchange_commission = self.EXCHANGE_BUY_COMMISSION + self.EXCHANGE_SELL_COMMISSION
        self.buy_prices = buy_price
        self.sell_prices = sell_price
        self.network = network
        self.coin_available_amount = 0
        self.to_use_usdt = 0
        self.base_profit = 0
        self.profit = 0
        self.fees = 0
        self.is_exhausted = False
        self.profit_sell_prices = set()
        self.spreads = []

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

    def run(self):
        # TODO: sell amount will be less than buy because of exchange commissions
        buy_p = None
        sell_p = None
        b_prices = self.buy_prices.copy()
        s_prices = self.sell_prices.copy()
        while b_prices and s_prices:
            if not buy_p:
                buy_data = b_prices.pop(0)
                buy_p = Price(float(buy_data[0]), float(buy_data[1]))
            if not sell_p:
                sell_data = s_prices.pop(0)
                sell_p = Price(float(sell_data[0]), float(sell_data[1]))

            price_diff = sell_p.price - buy_p.price
            spread = price_diff / buy_p.price
            coin_available_amount = min([buy_p.amount_available, sell_p.amount_available])
            if spread > self.BASE_SPREAD:
                self.base_profit += spread * coin_available_amount * sell_p.price
                self.coin_available_amount = coin_available_amount
                self.to_use_usdt += coin_available_amount * buy_p.price
                self.profit_sell_prices.add(sell_p.price)
                self.spreads.append(spread)

                if buy_p.amount_available > sell_p.amount_available:
                    buy_p.amount_available -= sell_p.amount_available
                    sell_p = None
                else:
                    sell_p.amount_available -= buy_p.amount_available
                    buy_p = None
            else:
                break

        if not b_prices or not s_prices:
            self.is_exhausted = True

        if self.coin_available_amount:
            self.fees = (
                self.network.withdraw_fee + (self.exchange_commission * self.coin_available_amount)
            ) * self.avg_sell_price
            self.profit = self.base_profit - self.fees

    @retry(tries=3, delay=1)
    def report(self, base_exchange_name, pair_exchange_name, pair, celery_source=False):
        filename = f"{pair.default_name}_price_info.json"
        with open(filename, "w") as file:
            data = {"buy": self.buy_prices, "sell": self.sell_prices}
            json.dump(data, file)

        message = (
            f"{base_exchange_name} -> {pair_exchange_name}.\n"
            f"<b>Pair</b>: {pair.default_name}. <b>Network</b>: {self.network.network.name}\n"
            f"<b>To Buy</b>: {round(self.to_use_usdt, 3)}\n"
            f"<b>Avg Spread</b>: {round(self.avg_spread * 100, 3)}%\n"
            f"<b>Base profit:</b> {round(self.base_profit, 3)}.\n"
            f"<b>Total Fee:</b> {round(self.fees, 3)}\n"
            f"<b>Profit</b>: <u>{round(self.profit, 3)} USDT</u>"
            f"\n{celery_source = }"
        )

        admin_ids = ["683204904", "703482485"]
        tg_bot = TeleBot("6162670103:AAFbm6YG2zHLR8mUj1Fr430yxMm6Tp2fCoo")
        with open(filename, "rb") as file:
            for admin_id in admin_ids:
                tg_bot.send_message(admin_id, message, parse_mode="HTML")
                tg_bot.send_document(admin_id, file)
                file.seek(0)

        os.remove(filename)

    def to_db(self):
        return {
            "to_use_usdt": self.to_use_usdt,
            "to_use_base_ccy": self.coin_available_amount,
            "avg_spread": self.avg_spread,
            "base_profit": self.base_profit,
            "total_fee": self.fees,
            "profit": self.profit,
            "is_exhausted": self.is_exhausted,
        }
