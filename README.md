# 闲鱼管理系统 v0.1.0

## 概述
单管理员 + 多闲鱼账号的自动化管理系统。支持自动回复、智能 AI 回复、自动发货、商品擦亮、自动确认发货。

## 架构说明
模块化架构，核心代码位于 `app/` 目录下：
- `app/protocol/` — 闲鱼协议层，WebSocket 和签名
- `app/db/` — 数据库层，SQLite，单管理员架构
- `app/bootstrap/` — 启动与配置
- `app/runtime/` — 运行时，多账号清单、WebSocket 客户端、消息管道
- `app/services/` — 业务服务，回复策略、AI 回复、发货、商品擦亮、自动确认
- `app/auth/` — 单管理员身份验证
- `app/api/` — FastAPI 路由层

## 功能特性
- 多闲鱼账号管理，单管理员下统一维护
- 自动回复，关键词、商品专属、默认回复
- AI 智能回复，OpenAI / Gemini / 兼容接口
- 自动发货，文字、批量数据、API 卡片、图片
- 商品擦亮 / 刷新
- 自动确认发货
- 二维码 / 密码登录
- Docker 部署

## 快速开始

### 本地运行
```bash
git clone https://github.com/Ethan0x0000/xianyu-manager.git
cd xianyu-manager
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
playwright install chromium

# 构建前端
cd frontend && npm install && npm run build && cd ..

# 设置必要的环境变量
set SECRET_KEY=your-secure-random-key
set SECRET_ENCRYPTION_KEY=your-encryption-key

python Start.py
# 访问 http://localhost:8848
```

### Docker 部署
```bash
# 编辑 docker-compose.yml 中的 SECRET_KEY 和 SECRET_ENCRYPTION_KEY
docker compose up -d --build
# 访问 http://localhost:8848
```

### 国内 Docker 部署
```bash
# 编辑 docker-compose-cn.yml 中的 SECRET_KEY 和 SECRET_ENCRYPTION_KEY
docker compose -f docker-compose-cn.yml up -d --build
# 访问 http://localhost:8848
```

## 环境变量
| 变量 | 说明 | 必填 |
|------|------|------|
| SECRET_KEY | 会话签名密钥 | 是 |
| SECRET_ENCRYPTION_KEY | 凭据加密密钥 | 是 |
| API_PORT | 端口，默认 8848 | 否 |
| DB_PATH | 数据库路径 | 否 |

## 重要说明
- 首次登录后请立即设置管理员密码
- `app/protocol/xianyu_js_version_2.js` 不可修改，签名逻辑依赖它
- 滑块验证功能内部实现不可修改
