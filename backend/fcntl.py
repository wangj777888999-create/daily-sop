"""Windows compatibility shim for the fcntl module.

On Linux, fcntl provides file locking. On Windows, we use msvcrt instead.
This module provides the same API used by sops/storage.py and artifacts.py.
"""
import msvcrt

LOCK_SH = 1
LOCK_EX = 2
LOCK_UN = 4


def flock(fd, operation):
    """Emulate fcntl.flock on Windows using msvcrt locking."""
    if operation == LOCK_UN:
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
        return

    # LOCK_EX or LOCK_SH → both map to exclusive lock on Windows
    try:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    except OSError:
        # Already locked — for read operations, proceed without lock
        if operation == LOCK_SH:
            return
        raise
