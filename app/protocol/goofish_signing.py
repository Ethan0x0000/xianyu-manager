"""
Goofish Signing Protocol Wrapper

This module provides a thin wrapper around the Goofish signing logic.
It delegates to the existing utils/xianyu_utils.py implementation which uses
PyExecJS to call the frozen JavaScript signing code in static/xianyu_js_version_2.js.

The signing algorithm is frozen and must not be modified. All changes to signing
logic must be made in the JavaScript file only, and only if absolutely necessary.

Key Functions:
- load_signing_runtime(): Returns the compiled JavaScript runtime for signing operations
- generate_sign(t, token, data): Generates MD5-based signature for API requests
"""

import os
from typing import Any
from loguru import logger


def get_js_path() -> str:
    """
    Get the path to the frozen Goofish signing JavaScript file.

    Returns:
        str: Absolute path to static/xianyu_js_version_2.js
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(current_dir))
    js_path = os.path.join(root_dir, "static", "xianyu_js_version_2.js")
    return js_path


def load_signing_runtime() -> Any:
    """
    Load and compile the Goofish signing JavaScript runtime.

    This function initializes the PyExecJS runtime with the frozen JavaScript
    signing code. The JavaScript file is frozen and must not be modified.

    Returns:
        Any: Compiled JavaScript runtime object that can execute signing functions

    Raises:
        RuntimeError: If JavaScript runtime is not available or file cannot be loaded

    Example:
        >>> runtime = load_signing_runtime()
        >>> # Use runtime to call JavaScript functions
    """
    try:
        import execjs

        # Get current runtime
        current_runtime = execjs.get()
        logger.debug(f"Using JavaScript runtime: {current_runtime.name}")

        # Load and compile the frozen JavaScript file
        js_path = get_js_path()
        with open(js_path, "r", encoding="utf-8") as f:
            js_code = f.read()

        xianyu_js = execjs.compile(js_code)
        logger.info("Goofish signing JavaScript runtime loaded successfully")

        return xianyu_js

    except ImportError as e:
        error_msg = f"PyExecJS not available: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    except FileNotFoundError as e:
        error_msg = f"JavaScript file not found: {get_js_path()}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"JavaScript runtime error: {error_msg}")

        if "Could not find an available JavaScript runtime" in error_msg:
            logger.error("Solution:")
            logger.error("1. Install Node.js: apt-get install nodejs")
            logger.error("2. Or install other JS runtime: apt-get install nodejs npm")
            logger.error("3. Check PATH environment variable includes Node.js path")

        raise RuntimeError(f"Failed to load Goofish signing runtime: {error_msg}")


def generate_sign(t: str, token: str, data: str) -> str:
    """
    Generate MD5-based signature for Goofish API requests.

    This is a thin wrapper around the signing logic in utils/xianyu_utils.py.
    The algorithm is frozen and must not be modified.

    Args:
        t: Timestamp string
        token: Authentication token
        data: Request data to sign

    Returns:
        str: MD5 hexdigest signature

    Example:
        >>> sign = generate_sign("1234567890", "my_token", "request_data")
        >>> print(sign)  # e.g., "a1b2c3d4e5f6..."
    """
    import hashlib

    app_key = "34839810"
    msg = f"{token}&{t}&{app_key}&{data}"

    # Generate MD5 signature
    md5_hash = hashlib.md5()
    md5_hash.update(msg.encode("utf-8"))
    return md5_hash.hexdigest()
