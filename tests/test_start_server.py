import socket
import unittest
from typing import cast
from unittest.mock import MagicMock, patch

import Start

from tests.helpers import make_settings


class CreateListenSocketsTests(unittest.TestCase):
    def test_create_listen_sockets_returns_dual_stack_sockets_for_unspecified_ipv6(
        self,
    ) -> None:
        listen_sockets = Start.create_listen_sockets("::", 0)
        self.addCleanup(self._close_sockets, listen_sockets)

        self.assertIsNotNone(listen_sockets)
        assert listen_sockets is not None
        self.assertEqual(2, len(listen_sockets))

        families = {sock.family for sock in listen_sockets}
        self.assertEqual({socket.AF_INET, socket.AF_INET6}, families)

        bound_ports = {sock.getsockname()[1] for sock in listen_sockets}
        self.assertEqual(1, len(bound_ports))

        ipv6_socket = next(
            sock for sock in listen_sockets if sock.family == socket.AF_INET6
        )
        self.assertEqual(
            1,
            ipv6_socket.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY),
        )

    def test_create_listen_sockets_returns_none_for_ipv4_host(self) -> None:
        self.assertIsNone(Start.create_listen_sockets("0.0.0.0", 8848))

    @staticmethod
    def _close_sockets(listen_sockets: list[socket.socket] | None) -> None:
        if listen_sockets is None:
            return
        for sock in listen_sockets:
            sock.close()


class RunServerTests(unittest.TestCase):
    @patch("Start.uvicorn.Server")
    @patch("Start.uvicorn.Config")
    @patch("Start.create_listen_sockets")
    def test_run_server_uses_explicit_sockets_for_unspecified_ipv6_host(
        self,
        create_listen_sockets: MagicMock,
        config_cls: MagicMock,
        server_cls: MagicMock,
    ) -> None:
        app = lambda: None
        settings = make_settings(api_host="::", api_port=8848)
        fake_sockets = [MagicMock(), MagicMock()]
        create_listen_sockets.return_value = fake_sockets

        Start.run_server(app, settings)

        config_instance = cast(MagicMock, config_cls.return_value)
        server_instance = cast(MagicMock, server_cls.return_value)
        server_run = cast(MagicMock, server_instance.run)

        create_listen_sockets.assert_called_once_with("::", 8848)
        config_cls.assert_called_once_with(app, host="::", port=8848, log_level="info")
        server_cls.assert_called_once_with(config_instance)
        server_run.assert_called_once_with(sockets=fake_sockets)

    @patch("Start.uvicorn.run")
    @patch("Start.create_listen_sockets")
    def test_run_server_falls_back_to_uvicorn_run_for_ipv4_host(
        self,
        create_listen_sockets: MagicMock,
        uvicorn_run: MagicMock,
    ) -> None:
        app = lambda: None
        settings = make_settings(api_host="0.0.0.0", api_port=8848)
        create_listen_sockets.return_value = None

        Start.run_server(app, settings)

        create_listen_sockets.assert_called_once_with("0.0.0.0", 8848)
        uvicorn_run.assert_called_once_with(
            app,
            host="0.0.0.0",
            port=8848,
            log_level="info",
        )
