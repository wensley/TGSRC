import traceback
# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

import asyncio
from shared_client import start_client
import importlib
import os
import sys

async def load_and_run_plugins():
    await start_client()
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
            # Gracefully shut down async generators
            loop.run_until_complete(loop.shutdown_asyncgens())
            # Cancel all pending tasks before closing the loop
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            # Let cancelled tasks finish winding down
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
        except Exception:
            pass
