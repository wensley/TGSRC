# Copyright (c) 2025 devgagan : https://github.com/devgaganin.
# Licensed under the GNU General Public License v3.0.
# See LICENSE file in the repository root for full license text.
"""Safety patches for Pyrogram/pyrofork sessions.

Pyrofork 2.3.x schedules ``Session.restart()`` from several independent
tasks (ping worker, receive worker and packet handler) without any
serialization.  When two restarts overlap, ``stop()`` can close a
connection that was already replaced by ``start()`` and an old
``recv_worker`` ends up reading the same connection as the new one.  That
produces::

    RuntimeError: read() called while another coroutine is already
    waiting for incoming data

and leaks TCP sockets in ``CLOSE_WAIT``.

The patch below serializes restarts with an ``asyncio.Lock`` and drops
duplicate restart requests while one is already running.
"""

from __future__ import annotations

import asyncio

_PATCH_FLAG = "_tgsrc_restart_patch"


def install_pyrogram_session_patch() -> None:
    """Install the restart-serialization patch once per process."""
    from pyrogram.session.session import Session

    if getattr(Session, _PATCH_FLAG, False):
        return

    original_start = Session.start
    original_restart = Session.restart

    async def start(self):
        # Marks the session as being in its (re)connection handshake so a
        # packet-handler restart cannot race with the initial start().
        self._tgsrc_starting = True
        try:
            return await original_start(self)
        finally:
            self._tgsrc_starting = False

    async def restart(self):
        # A start() is already in progress (initial connect or the start
        # half of another restart): there is nothing to do.
        if getattr(self, "_tgsrc_starting", False):
            return

        # Coalesce duplicate restart requests coming from ping/recv/packet
        # handlers.  The request that is already running performs the same
        # stop()+start() sequence.
        if getattr(self, "_tgsrc_restart_pending", False):
            return

        lock = getattr(self, "_tgsrc_restart_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            self._tgsrc_restart_lock = lock

        self._tgsrc_restart_pending = True
        try:
            async with lock:
                await original_restart(self)
        finally:
            self._tgsrc_restart_pending = False

    Session.start = start
    Session.restart = restart
    setattr(Session, _PATCH_FLAG, True)

    print("[pyrogram_guard] session restart serialization patch installed", flush=True)
