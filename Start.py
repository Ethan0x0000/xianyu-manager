"""Application entry point.

Starts Xianyu Manager using the new modular architecture.
"""

from __future__ import annotations

import socket
from collections.abc import Callable
from typing import cast

import uvicorn

from app.bootstrap.app_factory import create_app
from app.bootstrap.settings import Settings, load_settings


def create_listen_sockets(host: str, port: int) -> list[socket.socket] | None:
    if host != "::":
        return None

    listen_sockets: list[socket.socket] = []
    try:
        ipv6_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        listen_sockets.append(ipv6_socket)
        ipv6_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ipv6_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        ipv6_socket.bind((host, port))
        ipv6_socket.setblocking(False)

        bound_port = cast(tuple[str, int, int, int], ipv6_socket.getsockname())[1]

        ipv4_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_sockets.append(ipv4_socket)
        ipv4_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ipv4_socket.bind(("0.0.0.0", bound_port))
        ipv4_socket.setblocking(False)

        return listen_sockets
    except Exception:
        for listen_socket in listen_sockets:
            listen_socket.close()
        raise


def run_server(app: Callable[..., object] | str, settings: Settings) -> None:
    listen_sockets = create_listen_sockets(settings.api_host, settings.api_port)
    if listen_sockets is None:
        uvicorn.run(
            app,
            host=settings.api_host,
            port=settings.api_port,
            log_level="info",
        )
        return

    config = uvicorn.Config(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    try:
        server.run(sockets=listen_sockets)
    finally:
        for listen_socket in listen_sockets:
            listen_socket.close()


def main() -> None:
    settings = load_settings()
    app = create_app(settings)

    run_server(app, settings)


if __name__ == "__main__":
    main()
