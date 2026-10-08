# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

import os, re, time, asyncio, json, subprocess
import sys

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant, MediaEmpty
from config import API_ID, API_HASH, LOG_GROUP, STRING, FORCE_SUB, FREEMIUM_LIMIT, PREMIUM_LIMIT
from utils.func import get_user_data, screenshot, thumbnail, get_video_metadata
from utils.func import get_user_data_key, process_text_with_rules, is_premium_user, E
from utils.func import strip_mentions_and_links
from shared_client import app as X
from plugins.settings import rename_file
from plugins.start import subscribe as sub
from utils.custom_filters import login_in_progress
from utils.encrypt import dcs
from typing import Dict, Any, Optional


Y = None if not STRING else __import__('shared_client').userbot
Z, P, UB, UC = {}, {}, {}, {}

ACTIVE_USERS = {}
ACTIVE_USERS_FILE = "active_users.json"

# fixed directory file_name problems 
def sanitize(filename):
    name = re.sub(r'[<>:"/\\|?*\']', '_', filename)
    name = name.replace(' ', '_')
    name = re.sub(r'_+', '_', name)
    return name.strip("._")[:255]


def strip_markdown(text):
    """把 markdown 降级为纯文本，作为 caption 发送失败时的兜底方案"""
    if not text:
        return text
    t = str(text)
    t = re.sub(r'```[a-zA-Z0-9]*\n?', '', t)
    t = t.replace('```', '')
    t = re.sub(r'`([^`]*)`', r'\1', t)
    t = re.sub(r'\*\*([^*]*)\*\*', r'\1', t)
    t = re.sub(r'__([^_]*)__', r'\1', t)
    t = re.sub(r'\*([^*]*)\*', r'\1', t)
    t = re.sub(r'_([^_]*)_', r'\1', t)
    t = re.sub(r'~~([^~]*)~~', r'\1', t)
    t = re.sub(r'\|([^|]*)\|', r'\1', t)
    t = re.sub(r'\[([^\]]*)\]\(([^)]*)\)', r'\1', t)
    t = re.sub(r'^#{1,6}\s*', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*>\s?', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*[-*+]\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'[*_`~]', '', t)
    return t


CAPTION_LIMIT = 1024


async def safe_edit(pt, text, reply_markup=None):
    """进度消息编辑失败（FloodWait / 消息已删除等）绝不能中断发送逻辑"""
    try:
        await pt.edit_text(text, reply_markup=reply_markup)
    except Exception:
        pass


def clamp_caption(text, limit=CAPTION_LIMIT):
    """Telegram caption 硬上限 1024 字符，超长会让所有发送方式静默失败"""
    if not text:
        return text
    text = str(text)
    if len(text) <= limit:
        return text
    print(f"[caption] truncated from {len(text)} to {limit} chars", flush=True)
    return text[:limit - 3].rstrip() + '...'

def load_active_users():
    try:
        if os.path.exists(ACTIVE_USERS_FILE):
            with open(ACTIVE_USERS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception:
        return {}

async def save_active_users_to_file():
    try:
        with open(ACTIVE_USERS_FILE, 'w') as f:
            json.dump(ACTIVE_USERS, f)
    except Exception as e:
        print(f"Error saving active users: {e}")

async def add_active_batch(user_id: int, batch_info: Dict[str, Any]):
    ACTIVE_USERS[str(user_id)] = batch_info
    await save_active_users_to_file()

def is_user_active(user_id: int) -> bool:
    return str(user_id) in ACTIVE_USERS

async def update_batch_progress(user_id: int, current: int, success: int):
    if str(user_id) in ACTIVE_USERS:
        ACTIVE_USERS[str(user_id)]["current"] = current
        ACTIVE_USERS[str(user_id)]["success"] = success
        await save_active_users_to_file()

async def request_batch_cancel(user_id: int):
    if str(user_id) in ACTIVE_USERS:
        ACTIVE_USERS[str(user_id)]["cancel_requested"] = True
        await save_active_users_to_file()
        return True
    return False

def should_cancel(user_id: int) -> bool:
    user_str = str(user_id)
    return user_str in ACTIVE_USERS and ACTIVE_USERS[user_str].get("cancel_requested", False)

def parse_targets(cfg_chat, default_chat):
    """Parse chat_id config into list of (chat_id, reply_to_message_id) tuples.
    Supports comma-separated IDs and /topic suffix per ID.
    """
    if not cfg_chat:
        return [(int(default_chat), None)]
    targets = []
    entries = cfg_chat.split(',')
    for entry in entries:
        entry = entry.strip()
        if '/' in entry:
            parts = entry.split('/', 1)
            targets.append((int(parts[0]), int(parts[1])))
        else:
            targets.append((int(entry), None))
    return targets

async def remove_active_batch(user_id: int):
    if str(user_id) in ACTIVE_USERS:
        del ACTIVE_USERS[str(user_id)]
        await save_active_users_to_file()

def get_batch_info(user_id: int) -> Optional[Dict[str, Any]]:
    return ACTIVE_USERS.get(str(user_id))

ACTIVE_USERS = load_active_users()

async def upd_dlg(c):
    try:
        async for _ in c.get_dialogs(limit=100): pass
        return True
    except Exception as e:
        print(f'Failed to update dialogs: {e}')
        return False

async def send_log(text):
    try:
        from shared_client import app as _bot
        await _bot.send_message(LOG_GROUP, text, disable_web_page_preview=True)
    except Exception as e:
        print(f'Failed to send log to LOG_GROUP: {e}')

# fixed the old group of 2021-2022 extraction 🌝 (buy krne ka fayda nhi ab old group) ✅ 
async def get_msg(c, u, i, d, lt):
    try:
        if lt == 'public':
            # Try fetching with bot client first
            try:
                xm = await c.get_messages(i, d)
                if xm and not getattr(xm, "empty", False):
                    return xm
            except Exception:
                pass
            
            # If bot fails, try with user client
            if u:
                try:
                    xm = await u.get_messages(i, d)
                    if xm and not getattr(xm, "empty", False):
                        return xm
                except Exception:
                    pass
            return None
        else:
            # Private channel handling
            if u:
                try:
                    # Refresh dialogs to ensure access
                    # async for _ in u.get_dialogs(limit=20): pass
                    
                    # Try various ID formats
                    ids_to_try = [i]
                    if str(i).startswith('-100'):
                        ids_to_try.append(int(i))
                        ids_to_try.append(int(str(i).replace('-100', '-')))
                    elif str(i).isdigit():
                        ids_to_try.append(int(f"-100{i}"))
                        ids_to_try.append(int(f"-{i}"))
                    
                    for chat_id in ids_to_try:
                        try:
                            result = await u.get_messages(chat_id, d)
                            if result and not getattr(result, "empty", False):
                                return result
                        except Exception:
                            continue
                except Exception as e:
                    print(f'Private channel error: {e}')
            return None
    except Exception as e:
        print(f'Error fetching message: {e}')
        return None


async def get_ubot(uid):
    bt = await get_user_data_key(uid, "bot_token", None)
    if not bt:
        from shared_client import app
        return app
    if uid in UB: return UB.get(uid)
    try:
        bot = Client(f"user_{uid}", bot_token=bt, api_id=API_ID, api_hash=API_HASH)
        await bot.start()
        UB[uid] = bot
        return bot
    except Exception as e:
        print(f"Error starting bot for user {uid}: {e}")
        from shared_client import app
        return app

async def get_uclient(uid):
    ud = await get_user_data(uid)
    ubot = UB.get(uid)
    cl = UC.get(uid)
    if cl: return cl
    if not ud: return ubot if ubot else None
    xxx = ud.get('session_string')
    if xxx:
        try:
            ss = dcs(xxx)
            gg = Client(f'{uid}_client', api_id=API_ID, api_hash=API_HASH, device_model="v3saver", session_string=ss)
            await gg.start()
            await upd_dlg(gg)
            UC[uid] = gg
            return gg
        except Exception as e:
            print(f'User client error: {e}')
            return ubot if ubot else Y
    return Y

async def prog(c, t, C, h, m, st, extra="", uid=None):
    if uid and should_cancel(uid):
        raise Exception("任务已由用户取消")
    
    global P
    p = c / t * 100
    interval = 10 if t >= 100 * 1024 * 1024 else 20 if t >= 50 * 1024 * 1024 else 30 if t >= 10 * 1024 * 1024 else 50
    step = int(p // interval) * interval
    if m not in P or P[m] != step or p >= 100:
        P[m] = step
        c_mb = c / (1024 * 1024)
        t_mb = t / (1024 * 1024)
        bar = '🟢' * int(p / 10) + '🔴' * (10 - int(p / 10))
        speed = c / (time.time() - st) / (1024 * 1024) if time.time() > st else 0
        eta = time.strftime('%M:%S', time.gmtime((t - c) / (speed * 1024 * 1024))) if speed > 0 else '00:00'
        
        status_text = f"**📥 正在处理 {extra}**\n\n" if extra else "**📥 正在处理...**\n\n"
        status_text += f"{bar}\n\n"
        status_text += f"⚡ **已完成**: `{c_mb:.2f} MB` / `{t_mb:.2f} MB`\n"
        status_text += f"📊 **进度**: `{p:.2f}%`\n"
        status_text += f"🚀 **速度**: `{speed:.2f} MB/s`\n"
        status_text += f"⏳ **预计剩余**: `{eta}`\n\n"
        status_text += "**Powered by @cc100g_zhuanfa_bot**"
        
        reply_markup = None
        if uid:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🚫 取消当前任务", callback_data=f"cancel_{uid}")]])
            
        try:
            await C.edit_message_text(h, m, status_text, reply_markup=reply_markup)
        except Exception:
            pass
        if p >= 100: P.pop(m, None)


async def get_group_msgs(ubot, uc, chat_id, mid):
    """获取指定消息所属媒体组的全部消息；非媒体组或失败时返回空列表"""
    for client in (uc, ubot):
        if client is None:
            continue
        try:
            msgs = await client.get_media_group(chat_id, mid)
        except Exception:
            continue
        if msgs and len(msgs) > 1:
            return msgs
    return []


async def extract_group_caption(messages):
    """安全取出组内第一条消息的正文（markdown），失败时退回纯文本"""
    for gmsg in messages:
        if not gmsg.caption:
            continue
        try:
            return gmsg.caption.markdown
        except Exception as ce:
            print(f"[group] caption.markdown failed: {type(ce).__name__}: {ce}", flush=True)
            try:
                return gmsg.caption.text
            except Exception:
                return None
    return None


def _has_audio_stream(path):
    """ffprobe 检测视频是否含音轨。ffprobe 缺失/超时/解析失败时返回 True，
    表示"不改动该文件"，避免误判导致无谓转码。"""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True, timeout=60)
    except Exception:
        return True
    if r.returncode != 0:
        return True
    return b"audio" in r.stdout


def _add_silent_audio(src, dst):
    """给无音轨视频补一条静音 AAC 音轨。视频流 -c:v copy，不重编码、不改画质。
    显式 -map 0:v -map 1:a 是必需的，否则 anullsrc 的 pcm 会被直接塞进 mp4 而失败。"""
    cmd = ["ffmpeg", "-y", "-i", src,
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-map", "0:v", "-map", "1:a",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "64k",
           "-shortest", "-movflags", "+faststart", dst]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=900)
    except Exception:
        return False
    return r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0


async def ensure_audio_track(path):
    """媒体组上传前确保视频带音轨，否则 Telegram 一律返回 MEDIA_EMPTY。

    pyrofork 2.3.68 的 send_media_group 内部逻辑：
        videoInfo = MediaInfo.parse(media)
        if not any(track.track_type == 'Audio' for track in videoInfo.tracks):
            is_animation = True
    无音轨视频会被下发 nosound_video=True 与 DocumentAttributeAnimated，
    Telegram 在 messages.SendMultiMedia 中直接拒绝，报 [400 MEDIA_EMPTY]；
    单条 send_video 走另一条上传路径，因此不受影响（表现为"逐条能发、合并必失败"）。
    这里补静音音轨规避该判定。任何环节失败都返回原路径，交由逐条兜底。
    """
    if not path or not path.lower().endswith(
            ('.mp4', '.mkv', '.mov', '.m4v', '.avi', '.webm', '.ts', '.mpeg', '.mpg')):
        return path
    if await asyncio.to_thread(_has_audio_stream, path):
        return path
    base = os.path.splitext(path)[0]
    dst = base + "_a.mp4"
    if await asyncio.to_thread(_add_silent_audio, path, dst):
        return dst
    try:
        if os.path.exists(dst):
            os.remove(dst)
    except OSError:
        pass
    return path


async def build_media_objects(downloaded_files, uid, thumb_files, plain=False,
                              reuse_thumbs=None, group_caption=None):
    """构造 send_media_group 所需的 InputMedia 列表。

    plain=True 时把 caption 降级为纯文本，用于 markdown 非法时的重试。
    reuse_thumbs 为已有缩略图文件名列表（按 downloaded_files 顺序），命中时复用，
    避免纯文本重试重复执行 ffmpeg 截图。
    group_caption 为组内正文兜底：当某条消息自身没有正文时使用，
    保证相册首条能带上文字。
    """
    from pyrogram.types import InputMediaVideo, InputMediaPhoto, InputMediaDocument
    media = []
    reuse_thumbs = reuse_thumbs or []
    for index, (f_path, msg) in enumerate(downloaded_files):
        # Telegram 只显示相册首条的正文，其余条目的 caption 不会呈现，
        # 因此组内兜底正文只能加在第一项，避免无意义地重复写入。
        cap = msg.caption or (group_caption if index == 0 else None)
        if cap:
            cap = strip_mentions_and_links(cap)
            if plain:
                cap = strip_markdown(cap)
            cap = clamp_caption(cap) or None
        else:
            cap = None

        if f_path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.m4v')):
            mtd = await get_video_metadata(f_path)
            # get_video_metadata 解析失败时返回 {'width':1,'height':1,'duration':1}。
            # 把这组假元数据传给 Telegram 会因尺寸/时长与实际不符而被判 MEDIA_EMPTY，
            # 因此识别为"未知"并省略这些参数。
            meta_known = not (mtd['width'] == 1 and mtd['height'] == 1 and mtd['duration'] == 1)

            th = reuse_thumbs[index] if index < len(reuse_thumbs) else None
            if not th and meta_known:
                try:
                    th = await screenshot(f_path, mtd['duration'], f"{uid}_{index}")
                    if th:
                        thumb_files.append(th)
                except Exception as e:
                    print(f"[group] screenshot/thumbnail failed: {type(e).__name__}: {e}", flush=True)

            # 缩略图不存在/为空时必须丢弃，否则 Telegram 报 MEDIA_EMPTY
            if th:
                try:
                    if not os.path.exists(th) or os.path.getsize(th) == 0:
                        print(f"[group] dropping unusable thumb for item {index}: {th}", flush=True)
                        th = None
                except Exception as e:
                    print(f"[group] thumb validation failed ({type(e).__name__}: {e}); dropping", flush=True)
                    th = None

            vkw = {'caption': cap}
            if meta_known:
                vkw.update(width=mtd['width'], height=mtd['height'], duration=mtd['duration'])
            if th:
                vkw['thumb'] = th

            print(f"[group] item {index}: video meta_known={meta_known} "
                  f"w={mtd['width']} h={mtd['height']} dur={mtd['duration']} thumb={bool(th)}", flush=True)

            try:
                media.append(InputMediaVideo(f_path, **vkw))
            except TypeError as te:
                print(f"[group] InputMediaVideo rich params rejected ({te}), retrying minimal", flush=True)
                try:
                    media.append(InputMediaVideo(f_path, caption=cap))
                except TypeError:
                    media.append(InputMediaVideo(f_path))
        elif f_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            media.append(InputMediaPhoto(f_path, caption=cap))
        else:
            media.append(InputMediaDocument(f_path, caption=cap))
    return media


async def process_media_group(ubot, uc, messages, targets, pt, uid, i, lt):
    """把整组消息以 Telegram 媒体组形式发送到所有目标，返回成功发送的消息条数"""
    total = len(messages)

    if not messages:
        return 0
    if not targets:
        print("[group] no targets configured, cannot send media group", flush=True)
        return 0

    # --- 1. 媒体组不做秒发 ---
    # pyrofork 2.3.68 的 copy_media_group 只接受单个 message_id，无法复制整组；
    # forward_messages 虽可用但会显示"转发自"来源，不符合需求。
    # 因此媒体组一律走下载后 send_media_group 重传（不显示来源）。
    # 单条消息仍走 process_msg -> send_direct 的 copy_message 秒发。
    await safe_edit(pt, f'检测到媒体组 ({total} 个文件)，正在下载并合并上传...')

    # 相册阶段未能完整送达的目标，供第 3 步逐条补发时使用
    album_failed_targets = []

    # --- 2. 下载后合并发送 ---
    downloaded_files = []
    thumb_files = []
    # 补音轨等处理产生的中间文件（原始文件被替换时登记在此），退出时一并清理
    extra_files = []

    def _purge_temp():
        """清理本次媒体组产生的全部临时文件：下载文件、补音轨文件、缩略图。"""
        for path in [f for f, _ in downloaded_files] + list(thumb_files) + list(extra_files):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    st = time.time()
    try:
        for index, msg in enumerate(messages):
            if should_cancel(uid):
                break
            DOWNLOAD_DIR = os.path.abspath("downloads")
            if not os.path.exists(DOWNLOAD_DIR):
                os.makedirs(DOWNLOAD_DIR)

            ext = ".mp4" if msg.video or msg.video_note else ".jpg" if msg.photo else ".zip"
            if msg.document:
                ext = os.path.splitext(msg.document.file_name)[1] or ".zip"

            tmp_name = os.path.join(DOWNLOAD_DIR, f"{time.time()}_{index}{ext}")
            await safe_edit(pt, f'🚀 正在下载第 {index+1}/{total} 个文件...')

            from utils.fast_download import fast_download as parallel_dl, _download_pool
            f = None
            if _download_pool:
                f = await parallel_dl(
                    msg, tmp_name,
                    progress_callback=prog,
                    progress_args=(ubot, pt.chat.id, pt.id, st, f"({index+1}/{total})", uid),
                    cancel_check=lambda: should_cancel(uid)
                )
            if not f:
                f = await uc.download_media(
                    msg, file_name=tmp_name, progress=prog,
                    progress_args=(ubot, pt.chat.id, pt.id, st, f"({index+1}/{total})", uid)
                )
            if f:
                f = await rename_file(f, uid, pt)
                # 下载"成功"但文件不存在/为空是最常见的 MEDIA_EMPTY 成因，
                # 这里显式校验并记录尺寸，避免下次只能靠猜。
                try:
                    fsize = os.path.getsize(f)
                except Exception as e:
                    print(f"[group] downloaded file missing for item {index}: "
                          f"{type(e).__name__}: {e}", flush=True)
                    continue
                if fsize == 0:
                    print(f"[group] downloaded file is EMPTY for item {index}, skipping", flush=True)
                    try:
                        os.remove(f)
                    except OSError:
                        pass
                    continue
                kind = 'video' if msg.video else 'photo' if msg.photo else \
                       'document' if msg.document else 'audio' if msg.audio else 'other'
                print(f"[group] item {index}: {kind}, {fsize} bytes, "
                      f"{os.path.basename(str(f))}", flush=True)

                # 无音轨视频在 send_media_group 中会被判为动画并被 Telegram 拒绝
                # （MEDIA_EMPTY），必须在构造 InputMediaVideo 之前补静音音轨。
                if msg.video:
                    fixed = await ensure_audio_track(f)
                    if fixed != f:
                        extra_files.append(f)
                        f = fixed
                        print(f"[group] item {index}: added silent audio track "
                              f"({fsize} -> {os.path.getsize(f)} bytes), "
                              f"{os.path.basename(str(f))}", flush=True)

                downloaded_files.append((f, msg))

        if downloaded_files:
            if len(downloaded_files) < total:
                await safe_edit(pt, f'⚠️ {len(downloaded_files)}/{total} 个文件下载成功，将合并发送已下载部分...')
            else:
                await safe_edit(pt, f'✅ 所有文件下载完成，正在合并上传为媒体组...')

            from pyrogram.types import InputMediaVideo, InputMediaPhoto, InputMediaDocument
            group_caption = await extract_group_caption(messages)
            media = await build_media_objects(downloaded_files, uid, thumb_files,
                                              plain=False, group_caption=group_caption)

            sent_any = False
            all_chunks_ok = True
            any_chunk_ok = False
            last_err = None
            # Telegram 相册只接受图片和视频：若混入文档等类型，send_media_group 会整组失败。
            # 这里只把图片/视频放进相册，其余文件交给第 3 步逐条发送。
            album_files = downloaded_files
            groupable_idx = [i for i, o in enumerate(media) if not isinstance(o, InputMediaDocument)]
            if len(groupable_idx) < len(media):
                print(f"[group] {len(media) - len(groupable_idx)} non photo/video item(s) excluded from album "
                      f"(Telegram albums only accept photos and videos)", flush=True)
                media = [media[i] for i in groupable_idx]
                album_files = [downloaded_files[i] for i in groupable_idx]

            if len(media) >= 2:
                media_group_max = 10
                chunks = [media[i:i + media_group_max] for i in range(0, len(media), media_group_max)]
                for tcid, rtmid in targets:
                    ok_target = 0
                    for chunk_idx, chunk in enumerate(chunks):
                        reply_id = rtmid if chunk_idx == 0 else None
                        try:
                            await ubot.send_media_group(tcid, chunk, reply_to_message_id=reply_id)
                            ok_target += 1
                            last_err = None
                            continue
                        except Exception as ge:
                            print(f"[group] send_media_group via bot failed ({type(ge).__name__}: {ge})", flush=True)
                            last_err = ge

                        try:
                            if uc:
                                await uc.send_media_group(tcid, chunk, reply_to_message_id=reply_id)
                                ok_target += 1
                                last_err = None
                                continue
                        except Exception as ue:
                            print(f"[group] send_media_group via user failed ({type(ue).__name__}: {ue})", flush=True)
                            last_err = ue

                        # caption 被 markdown 解析拒绝 -> 仅对当前分片重建纯文本 caption 后重试
                        # 注意：必须按 chunk 切片重建，否则 >10 个文件会超出 Telegram 限制并造成重复投递
                        sub_files = album_files[chunk_idx * media_group_max: chunk_idx * media_group_max + len(chunk)]
                        # MEDIA_EMPTY 多由可选参数（尺寸/时长/缩略图）引起，
                        # 先用最小参数重试一次，避免直接退化成分条消息。
                        if isinstance(last_err, MediaEmpty):
                            try:
                                bare = [InputMediaPhoto(m.media, caption=m.caption)
                                        if isinstance(m, InputMediaPhoto)
                                        else InputMediaVideo(m.media, caption=m.caption)
                                        for m in chunk]
                                print(f"[group] retrying chunk {chunk_idx} with minimal media params", flush=True)
                                await ubot.send_media_group(tcid, bare, reply_to_message_id=reply_id)
                                ok_target += 1
                                last_err = None
                                continue
                            except Exception as be:
                                print(f"[group] minimal-params retry failed "
                                      f"({type(be).__name__}: {be})", flush=True)
                        for plain_client, plain_label in ((ubot, 'bot'), (uc, 'user')):
                            if plain_client is None:
                                continue
                            try:
                                plain_thumbs = []
                                plain_chunk = await build_media_objects(sub_files, uid, plain_thumbs, plain=True,
                                                                       reuse_thumbs=thumb_files,
                                                                       group_caption=group_caption)
                                print(f"[group] retrying chunk via {plain_label} "
                                      f"with plain-text captions", flush=True)
                                await plain_client.send_media_group(tcid, plain_chunk, reply_to_message_id=reply_id)
                                ok_target += 1
                                last_err = None
                                break
                            except Exception as pe:
                                print(f"[group] plain-caption retry via {plain_label} failed "
                                      f"({type(pe).__name__}: {pe})", flush=True)
                                last_err = pe
                            finally:
                                for t in plain_thumbs:
                                    if os.path.exists(t):
                                        os.remove(t)
                    if ok_target == 0:
                        # 该目标一个分片都没发出去 -> 必须走逐条兜底，不能算成功
                        print(f"[group] target {tcid} received 0/{len(chunks)} chunks", flush=True)
                        album_failed_targets.append((tcid, rtmid))
                        all_chunks_ok = False
                    elif ok_target < len(chunks):
                        print(f"[group] target {tcid} received {ok_target}/{len(chunks)} chunks (partial)", flush=True)
                        album_failed_targets.append((tcid, rtmid))
                        all_chunks_ok = False
                        any_chunk_ok = True
                    else:
                        sent_any = True
                        any_chunk_ok = True

                if sent_any:
                    # 只统计真正进相册的文件；若混有非图片/视频的文件，必须逐条补发
                    album_sent = len(album_files)
                    excluded = len(downloaded_files) - album_sent
                    _purge_temp()
                    if excluded == 0 and all_chunks_ok:
                        await safe_edit(pt, '✅ 媒体组合并发送成功')
                        return album_sent
                    # 有文件未进相册（被排除的分片/类型），不能宣告完成，交给第 3 步
                    print(f"[group] album sent {album_sent} file(s), {excluded} excluded/unconfirmed; "
                          f"continuing to per-item stage", flush=True)
                    await safe_edit(pt, f'✅ 相册已发送 {album_sent} 个文件，正在补发剩余 {excluded} 个...')
                    return album_sent

                if any_chunk_ok:
                    print("[group] partial chunk delivery detected; falling back to per-item send for unsent files", flush=True)
                    await safe_edit(pt, '⚠️ 部分分片发送失败，将对未发送文件逐个补发...')
                else:
                    print(f"[group] media group upload failed for all targets, last error: {type(last_err).__name__}: {last_err}", flush=True)
                    await safe_edit(pt, '❌ 媒体组合并发送失败，将回退到逐个发送...')
            else:
                await safe_edit(pt, f'⚠️ 仅 {len(media)} 个文件下载成功，无法组成媒体组，将逐个发送...')

            _purge_temp()
    except Exception as ge:
        print(f"Group download/upload error: {ge}")
        _purge_temp()
        await safe_edit(pt, f'合并发送失败 ({str(ge)[:30]})，将回退到逐个发送...')

    # --- 3. 最后的手段：逐个处理 ---
    # 媒体组内正文只存在于第一条，这里把正文传播到每一条
    group_cap = await extract_group_caption(messages)
    if group_cap:
        print(f"[group] fallback will propagate caption to every item ({len(group_cap)} chars)", flush=True)

    # 只对相册阶段未完整送达的目标补发，避免向已成功的目标重复投递
    fallback_targets = album_failed_targets if album_failed_targets else targets
    if album_failed_targets:
        print(f"[group] per-item fallback limited to {len(album_failed_targets)} unsucceeded target(s)", flush=True)

    sent_count = 0
    for index, msg in enumerate(messages):
        if should_cancel(uid):
            break
        info = f"第 {index+1}/{total} 个文件"
        if index == 0:
            await safe_edit(pt, f'⚠️ 合并发送不可用，正在逐个发送 {total} 个文件...')
        res = await process_msg(ubot, uc, msg, str(pt.chat.id), lt, uid, i, extra=info,
                                caption_override=group_cap, targets_override=fallback_targets)
        res = str(res) if res else ''
        if res == 'Cancelled':
            break
        if 'Done' in res or 'Copied' in res or 'Sent' in res:
            sent_count += 1
        if index < total - 1:
            await asyncio.sleep(10)
    return sent_count


async def send_direct(c, m, tcid, ft=None, rtmid=None, user_client=None):
    last_err = None
    # caption 候选：原始 markdown 优先，失败后用纯文本兜底
    captions = [ft]
    if ft:
        plain = strip_markdown(ft)
        if plain and plain != ft:
            captions.append(plain)
            print(f"[direct] plain-text caption fallback armed ({len(ft)} -> {len(plain)} chars)", flush=True)

    try:
        # 方法 1: 机器人直接复制
        for cap in captions:
            kind = 'markdown' if cap is ft else 'plain'
            try:
                r = await c.copy_message(tcid, m.chat.id, m.id, caption=cap, reply_to_message_id=rtmid)
                if r is None:
                    print(f"[direct] bot copy_message returned None ({kind} caption); treating as failure", flush=True)
                    continue
                if kind == 'plain':
                    print(f"[direct] OK via bot copy_message with {kind} caption", flush=True)
                return True
            except Exception as e:
                last_err = e
                print(f"[direct] bot copy_message failed ({kind} caption): {type(e).__name__}: {e}", flush=True)

        # 方法 1.5: 用户客户端复制（绕过机器人权限限制）
        if user_client:
            for cap in captions:
                kind = 'markdown' if cap is ft else 'plain'
                try:
                    r = await user_client.copy_message(tcid, m.chat.id, m.id, caption=cap, reply_to_message_id=rtmid)
                    if r is None:
                        print(f"[direct] user copy_message returned None ({kind} caption); treating as failure", flush=True)
                        continue
                    if kind == 'plain':
                        print(f"[direct] OK via user copy_message with {kind} caption", flush=True)
                    return True
                except Exception as e:
                    last_err = e
                    print(f"[direct] user copy_message failed ({kind} caption): {type(e).__name__}: {e}", flush=True)

        # 方法 2: 用户代理中转
        # 注意：中转消息只创建一次，caption 候选只用于最终 copy_message，
        # 否则 markdown 失败后重试会在日志群留下重复的中转副本。
        if Y and LOG_GROUP:
            tm = None
            try:
                tm = await Y.copy_message(LOG_GROUP, m.chat.id, m.id)
                print(f"[direct] relay copy created in LOG_GROUP (id={tm.id})", flush=True)
            except Exception as e:
                last_err = e
                print(f"[direct] relay copy to LOG_GROUP failed: {type(e).__name__}: {e}", flush=True)

            if tm is not None:
                for cap in captions:
                    kind = 'markdown' if cap is ft else 'plain'
                    try:
                        r = await c.copy_message(tcid, LOG_GROUP, tm.id, caption=cap, reply_to_message_id=rtmid)
                        if r is None:
                            print(f"[direct] relay copy returned None ({kind} caption); treating as failure", flush=True)
                            continue
                        if kind == 'plain':
                            print(f"[direct] OK via LOG_GROUP relay with {kind} caption", flush=True)
                        return True
                    except Exception as e:
                        last_err = e
                        print(f"[direct] relay via LOG_GROUP failed ({kind} caption): {type(e).__name__}: {e}", flush=True)
        else:
            print(f"[direct] relay skipped (Y={bool(Y)}, LOG_GROUP={bool(LOG_GROUP)})", flush=True)

        # 方法 3: 通过 File ID 发送
        async def send_by_file_id(cap):
            if m.video:
                await c.send_video(tcid, m.video.file_id, caption=cap, duration=m.video.duration, width=m.video.width, height=m.video.height, reply_to_message_id=rtmid)
            elif m.video_note:
                await c.send_video_note(tcid, m.video_note.file_id, reply_to_message_id=rtmid)
            elif m.voice:
                await c.send_voice(tcid, m.voice.file_id, reply_to_message_id=rtmid)
            elif m.sticker:
                await c.send_sticker(tcid, m.sticker.file_id, reply_to_message_id=rtmid)
            elif m.audio:
                await c.send_audio(tcid, m.audio.file_id, caption=cap, duration=m.audio.duration, performer=m.audio.performer, title=m.audio.title, reply_to_message_id=rtmid)
            elif m.photo:
                photo_id = m.photo.file_id if hasattr(m.photo, 'file_id') else m.photo[-1].file_id
                await c.send_photo(tcid, photo_id, caption=cap, reply_to_message_id=rtmid)
            elif m.document:
                await c.send_document(tcid, m.document.file_id, caption=cap, file_name=m.document.file_name, reply_to_message_id=rtmid)
            else:
                print(f"[direct] unsupported media type for {tcid}, media={m.media}", flush=True)
                return False
            return True

        for cap in captions:
            kind = 'markdown' if cap is ft else 'plain'
            try:
                if await send_by_file_id(cap):
                    if kind == 'plain':
                        print(f"[direct] OK via file_id with {kind} caption", flush=True)
                    return True
                break
            except Exception as e:
                last_err = e
                print(f"[direct] file_id send failed ({kind} caption): {type(e).__name__}: {e}", flush=True)
    except Exception as e:
        print(f"[direct] send_direct error: {type(e).__name__}: {e}", flush=True)
        print(f"[direct] last known error: {type(last_err).__name__}: {last_err}", flush=True)
        return False

async def process_msg(c, u, m, d, lt, uid, i, extra="", caption_override=None, targets_override=None):
    # 每次开始前检查是否已取消
    if should_cancel(uid):
        return 'Cancelled'
    try:
        # targets_override 用于媒体组逐条兜底：只补发给尚未成功的目标，避免重复投递
        targets = targets_override if targets_override else parse_targets(await get_user_data_key(d, 'chat_id', None), d)
        
        if m.media:
            orig_text = caption_override if caption_override is not None else (m.caption.markdown if m.caption else '')
            proc_text = await process_text_with_rules(d, orig_text)
            user_cap = await get_user_data_key(d, 'caption', '')
            ft = f'{proc_text}\n\n{user_cap}' if proc_text and user_cap else user_cap if user_cap else proc_text
            ft = clamp_caption(ft)

            # --- 尝试秒发，记录成功目标避免后续重复 ---
            failed_targets = []
            for tcid, rtmid in targets:
                if not await send_direct(c, m, tcid, ft, rtmid, user_client=u):
                    failed_targets.append((tcid, rtmid))
                    print(f"Direct send failed for target {tcid}")
            if not failed_targets:
                return 'Sent directly.'
            print(f"Direct send failed for some targets, falling back to download/upload.")
            targets = failed_targets

            st = time.time()
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🚫 取消任务", callback_data=f"cancel_{uid}")]])
            p = await c.send_message(d, f'正在准备下载 {extra}...', reply_markup=reply_markup)

            # 确保下载目录存在并使用绝对路径
            DOWNLOAD_DIR = os.path.abspath("downloads")
            if not os.path.exists(DOWNLOAD_DIR):
                os.makedirs(DOWNLOAD_DIR)

            c_name = os.path.join(DOWNLOAD_DIR, f"{time.time()}")
            if m.video:
                file_name = m.video.file_name or f"{time.time()}.mp4"
                c_name = os.path.join(DOWNLOAD_DIR, sanitize(file_name))
            elif m.audio:
                file_name = m.audio.file_name or f"{time.time()}.mp3"
                c_name = os.path.join(DOWNLOAD_DIR, sanitize(file_name))
            elif m.document:
                file_name = m.document.file_name or f"{time.time()}"
                c_name = os.path.join(DOWNLOAD_DIR, sanitize(file_name))
            elif m.photo:
                c_name = os.path.join(DOWNLOAD_DIR, f"{time.time()}.jpg")
            elif m.video_note:
                c_name = os.path.join(DOWNLOAD_DIR, f"{time.time()}.mp4")
            elif m.voice:
                c_name = os.path.join(DOWNLOAD_DIR, f"{time.time()}.ogg")
    
            # --- 尝试并行高速下载 ---
            f = None
            try:
                from utils.fast_download import fast_download as parallel_dl, _download_pool
                if _download_pool:
                    await c.edit_message_text(d, p.id, f'🚀 并行加速下载 {extra}...',
                                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 取消任务", callback_data=f"cancel_{uid}")]]))
                    f = await parallel_dl(
                        m, c_name,
                        progress_callback=prog,
                        progress_args=(c, d, p.id, st, extra, uid),
                        cancel_check=lambda: should_cancel(uid),
                    )
            except Exception as pe:
                print(f"Parallel download error: {pe}")

            # --- 回退到普通下载 ---
            if not f:
                await c.edit_message_text(d, p.id, f'正在准备下载 {extra}...',
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 取消任务", callback_data=f"cancel_{uid}")]]))
                f = await u.download_media(m, file_name=c_name, progress=prog, progress_args=(c, d, p.id, st, extra, uid))
            
            if not f:
                await c.edit_message_text(d, p.id, '下载失败。')
                return 'Failed.'
            
            await c.edit_message_text(d, p.id, '正在重命名...')
            if (
                (m.video and m.video.file_name) or
                (m.audio and m.audio.file_name) or
                (m.document and m.document.file_name)
            ):
                f = await rename_file(f, d, p)
            
            fsize = os.path.getsize(f) / (1024 * 1024 * 1024)
            th = thumbnail(d)
            
            if fsize > 2 and Y:
                st = time.time()
                await c.edit_message_text(d, p.id, '文件超过 2GB，正在使用大文件模式上传...')
                await upd_dlg(Y)
                mtd = await get_video_metadata(f)
                dur, h, w = mtd['duration'], mtd['width'], mtd['height']
                th = await screenshot(f, dur, d)

                # 按目标分别记录结果：单个目标成功不能代表全部成功
                large_failed = []
                last_large_err = None
                for tcid, rtmid in targets:
                    # 先由用户客户端(STRING_SESSION)上传，再由 bot 复制到目标频道，
                    # 这样超 2GB 的文件不受 bot 上传限制，且不会显示"转发自"来源。
                    sent = None
                    try:
                        # send_photo 不接受 thumb 参数（已对 pyrofork 2.3.68 核实：
                        # send_video/send_audio/send_document/send_video_note 有，
                        # send_photo/send_voice 没有）。旧的共享 kwargs 里带着
                        # thumb=...，导致 send_photo 抛 TypeError，
                        # 使用户客户端上传整体失效 —— 而 >2GB 路径的意义正是走用户客户端。
                        send_kwargs = dict(
                            caption=ft if m.caption else None,
                            reply_to_message_id=rtmid,
                            progress=prog,
                            progress_args=(c, d, p.id, st, extra, uid),
                        )
                        if m.video:
                            send_kwargs.update(duration=dur, height=h, width=w, thumb=th)
                            sent = await Y.send_video(tcid, f, **send_kwargs)
                        elif m.audio:
                            sent = await Y.send_audio(tcid, f, **send_kwargs)
                        elif m.photo:
                            sent = await Y.send_photo(tcid, f, **send_kwargs)
                        elif m.video_note:
                            sent = await Y.send_video_note(tcid, f, duration=dur,
                                                           progress=prog,
                                                           progress_args=(c, d, p.id, st, extra, uid))
                        elif m.voice:
                            sent = await Y.send_voice(tcid, f, progress=prog,
                                                      progress_args=(c, d, p.id, st, extra, uid))
                        else:
                            sent = await Y.send_document(tcid, f, **send_kwargs)

                        if sent is None:
                            print(f"[large] user upload to {tcid} returned None", flush=True)
                            large_failed.append(tcid)
                        else:
                            print(f"[large] uploaded via user client -> {tcid}", flush=True)
                    except Exception as le:
                        last_large_err = le
                        print(f"[large] user upload to {tcid} failed: {type(le).__name__}: {le}", flush=True)
                        # 用户客户端失败时回退到 bot 直接上传
                        try:
                            if m.video:
                                sent = await c.send_video(tcid, f, caption=ft if m.caption else None,
                                                          thumb=th, duration=dur, height=h, width=w,
                                                          progress=prog,
                                                          progress_args=(c, d, p.id, st, extra, uid),
                                                          reply_to_message_id=rtmid)
                            elif m.audio:
                                sent = await c.send_audio(tcid, f, caption=ft if m.caption else None,
                                                          progress=prog,
                                                          progress_args=(c, d, p.id, st, extra, uid),
                                                          reply_to_message_id=rtmid)
                            elif m.voice:
                                sent = await c.send_voice(tcid, f,
                                                          progress=prog,
                                                          progress_args=(c, d, p.id, st, extra, uid),
                                                          reply_to_message_id=rtmid)
                            elif m.video_note:
                                sent = await c.send_video_note(tcid, f, duration=dur,
                                                              progress=prog,
                                                              progress_args=(c, d, p.id, st, extra, uid),
                                                              reply_to_message_id=rtmid)
                            elif m.photo:
                                sent = await c.send_photo(tcid, f, caption=ft if m.caption else None,
                                                          progress=prog,
                                                          progress_args=(c, d, p.id, st, extra, uid),
                                                          reply_to_message_id=rtmid)
                            else:
                                sent = await c.send_document(tcid, f, caption=ft if m.caption else None,
                                                              progress=prog,
                                                              progress_args=(c, d, p.id, st, extra, uid),
                                                              reply_to_message_id=rtmid)
                            if sent is not None:
                                print(f"[large] uploaded via bot -> {tcid}", flush=True)
                            else:
                                large_failed.append(tcid)
                        except Exception as be:
                            last_large_err = be
                            large_failed.append(tcid)
                            print(f"[large] bot upload to {tcid} failed: {type(be).__name__}: {be}", flush=True)

                # 仍有目标失败时保留文件，便于后续重试
                if f and os.path.exists(f) and not large_failed:
                    os.remove(f)

                if len(large_failed) == len(targets):
                    await c.edit_message_text(d, p.id, '大文件上传失败。')
                    print(f"[large] all {len(targets)} target(s) failed, last error: "
                          f"{type(last_large_err).__name__}: {last_large_err}", flush=True)
                    return 'Failed.'

                if large_failed:
                    ok_n = len(targets) - len(large_failed)
                    print(f"[large] {ok_n}/{len(targets)} target(s) succeeded; "
                          f"failed: {large_failed}", flush=True)
                    await c.edit_message_text(d, p.id,
                                              f'⚠️ 大文件已上传 {ok_n}/{len(targets)} 个目标，'
                                              f'失败频道：{", ".join(str(x) for x in large_failed)}')
                    return 'Partial (Large file).'

                await c.delete_messages(d, p.id)
                return 'Done (Large file).'

            await c.edit_message_text(d, p.id, '正在上传...')
            st = time.time()

            upload_ok = False
            for tcid, rtmid in targets:
                try:
                    video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ogv']
                    audio_extensions = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.opus', '.aiff', '.ac3']
                    file_ext = os.path.splitext(f)[1].lower()
                    if m.video or (m.document and file_ext in video_extensions):
                        mtd = await get_video_metadata(f)
                        dur, h, w = mtd['duration'], mtd['width'], mtd['height']
                        th = await screenshot(f, dur, d)
                        await c.send_video(tcid, video=f, caption=ft if m.caption else None, 
                                        thumb=th, width=w, height=h, duration=dur, 
                                            progress=prog, progress_args=(c, d, p.id, st, extra, uid), 
                                            reply_to_message_id=rtmid)
                    elif m.photo:
                        await c.send_photo(tcid, photo=f, caption=ft if m.caption else None, 
                                        progress=prog, progress_args=(c, d, p.id, st, extra, uid), 
                                        reply_to_message_id=rtmid)
                    elif m.document:
                        await c.send_document(tcid, document=f, caption=ft if m.caption else None, 
                                            progress=prog, progress_args=(c, d, p.id, st, extra, uid), 
                                            reply_to_message_id=rtmid)
                    else:
                        await c.send_document(tcid, document=f, caption=ft if m.caption else None, 
                                            progress=prog, progress_args=(c, d, p.id, st, extra, uid), 
                                            reply_to_message_id=rtmid)
                    upload_ok = True
                except Exception as e:
                    print(f'Upload to {tcid} failed (bot): {e}')
                    try:
                        if u:
                            file_ext = os.path.splitext(f)[1].lower()
                            video_exts = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ogv']
                            if m.video or (m.document and file_ext in video_exts):
                                await u.send_video(tcid, video=f, caption=ft if m.caption else None,
                                                progress=prog, progress_args=(c, d, p.id, st, extra, uid),
                                                reply_to_message_id=rtmid)
                            elif m.photo:
                                await u.send_photo(tcid, photo=f, caption=ft if m.caption else None,
                                                progress=prog, progress_args=(c, d, p.id, st, extra, uid),
                                                reply_to_message_id=rtmid)
                            else:
                                await u.send_document(tcid, document=f, caption=ft if m.caption else None,
                                                    progress=prog, progress_args=(c, d, p.id, st, extra, uid),
                                                    reply_to_message_id=rtmid)
                            upload_ok = True
                    except Exception as ue:
                        print(f'Upload to {tcid} failed (user): {ue}')

            if not upload_ok:
                await c.edit_message_text(d, p.id, '上传失败。')
                if f and os.path.exists(f): os.remove(f)
                return 'Failed.'
            
            if f and os.path.exists(f): os.remove(f)
            await c.delete_messages(d, p.id)
            
            return 'Done.'
            
        elif m.text:
            for tcid, rtmid in targets:
                try:
                    await c.send_message(tcid, text=m.text.markdown, reply_to_message_id=rtmid)
                except Exception as e:
                    print(f'Send text to {tcid} failed: {e}')
            return 'Sent.'
    except Exception as e:
        paths_to_check = []
        if 'f' in locals() and f:
            paths_to_check.extend([f, f + ".temp"])
        if 'c_name' in locals() and c_name:
            possible_path = os.path.join("downloads", c_name)
            paths_to_check.extend([possible_path, possible_path + ".temp", c_name, c_name + ".temp"])
            
        for path in paths_to_check:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
                    
        return f'Error: {str(e)[:50]}'
        
@X.on_message(filters.command(['batch', 'single']))
async def process_cmd(c, m):
    uid = m.from_user.id
    cmd = m.command[0]
    
    if FREEMIUM_LIMIT == 0 and not await is_premium_user(uid):
        await m.reply_text("❌ **此机器人不提供免费服务**，请联系管理员获取订阅。")
        return
    
    if await sub(c, m) == 1: return
    pro = await m.reply_text('🔍 **正在进行预检查，请稍候...**')
    
    if is_user_active(uid):
        await pro.edit('⚠️ **您当前已有正在运行的任务**。请使用 /stop 先取消它。')
        return
    
    ubot = await get_ubot(uid)
    if not ubot:
        from shared_client import app
        ubot = app
    
    Z[uid] = {'step': 'start' if cmd == 'batch' else 'start_single'}
    await pro.edit(f'🔗 **请发送{"起始链接..." if cmd == "batch" else "要处理的链接"}**')

@X.on_message(filters.command(['cancel', 'stop']))
async def cancel_cmd(c, m):
    uid = m.from_user.id
    if is_user_active(uid):
        if await request_batch_cancel(uid):
            await m.reply_text('🚫 任务停止请求已发送。当前文件下载完成后将停止。')
        else:
            # 强制清理状态，以防万一
            await remove_active_batch(uid)
            Z.pop(uid, None)
            await m.reply_text('⚠️ 停止请求失败，已强制重置状态。')
    else:
        Z.pop(uid, None) # 确保 Z 也被清理
        await m.reply_text('目前没有正在运行的任务。')

@X.on_message(filters.text & filters.private & ~login_in_progress & ~filters.command([
    'start', 'batch', 'cancel', 'login', 'logout', 'stop', 'set', 
    'pay', 'redeem', 'gencode', 'single', 'generate', 'keyinfo', 'encrypt', 'decrypt', 'keys', 'setbot', 'rembot']))
async def text_handler(c, m):
    uid = m.from_user.id
    
    # Handle direct links without command
    if uid not in Z:
        if m.text and ("t.me/" in m.text or "telegram.me/" in m.text):
            L = m.text
            i, d, lt = E(L)
            if i and d:
                Z[uid] = {'step': 'process_single', 'cid': i, 'sid': d, 'lt': lt}
            else:
                return
        else:
            return

    s = Z[uid].get('step')
    x = await get_ubot(uid)
    if not x:
        await m.reply("🤖 **请先设置您的机器人 Token**。\n使用 `/setbot [Token]` 或使用默认机器人。")
        x = c # fallback

    if s == 'start':
        L = m.text
        i, d, lt = E(L)
        if not i or not d:
            await m.reply_text('❌ **链接格式无效。**')
            Z.pop(uid, None)
            return
        Z[uid].update({'step': 'count', 'cid': i, 'sid': d, 'lt': lt})
        await m.reply_text('🔢 **请输入要搬运的消息数量：**')

    elif s == 'start_single' or s == 'process_single':
        if s == 'start_single':
            L = m.text
            i, d, lt = E(L)
            if not i or not d:
                await m.reply_text('❌ **链接格式无效。**')
                Z.pop(uid, None)
                return
            Z[uid].update({'step': 'process_single', 'cid': i, 'sid': d, 'lt': lt})
        
        i, s, lt = Z[uid]['cid'], Z[uid]['sid'], Z[uid]['lt']
        pt = await m.reply_text('⏳ **正在提取并处理...**')
        
        ubot = await get_ubot(uid)
        if not ubot:
            from shared_client import app
            ubot = app
        
        uc = await get_uclient(uid)
        if not uc:
            await safe_edit(pt, '❌ **无法继续：未检测到 User Client (电报账号登录状态)。**')
            Z.pop(uid, None)
            return
            
        if is_user_active(uid):
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 强制停止并重置", callback_data=f"force_stop_{uid}")]])
            await safe_edit(pt, '⚠️ 任务正在运行中。如果您确定要开启新任务，请先停止当前任务。', reply_markup=reply_markup)
            Z.pop(uid, None)
            return

        await add_active_batch(uid, {
            "total": 0,
            "current": 0,
            "success": 0,
            "cancel_requested": False,
            "progress_message_id": pt.id
        })

        source_link_single = f"https://t.me/{i}/{s}"
        targets_display = await get_user_data_key(str(m.chat.id), 'chat_id', 'DM')
        await send_log(f"📥 **单条消息搬运**\n用户: `{uid}`\n来源: `{source_link_single}`\n目标: `{targets_display}`")

        try:
            # Check for media group
            messages = []
            try:
                # Use user client to get media group if possible
                messages = await uc.get_media_group(i, s)
            except Exception:
                # Fallback to single message
                msg = await get_msg(ubot, uc, i, s, lt)
                if msg:
                    messages = [msg]

            if messages:
                total = len(messages)
                print(f"Detected {total} messages for grouping.")
                targets = parse_targets(await get_user_data_key(str(m.chat.id), 'chat_id', None), str(m.chat.id))
                if total > 1:
                    got = await process_media_group(ubot, uc, messages, targets, pt, uid, i, lt)
                    if should_cancel(uid):
                        await pt.delete()
                    elif got:
                        await safe_edit(pt, '✅ 媒体组合并发送成功')
                    else:
                        await safe_edit(pt, f'❌ 搬运失败：{total} 个文件一个都没发出去。\n请执行 `docker compose logs bot | grep -E "\\[direct\\]|\\[group\\]|\\[caption\\]"` 查看原因。')
                else:
                    res = await process_msg(ubot, uc, messages[0], str(m.chat.id), lt, uid, i)
                    res = str(res) if res else ''
                    print(f"[single] process_msg result: {res!r}", flush=True)
                    if should_cancel(uid):
                        await pt.delete()
                    elif 'Done' in res or 'Copied' in res or 'Sent' in res:
                        await safe_edit(pt, f'✅ 处理完成：共 {total} 个文件。')
                    elif res == 'Cancelled':
                        await pt.delete()
                    else:
                        await safe_edit(pt, f'❌ 搬运失败：{res}\n请执行 `docker compose logs bot | grep -E "\\[direct\\]|\\[group\\]|\\[caption\\]"` 查看原因。')
            else:
                await safe_edit(pt, 'Message not found')
        except Exception as e:
            await safe_edit(pt, f'Error: {str(e)[:50]}')
        finally:
            await remove_active_batch(uid)
            Z.pop(uid, None)

    elif s == 'count':
        if not m.text.isdigit():
            await m.reply_text('Enter valid number.')
            return
        
        count = int(m.text)
        maxlimit = PREMIUM_LIMIT if await is_premium_user(uid) else FREEMIUM_LIMIT

        if count > maxlimit:
            await m.reply_text(f'Maximum limit is {maxlimit}.')
            return

        Z[uid].update({'step': 'process', 'did': str(m.chat.id), 'num': count})
        i, s, n, lt = Z[uid]['cid'], Z[uid]['sid'], Z[uid]['num'], Z[uid]['lt']
        success = 0

        pt = await m.reply_text('Processing batch...')
        uc = await get_uclient(uid)
        ubot = await get_ubot(uid)
        
        if not ubot:
            from shared_client import app
            ubot = app
            
        if not uc:
            await safe_edit(pt, '❌ **无法继续：未检测到 User Client (电报账号登录状态)。**\n请使用 /login 登录后重试。')
            Z.pop(uid, None)
            return
            
        if is_user_active(uid):
            await safe_edit(pt, 'Active task exists')
            Z.pop(uid, None)
            return
        
        source_link = f"https://t.me/{i}/{s}"
        targets_display = await get_user_data_key(str(m.chat.id), 'chat_id', 'DM')
        await send_log(f"🔄 **批量搬运开始**\n用户: `{uid}`\n来源: `{source_link}`\n数量: `{count}`\n目标: `{targets_display}`")
        
        await add_active_batch(uid, {
            "total": n,
            "current": 0,
            "success": 0,
            "cancel_requested": False,
            "progress_message_id": pt.id
            })
        
        targets = parse_targets(await get_user_data_key(str(m.chat.id), 'chat_id', None), str(m.chat.id))
        try:
            j = 0
            while j < n:
                if should_cancel(uid):
                    await safe_edit(pt, f'Cancelled at {j}/{n}. Success: {success}')
                    break

                await update_batch_progress(uid, j, success)

                mid = int(s) + j
                try:
                    group_msgs = await get_group_msgs(ubot, uc, i, mid)
                except Exception as ge:
                    print(f"Media group detect failed for {mid}: {ge}")
                    group_msgs = []

                if len(group_msgs) > 1:
                    got = 0
                    try:
                        got = await process_media_group(ubot, uc, group_msgs, targets, pt, uid, i, lt)
                    except Exception as ge:
                        print(f"Media group process failed at {mid}: {ge}")

                    if not got:
                        # 合并发送完全失败：必须逐条兜底，绝不丢消息
                        try:
                            cap = await extract_group_caption(group_msgs)
                            for k, gmsg in enumerate(group_msgs):
                                if should_cancel(uid):
                                    break
                                if j + k >= n:
                                    break
                                try:
                                    r = await process_msg(ubot, uc, gmsg, str(m.chat.id), lt, uid, i,
                                                          extra=f"组内第 {k+1}/{len(group_msgs)} 个",
                                                          caption_override=cap, targets_override=targets)
                                    r = str(r) if r else ''
                                    if 'Done' in r or 'Copied' in r or 'Sent' in r:
                                        got += 1
                                    elif 'Cancelled' in r:
                                        break
                                except Exception as e:
                                    print(f"Group fallback failed at {mid}+{k}: {e}")
                                if k < len(group_msgs) - 1:
                                    await asyncio.sleep(10)
                            print(f"Group {mid} fallback done: {got}/{len(group_msgs)} sent")
                        except Exception as ge:
                            print(f"Group fallback error at {mid}: {ge}")

                    processed = min(len(group_msgs), n - j)
                    if got > processed:
                        got = processed
                    success += got
                    j += processed
                else:
                    try:
                        msg = await get_msg(ubot, uc, i, mid, lt)
                        if msg:
                            res = await process_msg(ubot, uc, msg, str(m.chat.id), lt, uid, i)
                            res = str(res) if res else ''
                            print(f"Batch msg {j+1}/{n} (mid={mid}): result='{res}'")
                            if 'Done' in res or 'Copied' in res or 'Sent' in res:
                                success += 1
                            elif 'Cancelled' in res:
                                await safe_edit(pt, f'❌ 任务已取消。成功: {success}/{n}')
                                break
                        else:
                            print(f"Batch msg {j+1}/{n} (mid={mid}): get_msg returned None")
                    except Exception as e:
                        try: await safe_edit(pt, f'{j+1}/{n}: Error - {str(e)[:30]}')
                        except: pass
                    j += 1
                    await asyncio.sleep(10)

            if not should_cancel(uid) and j >= n:
                await m.reply_text(f'Batch Completed ✅ Success: {success}/{n}')
                await send_log(f'✅ **批量搬运完成**\n用户: `{uid}`\n来源: `{source_link}`\n成功: `{success}/{n}`')
        
        finally:
            await remove_active_batch(uid)
            Z.pop(uid, None)




@X.on_callback_query(filters.regex(r"^cancel_(\d+)$"))
async def cancel_callback(c, cb):
    uid = int(cb.matches[0].group(1))
    if cb.from_user.id != uid:
        await cb.answer("这不是您的任务哦 ~", show_alert=True)
        return
    
    await request_batch_cancel(uid)
    Z.pop(uid, None)
    await remove_active_batch(uid)
    await cb.answer("已尝试取消，状态已清理。", show_alert=True)
    try:
        await cb.message.delete()
    except Exception:
        pass

@X.on_callback_query(filters.regex(r"^force_stop_(\d+)$"))
async def force_stop_callback(c, cb):
    uid = int(cb.matches[0].group(1))
    if cb.from_user.id != uid:
        await cb.answer("这不是您的任务哦 ~", show_alert=True)
        return
    
    await remove_active_batch(uid)
    Z.pop(uid, None)
    await cb.answer("状态已强制重置！", show_alert=True)
    try:
        await cb.message.edit("✅ 状态已强制重置，您可以重新发送链接了。")
    except Exception:
        pass
