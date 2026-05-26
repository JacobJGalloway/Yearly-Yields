"""
Tests for edge-case paths in app.core.security.
"""

import pytest

from app.core.security import (
    create_refresh_token,
    decode_access_payload,
)


def test_decode_access_payload_wrong_type_returns_none():
    """A refresh token must not decode as an access payload."""
    refresh_tok = create_refresh_token("test-user-id")
    result = decode_access_payload(refresh_tok)
    assert result is None


def test_decode_access_payload_invalid_token_returns_none():
    result = decode_access_payload("not.a.jwt")
    assert result is None


def test_decode_access_payload_success():
    from app.core.security import create_access_token
    token = create_access_token("my-user-id", role="owner")
    payload = decode_access_payload(token)
    assert payload is not None
    assert payload["sub"] == "my-user-id"
    assert payload["role"] == "owner"
