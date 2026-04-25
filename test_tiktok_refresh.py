"""Tests for tiktok_api OAuth refresh / bootstrap."""

from unittest.mock import Mock, patch

import pytest
import requests

import tiktok_api


@pytest.fixture(autouse=True)
def _tiktok_env(monkeypatch):
    """Default env for every test — individual tests can override or delete."""
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "ck_test")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "cs_test")
    monkeypatch.setenv("TIKTOK_REFRESH_TOKEN", "rt_old")


def _mock_response(status: int, payload: dict | None = None, text: str | None = None) -> Mock:
    resp = Mock()
    resp.status_code = status
    if payload is not None:
        resp.json = Mock(return_value=payload)
        resp.text = ""
    else:
        resp.json = Mock(side_effect=ValueError("no json"))
        resp.text = text or ""
    return resp


class TestRefreshAccessToken:
    def test_success_returns_rotated_tokens(self, monkeypatch):
        mock_resp = _mock_response(200, {
            "access_token": "at_new",
            "refresh_token": "rt_new",
            "expires_in": 86400,
            "refresh_expires_in": 31536000,
            "scope": "video.publish",
            "open_id": "open_xyz",
        })
        with patch("tiktok_api.requests.post", return_value=mock_resp) as mock_post:
            result = tiktok_api.refresh_access_token()

        assert result["ok"] is True
        assert result["access_token"] == "at_new"
        assert result["refresh_token"] == "rt_new"
        assert result["expires_in"] == 86400

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["data"]["grant_type"] == "refresh_token"
        assert kwargs["data"]["refresh_token"] == "rt_old"
        assert kwargs["data"]["client_key"] == "ck_test"

    def test_invalid_grant_returns_structured_error(self):
        """Expired refresh token — the failure users actually see in production."""
        mock_resp = _mock_response(200, {
            "error": "invalid_grant",
            "error_description": "Refresh token is expired or revoked",
            "log_id": "log_abc",
        })
        with patch("tiktok_api.requests.post", return_value=mock_resp):
            result = tiktok_api.refresh_access_token()

        assert result["ok"] is False
        assert "invalid_grant" in result["error"]
        assert "expired or revoked" in result["error"]

    def test_missing_env_vars_reported_by_name(self, monkeypatch):
        monkeypatch.delenv("TIKTOK_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("TIKTOK_REFRESH_TOKEN", raising=False)

        result = tiktok_api.refresh_access_token()

        assert result["ok"] is False
        assert "TIKTOK_CLIENT_SECRET" in result["error"]
        assert "TIKTOK_REFRESH_TOKEN" in result["error"]
        assert "TIKTOK_CLIENT_KEY" not in result["error"]  # still set

    def test_network_timeout_handled(self):
        with patch(
            "tiktok_api.requests.post",
            side_effect=requests.Timeout("connection timed out"),
        ):
            result = tiktok_api.refresh_access_token()

        assert result["ok"] is False
        assert "timed out" in result["error"].lower()

    def test_non_json_response_handled(self):
        mock_resp = _mock_response(502, payload=None, text="<html>Bad gateway</html>")
        with patch("tiktok_api.requests.post", return_value=mock_resp):
            result = tiktok_api.refresh_access_token()

        assert result["ok"] is False
        assert "Non-JSON" in result["error"] or "502" in result["error"]

    def test_echoes_old_refresh_token_when_rotation_disabled(self):
        """Some apps don't rotate — response omits refresh_token. Echo the old one."""
        mock_resp = _mock_response(200, {
            "access_token": "at_new",
            "expires_in": 86400,
            "refresh_expires_in": 31536000,
        })
        with patch("tiktok_api.requests.post", return_value=mock_resp):
            result = tiktok_api.refresh_access_token()

        assert result["ok"] is True
        assert result["refresh_token"] == "rt_old"

    def test_explicit_args_override_env(self, monkeypatch):
        monkeypatch.delenv("TIKTOK_CLIENT_KEY", raising=False)
        mock_resp = _mock_response(200, {
            "access_token": "at_new",
            "refresh_token": "rt_new",
            "expires_in": 86400,
            "refresh_expires_in": 31536000,
        })
        with patch("tiktok_api.requests.post", return_value=mock_resp) as mock_post:
            result = tiktok_api.refresh_access_token(
                client_key="ck_arg", client_secret="cs_arg", refresh_token="rt_arg",
            )

        assert result["ok"] is True
        _, kwargs = mock_post.call_args
        assert kwargs["data"]["client_key"] == "ck_arg"
        assert kwargs["data"]["refresh_token"] == "rt_arg"


class TestExchangeAuthorizationCode:
    def test_success(self):
        mock_resp = _mock_response(200, {
            "access_token": "at_init",
            "refresh_token": "rt_init",
            "expires_in": 86400,
            "refresh_expires_in": 31536000,
            "scope": "video.publish",
            "open_id": "open_xyz",
        })
        with patch("tiktok_api.requests.post", return_value=mock_resp) as mock_post:
            result = tiktok_api.exchange_authorization_code(
                code="auth_code_123",
                redirect_uri="https://hotproductsdot.com/oauth/callback",
            )

        assert result["ok"] is True
        assert result["access_token"] == "at_init"
        _, kwargs = mock_post.call_args
        assert kwargs["data"]["grant_type"] == "authorization_code"
        assert kwargs["data"]["code"] == "auth_code_123"
        assert kwargs["data"]["redirect_uri"] == "https://hotproductsdot.com/oauth/callback"

    def test_missing_client_credentials(self, monkeypatch):
        monkeypatch.delenv("TIKTOK_CLIENT_KEY", raising=False)
        result = tiktok_api.exchange_authorization_code(
            code="c", redirect_uri="https://x/cb",
        )
        assert result["ok"] is False
        assert "TIKTOK_CLIENT_KEY" in result["error"]
