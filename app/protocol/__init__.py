"""
Protocol Module - WebSocket and Goofish Signing Protocol Wrappers

This module provides thin wrapper interfaces around the existing Goofish signing
and WebSocket payload logic. These wrappers freeze the protocol invariants and
provide a clean API for the rest of the application.

Key Invariants:
- Heartbeat frame format: {"lwp": "/!", "headers": {"mid": <generated_mid>}}
- Signing algorithm: MD5-based with token, timestamp, app_key, and data
- WebSocket URL: wss://wss-goofish.dingtalk.com/
- JavaScript signing runtime: static/xianyu_js_version_2.js (frozen, do not modify)
"""

from .goofish_signing import load_signing_runtime
from .websocket_protocol import build_heartbeat_frame, build_send_frame

__all__ = [
    "load_signing_runtime",
    "build_heartbeat_frame",
    "build_send_frame",
]
