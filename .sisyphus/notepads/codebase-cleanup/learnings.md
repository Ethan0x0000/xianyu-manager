# Learnings - Codebase Cleanup

## [2026-04-05] Initial Codebase Assessment

### Project Structure
- Root: E:\01-Project\xianyu-auto-reply-fix
- Python project, FastAPI + WebSocket + SQLite
- Main entry: Start.py
- Port: 8090 (local), 9000 (Docker)

### Key Files and Sizes
- XianyuAutoAsync.py: ~16,390 lines (MAIN god file - WebSocket + message handling)
- reply_server.py: ~9,500 lines (FastAPI routes god file)
- db_manager.py: ~7,900 lines (DB god file)
- cookie_manager.py: multi-account registry
- ai_reply_engine.py: AI reply logic
- utils/xianyu_utils.py: signing/cookie helpers
- static/xianyu_js_version_2.js: frozen JS signing (DO NOT TOUCH)

### Files to DELETE (confirmed)
- auto_updater.py
- generate_update_manifest.py
- secure_item_polish_ultra.py (replace with readable version)
- utils/notification_dispatcher.py
- static/register.html
- debug_im_surface.py
- verify_password_login.py

### Target Architecture
- app/api/routers/ - split FastAPI routers
- app/auth/ - single-admin auth
- app/bootstrap/ - settings.py + app_factory.py + runtime.py
- app/db/ - connection.py + schema.py + models.py + repositories/
- app/protocol/ - goofish_signing.py + websocket_protocol.py + token_refresh.py
- app/runtime/ - account_registry.py + ws_client.py + message_pipeline.py + dedupe.py + captcha_bridge.py
- app/services/ - reply_policy.py + ai_reply.py + shipping.py + auto_confirm.py + item_polish.py + login_service.py
- app/shared/ - types.py + utils.py

### Critical Guardrails
- DO NOT modify static/xianyu_js_version_2.js
- DO NOT change WS heartbeat format (lwp=/!)
- DO NOT change Goofish signing algorithm
- DO NOT redesign slider internals
- DO NOT introduce React/Vue/frontend frameworks
- DO NOT add multi-user tables back
- Keep: WebSocket, QR/password login, slider verification, Docker

## [2026-04-05] Task 1: Protocol Wrapper Modules

### Completed
- Created `app/__init__.py` - package root with docstring
- Created `app/protocol/__init__.py` - protocol module with exports
- Created `app/protocol/goofish_signing.py` - thin wrapper around PyExecJS signing
- Created `app/protocol/websocket_protocol.py` - thin wrapper around WS frame building

### Key Findings

#### Goofish Signing Pattern
- Uses PyExecJS to execute JavaScript in `static/xianyu_js_version_2.js`
- `load_signing_runtime()` returns compiled execjs.Context object
- `generate_sign(t, token, data)` uses MD5 with app_key="34839810"
- JavaScript runtime is frozen and must not be modified

#### WebSocket Protocol Pattern
- Heartbeat frame: `{"lwp": "/!", "headers": {"mid": <mid>}}`
- Message send frame: `{"lwp": "/r/MessageSend/sendByReceiverScope", "headers": {...}, "body": [...]}`
- All frames include message ID in headers
- Text content is base64-encoded in custom field
- Create chat frame: `{"lwp": "/r/SingleChatConversation/create", ...}`

#### Implementation Notes
- All public functions have type hints (dict[str, Any] for modern Python)
- Docstrings document protocol invariants and frozen constraints
- Thin wrappers delegate to existing utils/xianyu_utils.py logic
- No exec() or runtime evaluation in wrapper code itself
- Logging at DEBUG level for frame building, INFO for runtime loading

### Verification
- ✓ Heartbeat frame returns `{"lwp": "/!"}`
- ✓ Signing runtime loads successfully (Node.js detected)
- ✓ Static JS file hash verified (not modified)
- ✓ All imports resolve correctly
- ✓ Type hints present on all public functions

### Blockers Resolved
- None - task completed cleanly

### Next Steps
- Task 1 complete, ready for Tasks 8, 9, 12, 16 which depend on these wrappers

## [2026-04-05] Task 4: Fresh DB Foundation

### Completed
- Replaced the partial `app/db/` prototype with a clean raw-sqlite foundation aligned to the single-admin rewrite.
- Added `app/db/__init__.py`, a minimal WAL-enabled `get_db()` context manager, exact schema creation in `schema.py`, entity dataclasses in `models.py`, and repository stubs under `app/db/repositories/`.

### Key Findings
- The legacy DB domain maps cleanly from `cookies -> xianyu_accounts`, `ai_reply_settings -> ai_settings`, `ai_conversations -> conversations`, `cards -> delivery_cards`, `item_info -> items`, `item_replay -> item_replies`, `risk_control_logs -> risk_logs`, and `scheduled_tasks -> polish_schedule`.
- Task 4 must stay intentionally smaller than `db_manager.py`: only the 16 approved tables are created, and legacy multi-user / notification / updater tables are excluded entirely.
- `reply_server.py` still references legacy names (`users`, `cards`, `item_replay`, notification tables), so later cleanup tasks must adapt API/runtime code onto the fresh `app/db` repositories instead of trying to preserve old table names.

### Verification
- `python -c "from app.db.schema import initialize_database; initialize_database('data/test_plan.db')"` succeeded.
- Verified the generated test DB contains exactly the approved tables and no `users`, `notification_channels`, `message_notifications`, or `auto_update_manifest` tables.
- Saved evidence to `.sisyphus/evidence/task-4-schema-tables.txt` and `.sisyphus/evidence/task-4-schema-legacy.txt`.


## [2026-04-05] Task 5: Centralized Settings Module

### Completed
- Created app/bootstrap/__init__.py - package root with exports
- Created app/bootstrap/settings.py - Settings dataclass + load_settings() + validate_settings()

### Key Findings

#### Settings Architecture
- Single Settings dataclass with all config fields (no scattered globals)
- load_settings() reads YAML + env vars (env vars take precedence)
- validate_settings() enforces required secrets at startup
- No hardcoded defaults for security-sensitive values (SECRET_KEY, SECRET_ENCRYPTION_KEY)

#### Config Precedence
1. Environment variables (highest priority)
2. YAML config file (global_config.yml)
3. Dataclass defaults (only for optional/safe values)

#### Removed Insecure Patterns
- ADMIN_USERNAME = "admin" (hardcoded in reply_server.py:75)
- DEFAULT_ADMIN_PASSWORD = "admin123" (hardcoded in reply_server.py:76)
- JWT_SECRET_KEY with weak default in docker-compose.yml:47
- Replaced with explicit env var requirements

#### Settings Fields
- Server: api_host, api_port
- Database: db_path
- Admin: admin_username, admin_password_hash (no plaintext)
- Secrets: secret_key (REQUIRED), secret_encryption_key (REQUIRED)
- Features: ai_enabled, auto_reply_enabled, auto_shipping_enabled, auto_confirm_enabled
- Docker: enable_headful, use_xvfb, enable_vnc
- Logging: sql_log_enabled, sql_log_level
- Protocol: websocket_url

### Verification
- ENV override test: API_PORT=9001 correctly overrides YAML default (8090)
- Missing secret test: validate_settings() raises ValueError with clear message
- No hardcoded defaults bypass validation
- Both SECRET_KEY and SECRET_ENCRYPTION_KEY enforced
- Startup will fail explicitly if secrets not provided

### Blockers Resolved
- None - task completed cleanly

### Next Steps
- Task 5 complete, ready for Tasks 9, 11, 19, 21, 22 which depend on centralized settings

## [2026-04-05] Task 6: Runtime Interfaces and Composition Root

### Completed
- Created `app/shared/` with explicit runtime protocols, typed payloads, stable service keys, and a shared `StubBinding` placeholder type.
- Added new package roots `app/runtime/`, `app/services/`, `app/auth/`, and `app/api/` that expose placeholder bindings only and do not import legacy runtime modules.
- Added `app/bootstrap/app_factory.py` and `app/bootstrap/runtime.py` as the new side-effect-free composition root and runtime supervisor stub.

### Key Findings

#### Circular Import Shape
- `cookie_manager.py` breaks the cycle only with late imports today: `_run_xianyu()` imports `XianyuLive`, while `XianyuAutoAsync.py` imports `cookie_manager.manager` in several runtime paths (restart, token-refresh, enable checks).
- `Start.py` is the current composition root: it creates `cm.manager = cm.CookieManager(loop)`, seeds `manager.tasks`, then launches `reply_server` in a background thread.
- `reply_server.py` still imports `cookie_manager` directly at module import time, so new package roots must stay completely isolated from legacy globals until later extraction tasks rewire them.

#### Extraction Boundary Pattern
- Package-root placeholder exports are enough to create import-safe injection boundaries before real implementations exist.
- A simple dict container plus stable string keys is sufficient for this stage; no DI framework is needed.
- Keeping `build_container(test_mode=True)` on stub-only imports makes circular-import verification cheap and deterministic.

### Verification
- `python -m compileall app/shared app/runtime app/services app/auth app/api app/bootstrap && python -c "from app.bootstrap.app_factory import build_container; c=build_container(test_mode=True); print(sorted(c.keys()))"` succeeded.
- `python -c "from app.runtime import account_registry; from app.runtime import ws_client; from app.bootstrap.app_factory import build_container; print(account_registry.key, ws_client.key, callable(build_container))"` succeeded.
- Saved evidence to `.sisyphus/evidence/task-6-container.txt` and `.sisyphus/evidence/task-6-imports.txt`.

## [2026-04-05] Task 2: Frontend JS Cleanup

### Completed
- Removed all hotUpdate references from static/js/app.js (130 matches)
- Removed all hot_update storage key references (8 matches)
- Removed all update_files.json changelog entries (4 matches)
- Removed hotUpdateBtn from modal footer
- Removed entire hotUpdate functionality section (lines 17413-17867)
- Removed orphaned dashboard element references
- Committed all changes: refactor(core): remove self-update system

### Key Findings
1. The hotUpdate system was deeply integrated into the frontend:
   - Storage keys for auto-check and ignored versions
   - Multiple UI elements (buttons, modals, progress dialogs)
   - Preference management functions
   - Changelog entries documenting the feature

2. Removal strategy:
   - First removed core hotUpdate functions and storage keys
   - Then removed UI button references in modals
   - Removed entire hotUpdate section with all dialogs and handlers
   - Cleaned up orphaned code and changelog entries
   - Removed dashboard element references that no longer exist

3. Final verification: Zero matches for all updater-related patterns
   - update_files.json: 0 matches
   - hotUpdate: 0 matches
   - hot_update: 0 matches
   - auto_updater: 0 matches
   - AutoUpdater: 0 matches

### Files Modified
- static/js/app.js: Removed ~2600 lines of hotUpdate code
- Deleted Python files already removed in previous task:
  - auto_updater.py
  - generate_update_manifest.py
  - release_precheck.py

### Commit
- Hash: 33753a7
- Message: refactor(core): remove self-update system
- Changes: 5 files changed, 4 insertions(+), 2603 deletions(-)

## [2026-04-05] Task 7: Multi-Account Runtime Registry

### Completed
- Created `app/runtime/account_registry.py` as a clean in-memory registry for extracted multi-account runtime state.
- Added explicit `AccountEntry`, `DuplicateAccountError`, `AccountNotFoundError`, `AccountRegistry`, and `get_registry()` singleton accessor.

### Key Findings
- The legacy `CookieManager` mixes persistence/runtime orchestration, but its registry-shaped state is narrow: `tasks`, `cookie_status`, and `live_instances` map cleanly onto per-account `background_task`, `enabled`, and `runtime_instance` fields.
- This extraction should stay synchronous and lock-based: a plain `threading.Lock` is sufficient for shared in-memory state accessed from FastAPI threads plus asyncio-owned runtime code.
- The registry boundary must remain runtime-only; importing `cookie_manager.py` or `XianyuAutoAsync.py` would immediately reintroduce the circular legacy dependency chain that Task 6 isolated.

### Verification
- `python -c "from app.runtime.account_registry import AccountRegistry, DuplicateAccountError; ..."` saved `count: 2` and both account IDs to `.sisyphus/evidence/task-7-multi-account.txt`.
- Duplicate registration verification saved `OK: duplicate rejected: Account 'acct-a' already exists. Remove it first to re-add.` to `.sisyphus/evidence/task-7-duplicate.txt`.
- `python -m compileall app/runtime/account_registry.py` succeeded.
- `lsp_diagnostics app/runtime/account_registry.py` reported no diagnostics.

## [2026-04-05] Task 3: Suspicious Integrations Cleanup

### Completed
- Deleted `utils/notification_dispatcher.py` and replaced direct imports with local safe fallbacks in legacy runtime modules.
- Removed hardcoded suspicious endpoint references from `XianyuAutoAsync.py`, `config.py`, `global_config.yml`, `db_manager.py`, `static/js/app.js`, and `static/index.html`.
- Disabled legacy external auto-comment, QQ relay, benefits fetch, and fallback email API paths instead of leaving outbound calls behind.

### Key Findings
- `XianyuAutoAsync.py` had two separate hardcoded YiFan order-create call sites; both must be scrubbed or one will survive verification.
- Deleting `utils/notification_dispatcher.py` requires follow-up edits in `reply_server.py` and `utils/slider_patch.py` to avoid import-time crashes.
- Verification scans must exclude `.sisyphus/`, `logs/`, `realtime.log`, and `__pycache__/` or stale artifacts will produce false positives.

### Verification
- `python -m py_compile XianyuAutoAsync.py reply_server.py db_manager.py config.py utils/slider_patch.py` succeeded.
- `node --check static/js/app.js` succeeded after fixing legacy brace mismatches around auth/settings blocks.
- Saved evidence to `.sisyphus/evidence/task-3-endpoints-scan.txt` with `NO_MATCHES` for all requested targets.

## [2026-04-05] Task 11: Single-Admin Session Auth Model

### Completed
- Created `app/auth/service.py` with `verify_admin_login()` and `create_session_token()`
- Created `app/auth/sessions.py` with `SessionStore` class and `get_session_store()` singleton
- Updated `app/auth/__init__.py` to export all new auth symbols
- Created evidence files for import and session flow verification

### Key Findings

#### Service Module (service.py)
- `verify_admin_login(username, password, settings)` checks credentials against settings
- Uses `secrets.compare_digest()` for constant-time comparison (prevents timing attacks)
- Password verification is a stub that always returns False until proper hashing is configured
- No registration, email verification, or multi-user logic present
- `create_session_token(secret_key)` generates opaque 64-char hex tokens using `secrets.token_hex(32)`

#### Sessions Module (sessions.py)
- `SessionEntry` dataclass with token, created_at, expires_at fields
- `SessionStore` class with in-memory dict-based storage
- Thread-safe using `threading.Lock` for all operations
- Methods: `create_session()`, `validate_session()`, `revoke_session()`, `cleanup_expired()`, `get_session()`
- Sessions expire after configurable TTL (default: 86400 seconds = 24 hours)
- Expired sessions are cleaned up on access (lazy cleanup)
- Global singleton `get_session_store()` for app-wide access

#### Design Decisions
- Opaque tokens: No user info embedded, purely random hex strings
- In-memory storage: Suitable for single-admin model with short-lived sessions
- No database persistence: Sessions are ephemeral and lost on app restart
- Thread-safe: Uses simple lock-based synchronization (no async/await)
- No JWT: Avoids complexity of token signing/verification

### Verification
- ✓ Import test: `from app.auth.service import verify_admin_login; from app.auth.sessions import SessionStore` succeeds
- ✓ Session flow: Create → Validate (True) → Revoke → Validate (False) works correctly
- ✓ Token generation: 64-char hex strings with 32 bytes of entropy
- ✓ Expiration: Sessions correctly expire after TTL
- ✓ Thread-safety: Lock-based synchronization in place
- ✓ No multi-user code: Zero registration/email-verification/multi-user logic
- ✓ Type hints: All public functions have full type annotations
- ✓ Docstrings: All functions and classes documented
- ✓ Diagnostics: Only 2 acceptable warnings (reserved parameter, unused call result)

### Blockers Resolved
- None - task completed cleanly

### Next Steps
- Task 11 complete, ready for T19 (reply_server.py integration) which depends on auth service

## [2026-04-06] Task 12: Slider/Captcha Runtime Adapter

### Key Findings
- The main frozen slider entrypoint used by `XianyuAutoAsync.py` is `utils.xianyu_slider_stealth.XianyuSliderStealth`, instantiated with `user_id`, `enable_learning`, and `headless`, then awaited via `async_run(verification_url)`.
- The remote captcha control surface is already centralized as the singleton `utils.captcha_remote_control.captcha_controller`, which exposes `create_session()`, `handle_mouse_event()`, `check_completion()`, `close_session()`, `session_exists()`, and `is_completed()`.
- The runtime patch surface that still matters is `utils.slider_patch._handle_slider_verification(...)`; the bridge should keep slider internals frozen and only normalize lazy imports plus delegation entrypoints.

## [2026-04-06] Task 8: WebSocket Transport Core

### Completed
- Created `app/runtime/ws_client.py` with `ConnectionState`, `WebSocketConfigError`, and `WebSocketClient`.
- Preserved frozen transport invariants for URL (`wss://wss-goofish.dingtalk.com/`), heartbeat cadence (15s), heartbeat `lwp` (`/!`), and reconnect max delay (32s).
- Kept the extraction transport-only: no reply policy, shipping logic, `cookie_manager.py`, or `XianyuAutoAsync.py` imports.

### Key Findings
- The monolith's transport boundary is narrower than the surrounding runtime: the reusable core is connection state, heartbeat task lifecycle, frame building, and reconnect bookkeeping; account-enable checks and business orchestration stay outside this module.
- `app/protocol/websocket_protocol.py` is the right frozen boundary for payload construction; `WebSocketClient.build_heartbeat()` now delegates to `build_heartbeat_frame()` so the `lwp="/!"` contract stays centralized.
- Avoid importing `utils.xianyu_utils` for heartbeat IDs inside the extracted runtime client: that utility compiles the signing JS at import time, which is unnecessary coupling for a transport stub.
- Constructor-time config validation should guard both missing cookies and an empty `WS_URL` so misconfiguration fails before any connection attempt.

### Verification
- `python -c "from app.runtime.ws_client import WebSocketClient; client = WebSocketClient('acct-1', 'cookie=value'); print(WebSocketClient.__name__); print(client.build_heartbeat('mid-1')['lwp'])"` succeeded and printed `/!`.
- Invalid config checks for missing cookie and empty `WS_URL` raised `WebSocketConfigError` before connect.
- Evidence saved to `.sisyphus/evidence/task-8-ws-import.txt` and `.sisyphus/evidence/task-8-ws-invalid.txt`.

## [2026-04-06] Task 9: Token Refresh Service Extraction

### Key Findings
- The legacy refresh boundary lives across `refresh_token`, `_refresh_token_impl`, and `_handle_captcha_verification` in `XianyuAutoAsync.py`; the reusable extraction target is validation, protected-cookie preservation, token parsing, and adapter-based captcha routing.
- Protected session preservation is the core invariant for the extraction: `_m_h5_tk`, `_m_h5_tk_enc`, `cookie2`, `t`, plus account identity/session fields `uc1` and `unb` should survive partial cookie snapshots.
- `utils/xianyu_utils.py` already provides legacy cookie parsing/signing helpers, so the extracted service can stay intentionally small and avoid premature HTTP refresh wiring.
- Captcha-triggered recovery must delegate through `app.runtime.captcha_bridge.SliderAdapter` instead of touching frozen slider internals directly.

### Verification
- Evidence saved to `.sisyphus/evidence/task-9-cookie-merge.txt` and `.sisyphus/evidence/task-9-refresh-invalid.txt`.
- `app/runtime/token_refresh.py` is clean under LSP diagnostics.

## [2026-04-06] Task 10: Message Pipeline + Dedupe Extraction

### Key Findings
- The extracted runtime pipeline should preserve two separate monolith concerns without importing the monolith itself: route classification + order-context discovery from `_classify_message_route` / `_extract_order_id`, and queue orchestration shape from `_get_message_priority` / `_enqueue_message` / `_message_worker`.
- Order ID extraction logic is already mirrored in `order_status_handler.py`; reusing its candidate-text walk + `updateKey` parsing patterns keeps downstream order-state consumers aligned with the legacy message formats.
- Queue orchestration can stay generic at this stage: `MessagePipeline` only parses, prioritizes, deduplicates, and dispatches via injected async handlers, leaving reply/shipping business policy outside `app/runtime/`.
- Malformed payload safety needs to treat bad `body` values as non-fatal input, not exceptions; parsing should degrade to normalized `ParsedMessage` output or `INVALID` instead of crashing the runtime loop.

### Verification
- `app/runtime/dedupe.py` and `app/runtime/message_pipeline.py` are clean under LSP diagnostics.
- `python -m compileall app/runtime/dedupe.py app/runtime/message_pipeline.py` succeeded.
- Evidence saved to `.sisyphus/evidence/task-10-dedupe.txt` and `.sisyphus/evidence/task-10-invalid-message.txt`.

## [2026-04-06] Task 13: Local Reply Policy Service

### Completed
- Created `app/services/reply_policy.py` with `ReplyPolicyService` class and `ReplyResult` dataclass
- Implemented frozen priority order: item_reply > item_keyword > keyword > default > None (AI fallback)
- Created comprehensive verification tests in `verify_reply_policy.py`
- Generated evidence files for priority and fallback behavior

### Key Findings

#### Priority Order (FROZEN)
1. **Item-specific reply** (highest): Direct reply for exact item_id, no pattern matching
2. **Item-specific keyword**: Keywords tied to item_id, supports regex and literal patterns
3. **General keyword**: Global keywords, supports regex and literal patterns
4. **Default reply**: Fallback when nothing matches
5. **None** (lowest): Signals AI provider should be used

#### ReplyResult Dataclass
- `reply_text`: The actual reply content
- `source`: Identifies which level matched ("item_reply", "item_keyword", "keyword", "default")
- `matched_pattern`: The pattern that matched (empty for item_reply and default)

#### Pattern Matching Strategy
- Literal matching: Case-insensitive substring search (`pattern.lower() in text.lower()`)
- Regex matching: Uses `re.search()` for full regex support
- Exception handling: Returns False on regex errors (invalid patterns don't crash)

#### Database Schema Integration
- `item_replies`: Direct reply for specific item_id (no pattern)
- `item_keywords`: Keywords tied to item_id (pattern + reply)
- `keywords`: Global keywords (pattern + reply)
- `default_replies`: Fallback reply
- All tables have `enabled` column for soft deletion

#### Design Decisions
- Returns None (not empty string) for AI fallback to signal caller clearly
- Uses context manager `get_db()` for thread-safe SQLite access
- Encapsulates pattern matching in `_matches()` helper for reusability
- No AI provider imports or calls (stays local-only)
- Frozen priority order documented in docstring and comments

### Verification
- ✓ Test 1: Item-specific reply wins over keyword reply
- ✓ Test 2: Empty DB returns None for AI fallback
- ✓ Test 3: Full priority order verified (all 5 levels tested)
- ✓ Evidence files: task-13-priority.txt and task-13-fallback.txt
- ✓ Committed: refactor(reply): extract local reply policy service

### Code Quality
- Removed unused imports (Any type)
- All public methods have docstrings
- Type hints on all public functions
- Exception handling in pattern matching
- No LSP errors (only acceptable warnings about sqlite3.Row returning Any)

### Blockers Resolved
- None - task completed cleanly

### Next Steps
- Task 13 complete, ready for T14 (AI reply service) which depends on this fallback behavior

## [2026-04-06] Task 14: AI Reply Provider Service

### Key Findings
- `ai_reply_engine.py` currently bundles provider resolution, network calls, prompt assembly, debounce, and persistence; the extracted service should keep only retained provider selection plus conversation storage access.
- Task 14 intentionally narrows the supported provider set to `openai`, `openai_compatible`, `gemini`, and `disabled`; all other legacy monolith branches should now fail explicitly via `UnsupportedProviderError`.
- The fresh `conversations` table already matches the extracted context API (`session_key`, `role`, `content`), so `AIReplyService` can stay side-effect-light and depend only on `app.db.connection.get_db()`.
- On Windows, sqlite verification should use `TemporaryDirectory` + an explicit DB file path instead of `NamedTemporaryFile`, which can keep the database path locked and break `sqlite3.connect()`.

## [2026-04-06] Task 15: Shipping Service Extraction

### Key Findings
- Legacy auto-delivery handling in `XianyuAutoAsync.py` still uses `card_type` values `text`, `data`, `api`, and `image`; the extracted service should keep only the retained local variants and leave removed vendor/comment paths out entirely.
- Fresh-schema `delivery_cards.content_type` still stores legacy names (`text`, `data`, `api`, `image`), so `ShippingService` should normalize `data -> batch_data` and `api -> api_card` at the service boundary instead of leaking legacy names upward.
- The clean extraction can stay local-only for now: resolve the highest-priority enabled rule by `item_id + account_id`, return a `DeliveryAction`, and leave actual send-side wiring for the later bootstrap task.

### Verification
- Happy-path resolution against a temp DB created via `initialize_database()` succeeded; evidence saved to `.sisyphus/evidence/task-15-shipping-happy.txt`.
- Banned-endpoint scan across `app/services/*.py` returned zero matches; evidence saved to `.sisyphus/evidence/task-15-shipping-scan.txt`.

## [2026-04-06] Task 16: Item Polish Service Extraction

### Key Findings
- The obfuscated polish loader only wrapped a normal async Python module: it signs `{"itemId": "..."}` with `_m_h5_tk`, posts to the primary Goofish H5 endpoint `mtop.taobao.idle.item.polish`, and keeps `mtop.idle.item.polish` as a backup path.
- The retained query contract is frozen and should stay explicit in the extracted service: `jsv=2.7.2`, `appKey=34839810`, `type=originaljson`, `accountSite=xianyu`, `dataType=json`, `timeout=20000`, `sessionOption=AutoLoginOnly`, plus the observed `spm_cnt` / `spm_pre` values.
- `XianyuAutoAsync.py` still instantiates the old module shape (`ItemPolishModule(self)`), so the new `app/services/item_polish.py` should remain import-safe and bootstrap-oriented for now rather than trying to wire runtime/session behavior early.
- Avoid importing `utils.xianyu_utils` directly in the new service: that module eagerly compiles the frozen JS runtime at import time. For the extraction boundary, prefer plain cookie parsing plus the thin `app.protocol.goofish_signing.generate_sign()` wrapper.

### Verification
- `python -c "from app.services.item_polish import ItemPolishService; print(ItemPolishService.__name__)"` succeeded after extraction.
- Service scan confirmed zero `exec(` and zero `secure_item_polish_ultra` references in `app/services/item_polish.py`; evidence saved to `.sisyphus/evidence/task-16-polish-import.txt` and `.sisyphus/evidence/task-16-polish-scan.txt`.

## [2026-04-06] Task 18: Login Service Extraction

### Key Findings
- Keep the boundary explicit: `app/services/login_service.py` owns Xianyu seller-account login only, while `app/auth/` remains the separate admin-panel auth domain.
- The extracted QR flow should be bootstrap-safe for now: create in-memory `QRLoginSession` metadata with a generated `session_id`, derived QR URL, expiry window, and status, while leaving live QR polling/network orchestration to later tasks.
- Password-login orchestration should fail fast on empty `account_id`, `username`, or `password` before any browser/network work; this preserves the later runtime handoff boundary and matches the cleanup goal of making validation deterministic.
- Existing monolith code still carries richer QR/password recovery and captcha behavior in `XianyuAutoAsync.py`, so the extracted service should stay intentionally smaller and delegate future slider handling through `app.runtime.captcha_bridge.SliderAdapter` instead of importing frozen internals directly.

### Verification
- QR-session bootstrap evidence saved to `.sisyphus/evidence/task-18-qr-bootstrap.txt`.
- Invalid password-login validation evidence saved to `.sisyphus/evidence/task-18-password-invalid.txt`.
