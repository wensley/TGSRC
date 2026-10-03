# Copyright (c) 2025 devgagan : https://github.com/devgaganin.
# Licensed under the GNU General Public License v3.0.
# See LICENSE file in the repository root for full license text.

import concurrent.futures
import time
import os
import re
import uuid
import cv2
import logging
import asyncio
import json
from datetime import datetime, timedelta
import redis.asyncio as aioredis
from config import REDIS_URL

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

PUBLIC_LINK_PATTERN = re.compile(r'(https?://)?(t\.me|telegram\.me)/([^/]+)(/(\d+))?')
PRIVATE_LINK_PATTERN = re.compile(r'(https?://)?(t\.me|telegram\.me)/c/(\d+)(/(\d+))?')
VIDEO_EXTENSIONS = {"mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "mpeg", "mpg", "3gp"}

_redis_pool = None
_redis_lock = asyncio.Lock()

_JSON_PREFIX = "_JS_"

async def get_redis():
    global _redis_pool
    if _redis_pool is None:
        async with _redis_lock:
            if _redis_pool is None:
                _redis_pool = aioredis.from_url(
                    REDIS_URL,
                    decode_responses=True,
                    socket_keepalive=True,
                    health_check_interval=30
                )
    return _redis_pool

async def close_redis():
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None

def _serialize(value):
    if isinstance(value, (dict, list, bool)):
        return _JSON_PREFIX + json.dumps(value)
    return str(value)

def _deserialize(value, default=None):
    if value is None:
        return default
    if isinstance(value, str) and value.startswith(_JSON_PREFIX):
        try:
            return json.loads(value[len(_JSON_PREFIX):])
        except (json.JSONDecodeError, TypeError):
            return value[len(_JSON_PREFIX):]
    return value

# ------- < start > Session Encoder don't change -------

a1 = "c2F2ZV9yZXN0cmljdGVkX2NvbnRlbnRfYm90cw=="
a2 = "Nzk2"
a3 = "Z2V0X21lc3NhZ2Vz" 
a4 = "cmVwbHlfcGhvdG8=" 
a5 = "c3RhcnQ="
attr1 = "cGhvdG8="
attr2 = "ZmlsZV9pZA=="
a7 = "SGkg8J+RiyBXZWxjb21lLCBXYW5uYSBpbnRyby4uLj8gCgrinLPvuI8gSSBjYW4gc2F2ZSBwb3N0cyBmcm9tIGNoYW5uZWxzIG9yIGdyb3VwcyB3aGVyZSBmb3J3YXJkaW5nIGlzIG9mZi4gSSBjYW4gZG93bmxvYWQgdmlkZW9zL2F1ZGlvIGZyb20gWVQsIElOU1RBLCAuLi4gc29jaWFsIHBsYXRmb3JtcwrinLPvuI8gU2ltcGx5IHNlbmQgdGhlIHBvc3QgbGluayBvZiBhIHB1YmxpYyBjaGFubmVsLiBGb3IgcHJpdmF0ZSBjaGFubmVscywgZG8gL2xvZ2luLiBTZW5kIC9oZWxwIHRvIGtub3cgbW9yZS4="
a8 = "Sm9pbiBDaGFubmVs"
a9 = "R2V0IFByZW1pdW0=" 
a10 = "aHR0cHM6Ly90Lm1lL3hpeWlheWE=" 
a11 = "aHR0cHM6Ly90Lm1lL3hpeWlheWE=" 

# ------- < end > Session Encoder don't change --------

def is_private_link(link):
    return bool(PRIVATE_LINK_PATTERN.match(link))


def thumbnail(sender):
    return f'{sender}.jpg' if os.path.exists(f'{sender}.jpg') else None


def hhmmss(seconds):
    return time.strftime('%H:%M:%S', time.gmtime(seconds))


def E(L):   
    private_match = re.match(r'https://t\.me/c/(\d+)/(?:\d+/)?(\d+)', L)
    public_match = re.match(r'https://t\.me/([^/]+)/(?:\d+/)?(\d+)', L)
    
    if private_match:
        return f'-100{private_match.group(1)}', int(private_match.group(2)), 'private'
    elif public_match:
        return public_match.group(1), int(public_match.group(2)), 'public'
    
    return None, None, None


def get_display_name(user):
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    elif user.first_name:
        return user.first_name
    elif user.last_name:
        return user.last_name
    elif user.username:
        return user.username
    else:
        return "Unknown User"


def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


def get_dummy_filename(info):
    file_type = info.get("type", "file")
    extension = {
        "video": "mp4",
        "photo": "jpg",
        "document": "pdf",
        "audio": "mp3"
    }.get(file_type, "bin")
    
    return f"downloaded_file_{int(time.time())}.{extension}"


async def is_private_chat(event):
    return event.is_private


async def save_user_data(user_id, key, value):
    r = await get_redis()
    await r.hset(f"user:{user_id}", key, _serialize(value))


async def get_user_data_key(user_id, key, default=None):
    r = await get_redis()
    val = await r.hget(f"user:{user_id}", key)
    return _deserialize(val, default)


async def get_user_data(user_id):
    r = await get_redis()
    data = await r.hgetall(f"user:{user_id}")
    if not data:
        return None
    result = {}
    for k, v in data.items():
        result[k] = _deserialize(v)
    return result


async def delete_user_data_field(user_id, key):
    r = await get_redis()
    await r.hdel(f"user:{user_id}", key)


async def delete_user_data_fields(user_id, keys):
    r = await get_redis()
    await r.hdel(f"user:{user_id}", *keys)


async def save_user_session(user_id, session_string):
    r = await get_redis()
    await r.hset(f"user:{user_id}", "session_string", _serialize(session_string))
    await r.hset(f"user:{user_id}", "updated_at", _serialize(datetime.now().isoformat()))
    logger.info(f"Saved session for user {user_id}")
    return True


async def remove_user_session(user_id):
    r = await get_redis()
    await r.hdel(f"user:{user_id}", "session_string")
    logger.info(f"Removed session for user {user_id}")
    return True


async def save_user_bot(user_id, bot_token):
    r = await get_redis()
    await r.hset(f"user:{user_id}", "bot_token", _serialize(bot_token))
    await r.hset(f"user:{user_id}", "updated_at", _serialize(datetime.now().isoformat()))
    logger.info(f"Saved bot token for user {user_id}")
    return True


async def remove_user_bot(user_id):
    r = await get_redis()
    await r.hdel(f"user:{user_id}", "bot_token")
    logger.info(f"Removed bot token for user {user_id}")
    return True


_MARKDOWN_LINK_PATTERN = re.compile(r'\[[^\]]*\]\(\s*(?:https?://|www\.)[^)]*\)')
_URL_PATTERN = re.compile(r'(?:https?://|www\.)[^\s<>"\'()\[\]]+')
_MENTION_PATTERN = re.compile(r'(?<![\w.])@[A-Za-z][A-Za-z0-9_]{4,31}')


def strip_mentions_and_links(text):
    """移除 caption 中的 @用户名、http/https 链接与裸 www 域名，并清理多余空白。"""
    if not text:
        return text

    cleaned = _MARKDOWN_LINK_PATTERN.sub(" ", text)
    cleaned = _URL_PATTERN.sub(" ", cleaned)
    cleaned = _MENTION_PATTERN.sub(" ", cleaned)

    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'[ \t]*\n[ \t]*', '\n', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


async def process_text_with_rules(user_id, text):
    if not text:
        return ""
    
    try:
        replacements = await get_user_data_key(user_id, "replacement_words", {})
        delete_words = await get_user_data_key(user_id, "delete_words", [])
        
        processed_text = text
        for word, replacement in replacements.items():
            processed_text = processed_text.replace(word, replacement)
        
        if delete_words:
            words = processed_text.split()
            filtered_words = [w for w in words if w not in delete_words]
            processed_text = " ".join(filtered_words)
        
        return strip_mentions_and_links(processed_text)
    except Exception as e:
        logger.error(f"Error processing text with rules: {e}")
        return text


async def screenshot(video: str, duration: int, sender: str) -> str | None:
    existing_screenshot = f"{sender}.jpg"
    if os.path.exists(existing_screenshot):
        return existing_screenshot

    time_stamp = hhmmss(duration // 2)
    output_file = f"ss_{uuid.uuid4().hex}.jpg"

    cmd = [
        "ffmpeg",
        "-ss", time_stamp,
        "-i", video,
        "-frames:v", "1",
        output_file,
        "-y"
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()

    if os.path.isfile(output_file):
        return output_file
    else:
        print(f"FFmpeg Error: {stderr.decode().strip()}")
        return None


async def get_video_metadata(file_path):
    default_values = {'width': 1, 'height': 1, 'duration': 1}
    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    
    try:
        def _extract_metadata():
            try:
                vcap = cv2.VideoCapture(file_path)
                if not vcap.isOpened():
                    return default_values

                width = round(vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = round(vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = vcap.get(cv2.CAP_PROP_FPS)
                frame_count = vcap.get(cv2.CAP_PROP_FRAME_COUNT)

                if fps <= 0:
                    return default_values

                duration = round(frame_count / fps)
                if duration <= 0:
                    return default_values

                vcap.release()
                return {'width': width, 'height': height, 'duration': duration}
            except Exception as e:
                logger.error(f"Error in video_metadata: {e}")
                return default_values
        
        return await loop.run_in_executor(executor, _extract_metadata)
        
    except Exception as e:
        logger.error(f"Error in get_video_metadata: {e}")
        return default_values


async def add_premium_user(user_id, duration_value, duration_unit):
    try:
        now = datetime.now()
        
        unit_map = {
            "min": "minutes", "hours": "hours", "days": "days",
            "weeks": "weeks", "month": "days", "year": "days", "decades": "days"
        }
        value_map = {
            "min": duration_value, "hours": duration_value, "days": duration_value,
            "weeks": duration_value, "month": duration_value * 30,
            "year": duration_value * 365, "decades": duration_value * 3650
        }
        
        unit = unit_map.get(duration_unit)
        if not unit:
            return False, "Invalid duration unit"
        
        kwargs = {unit: value_map[duration_unit]}
        expiry_date = now + timedelta(**kwargs)
        
        r = await get_redis()
        key = f"premium:{user_id}"
        
        data = {
            "user_id": str(user_id),
            "subscription_start": now.timestamp(),
            "subscription_end": expiry_date.timestamp(),
            "expireAt": expiry_date.timestamp()
        }
        
        for k, v in data.items():
            await r.hset(key, k, _serialize(v))
        
        return True, expiry_date
    except Exception as e:
        logger.error(f"Error adding premium user {user_id}: {e}")
        return False, str(e)


async def is_premium_user(user_id):
    try:
        r = await get_redis()
        end_ts = await r.hget(f"premium:{user_id}", "subscription_end")
        if end_ts is None:
            return False
        end_val = _deserialize(end_ts)
        now = datetime.now().timestamp()
        return now < float(end_val)
    except Exception as e:
        logger.error(f"Error checking premium status for {user_id}: {e}")
        return False


async def get_premium_details(user_id):
    try:
        r = await get_redis()
        data = await r.hgetall(f"premium:{user_id}")
        if not data or "subscription_end" not in data:
            return None
        
        result = {}
        for k, v in data.items():
            result[k] = _deserialize(v)
        
        if "subscription_end" in result:
            result["subscription_end"] = datetime.fromtimestamp(float(result["subscription_end"]))
        if "subscription_start" in result:
            result["subscription_start"] = datetime.fromtimestamp(float(result["subscription_start"]))
        
        return result
    except Exception as e:
        logger.error(f"Error getting premium details for {user_id}: {e}")
        return None


async def remove_premium_user(user_id):
    r = await get_redis()
    return await r.delete(f"premium:{user_id}")
