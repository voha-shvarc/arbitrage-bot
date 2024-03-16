from .bundle import bundle_router
from .menu import menu_router
from .set_exchange_max_liquid import set_exchange_max_liquid_router
from .user import user_router


routers_list = [
    bundle_router,
    user_router,
    menu_router,
    set_exchange_max_liquid_router,
]

__all__ = [
    "routers_list",
]
