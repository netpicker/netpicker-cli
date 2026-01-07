from __future__ import annotations
import os
import tempfile

def atomic_write(path: str, data: bytes) -> None:
    """Atomically write data to a file.
    
    Args:
        path: Target file path
        data: Binary data to write
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".np-", dir=os.path.dirname(path) or ".")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
