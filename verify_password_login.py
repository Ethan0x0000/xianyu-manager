import json
import os
import sys
import time
from typing import Any, Dict, List, Tuple


def read_account_file(path: str) -> Tuple[str, str]:
    account = ""
    password = ""
    current = None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line == "[userName]":
                current = "account"
                continue
            if line == "[password]":
                current = "password"
                continue
            if current == "account" and not account:
                account = line
            elif current == "password" and not password:
                password = line
    if not account or not password:
        raise RuntimeError(f"failed to parse credentials from {path}")
    return account, password


def main() -> int:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

    from utils.xianyu_slider_stealth import XianyuSliderStealth

    account, password = read_account_file("account.txt")
    verify_user_id = os.environ.get("VERIFY_USER_ID", "verify_login_user")
    show_browser = os.environ.get("VERIFY_SHOW_BROWSER", "true").lower() == "true"
    attempt_mode = os.environ.get("VERIFY_ATTEMPT_MODE", "default").lower()
    if attempt_mode == "single-persistent":
        attempts: List[Dict[str, Any]] = [
            {"force_clean_context": False, "label": "persistent-context"}
        ]
    elif attempt_mode == "single-clean":
        attempts = [{"force_clean_context": True, "label": "clean-context"}]
    else:
        attempts = [
            {"force_clean_context": False, "label": "persistent-context"},
            {"force_clean_context": True, "label": "clean-context"},
            {"force_clean_context": False, "label": "persistent-context-retry"},
        ]

    print("=== password login verification start ===")
    print(f"account={account}")
    print(f"verify_user_id={verify_user_id}")
    print(f"show_browser={show_browser}")
    print(f"cwd={os.getcwd()}")
    print(f"display={os.environ.get('DISPLAY', '')}")

    results: List[Dict[str, Any]] = []
    for idx, attempt in enumerate(attempts, start=1):
        print("\n" + "=" * 80)
        print(f"attempt {idx}/{len(attempts)}: {attempt['label']}")
        print("=" * 80)
        started = time.time()
        slider = None
        try:
            slider = XianyuSliderStealth(
                user_id=verify_user_id,
                enable_learning=True,
                headless=not show_browser,
            )
            force_clean_context = bool(attempt["force_clean_context"])
            cookies = slider.login_with_password_playwright(
                account=account,
                password=password,
                show_browser=show_browser,
                force_clean_context=force_clean_context,
            )
            elapsed = round(time.time() - started, 2)
            cookie_dict: Dict[str, str] = dict(cookies or {})
            success = bool(cookie_dict)
            last_error = getattr(slider, "last_login_error", "")
            result = {
                "label": attempt["label"],
                "success": success,
                "elapsed_seconds": elapsed,
                "cookie_count": len(cookie_dict),
                "cookie_keys": sorted(list(cookie_dict.keys()))[:20],
                "last_login_error": last_error,
                "last_verification_feedback": getattr(
                    slider, "last_verification_feedback", {}
                ),
            }
            results.append(result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if success:
                print("SUCCESS: login returned cookies")
                with open(
                    "verify_password_login_result.json", "w", encoding="utf-8"
                ) as f:
                    json.dump(
                        {"results": results, "winner": result},
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
                return 0
        except Exception as e:
            elapsed = round(time.time() - started, 2)
            result = {
                "label": attempt["label"],
                "success": False,
                "elapsed_seconds": elapsed,
                "exception": repr(e),
            }
            results.append(result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            try:
                if slider:
                    slider.close_browser()
            except Exception as cleanup_error:
                print(f"cleanup warning: {cleanup_error}")

    with open("verify_password_login_result.json", "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False, indent=2)
    print("FAILED: all attempts failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
