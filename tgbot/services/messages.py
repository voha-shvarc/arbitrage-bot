from datetime import datetime

from db.models import BundleStatus
from db.models import ProfitBundleItem
from exchanges import BinanceAPI
from exchanges import BingxAPI
from exchanges import BitgetAPI
from exchanges import BybitAPI
from exchanges import GateIOAPI
from exchanges import HuobiAPI
from exchanges import KuCoinAPI
from exchanges import MexcAPI
from exchanges import OkxAPI
from exchanges import WhitebitAPI


exchange_mapping = {
    BinanceAPI.NAME: BinanceAPI,
    BybitAPI.NAME: BybitAPI,
    HuobiAPI.NAME: HuobiAPI,
    GateIOAPI.NAME: GateIOAPI,
    OkxAPI.NAME: OkxAPI,
    KuCoinAPI.NAME: KuCoinAPI,
    BitgetAPI.NAME: BitgetAPI,
    WhitebitAPI.NAME: WhitebitAPI,
    BingxAPI.NAME: BingxAPI,
    MexcAPI.NAME: MexcAPI,
}


def get_bundle_message(bundle, bundle_item: ProfitBundleItem, show_more: bool = False) -> str:
    if bundle.status == BundleStatus.in_progress:
        time_live = datetime.utcnow() - bundle.created_at
    else:
        time_live = bundle.updated_at - bundle.created_at

    base_exchange = exchange_mapping[bundle.base_exchange.name]
    pair_exchange = exchange_mapping[bundle.pair_exchange.name]

    base_ex_spot_link = base_exchange.spot_link(bundle.pair)
    base_ex_withdraw_link = base_exchange.withdraw_link(bundle.coin_network_exchange)
    pair_ex_spot_link = pair_exchange.spot_link(bundle.pair)
    pair_ex_deposit_link = pair_exchange.deposit_link(bundle.coin_network_exchange)

    base_exchange_price_section = (
        f"📕 {bundle.base_exchange.name} | <a href='{base_ex_spot_link}'>spot</a> | <a href='{base_ex_withdraw_link}'>withdraw</a>\n"
        f"📈 [ <code>{bundle_item.user_based_base_exchange_min_price}</code> - "
        f"<code>{bundle_item.user_based_base_exchange_max_price}</code> ] "
        f"| {bundle_item.user_based_used_buy_orders} orders | {(bundle_item.user_based_percent_of_base_trading_vol * 100):.3f}%"
    )
    if bundle.base_exchange_chart_change is not None:
        base_exchange_price_section += f" | {bundle.base_exchange_chart_change:+.1f}%"
    if show_more:
        base_exchange_price_section += f"\n🛒 {bundle_item.used_buy_orders} orders | {bundle_item.to_use_usdt:.2f}$ | {(bundle_item.percent_of_base_trading_vol * 100):.3f}%"

    pair_exchange_price_section = (
        f"📗 {bundle.pair_exchange.name} | <a href='{pair_ex_spot_link}'>spot</a> | <a href='{pair_ex_deposit_link}'>deposit</a>\n"
        f"📈 [ <code>{bundle_item.user_based_pair_exchange_min_price}</code> - "
        f"<code>{bundle_item.user_based_pair_exchange_max_price}</code> ] "
        f"| {bundle_item.user_based_used_sell_orders} orders | {(bundle_item.user_based_percent_of_pair_trading_vol * 100):.3f}%"
    )
    if bundle.pair_exchange_chart_change is not None:
        pair_exchange_price_section += f" | {bundle.pair_exchange_chart_change:+.1f}%"
    if show_more:
        pair_exchange_price_section += f"\n🛒 {bundle_item.used_sell_orders} orders | {bundle_item.to_use_usdt:.2f}$ | {(bundle_item.percent_of_pair_trading_vol * 100):.3f}%"

    fees_section = f"‼️️ Spot Fee: <b>{bundle_item.user_based_spot_fee:.2f}$</b> | Network Fee: <b>{bundle_item.user_based_network_fee:.2f}$</b>"
    if bundle.network_speed is not None:
        fees_section += f"\n🚀 Network Speed: {bundle.network_speed:.1f} - {bundle.network_speed + 2:.1f} minutes"

    status = (
        f"🟢 Status: {bundle.status}" if bundle.status == BundleStatus.in_progress else f"🔴 Status: {bundle.status}"
    )
    message = (
        f"<b>{bundle.base_exchange.name} -> {bundle.pair_exchange.name} | <code>{bundle_item.user_based_to_use_usdt:.2f}</code>$ "
        f"{bundle_item.user_based_profit:+.2f}$ ({bundle_item.user_based_avg_spread * 100:.2f}%)</b>\n\n"
        f"<b>{bundle.pair.dashed_name}</b> | <b>{bundle.coin_network_exchange.base_network.name}</b>\n\n"
        f"{base_exchange_price_section}\n\n"
        f"{pair_exchange_price_section}\n\n"
        f"{fees_section}\n\n"
        f"{status}\n"
        f"⏳ Alive: {time_live.total_seconds() / 60:.1f} minutes"
    )

    return message
