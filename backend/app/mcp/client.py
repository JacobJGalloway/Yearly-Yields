"""
MCP server lifecycle — start/stop and session accessor.

Called from app/main.py lifespan. Agent modules use get_session()
to call tools without managing the connection themselves.
"""

import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.config import settings

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

_client_ctx = None
_session_ctx = None
_session: ClientSession | None = None


async def start_mcp_server() -> None:
    global _client_ctx, _session_ctx, _session

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp.server"],
        env={
            "DATABASE_URL": settings.DATABASE_URL,
            "PYTHONPATH": str(_BACKEND_DIR),
        },
        cwd=str(_BACKEND_DIR),
    )
    _client_ctx = stdio_client(params)
    read, write = await _client_ctx.__aenter__()

    _session_ctx = ClientSession(read, write)
    _session = await _session_ctx.__aenter__()
    await _session.initialize()


async def stop_mcp_server() -> None:
    global _client_ctx, _session_ctx, _session

    if _session_ctx is not None:
        try:
            await _session_ctx.__aexit__(None, None, None)
        except Exception:
            pass
    if _client_ctx is not None:
        try:
            await _client_ctx.__aexit__(None, None, None)
        except Exception:
            pass

    _session = None
    _session_ctx = None
    _client_ctx = None


def get_session() -> ClientSession:
    if _session is None:
        raise RuntimeError("MCP server not initialized — call start_mcp_server() first")
    return _session
