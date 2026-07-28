# TGSRC — Telegram 受限内容搬运机器人

本项目基于 devgagan 的实现（https://github.com/devgaganin），在此基础上进行了若干修复与改进。原作者保留所有原始版权和许可信息。

基于 Pyrogram + Telethon 双客户端的 Telegram Bot，支持：
- 破解转发/保存限制，搬运私有频道内容
- 批量搬运（按消息 ID 范围）
- YouTube / Instagram / TikTok / Twitter 等视频下载
- Spotify 音频下载
- Telegram Stars 订阅付费

- 发送社交媒体链接即可自动识别并触发下载，无需额外 `/dl` 命令。
- 使用 `/help` 可以查看完整的可用命令列表，包含下载、搬运、设置、会员及管理命令。

---

## 目录

- [Docker 部署（推荐）](#docker-部署推荐)
  - [前置要求](#前置要求)
  - [快速启动](#快速启动)
  - [配置说明](#配置说明)
  - [数据持久化](#数据持久化)
  - [管理命令](#管理命令)
- [手动部署](#手动部署)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

---

## Docker 部署（推荐）

### 前置要求

- Docker Engine ≥ 20.10
- Docker Compose ≥ 2.0
- Telegram API 凭证（从 https://my.telegram.org 获取）

### 快速启动

**1. 克隆并进入项目目录**

```bash
git clone https://github.com/wensley/TGSRC.git
cd TGSRC
```

**2. 创建 `.env` 配置文件**

```bash
cp .env.example .env
```

编辑 `.env`，填入必要信息（参见下方配置说明）。

**3. 启动服务**

```bash
docker compose up -d
```

首次启动会自动构建镜像。查看启动日志：

```bash
docker compose logs -f bot
```

看到 `SpyLib started...` 和 `Pyro App Started...` 即表示启动成功。在 Telegram 中向机器人发送 `/start` 测试。

**4. 停止服务**

```bash
docker compose down
```

保留数据卷停止：
```bash
docker compose down --volumes
```

### 配置说明

所有配置通过 `.env` 文件传入，`docker-compose.yml` 会自动加载。

| 变量 | 必需 | 说明 |
|------|------|------|
| `API_ID` | ✅ | 从 https://my.telegram.org 获取 |
| `API_HASH` | ✅ | 同上 |
| `BOT_TOKEN` | ✅ | 从 @BotFather 创建机器人获取 |
| `OWNER_ID` | ✅ | 管理员用户 ID，多个用空格分隔（如 `894148445 474767627`） |
| `REDIS_URL` | ❌ | Redis 连接地址，Docker 部署无需修改（默认 `redis://redis:6379/0`） |
| `STRING` | ❌ | Pyrogram Session 字符串。留空时 userbot 功能不可用，部分私有频道和 2GB 以上文件需此功能 |
| `LOG_GROUP` | ✅ | 日志频道/群组 ID（带 `-100` 前缀） |
| `FORCE_SUB` | ✅ | 强制订阅频道 ID（带 `-100` 前缀） |
| `MASTER_KEY` | ❌ | Session 加密主密钥，默认值可用，建议自定义 |
| `IV_KEY` | ❌ | 加密向量密钥，建议与 MASTER_KEY 一起自定义 |
| `YT_COOKIES` | ❌ | YouTube cookies（Netscape 格式），用于下载年龄限制或地域限制视频 |
| `INSTA_COOKIES` | ❌ | Instagram cookies（Netscape 格式） |
| `FREEMIUM_LIMIT` | ❌ | 免费用户每日限额，`0` 表示不提供免费服务（默认 `100`） |
| `PREMIUM_LIMIT` | ❌ | 付费用户限额（默认 `500`） |
| `JOIN_LINK` | ✅ | /start 中显示的频道链接 |
| `ADMIN_CONTACT` | ✅ | 管理员联系方式 |

**关于 `STRING`：**
- `STRING` 是 Pyrogram 的 Session String，让机器人拥有一个"用户账号"作为代理。
- 如果不填，`/login` 功能不可用，无法搬运私有频道（但公开频道仍可）。
- 获取方法：在本机运行一段 Pyrogram 脚本导出 session string，或直接留空用 `/login` 功能从手机号登录。

### 数据持久化

Docker Compose 配置了三个持久化卷：

```
volumes:
  - ./sessions:/app/sessions      # Telethon/Pyrogram 会话文件
  - ./downloads:/app/downloads     # 临时下载文件
  - ./redis_data:/data             # Redis 持久化数据
```

- `sessions/` 和 `downloads/` 已在 `.gitignore` 中排除，不会提交到 Git。
- Redis 数据存储在 `redis_data/` 目录。

### 管理命令

**查看日志：**
```bash
docker compose logs -f bot        # 实时 bot 日志
docker compose logs -f redis      # 实时 Redis 日志
```

**重启 Bot（不重启 Redis）：**
```bash
docker compose restart bot
```

**重新构建镜像：**
```bash
docker compose build --no-cache bot
docker compose up -d
```

**进入容器内部：**
```bash
docker compose exec bot bash
```

**查看资源占用：**
```bash
docker compose stats
```

### 资源限制

`docker-compose.yml` 中预设了资源限制：

```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: "1.5"
```

可依据服务器配置调整。如果下载大文件频繁，建议增加内存限制到 1GB。

---

## 手动部署

### 前置要求

- Python ≥ 3.10
- Redis ≥ 6.0
- FFmpeg
- pip

### 步骤

```bash
# 1. 安装系统依赖
apt install ffmpeg redis-server

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装 Python 依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入配置

# 5. 启动 Redis
redis-server --daemonize yes

# 6. 启动 Bot
python3 main.py
```

---

## 项目结构

```
TGSRC/
├── main.py              # 入口：启动客户端、加载插件
├── app.py               # Flask 健康检查 Web 服务（端口 5000）
├── config.py            # 环境变量配置
├── shared_client.py     # Telethon + Pyrogram 双客户端初始化
├── Dockerfile           # Docker 构建
├── docker-compose.yml   # Docker Compose（含 Redis）
├── entrypoint.sh        # 容器启动入口（Flask + Bot 双进程）
├── Procfile             # Heroku 部署
├── .env                 # 本地配置（不提交 Git）
├── requirements.txt     # Python 依赖
│
├── plugins/             # 插件目录（自动加载）
│   ├── start.py         #   /start /help /set
│   ├── login.py         #   /login /logout /setbot
│   ├── batch.py         #   /batch /single 批量搬运
│   ├── ytdl.py          #   /dl /adl /music 媒体下载
│   ├── settings.py      #   /settings 自定义配置
│   ├── stats.py         #   /status /transfer /rem
│   ├── pay.py           #   /pay Telegram Stars 支付
│   └── premium.py       #   /add 会员管理
│
├── utils/               # 工具库
│   ├── func.py          # Redis 操作、链接解析、截图、元数据提取
│   ├── encrypt.py       # AES-256-GCM Session 加解密
│   ├── fast_download.py # 并行分块下载器
│   └── custom_filters.py # Pyrogram 自定义过滤器
│
├── sessions/            # 客户端会话文件（运行时/卷挂载）
└── downloads/           # 下载临时文件（运行时/卷挂载）
```

---

## 常见问题

### Q: 启动后 Bot 没反应

检查日志：
```bash
docker compose logs bot
```
确认是否有 `SpyLib started...` 和 `Pyro App Started...`。如果没有，检查 `.env` 中的 `API_ID`、`API_HASH`、`BOT_TOKEN` 是否正确。

### Q: 批量搬运时提示"未检测到 User Client"

说明未登录账号。发送 `/login` 按提示用手机号登录，或在 `.env` 中配置 `STRING`。

### Q: 2GB 以上文件上传失败

上传超过 2GB 的文件需要 `STRING`（userbot session）配合中转频道（`LOG_GROUP`）。配置 `STRING` 后重启即可。

### Q: 如何更新 Bot

```bash
git pull
docker compose build bot
docker compose up -d
```

### Q: Redis 连接失败

确保 Redis 容器正常运行：
```bash
docker compose ps redis
docker compose logs redis
```

### Q: 支付/Stars 功能不工作

确保 Bot 通过了 @BotFather 的 Stars 申请（Bot Settings → Payments → Telegram Stars）。这是 Telegram 侧的要求，代码本身没有限制。
