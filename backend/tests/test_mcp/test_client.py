"""
Tests for app/mcp/client.py — MCP server lifecycle.

Uses mocks so the actual subprocess and MCP transport are never spawned.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.mcp.client as mcp_client
from app.mcp.client import get_session, start_mcp_server, stop_mcp_server

pytestmark = pytest.mark.asyncio


async def test_get_session_raises_when_not_initialized():
    """get_session() must raise RuntimeError when MCP server has not started."""
    original = mcp_client._session
    mcp_client._session = None
    try:
        with pytest.raises(RuntimeError, match="MCP server not initialized"):
            get_session()
    finally:
        mcp_client._session = original


async def test_stop_mcp_server_cleans_up_globals():
    """stop_mcp_server() exits both context managers and nulls all globals."""
    mock_session_ctx = AsyncMock()
    mock_client_ctx = AsyncMock()

    mcp_client._session_ctx = mock_session_ctx
    mcp_client._client_ctx = mock_client_ctx
    mcp_client._session = MagicMock()

    await stop_mcp_server()

    mock_session_ctx.__aexit__.assert_called_once_with(None, None, None)
    mock_client_ctx.__aexit__.assert_called_once_with(None, None, None)
    assert mcp_client._session is None
    assert mcp_client._session_ctx is None
    assert mcp_client._client_ctx is None


async def test_stop_mcp_server_tolerates_exit_exceptions():
    """stop_mcp_server() swallows exceptions from __aexit__ without raising."""
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aexit__.side_effect = Exception("connection reset")
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aexit__.side_effect = Exception("pipe broken")

    mcp_client._session_ctx = mock_session_ctx
    mcp_client._client_ctx = mock_client_ctx
    mcp_client._session = MagicMock()

    await stop_mcp_server()  # must not raise

    assert mcp_client._session is None


async def test_start_mcp_server_initializes_session():
    """start_mcp_server() wires up the client/session context managers."""
    mock_read = MagicMock()
    mock_write = MagicMock()

    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))

    mock_session = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)

    with patch("app.mcp.client.stdio_client", return_value=mock_client_ctx), \
         patch("app.mcp.client.ClientSession", return_value=mock_session_ctx):
        await start_mcp_server()

    assert mcp_client._session is mock_session
    assert mcp_client._session_ctx is mock_session_ctx
    assert mcp_client._client_ctx is mock_client_ctx

    # Cleanup
    mcp_client._session = None
    mcp_client._session_ctx = None
    mcp_client._client_ctx = None
