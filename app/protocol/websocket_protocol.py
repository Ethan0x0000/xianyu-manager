"""
WebSocket Protocol Wrapper

This module provides thin wrappers around the WebSocket payload building logic.
It freezes the protocol invariants for Goofish WebSocket communication.

Key Invariants:
- Heartbeat frame: {"lwp": "/!", "headers": {"mid": <generated_mid>}}
- Message send frame: {"lwp": "/r/MessageSend/sendByReceiverScope", "headers": {...}, "body": [...]}
- All frames include a "mid" (message ID) in headers
- All frames are JSON-serialized before sending

The WebSocket protocol is frozen and must not be modified. Changes to frame
structure or format must be made carefully and tested thoroughly.

Key Functions:
- build_heartbeat_frame(message_id): Build heartbeat frame with lwp="/!"
- build_send_frame(...): Build message send frame with proper structure
"""

import base64
import json
from typing import Any, Optional
from loguru import logger


def build_heartbeat_frame(message_id: str) -> dict[str, Any]:
    """
    Build a WebSocket heartbeat frame.

    The heartbeat frame is the simplest frame type, containing only the
    lwp (lightweight protocol) path "/!" and a message ID header.

    Args:
        message_id: Generated message ID (typically from generate_mid())

    Returns:
        Dict[str, Any]: Heartbeat frame dictionary with structure:
            {
                "lwp": "/!",
                "headers": {
                    "mid": <message_id>
                }
            }

    Example:
        >>> from utils.xianyu_utils import generate_mid
        >>> mid = generate_mid()
        >>> frame = build_heartbeat_frame(mid)
        >>> print(frame["lwp"])  # "/!"
        >>> print(json.dumps(frame))  # Ready to send over WebSocket
    """
    frame = {"lwp": "/!", "headers": {"mid": message_id}}
    logger.debug(f"Built heartbeat frame with mid={message_id}")
    return frame


def build_send_frame(
    message_id: str,
    conversation_id: str,
    receiver_id: str,
    sender_id: str,
    text_content: str,
    item_id: str | None = None,
) -> dict[str, Any]:
    """
    Build a WebSocket message send frame.

    This frame is used to send text messages in a conversation. The message
    content is base64-encoded as per the Goofish protocol.

    Args:
        message_id: Generated message ID (from generate_mid())
        conversation_id: Conversation ID (typically in format "cid@goofish")
        receiver_id: Receiver user ID (typically in format "userid@goofish")
        sender_id: Sender user ID (typically in format "userid@goofish")
        text_content: Plain text message to send
        item_id: Optional item ID for context (default: None)

    Returns:
        Dict[str, Any]: Message send frame with structure:
            {
                "lwp": "/r/MessageSend/sendByReceiverScope",
                "headers": {"mid": <message_id>},
                "body": [
                    {
                        "uuid": <generated_uuid>,
                        "cid": <conversation_id>,
                        "conversationType": 1,
                        "content": {
                            "contentType": 101,
                            "custom": {
                                "type": 1,
                                "data": <base64_encoded_text>
                            }
                        },
                        "redPointPolicy": 0,
                        "extension": {"extJson": "{}"},
                        "ctx": {"appVersion": "1.0", "platform": "web"},
                        "mtags": {},
                        "msgReadStatusSetting": 1
                    },
                    {
                        "actualReceivers": [<receiver_id>, <sender_id>]
                    }
                ]
            }

    Example:
        >>> from utils.xianyu_utils import generate_mid, generate_uuid
        >>> mid = generate_mid()
        >>> frame = build_send_frame(
        ...     message_id=mid,
        ...     conversation_id="12345@goofish",
        ...     receiver_id="user123@goofish",
        ...     sender_id="myid@goofish",
        ...     text_content="Hello, this is a test message"
        ... )
        >>> print(frame["lwp"])  # "/r/MessageSend/sendByReceiverScope"
    """
    from utils.xianyu_utils import generate_uuid

    # Build the text content structure
    text_obj = {"contentType": 1, "text": {"text": text_content}}

    # Base64 encode the text object
    text_base64 = base64.b64encode(json.dumps(text_obj).encode("utf-8")).decode("utf-8")

    # Generate UUID for this message
    uuid = generate_uuid()

    # Build the message frame
    frame = {
        "lwp": "/r/MessageSend/sendByReceiverScope",
        "headers": {"mid": message_id},
        "body": [
            {
                "uuid": uuid,
                "cid": conversation_id,
                "conversationType": 1,
                "content": {
                    "contentType": 101,
                    "custom": {"type": 1, "data": text_base64},
                },
                "redPointPolicy": 0,
                "extension": {"extJson": "{}"},
                "ctx": {"appVersion": "1.0", "platform": "web"},
                "mtags": {},
                "msgReadStatusSetting": 1,
            },
            {"actualReceivers": [receiver_id, sender_id]},
        ],
    }

    logger.debug(
        f"Built send frame: mid={message_id}, cid={conversation_id}, "
        "receiver={receiver_id}, text_len={len(text_content)}"
    )

    return frame


def build_create_chat_frame(
    message_id: str,
    to_id: str,
    my_id: str,
    item_id: str = "891198795482",
) -> dict[str, Any]:
    """
    Build a WebSocket create chat frame.

    This frame is used to initiate a new conversation with a user.

    Args:
        message_id: Generated message ID (from generate_mid())
        to_id: Target user ID (without @goofish suffix)
        my_id: Current user ID (without @goofish suffix)
        item_id: Item ID for context (default: "891198795482")

    Returns:
        Dict[str, Any]: Create chat frame with structure:
            {
                "lwp": "/r/SingleChatConversation/create",
                "headers": {"mid": <message_id>},
                "body": [
                    {
                        "pairFirst": <to_id>@goofish,
                        "pairSecond": <my_id>@goofish,
                        "bizType": "1",
                        "extension": {"itemId": <item_id>},
                        "ctx": {"appVersion": "1.0", "platform": "web"}
                    }
                ]
            }
    """
    frame = {
        "lwp": "/r/SingleChatConversation/create",
        "headers": {"mid": message_id},
        "body": [
            {
                "pairFirst": f"{to_id}@goofish",
                "pairSecond": f"{my_id}@goofish",
                "bizType": "1",
                "extension": {"itemId": item_id},
                "ctx": {"appVersion": "1.0", "platform": "web"},
            }
        ],
    }

    logger.debug(
        f"Built create chat frame: mid={message_id}, to_id={to_id}, "
        "my_id={my_id}, item_id={item_id}"
    )

    return frame
