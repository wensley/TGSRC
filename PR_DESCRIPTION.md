**概要**
- 分支: `fix/tests-and-security`
- 目标: 修复导入时的 None/缺失依赖导致的崩溃、提高安全性（移除/禁止硬编码敏感默认值）、增强加密实现、为 `plugins/ytdl.py` 添加 HTTP 重试与导入保护、并增加单元测试覆盖。

**修复与改进（要点）**
- `utils/custom_filters.py`: 修复 message.from_user 为 None 导致的 AttributeError。
- `config.py`: 强制 `OWNER_ID`、`MASTER_KEY`、`IV_KEY` 必须通过环境变量提供，避免在仓库中使用默认敏感值（启动缺失时抛错）。
- `utils/encrypt.py`: 重构为 `derive_key` / `encrypt_str` / `decrypt_str`，PBKDF2 迭代次数提高到 300000；保留向后兼容别名。
- `plugins/ytdl.py`: 
  - 将 `aiohttp`/`aiofiles`/`pyrogram` 等可选依赖设为可缺省并添加安全守卫，防止在测试环境导入时报错。
  - 添加同步/异步的 HTTP 重试 helper（`http_get_sync_with_retries` / `http_get_async_with_retries`），并用于缩略图下载。
  - 修复 `speed_bps` 未定义等小错误，避免在线程中使用 `asyncio.run`。
- `plugins/batch.py`:
  - 将媒体组的 forward fallback 改为 download+resend，避免转发带原频道 attribution（避免 `via @channel`）。
  - 在不能安全复用 `file_id`（如转发消息）时，改为 download+send，以确保预览 thumbnail 与视频旋转/尺寸正确。
- 新增 pytest 测试覆盖：`tests/test_encrypt.py`、`tests/test_ytdl_progress.py`、`tests/test_thumbnail_download.py`。

**破坏性变更 / 注意事项（必须）**
- `OWNER_ID`、`MASTER_KEY`、`IV_KEY` 现在必须在部署环境通过环境变量设置；若缺失程序会在导入时抛出 `RuntimeError`。请不要将这些密钥提交到仓库。
- `encrypt` 模块的公开函数名有重命名（但保持了兼容别名）。部署脚本或调用处应优先使用 `encrypt_str` / `decrypt_str`。

**迁移步骤**
1. 在部署环境（或 CI）设置必要的环境变量：
   - `OWNER_ID`（space-separated Telegram IDs）
   - `MASTER_KEY`（32+ 字节随机字符串）
   - `IV_KEY`（12 字节随机字符串用于 AES-GCM 推荐）

2. 若 CI 需要运行测试，请在测试环境安装轻量依赖或使用本分支中的导入保护（无需安装全部第三方库）。推荐在真实集成测试时安装：`pyrogram`, `telethon`, `yt-dlp`, `aiohttp`, `mutagen`, `opencv-python-headless`。

3. 验证媒体搬运流程：对于媒体组与转发场景，请在测试频道做端到端验证以确认：
   - 非限制内容不再通过 `forward` 导致带原频道 attribution（现在会选用复制或 download+send）。
   - 限制内容（如竖屏视频）在 download+send 路径能够正确生成缩略图并保持正确的宽高比。

**测试说明**
- 当前新增的单元测试已经在无外部依赖的情况下通过（通过为缺失依赖注入 stub）。如果需要更高保真测试，请在 CI 中使用真实依赖并运行 `pytest`。

**建议**
- 将 `.env.example` 填入部署环境并在 CI 中使用密钥注入（Secrets）。
- 在 PR 合并后，在受控测试频道执行一次完整的媒体搬运验证。
