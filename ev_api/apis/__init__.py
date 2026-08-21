"""Domain-oriented API objects used by black-box tests."""

from ev_api.apis.after_sales_api import AfterSalesApi
from ev_api.apis.ai_api import AiApi
from ev_api.apis.auth_api import AuthApi
from ev_api.apis.catalog_api import CatalogApi
from ev_api.apis.customer_api import CustomerApi
from ev_api.apis.delivery_api import DeliveryApi
from ev_api.apis.finance_api import FinanceApi
from ev_api.apis.inventory_api import InventoryApi
from ev_api.apis.order_api import OrderApi
from ev_api.apis.test_drive_api import TestDriveApi

__all__ = [
    "AfterSalesApi",
    "AiApi",
    "AuthApi",
    "CatalogApi",
    "CustomerApi",
    "DeliveryApi",
    "FinanceApi",
    "InventoryApi",
    "OrderApi",
    "TestDriveApi",
]
