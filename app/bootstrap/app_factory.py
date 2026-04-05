"""Application composition root for the refactored service container."""

from __future__ import annotations

from collections.abc import Mapping

from app.auth import token_refresh
from app.bootstrap.settings import load_settings
from app.runtime import account_registry, ws_client
from app.services import (
    ai_reply,
    auto_confirm,
    item_polish,
    login_service,
    reply_policy,
    shipping,
)
from app.shared.types import DEFAULT_DB_PATH, ServiceContainerDict, ServiceKey


def build_container(test_mode: bool = False) -> dict[str, object]:
    """Build the application service container.

    In ``test_mode=True`` the container is intentionally assembled from package
    root stubs only, so imports stay side-effect free and avoid legacy circular
    dependencies. Production wiring is deferred to later extraction tasks.
    """

    settings = None
    db_path = DEFAULT_DB_PATH
    if not test_mode:
        settings = load_settings()
        db_path = settings.db_path

    container: ServiceContainerDict = {
        ServiceKey.ACCOUNT_REGISTRY.value: account_registry,
        ServiceKey.WS_CLIENT.value: ws_client,
        ServiceKey.TOKEN_REFRESH.value: token_refresh,
        ServiceKey.REPLY_POLICY.value: reply_policy,
        ServiceKey.AI_REPLY.value: ai_reply,
        ServiceKey.SHIPPING.value: shipping,
        ServiceKey.ITEM_POLISH.value: item_polish,
        ServiceKey.AUTO_CONFIRM.value: auto_confirm,
        ServiceKey.LOGIN_SERVICE.value: login_service,
        ServiceKey.SETTINGS.value: settings,
        ServiceKey.DB_PATH.value: db_path,
    }
    return dict(container)


def get_service(container: Mapping[str, object], name: str) -> object:
    """Get a service from the container, raising if not registered."""

    if name not in container:
        raise KeyError(f"Service '{name}' is not registered in the container")
    return container[name]


__all__ = ["build_container", "get_service"]
