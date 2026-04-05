"""Fresh sqlite database foundation for the refactored app."""

from .connection import get_db
from .models import (
    AISetting,
    AdminSession,
    Conversation,
    DefaultReply,
    DeliveryCard,
    DeliveryLog,
    DeliveryRule,
    Item,
    ItemKeyword,
    ItemReply,
    Keyword,
    Order,
    PolishSchedule,
    RiskLog,
    SystemSetting,
    XianyuAccount,
)
from .schema import EXPECTED_TABLES, initialize_database

__all__ = [
    "AISetting",
    "AdminSession",
    "Conversation",
    "DefaultReply",
    "DeliveryCard",
    "DeliveryLog",
    "DeliveryRule",
    "EXPECTED_TABLES",
    "Item",
    "ItemKeyword",
    "ItemReply",
    "Keyword",
    "Order",
    "PolishSchedule",
    "RiskLog",
    "SystemSetting",
    "XianyuAccount",
    "get_db",
    "initialize_database",
]
