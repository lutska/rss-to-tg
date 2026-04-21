"""Unit tests for secret_store.py (Task 5.1).

Requirements: 4.3
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock
from botocore.exceptions import ClientError

import pytest

import secret_store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ssm_client(bot_token="tok123", chat_id="chat456"):
    """Return a mock SSM client that returns the given values."""
    client = MagicMock()

    def _get_parameter(Name, WithDecryption=False):
        values = {
            "/notifier/telegram/bot_token": bot_token,
            "/notifier/telegram/chat_id": chat_id,
        }
        if Name not in values:
            error = {"Error": {"Code": "ParameterNotFound", "Message": "not found"}}
            raise ClientError(error, "GetParameter")
        return {"Parameter": {"Value": values[Name]}}

    client.get_parameter.side_effect = _get_parameter
    return client


# ---------------------------------------------------------------------------
# Tests: successful load
# ---------------------------------------------------------------------------

def test_load_secrets_returns_correct_keys():
    """Successful SSM call returns dict with bot_token and chat_id."""
    client = _make_ssm_client(bot_token="mytoken", chat_id="mychat")
    result = secret_store.load_secrets(client)
    assert result == {"bot_token": "mytoken", "chat_id": "mychat"}


def test_load_secrets_uses_with_decryption():
    """get_parameter must be called with WithDecryption=True for SecureString."""
    client = _make_ssm_client()
    secret_store.load_secrets(client)
    for call in client.get_parameter.call_args_list:
        assert call.kwargs.get("WithDecryption") is True or call[1].get("WithDecryption") is True


def test_load_secrets_reads_default_paths(monkeypatch):
    """Default SSM paths are used when env vars are not set."""
    monkeypatch.delenv("SSM_BOT_TOKEN_PATH", raising=False)
    monkeypatch.delenv("SSM_CHAT_ID_PATH", raising=False)

    client = _make_ssm_client()
    secret_store.load_secrets(client)

    called_paths = [call.kwargs.get("Name") or call[1].get("Name") or call[0][0]
                    for call in client.get_parameter.call_args_list]
    assert "/notifier/telegram/bot_token" in called_paths
    assert "/notifier/telegram/chat_id" in called_paths


def test_load_secrets_reads_custom_paths(monkeypatch):
    """Custom SSM paths from env vars are used when set."""
    monkeypatch.setenv("SSM_BOT_TOKEN_PATH", "/custom/bot")
    monkeypatch.setenv("SSM_CHAT_ID_PATH", "/custom/chat")

    client = MagicMock()
    client.get_parameter.return_value = {"Parameter": {"Value": "val"}}

    secret_store.load_secrets(client)

    called_paths = [call.kwargs.get("Name") or call[1].get("Name") or call[0][0]
                    for call in client.get_parameter.call_args_list]
    assert "/custom/bot" in called_paths
    assert "/custom/chat" in called_paths


# ---------------------------------------------------------------------------
# Tests: SSM unavailable / missing secret → exception raised
# ---------------------------------------------------------------------------

def test_load_secrets_raises_on_ssm_client_error():
    """ClientError from SSM propagates — no swallowing (Requirement 4.3)."""
    client = MagicMock()
    error = {"Error": {"Code": "InternalServerError", "Message": "oops"}}
    client.get_parameter.side_effect = ClientError(error, "GetParameter")

    with pytest.raises(ClientError):
        secret_store.load_secrets(client)


def test_load_secrets_raises_when_bot_token_missing():
    """ParameterNotFound for bot_token propagates immediately."""
    client = MagicMock()

    def _get(Name, WithDecryption=False):
        if "bot_token" in Name:
            error = {"Error": {"Code": "ParameterNotFound", "Message": "not found"}}
            raise ClientError(error, "GetParameter")
        return {"Parameter": {"Value": "chat456"}}

    client.get_parameter.side_effect = _get

    with pytest.raises(ClientError):
        secret_store.load_secrets(client)


def test_load_secrets_raises_when_chat_id_missing():
    """ParameterNotFound for chat_id propagates immediately."""
    client = MagicMock()

    def _get(Name, WithDecryption=False):
        if "chat_id" in Name:
            error = {"Error": {"Code": "ParameterNotFound", "Message": "not found"}}
            raise ClientError(error, "GetParameter")
        return {"Parameter": {"Value": "tok123"}}

    client.get_parameter.side_effect = _get

    with pytest.raises(ClientError):
        secret_store.load_secrets(client)


def test_load_secrets_raises_on_empty_value():
    """An empty parameter value raises ValueError (Requirement 4.3)."""
    client = MagicMock()
    client.get_parameter.return_value = {"Parameter": {"Value": ""}}

    with pytest.raises(ValueError):
        secret_store.load_secrets(client)
