from __future__ import annotations

import getpass
import socket


def local_actor_identifier(role: str) -> str:
    user = getpass.getuser() or "unknown-user"
    host = socket.gethostname() or "unknown-host"
    return f"{role or 'unknown'}@{user}/{host}"
