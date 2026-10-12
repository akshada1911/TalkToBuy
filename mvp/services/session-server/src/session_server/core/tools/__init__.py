"""The nine tools (mvp/contracts/tools.schema.json), as provider-neutral async handlers."""

from session_server.core.tool_router import Handler
from session_server.core.tools.cart import add_to_cart, show_products, update_cart
from session_server.core.tools.catalog import search_catalog
from session_server.core.tools.checkout import confirm_checkout, start_checkout
from session_server.core.tools.family import notify_family
from session_server.core.tools.pace import set_pace
from session_server.core.tools.usual import get_usual_order

HANDLERS: dict[str, Handler] = {
    "search_catalog": search_catalog,
    "show_products": show_products,
    "add_to_cart": add_to_cart,
    "update_cart": update_cart,
    "get_usual_order": get_usual_order,
    "set_pace": set_pace,
    "start_checkout": start_checkout,
    "confirm_checkout": confirm_checkout,
    "notify_family": notify_family,
}
