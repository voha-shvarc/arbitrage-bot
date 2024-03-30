from db.models import CoinNetworkExchange
from db.structs import Price
from db.structs import ProfitBookOrder


class PriceAnalyzer:
    BASE_SPREAD = 0.004  # 0.4%
    EXCHANGE_BUY_COMMISSION = 0.001  # 0.1%
    EXCHANGE_SELL_COMMISSION = 0.001  # 0.1%

    def __init__(
        self,
        buy_price,
        sell_price,
        withdraw_cne: CoinNetworkExchange,
        deposit_cne: CoinNetworkExchange = None,
        custom_liquid_limit: float = None,
    ):
        self.withdraw_cne = withdraw_cne
        self.deposit_cne = deposit_cne
        self.MAX_LIQUID_AMOUNT = custom_liquid_limit or withdraw_cne.exchange.max_liquid_amount

        self.is_exhausted = False
        self.exchange_commission = self.EXCHANGE_BUY_COMMISSION + self.EXCHANGE_SELL_COMMISSION
        self.buy_prices = buy_price
        self.sell_prices = sell_price
        self.avg_buy_price = 0
        self.avg_sell_price = 0
        self.profit_orders: list[ProfitBookOrder] = []

        # general info
        self.to_use_usdt = 0
        self.coins_to_buy = 0
        self.avg_spread = 0

        self.min_buy_price = 0
        self.max_buy_price = 0
        self.min_sell_price = 0
        self.max_sell_price = 0

        self.used_buy_orders = 0
        self.used_sell_orders = 0

        # user based info
        self.is_user_based = True

        self.user_based_to_use_usdt = 0
        self.user_based_coin_available_amount = 0
        self.user_based_avg_spread = 0
        self.user_based_spot_fee = 0
        self.user_based_network_fee = 0
        self.user_based_profit = 0

        self.user_based_min_buy_price = 0
        self.user_based_max_buy_price = 0
        self.user_based_min_sell_price = 0
        self.user_based_max_sell_price = 0

        self.user_based_used_buy_orders = 0
        self.user_based_used_sell_orders = 0

    @property
    def spot_fee(self):
        return self.coins_to_buy * self.exchange_commission

    def profit(self):
        total_fee = self.withdraw_cne.withdraw_fee + self.spot_fee
        profit_orders = self.profit_orders.copy()

        while profit_orders:
            profit_book_order = profit_orders.pop()
            if total_fee > profit_book_order.coin_amount:
                total_fee -= profit_book_order.coin_amount
            else:
                profit_book_order.coin_amount -= total_fee
                profit_orders.append(profit_book_order)
                break

        profit = sum(
            [
                profit_order.spread * profit_order.coin_amount * profit_order.sell_price
                for profit_order in self.profit_orders
            ],
        )
        self.set_avg_values(profit_orders)
        return profit

    def set_avg_values(self, profit_orders):
        buy_prices = set()
        sell_prices = set()
        spreads = set()
        for profit_order in profit_orders:
            buy_prices.add(profit_order.buy_price)
            sell_prices.add(profit_order.sell_price)
            spreads.add(profit_order.spread)

        self.avg_buy_price = sum(buy_prices) / len(buy_prices)
        self.avg_sell_price = sum(sell_prices) / len(sell_prices)
        self.avg_spread = sum(spreads) / len(spreads)

    def set_user_based_data(self, buy_price: Price, sell_price: Price):
        self.user_based_profit = self.profit  # need to be calculated the first
        self.user_based_coin_available_amount = self.coins_to_buy
        self.user_based_to_use_usdt = self.to_use_usdt
        self.user_based_avg_spread = self.avg_spread
        self.user_based_spot_fee = self.spot_fee * self.avg_sell_price
        self.user_based_network_fee = self.withdraw_cne.withdraw_fee * self.avg_buy_price

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
        buy_p = Price(amount_available=0)
        sell_p = Price(amount_available=0)
        b_prices = self.buy_prices.copy()
        s_prices = self.sell_prices.copy()
        complete_user_based = False
        while b_prices and s_prices:
            if buy_p.amount_available == 0:
                buy_p = self.get_price(b_prices.pop(0))
            if sell_p.amount_available == 0:
                sell_p = self.get_price(s_prices.pop(0))

            spread = (sell_p.price - buy_p.price) / buy_p.price
            coins_to_buy = min([buy_p.amount_available, sell_p.amount_available])

            left_user_based_coins = self.MAX_LIQUID_AMOUNT / buy_p.price
            if self.is_user_based and coins_to_buy >= left_user_based_coins:
                coins_to_buy = left_user_based_coins
                complete_user_based = True

            if spread > self.BASE_SPREAD:
                self.MAX_LIQUID_AMOUNT -= coins_to_buy * buy_p.price
                self.profit_orders.append(ProfitBookOrder(spread, coins_to_buy, buy_p.price, sell_p.price))
                self.coins_to_buy += coins_to_buy
                self.to_use_usdt += coins_to_buy * buy_p.price

                self.set_min_max_prices(buy_p, sell_p)
                self.set_used_orders(buy_p, sell_p, complete_user_based, coins_to_buy)
                if complete_user_based:
                    self.set_user_based_data(buy_p, sell_p)
                    self.is_user_based = complete_user_based = False
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

    @staticmethod
    def get_price(price_data: list) -> Price:
        return Price(float(price_data[1]), float(price_data[0]))

    def set_min_max_prices(self, buy_p: Price, sell_p: Price):
        if not self.min_buy_price:
            self.min_buy_price = buy_p.price

        self.max_buy_price = buy_p.price

        if not self.min_sell_price:
            self.min_sell_price = sell_p.price
        self.max_sell_price = sell_p.price

    def set_used_orders(self, buy_p: Price, sell_p: Price, double_minus: bool, coins_to_buy: float):
        if double_minus:
            buy_p.amount_available -= coins_to_buy
            sell_p.amount_available -= coins_to_buy
            buy_p.partial_exhausted = sell_p.partial_exhausted = True

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

    def to_db(self):
        """Convert to ProfitBundleItem model object"""
        return {
            "is_exhausted": self.is_exhausted,
            # general info
            "to_use_usdt": self.to_use_usdt,
            "to_use_base_ccy": self.coins_to_buy,
            "profit": self.profit,
            "avg_spread": self.avg_spread,
            "spot_fee": self.spot_fee * self.avg_sell_price,
            "network_fee": self.withdraw_cne.withdraw_fee * self.avg_buy_price,
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
