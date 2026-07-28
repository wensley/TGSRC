import sys, types, traceback

# Set minimal stubs similar to tests
sys.modules.setdefault('shared_client', types.SimpleNamespace(client=None, app=None))
sys.modules.setdefault('telethon', types.ModuleType('telethon'))
sys.modules.setdefault('telethon.sync', types.ModuleType('telethon.sync'))
sys.modules.setdefault('telethon.tl', types.ModuleType('telethon.tl'))
sys.modules.setdefault('telethon.tl.types', types.ModuleType('telethon.tl.types'))
# stub utils.func
uf = types.ModuleType('utils.func')
uf.get_video_metadata = lambda path: {'width': 640, 'height': 360, 'duration': 10}
async def fake_screenshot(path, duration, sender_id):
    return None
uf.screenshot = fake_screenshot
sys.modules['utils.func'] = uf
# stub mutagen
mm = types.ModuleType('mutagen')
mm.id3 = types.ModuleType('mutagen.id3')
mm.mp3 = types.ModuleType('mutagen.mp3')
class DummyTag(dict): pass
class DummyID3: pass
class DummyTIT2: pass
class DummyTPE1: pass
class DummyCOMM: pass
class DummyAPIC: pass
class DummyMP3:
    def __init__(self, *a, **k):
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
# Ensure required env vars for config
import os
os.environ.setdefault('OWNER_ID', '123456')
os.environ.setdefault('MASTER_KEY', 'test_master')
os.environ.setdefault('IV_KEY', 'test_iv')

try:
    import plugins.ytdl as ytdl
    print('Imported plugins.ytdl successfully')
except Exception:
    traceback.print_exc()

print('done')
