import os
import importlib


def test_d_thumbnail_success(monkeypatch, tmp_path):
    import os, sys, types
    os.environ.setdefault('OWNER_ID', '123456')
    os.environ.setdefault('MASTER_KEY', 'test_master')
    os.environ.setdefault('IV_KEY', 'test_iv')
    sys.modules.setdefault('shared_client', types.SimpleNamespace(client=None, app=None))
    sys.modules.setdefault('telethon', types.ModuleType('telethon'))
    sys.modules.setdefault('telethon.sync', types.ModuleType('telethon.sync'))
    sys.modules.setdefault('telethon.tl', types.ModuleType('telethon.tl'))
    sys.modules.setdefault('telethon.tl.types', types.ModuleType('telethon.tl.types'))
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
    # stub utils.func to avoid cv2 dependency
    uf = types.ModuleType('utils.func')
    def fake_get_video_metadata(path):
        return {'width': 640, 'height': 360, 'duration': 10}
    async def fake_screenshot(path, duration, sender_id):
        return None
    uf.get_video_metadata = fake_get_video_metadata
    uf.screenshot = fake_screenshot
    sys.modules['utils.func'] = uf
    sys.modules.setdefault('yt_dlp', types.ModuleType('yt_dlp'))
    import plugins.ytdl as ytdl
    importlib.reload(ytdl)

    # create fake response
    class DummyResp:
        def __init__(self, content=b'abc'):
            self.status_code = 200
            self._content = content
        def raise_for_status(self):
            return None
        def iter_content(self, chunk_size=8192):
            yield self._content

    def fake_get(url, stream=True, timeout=10):
        return DummyResp(b'data')

    monkeypatch.setattr('plugins.ytdl.requests.Session.get', lambda self, url, stream=True, timeout=10: fake_get(url, stream, timeout))

    save_path = tmp_path / 'thumb.jpg'
    res = ytdl.d_thumbnail('http://example.com/thumb.jpg', str(save_path))
    assert res is not None
    assert os.path.exists(str(save_path))
