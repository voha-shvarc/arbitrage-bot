from db.models import CoinNetworkExchange
from db.models import OpportunityStatus
from db.structs import Price
from db.structs import ProfitBookOrder


class PriceAnalyzer:
    BASE_SPREAD = 0.004  # 0.4%

    def __init__(
        self,
        buy_price,
        sell_price,
        spot_buy_fee: float,
        spot_sell_fee: float,
        withdraw_cne: CoinNetworkExchange,
        deposit_cne: CoinNetworkExchange = None,
        custom_liquid_limit: float = None,
    ):
        self.withdraw_cne = withdraw_cne
        self.deposit_cne = deposit_cne
        self.MAX_LIQUID_AMOUNT = custom_liquid_limit or withdraw_cne.exchange.max_liquid_amount

        self.is_exhausted = False
        self.spot_buy_fee = spot_buy_fee
        self.spot_sell_fee = spot_sell_fee
        self.buy_prices = buy_price
        self.sell_prices = sell_price
        self.profit_orders: list[ProfitBookOrder] = []
        self.opportunity_status = OpportunityStatus.equal_opportunity

        # general info
        self.to_use_usdt = 0
        self.coins_to_buy = 0

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
        return self.coins_to_buy * (self.spot_buy_fee + self.spot_sell_fee)

    @property
    def avg_buy_price(self) -> float:
        return (self.max_buy_price + self.min_buy_price) / 2

    @property
    def avg_sell_price(self) -> float:
        return (self.max_sell_price + self.min_sell_price) / 2

    @property
    def profit(self):
        total_fee = self.withdraw_cne.withdraw_fee + self.spot_fee
        profit_orders = self.profit_orders.copy()
        left_coins = self.coins_to_buy - total_fee

        usdt_to_get = 0
        while left_coins > 0:
            profit_order = profit_orders.pop(0)
            if profit_order.coin_amount > left_coins:
                usdt_to_get += left_coins * profit_order.sell_price
                break

            usdt_to_get += profit_order.coin_amount * profit_order.sell_price
            left_coins -= profit_order.coin_amount

        return usdt_to_get - self.to_use_usdt

    @property
    def back_way_network_fee(self) -> float:
        return self.avg_buy_price * self.deposit_cne.withdraw_fee

    def set_user_based_data(self, buy_price: Price, sell_price: Price):
        self.user_based_coin_available_amount = self.coins_to_buy
        self.user_based_to_use_usdt = self.to_use_usdt
        self.user_based_spot_fee = self.spot_fee * self.avg_sell_price
        self.user_based_network_fee = self.withdraw_cne.withdraw_fee * self.avg_buy_price
        self.user_based_profit = self.profit

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
        buy_p = sell_p = Price(amount_available=0)
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
            self.opportunity_status = OpportunityStatus.exhausted_opportunity
        elif not self.profit_orders:
            pass
        else:
            last_profit_book_order = self.profit_orders[-1]
            if last_profit_book_order.buy_price != buy_p.price:
                if last_profit_book_order.sell_price != sell_p.price:
                    # double switch of book order
                    last_buy_spread = (last_profit_book_order.buy_price / sell_p.price) / last_profit_book_order.buy_price
                    last_sell_spread = (last_profit_book_order.sell_price / buy_p.price) / last_profit_book_order.sell_price
                    if last_buy_spread > self.BASE_SPREAD:
                        self.opportunity_status = OpportunityStatus.buy_opportunity
                    elif last_sell_spread > self.BASE_SPREAD:
                        self.opportunity_status = OpportunityStatus.sell_opportunity
                else:
                    self.opportunity_status = OpportunityStatus.buy_opportunity
            else:
                self.opportunity_status = OpportunityStatus.sell_opportunity

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
            "spot_fee": self.spot_fee * self.avg_sell_price,
            "network_fee": self.withdraw_cne.withdraw_fee * self.avg_buy_price,
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
