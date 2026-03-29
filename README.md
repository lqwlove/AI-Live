# TK-Live — 直播 AI 语音助手

实时监听直播间弹幕，通过 AI 自动生成回复并语音播报，支持将回复发送到直播间聊天。

**支持平台：抖音 / TikTok / YouTube**

## 功能特性

- **多平台弹幕抓取** — 抖音（WebSocket + Protobuf）、TikTok（tiktoklive）、YouTube（Data API v3）
- **智能消息过滤** — 关键词匹配、长度过滤、冷却时间，精准识别需要回复的弹幕
- **AI 回复生成** — 支持 OpenAI / DeepSeek / 豆包 / 通义千问等任意 OpenAI 兼容 API
- **TTS 语音合成** — 支持 Edge TTS（免费）和火山引擎（高质量声音克隆）
- **音频播放** — macOS 原生 `afplay` 或 pygame 播放
- **YouTube 自动回复** — 将 AI 回复自动发送到 YouTube 直播聊天
- **多语言支持** — 自动检测弹幕语言，中英文分别处理
- **Web 控制台** — 基于 React 的可视化管理界面，实时查看弹幕和 AI 回复状态
- **WebSocket 事件推送** — 前端实时接收弹幕、AI 回复、TTS 合成等全流程事件

## 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                    Web 控制台 (React)                      │
│          Dashboard / Settings / WebSocket 实时推送         │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP + WebSocket
┌──────────────────────▼───────────────────────────────────┐
│                   FastAPI 后端                             │
│  /api/config  /api/session/start|stop  /ws               │
├──────────────────────┬───────────────────────────────────┤
│              LiveEngine (核心引擎)                         │
│  EventBus ←→ SessionManager ←→ TaskQueue                 │
├──────┬──────────┬───────────┬──────────┬─────────────────┤
│弹幕客户端│  AI 回复  │  TTS 合成  │ 音频播放  │ 消息过滤       │
│ Douyin │ OpenAI   │ Edge-TTS  │ afplay  │ 关键词+冷却     │
│ TikTok │ DeepSeek │ 火山引擎   │ pygame  │                │
│YouTube │ ...      │           │         │                │
└──────┴──────────┴───────────┴──────────┴─────────────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12+, FastAPI, uvicorn, asyncio |
| 弹幕协议 | websocket-client, grpcio, protobuf, betterproto |
| TikTok | tiktoklive |
| YouTube | google-api-python-client, google-auth-oauthlib |
| AI | openai SDK（兼容任意 OpenAI 格式 API） |
| TTS | edge-tts / 火山引擎 |
| 音频 | pygame, macOS afplay |
| 前端 | React 19, TypeScript, Vite 8, Tailwind CSS 4, Zustand |
| 实时通信 | WebSocket (FastAPI ↔ React) |

## 项目结构

```
tk-live/
├── main.py                     # CLI 入口（LiveAssistant）
├── server.py                   # Web 服务入口（FastAPI + uvicorn）
├── config.py                   # 配置管理（加载、合并、脱敏、校验）
├── config.yaml                 # 配置文件
├── pyproject.toml              # Python 项目定义和依赖
├── .python-version             # Python 版本锁定 (3.12)
│
├── api/                        # FastAPI 接口层
│   ├── app.py                  # 应用工厂、中间件、静态资源挂载
│   ├── ws.py                   # WebSocket 事件推送
│   └── routes/
│       ├── health.py           # GET /api/health
│       ├── config_routes.py    # GET/PUT /api/config
│       └── session.py          # POST /api/session/start|stop
│
├── core/                       # 核心业务逻辑
│   ├── engine.py               # LiveEngine — 弹幕→AI→TTS→播放 主流程
│   ├── events.py               # EventBus 事件总线
│   └── session.py              # SessionManager 会话生命周期管理
│
├── danmaku/                    # 弹幕客户端
│   ├── client.py               # 抖音 WebSocket 客户端 + MockClient
│   ├── tiktok_client.py        # TikTok 弹幕客户端
│   └── youtube_client.py       # YouTube 直播聊天客户端
│
├── ai/
│   └── replier.py              # AI 回复生成（OpenAI 兼容 API）
│
├── tts/
│   ├── speaker.py              # Edge TTS 语音合成
│   └── volcengine_speaker.py   # 火山引擎 TTS（声音克隆）
│
├── utils/
│   ├── audio_player.py         # 音频播放器（afplay / pygame）
│   └── message_queue.py        # 消息过滤器 + 任务队列
│
├── proto/                      # Protobuf 协议定义
│   ├── douyin.proto            # 抖音消息协议
│   └── compile_proto.sh        # protoc 编译脚本
│
├── web/                        # 前端工程
│   ├── src/
│   │   ├── pages/              # DashboardPage, SettingsPage
│   │   ├── components/         # layout, dashboard, settings, ui
│   │   └── ...
│   ├── package.json
│   ├── vite.config.ts
│   └── dist/                   # 构建产物（被 FastAPI 挂载）
│
├── audio_cache/                # TTS 语音缓存目录
├── scripts/
│   └── train_voice.py          # 声音训练脚本
└── design/                     # 设计稿
```

## 部署指南

### 环境要求

- **Python** >= 3.12
- **Node.js** >= 18（前端构建需要）
- **macOS**（音频播放默认使用 `afplay`；Linux 可通过 pygame 播放）
- **protoc**（如需重新编译抖音 Protobuf 协议，可选）

### 一、安装后端依赖

推荐使用 [uv](https://docs.astral.sh/uv/) 进行包管理（更快），也可用 pip。

**方式 A：使用 uv（推荐）**

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆项目
git clone <repo-url> tk-live
cd tk-live

# 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate
uv pip install -e .
```

**方式 B：使用 pip**

```bash
cd tk-live

# 创建虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e .
```

### 二、安装前端依赖并构建

```bash
cd web

# 安装依赖
npm install

# 构建生产版本（输出到 web/dist/）
npm run build

cd ..
```

构建完成后，`web/dist/` 目录会被 FastAPI 自动挂载为静态资源，无需额外配置 Nginx。

### 三、生成并编辑配置文件

```bash
# 生成默认配置模板
python main.py --init-config
```

编辑 `config.yaml`，至少需要配置以下内容：

```yaml
# AI 配置（必填）
ai:
  api_key: "你的API密钥"
  base_url: "https://api.deepseek.com"    # 或任意 OpenAI 兼容地址
  model: "deepseek-chat"                  # 使用的模型名称
  system_prompt: "你是一个直播间的AI助手..."
  max_history: 10                         # 对话历史轮数
  multilang: false                        # 多语言支持

# TTS 配置
tts:
  engine: "edge-tts"                      # edge-tts（免费）或 volcengine
  voice: "zh-CN-XiaoxiaoNeural"           # 语音角色
  rate: "+0%"                             # 语速调节
  volume: "+0%"                           # 音量调节
  output_dir: "audio_cache"               # 语音缓存目录

# 弹幕过滤
filter:
  keywords: ["怎么", "什么", "吗", "?", "？", "how", "what", "why"]
  min_length: 2                           # 最短消息长度
  max_length: 200                         # 最长消息长度
  cooldown_seconds: 3                     # 同用户冷却时间（秒）
```

### 四、平台配置

根据你使用的直播平台，在 `config.yaml` 中配置对应段落：

#### 抖音

```yaml
douyin:
  live_url: "https://live.douyin.com/你的直播间ID"
  # 或
  room_id: "直播间ID"
  cookie: "你的抖音cookie"    # 从浏览器获取
```

#### TikTok

```yaml
tiktok:
  unique_id: "username"       # TikTok 用户名（不带 @）
  proxy: ""                   # 代理地址（可选，国内需要）
```

#### YouTube

YouTube 需要额外的 OAuth2 配置，步骤如下：

1. 访问 [Google Cloud Console](https://console.cloud.google.com/) 创建项目
2. 启用 **YouTube Data API v3**
3. 创建 **OAuth 客户端 ID**（类型选「桌面应用」）
4. 下载 JSON 凭证，重命名为 `client_secret.json` 放在项目根目录
5. 配置 `config.yaml`：

```yaml
youtube:
  video_id: "视频ID"                        # 从直播链接 ?v= 后获取
  # 或
  channel_id: "频道ID"                      # 自动查找频道当前直播
  api_key: "你的YouTube API Key"            # Google Cloud 获取
  client_secrets_file: "client_secret.json" # OAuth 凭证文件路径
  auto_reply: true                          # 是否自动回复到聊天
  reply_prefix: ""                          # 回复前缀
```

首次运行时会自动打开浏览器进行 Google 账号授权，token 保存在 `youtube_token.json`，后续无需重复。

### 五、火山引擎 TTS 配置（可选）

如需使用火山引擎的声音克隆 TTS（更高质量），需额外配置：

```yaml
tts:
  engine: "volcengine"

volcengine:
  api_key: "你的火山引擎API Key"
  app_id: "应用ID"
  access_token: "访问令牌"
  speaker_id: "音色ID"
  resource_id: "seed-icl-2.0"
```

### 六、Protobuf 编译（可选）

如果需要重新编译抖音弹幕协议（一般不需要）：

```bash
cd proto
bash compile_proto.sh
cd ..
```

## 运行方式

### 方式一：CLI 模式

适合快速测试或不需要 Web 界面的场景。

```bash
# 模拟模式 — 使用模拟弹幕测试完整流程
python main.py --mock

# 抖音直播间
python main.py --url https://live.douyin.com/你的直播间ID
python main.py --room 123456789

# TikTok 直播间
python main.py --platform tiktok --user username

# YouTube 直播间
python main.py --platform youtube --video VIDEO_ID
python main.py --platform youtube --channel CHANNEL_ID

# 指定配置文件
python main.py --config /path/to/config.yaml --mock
```

安装后也可以使用命令行工具：

```bash
tk-live --mock
tk-live --platform youtube --video VIDEO_ID
```

### 方式二：Web 服务模式

提供 Web 管理界面，可通过浏览器控制会话、修改配置、实时查看弹幕和 AI 回复。

```bash
# 启动 Web 服务（默认监听 0.0.0.0:8000）
python server.py

# 或使用命令行工具
tk-live-web
```

启动后访问 `http://localhost:8000` 即可打开 Web 控制台。

**前端开发模式**（带热更新）：

```bash
# 终端 1：启动后端
python server.py

# 终端 2：启动前端开发服务器
cd web
npm run dev
```

前端开发服务器会自动将 `/api` 和 `/ws` 请求代理到 `http://localhost:8000`。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/config` | 获取配置（敏感字段脱敏） |
| PUT | `/api/config` | 更新配置并持久化 |
| POST | `/api/config/validate` | 校验指定平台配置是否完整 |
| POST | `/api/session/start` | 启动直播助手会话 |
| POST | `/api/session/stop` | 停止当前会话 |
| GET | `/api/session/status` | 获取会话状态和统计信息 |
| WebSocket | `/ws` | 实时事件推送 |

### WebSocket 事件类型

| 事件 | 说明 |
|------|------|
| `chat_received` | 收到弹幕消息 |
| `ai_reply_start` | AI 开始生成回复 |
| `ai_reply_done` | AI 回复完成 |
| `tts_start` | TTS 开始合成 |
| `tts_done` | TTS 合成完成 |
| `audio_playing` | 音频播放中 |
| `audio_done` | 音频播放完成 |
| `session_started` | 会话已启动 |
| `session_stopped` | 会话已停止 |
| `session_error` | 会话错误 |
| `stats_update` | 统计数据更新 |
| `like` | 收到点赞 |
| `gift` | 收到礼物 |
| `member_join` | 用户进入直播间 |

## 配置参考

完整的 `config.yaml` 配置项：

```yaml
# ===== AI 配置 =====
ai:
  api_key: ""                    # LLM API 密钥
  base_url: "https://api.openai.com/v1"  # API 基础地址
  model: "gpt-4o-mini"          # 模型名称
  system_prompt: "你是一个直播间的AI助手。你需要用简短、友好、有趣的方式回答观众的问题。回答控制在50字以内，适合语音播报。不要使用markdown格式、表情符号或特殊符号。"
  max_history: 10               # 保留的对话历史轮数
  multilang: false              # 是否启用多语言检测

# ===== TTS 配置 =====
tts:
  engine: "edge-tts"            # TTS 引擎：edge-tts | volcengine
  voice: "zh-CN-XiaoxiaoNeural" # 语音角色
  rate: "+0%"                   # 语速调节（如 +10%、-5%）
  volume: "+0%"                 # 音量调节
  output_dir: "audio_cache"     # 语音文件缓存目录

# ===== 火山引擎 TTS（当 tts.engine 为 volcengine 时生效）=====
volcengine:
  api_key: ""
  app_id: ""
  access_token: ""
  speaker_id: ""
  resource_id: "seed-icl-2.0"

# ===== 弹幕过滤 =====
filter:
  keywords:                     # 触发 AI 回复的关键词列表
    - "怎么"
    - "什么"
    - "吗"
    - "如何"
    - "为什么"
    - "?"
    - "？"
  min_length: 2                 # 最短消息长度
  max_length: 200               # 最长消息长度
  cooldown_seconds: 3           # 同一用户的冷却时间（秒）

# ===== 音频播放 =====
audio:
  device: "default"             # 音频输出设备

# ===== 抖音 =====
douyin:
  live_url: ""                  # 直播间链接
  room_id: ""                   # 直播间 ID
  cookie: ""                    # 浏览器 Cookie

# ===== TikTok =====
tiktok:
  unique_id: ""                 # 用户名
  proxy: ""                     # 代理地址

# ===== YouTube =====
youtube:
  video_id: ""                  # 直播视频 ID
  channel_id: ""                # 频道 ID（自动查找当前直播）
  api_key: ""                   # YouTube Data API Key
  client_secrets_file: ""       # OAuth 凭证文件路径
  auto_reply: false             # 是否自动回复到聊天
  reply_prefix: ""              # 回复消息前缀
```

## 常见问题

**Q: 抖音弹幕无法抓取？**
A: 确保 `cookie` 字段已填写有效的抖音登录 Cookie（从浏览器 DevTools 获取），且直播间正在直播中。

**Q: TikTok 连接失败？**
A: 国内环境需要配置 `proxy` 代理。确认用户名正确且正在直播。

**Q: YouTube 授权失败？**
A: 检查 `client_secret.json` 文件是否存在且格式正确。确认已在 Google Cloud Console 启用 YouTube Data API v3，且 OAuth 同意屏幕已配置。

**Q: 语音合成没有声音？**
A: 检查系统音量设置。确认 `audio_cache/` 目录有写入权限。若使用火山引擎，会自动降级到 Edge TTS。

**Q: 如何更换 AI 模型？**
A: 修改 `config.yaml` 中 `ai.base_url` 和 `ai.model`。支持任意兼容 OpenAI 格式的 API，如 DeepSeek、豆包、通义千问、本地 Ollama 等。

## 打包分发（PyInstaller）

将项目打包为单一可执行文件，用户无需安装 Python / Node.js 环境即可使用。

### 打包环境要求

- Python >= 3.12（仅打包时需要）
- Node.js >= 18（仅构建前端时需要）
- PyInstaller：`pip install pyinstaller`

### 一、构建前端

```bash
cd web
npm install
npm run build
cd ..
```

确认 `web/dist/` 目录生成成功。

### 二、执行打包

```bash
# 安装 PyInstaller（如果尚未安装）
pip install pyinstaller

# 使用 spec 文件打包
pyinstaller tk-live.spec
```

打包产物在 `dist/tk-live/` 目录下。

### 三、准备分发包

将以下文件/目录一起打包分发给用户：

```
TK-Live/
├── tk-live                  # 主程序（打包产物 dist/tk-live/ 中的全部文件）
├── config.yaml.example      # 配置模板（用户首次使用时复制为 config.yaml）
└── ...                      # dist/tk-live/ 下的其他文件
```

可使用以下命令创建分发包：

```bash
# 复制配置模板
cp config.yaml dist/tk-live/config.yaml.example

# macOS: 创建 zip 分发包
cd dist && zip -r tk-live-macos.zip tk-live/ && cd ..

# 或创建 tar.gz
cd dist && tar -czf tk-live-macos.tar.gz tk-live/ && cd ..
```

### 四、用户使用方式

用户收到分发包后：

```bash
# 解压
unzip tk-live-macos.zip
cd tk-live

# 首次使用：复制配置模板并编辑
cp config.yaml.example config.yaml
# 编辑 config.yaml，填写 AI API Key 等必要配置

# 启动
./tk-live
```

启动后会自动打开浏览器访问 `http://localhost:8000`。

### 打包后的目录结构

```
tk-live/                     # 用户的工作目录
├── tk-live                  # 可执行文件
├── config.yaml              # 用户配置（可编辑）
├── products.json            # 商品知识库（可选）
├── audio_cache/             # TTS 语音缓存（自动创建）
├── client_secret.json       # YouTube OAuth 凭证（如需 YouTube 功能）
└── _internal/               # PyInstaller 内部资源（勿修改）
    ├── web/dist/            # 前端静态文件
    ├── sign.js              # 抖音签名脚本
    └── ...
```

### 注意事项

- 抖音功能需要用户机器上安装 Node.js（用于签名计算）
- macOS / Windows / Linux 需分别打包，不可跨平台使用
- 打包产物较大（约 200-400MB），因包含完整 Python 运行时和所有依赖
- `audio_cache/`、`config.yaml`、`products.json` 等用户数据位于可执行文件旁边，方便用户管理

## License

MIT
