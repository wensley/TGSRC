import traceback
# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

import asyncio
from shared_client import start_client
import importlib
import os
import sys

async def pyrogram_watchdog(app, max_down_seconds: int = 120):
    """Restart the container if the Pyrogram session stays down too long.

    A transient reconnect normally takes a few seconds.  If the session is
    still not started after ``max_down_seconds`` the process is in a broken
    restart loop; exiting lets Docker's ``restart: always`` policy recover
    it with a clean state (and clears leaked sockets).
    """
    print(f"[watchdog] started (threshold={max_down_seconds}s)", flush=True)
    down_since = None
    while True:
        await asyncio.sleep(30)
        try:
            session = getattr(app, "session", None)
            alive = bool(session is not None and session.is_started.is_set())
        except Exception:
            alive = False

        if alive:
            if down_since is not None:
                print("[watchdog] Pyrogram session recovered", flush=True)
            down_since = None
            continue

        now = asyncio.get_event_loop().time()
        if down_since is None:
            down_since = now
            print("[watchdog] Pyrogram session is down, waiting for recovery...", flush=True)
        elif now - down_since >= max_down_seconds:
            print(
                f"[watchdog] Pyrogram session down for more than {max_down_seconds}s; "
                "exiting so Docker can restart the bot",
                flush=True,
            )
            os._exit(1)


async def load_and_run_plugins():
    client, app, userbot = await start_client()
    # Keep a strong reference for the lifetime of the client so the task
    # cannot be garbage-collected while it is sleeping.
    app._tgsrc_watchdog_task = asyncio.create_task(pyrogram_watchdog(app))
    plugin_dir = "plugins"
    plugins = [f[:-3] for f in os.listdir(plugin_dir) if f.endswith(".py") and f != "__init__.py"]

    for plugin in plugins:
        module = importlib.import_module(f"plugins.{plugin}")
        if hasattr(module, f"run_{plugin}_plugin"):
            print(f"Running {plugin} plugin...")
            await getattr(module, f"run_{plugin}_plugin")()  

async def main():
    await load_and_run_plugins()
    while True:
        await asyncio.sleep(1)  

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    print("Starting clients ...")
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            loop.close()
        except Exception:
            pass
