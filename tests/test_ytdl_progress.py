import importlib
import time


def test_progress_callback_returns_string():
    import os, sys, types
    # Ensure config import does not fail
    importlib.reload(importlib.import_module('importlib'))
    os.environ.setdefault('OWNER_ID', '123456')
    os.environ.setdefault('MASTER_KEY', 'test_master')
    os.environ.setdefault('IV_KEY', 'test_iv')
    # Provide minimal dummy modules to satisfy top-level imports
    sys.modules.setdefault('shared_client', types.SimpleNamespace(client=None, app=None))
    sys.modules.setdefault('telethon', types.ModuleType('telethon'))
    sys.modules.setdefault('telethon.sync', types.ModuleType('telethon.sync'))
    sys.modules.setdefault('telethon.tl', types.ModuleType('telethon.tl'))
    sys.modules.setdefault('telethon.tl.types', types.ModuleType('telethon.tl.types'))
    # stub utils.func to avoid heavy dependencies like cv2
    uf = types.ModuleType('utils.func')
    def fake_get_video_metadata(path):
        return {'width': 1280, 'height': 720, 'duration': 60}
    async def fake_screenshot(path, duration, sender_id):
        return None
    uf.get_video_metadata = fake_get_video_metadata
    uf.screenshot = fake_screenshot
    sys.modules['utils.func'] = uf
    sys.modules.setdefault('aiohttp', types.ModuleType('aiohttp'))
    sys.modules.setdefault('aiofiles', types.ModuleType('aiofiles'))
    # stub mutagen to avoid import errors
    mm = types.ModuleType('mutagen')
    mm.id3 = types.ModuleType('mutagen.id3')
    mm.mp3 = types.ModuleType('mutagen.mp3')
    class DummyTag(dict):
        pass
    class DummyID3: pass
    class DummyTIT2: pass
    class DummyTPE1: pass
    class DummyCOMM: pass
    class DummyAPIC: pass
    class DummyMP3:
        def __init__(self, *args, **kwargs):
            self.tags = DummyTag()
        def add_tags(self):
            return None
        def save(self):
            return None
    mm.id3.ID3 = DummyID3
    mm.id3.TIT2 = DummyTIT2
    mm.id3.TPE1 = DummyTPE1
    mm.id3.COMM = DummyCOMM
    mm.id3.APIC = DummyAPIC
    mm.mp3.MP3 = DummyMP3
    sys.modules['mutagen'] = mm
    sys.modules['mutagen.id3'] = mm.id3
    sys.modules['mutagen.mp3'] = mm.mp3
    sys.modules.setdefault('yt_dlp', types.ModuleType('yt_dlp'))
    import plugins.ytdl as ytdl
    importlib.reload(ytdl)

    user_id = 12345
    # ensure previous state exists
    ytdl.user_progress.pop(user_id, None)
    # simulate initial state
    ytdl.user_progress[user_id] = {'previous_done': 0, 'previous_time': time.time() - 1}

    done = 1024 * 1024 * 5  # 5 MB
    total = 1024 * 1024 * 10  # 10 MB
    out = ytdl.progress_callback(done, total, user_id)
    assert isinstance(out, str)
    assert '进度' in out or 'Progress' in out
