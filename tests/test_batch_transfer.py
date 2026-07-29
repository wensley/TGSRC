import asyncio
import importlib
import sys
import types
from types import SimpleNamespace


class _Filter:
    def __and__(self, other):
        return self

    def __invert__(self):
        return self


class _Filters:
    text = _Filter()
    private = _Filter()

    @staticmethod
    def command(*args, **kwargs):
        return _Filter()

    @staticmethod
    def regex(*args, **kwargs):
        return _Filter()


class _App:
    def on_message(self, *args, **kwargs):
        return lambda function: function

    def on_callback_query(self, *args, **kwargs):
        return lambda function: function


def _load_batch(monkeypatch):
    monkeypatch.setitem(sys.modules, "config", SimpleNamespace(
        API_ID=1, API_HASH="hash", LOG_GROUP=-100, STRING=None,
        FORCE_SUB=0, FREEMIUM_LIMIT=10, PREMIUM_LIMIT=10,
    ))

    pyrogram = types.ModuleType("pyrogram")
    pyrogram.Client = object
    pyrogram.filters = _Filters()
    pyrogram_types = types.ModuleType("pyrogram.types")
    pyrogram_types.Message = object
    pyrogram_types.InlineKeyboardMarkup = lambda buttons: buttons
    pyrogram_types.InlineKeyboardButton = lambda *args, **kwargs: (args, kwargs)
    pyrogram_errors = types.ModuleType("pyrogram.errors")
    pyrogram_errors.UserNotParticipant = Exception
    monkeypatch.setitem(sys.modules, "pyrogram", pyrogram)
    monkeypatch.setitem(sys.modules, "pyrogram.types", pyrogram_types)
    monkeypatch.setitem(sys.modules, "pyrogram.errors", pyrogram_errors)

    monkeypatch.setitem(sys.modules, "shared_client", SimpleNamespace(app=_App(), userbot=None))
    func = types.ModuleType("utils.func")
    func.get_user_data = lambda *args, **kwargs: None
    func.get_user_data_key = lambda *args, **kwargs: None
    func.screenshot = lambda *args, **kwargs: None
    func.thumbnail = lambda *args, **kwargs: None
    func.get_video_metadata = lambda *args, **kwargs: None
    func.process_text_with_rules = lambda *args, **kwargs: None
    func.is_premium_user = lambda *args, **kwargs: None
    func.E = lambda *args, **kwargs: (None, None, None)
    monkeypatch.setitem(sys.modules, "utils.func", func)
    monkeypatch.setitem(sys.modules, "plugins.settings", SimpleNamespace(rename_file=lambda *args: None))
    monkeypatch.setitem(sys.modules, "plugins.start", SimpleNamespace(subscribe=lambda *args: None))
    monkeypatch.setitem(sys.modules, "utils.custom_filters", SimpleNamespace(login_in_progress=_Filter()))
    monkeypatch.setitem(sys.modules, "utils.encrypt", SimpleNamespace(decrypt_str=lambda value: value))
    sys.modules.pop("plugins.batch", None)
    return importlib.import_module("plugins.batch")


def test_parse_targets_supports_default_and_topics(monkeypatch):
    batch = _load_batch(monkeypatch)

    assert batch.parse_targets(None, "-1001") == [(-1001, None)]
    assert batch.parse_targets("-1002/77, -1003", "-1001") == [(-1002, 77), (-1003, None)]


def test_send_direct_prefers_bot_copy(monkeypatch):
    batch = _load_batch(monkeypatch)

    class Client:
        def __init__(self):
            self.calls = []

        async def copy_message(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    client = Client()
    message = SimpleNamespace(chat=SimpleNamespace(id=-200), id=8)

    assert asyncio.run(batch.send_direct(client, message, -300, "caption", 12)) is True
    assert client.calls == [((-300, -200, 8), {"caption": "caption", "reply_to_message_id": 12})]


def test_send_direct_uses_user_copy_after_bot_copy_failure(monkeypatch):
    batch = _load_batch(monkeypatch)

    class FailingBot:
        async def copy_message(self, *args, **kwargs):
            raise RuntimeError("restricted")

    class UserClient:
        def __init__(self):
            self.calls = []

        async def copy_message(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    user_client = UserClient()
    message = SimpleNamespace(chat=SimpleNamespace(id=-200), id=8)

    assert asyncio.run(batch.send_direct(FailingBot(), message, -300, user_client=user_client)) is True
    assert user_client.calls == [((-300, -200, 8), {"caption": None, "reply_to_message_id": None})]


def test_send_direct_downloads_forwarded_media_instead_of_reusing_file_id(monkeypatch, tmp_path):
    batch = _load_batch(monkeypatch)
    downloaded = tmp_path / "forwarded.jpg"
    downloaded.write_bytes(b"image")

    class Client:
        def __init__(self):
            self.photos = []

        async def copy_message(self, *args, **kwargs):
            raise RuntimeError("restricted")

        async def download_media(self, message, file_name):
            return str(downloaded)

        async def send_photo(self, *args, **kwargs):
            self.photos.append((args, kwargs))

    client = Client()
    message = SimpleNamespace(
        chat=SimpleNamespace(id=-200), id=8, forward_from_chat=SimpleNamespace(id=-400),
        photo=SimpleNamespace(file_id="would-leak-source"), video=None, video_note=None,
        voice=None, sticker=None, audio=None, document=None,
    )

    assert asyncio.run(batch.send_direct(client, message, -300, "caption", 12)) is True
    assert client.photos == [((-300,), {"photo": str(downloaded), "caption": "caption", "reply_to_message_id": 12})]
    assert not downloaded.exists()


def test_media_group_fallback_keeps_portrait_dimensions_and_thumbnail(monkeypatch, tmp_path):
    batch = _load_batch(monkeypatch)
    downloaded = tmp_path / "portrait.mp4"
    downloaded.write_bytes(b"video")
    thumbnail = tmp_path / "portrait.jpg"
    thumbnail.write_bytes(b"thumbnail")

    class Client:
        def __init__(self):
            self.videos = []

        async def copy_media_group(self, *args, **kwargs):
            raise RuntimeError("restricted")

        async def download_media(self, message, file_name):
            return str(downloaded)

        async def send_video(self, *args, **kwargs):
            self.videos.append((args, kwargs))

    async def no_local_metadata(path):
        return {"duration": None, "width": None, "height": None}

    async def generated_thumbnail(path, duration, sender_id):
        return str(thumbnail)

    monkeypatch.setattr(batch, "get_video_metadata", no_local_metadata)
    monkeypatch.setattr(batch, "screenshot", generated_thumbnail)
    client = Client()
    message = SimpleNamespace(
        chat=SimpleNamespace(id=-200), id=8, caption="portrait",
        video=SimpleNamespace(duration=14, width=720, height=1280), video_note=None,
        photo=None, sender_id=99, from_user=None,
    )

    assert asyncio.run(batch.send_direct_group(client, [message], -300, rtmid=12)) is True
    assert client.videos == [((-300,), {
        "video": str(downloaded), "caption": "portrait", "thumb": str(thumbnail),
        "width": 720, "height": 1280, "duration": 14,
        "supports_streaming": True, "reply_to_message_id": 12,
    })]
    assert not downloaded.exists()
    assert not thumbnail.exists()


def test_process_msg_sends_text_to_each_target(monkeypatch):
    batch = _load_batch(monkeypatch)

    async def configured_targets(*args, **kwargs):
        return "-1002/77,-1003"

    monkeypatch.setattr(batch, "get_user_data_key", configured_targets)
    client = SimpleNamespace(sent=[])

    async def send_message(*args, **kwargs):
        client.sent.append((args, kwargs))

    client.send_message = send_message
    message = SimpleNamespace(media=None, text=SimpleNamespace(markdown="hello"))

    assert asyncio.run(batch.process_msg(client, None, message, "-1001", "public", 1, "source")) == "Sent."
    assert client.sent == [
        ((-1002,), {"text": "hello", "reply_to_message_id": 77}),
        ((-1003,), {"text": "hello", "reply_to_message_id": None}),
    ]
