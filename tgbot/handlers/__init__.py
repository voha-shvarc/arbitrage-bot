from .menu import menu_router
from .refresh_bundle import refresh_bundle_router
from .user import user_router


routers_list = [
    refresh_bundle_router,
    user_router,
    menu_router,
]

__all__ = [
    "routers_list",
]
