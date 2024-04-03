from datetime import datetime

from abstract.abstract import AbstractExchange
from abstract.abstract import WithdrawStatus
from db.models import BundleStatus
from db.models import ProfitBundle
from db.models import ProfitBundleItem
from exchanges import EXCHANGES_MAPPING


def format_number(num):
    suffixes = ["", "K", "M", "B", "T"]
    suffix_index = 0
    while num >= 1000 and suffix_index < len(suffixes) - 1:
        suffix_index += 1
        num /= 1000.0
    return f"{num:.2f}{suffixes[suffix_index]}"


def get_bundle_message(bundle: ProfitBundle, bundle_item: ProfitBundleItem) -> str:
    if bundle.status == BundleStatus.in_progress:
        time_live = datetime.utcnow() - bundle.created_at
    else:
        time_live = bundle.updated_at - bundle.created_at

    base_exchange: AbstractExchange = EXCHANGES_MAPPING[bundle.base_exchange.name]
    pair_exchange: AbstractExchange = EXCHANGES_MAPPING[bundle.pair_exchange.name]

    base_ex_spot_link = base_exchange.spot_link(bundle.pair)
    base_ex_withdraw_link = base_exchange.withdraw_link(bundle.withdraw_coin_network_exchange)
    pair_ex_spot_link = pair_exchange.spot_link(bundle.pair)
    pair_ex_deposit_link = pair_exchange.deposit_link(bundle.deposit_coin_network_exchange)

    base_exchange_price_section = (
        f"📕 {bundle.base_exchange.name} | <a href='{base_ex_spot_link}'>spot</a> | <a href='{base_ex_withdraw_link}'>withdraw</a>\n"
        f"💲 [ <code>{bundle_item.user_based_base_exchange_min_price}</code> - "
        f"<code>{bundle_item.user_based_base_exchange_max_price}</code> ] | "
        f"{format_number(bundle_item.user_based_to_use_base_ccy)} {bundle.withdraw_coin_network_exchange.coin.name}\n"
        f"📈 {bundle_item.user_based_used_buy_orders} orders | {(bundle_item.user_based_percent_of_base_trading_vol * 100):.3f}%"
        f" | {bundle.base_exchange_chart_change:+.1f}%\n"
        f"🛒 {bundle_item.used_buy_orders} orders | {(bundle_item.percent_of_base_trading_vol * 100):.3f}% | {bundle_item.to_use_usdt:.2f}$"
    )

    pair_exchange_price_section = (
        f"📗 {bundle.pair_exchange.name} | <a href='{pair_ex_spot_link}'>spot</a> | <a href='{pair_ex_deposit_link}'>deposit</a>\n"
        f"💲[ <code>{bundle_item.user_based_pair_exchange_min_price}</code> - "
        f"<code>{bundle_item.user_based_pair_exchange_max_price}</code> ] | "
        f"{format_number(bundle_item.user_based_to_use_base_ccy)} {bundle.withdraw_coin_network_exchange.coin.name}\n"
        f"📈 {bundle_item.user_based_used_sell_orders} orders | {(bundle_item.user_based_percent_of_pair_trading_vol * 100):.3f}%"
        f" | {bundle.pair_exchange_chart_change:+.1f}%\n"
        f"🛒 {bundle_item.used_sell_orders} orders | {(bundle_item.percent_of_pair_trading_vol * 100):.3f}% | {bundle_item.to_use_usdt:.2f}$"
    )

    fees_section = f"‼️️ Spot Fee: <b>{bundle_item.user_based_spot_fee:.2f}$</b> | Network Fee: <b>{bundle_item.user_based_network_fee:.2f}$</b>"
    if bundle.back_way_network_fee is not None:
        fees_section += f"\n‼️ Back Way Network Fee: <b>{bundle.back_way_network_fee:.2f}$</b>"
    if bundle.network_speed is not None:
        fees_section += f"\n🚀 Network Speed: {bundle.network_speed:.1f} - {bundle.network_speed + 2:.1f} minutes"

    status = (
        f"🟢 Status: {bundle.status}" if bundle.status == BundleStatus.in_progress else f"🔴 Status: {bundle.status}"
    )

    if base_exchange.withdraw_status == WithdrawStatus.whitelist:
        whitelist_status = "✅ Whitelisted" if bundle.is_whitelisted else "🚫 Not whitelisted"
    else:
        whitelist_status = ""

    exhausted_status = "🩸 Order Book is exhausted\n\n" if bundle_item.is_exhausted else ""

    message = (
        f"<b>{bundle.base_exchange.name} -> {bundle.pair_exchange.name} | "
        f"<code>{bundle_item.user_based_to_use_usdt:.2f}</code>$ {bundle_item.user_based_profit:+.2f}$</b>\n\n"
        f"<code>{bundle.pair.base_coin.name}</code>-<b>{bundle.pair.quote_coin.name}</b> | "
        f"<b>{bundle.withdraw_coin_network_exchange.base_network.name}</b> {whitelist_status}\n\n"
        f"{exhausted_status}"
        f"{base_exchange_price_section}\n\n"
        f"{pair_exchange_price_section}\n\n"
        f"{fees_section}\n\n"
        f"{status}\n"
        f"⏳ Alive: {time_live.total_seconds() / 60:.1f} minutes"
    )

    return message
