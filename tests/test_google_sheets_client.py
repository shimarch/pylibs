"""Tests for google_sheet_client module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from smrlib.google_sheets_client import GoogleSheetsClient
from smrlib.secret_core import SecretCore
from smrlib.structured_logger import LoggerContext, StructuredLogger


class TestGoogleSheetsClient:
    """Test GoogleSheetsClient class."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        print("Setting up GoogleSheetsClient tests")
        # Initialize logger and SecretCore
        LoggerContext.initialize(StructuredLogger("test_sheet_client"))
        SecretCore._instance = None
        SecretCore._initialized = False

    def test_initialization_with_default_scopes(self, temp_env_file):
        """Test: デフォルトスコープでの初期化を確認"""
        print("Testing GoogleSheetsClient initialization with default scopes")

        # Mock SecretCore with proper client secret format
        mock_secret = SecretCore.initialize(
            env_file_path=str(temp_env_file),
            allow_overwrite_keys=["GSHEET_CLIENT_SECRET", "GSHEET_REFRESH_TOKEN"],
        )
        client_secret = {
            "installed": {
                "client_id": "test_client_id",
                "client_secret": "test_secret",
                "redirect_uris": ["http://localhost"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        mock_secret.set("GSHEET_CLIENT_SECRET", json.dumps(client_secret))

        with patch("smrlib.google_sheet_client.Credentials") as mock_creds:
            with patch("smrlib.google_sheet_client.InstalledAppFlow") as mock_flow:
                with patch("smrlib.google_sheet_client.gspread.authorize") as mock_authorize:
                    mock_creds_instance = MagicMock()
                    mock_creds_instance.valid = True
                    mock_creds.from_authorized_user_info.return_value = mock_creds_instance

                    # Mock the flow to avoid actual authentication
                    mock_flow_instance = MagicMock()
                    mock_flow_instance.run_local_server.return_value = mock_creds_instance
                    mock_flow.from_client_config.return_value = mock_flow_instance

                    client = GoogleSheetsClient(secret_core=mock_secret)

                    assert client is not None
                    assert client.scopes == ["https://www.googleapis.com/auth/spreadsheets.readonly"]

        print("Confirmed: GoogleSheetsClient initializes with default scopes")

    def test_initialization_with_custom_scopes(self, temp_env_file):
        """Test: カスタムスコープでの初期化を確認"""
        print("Testing GoogleSheetsClient initialization with custom scopes")

        custom_scopes = ["https://www.googleapis.com/auth/spreadsheets"]

        mock_secret = SecretCore.initialize(
            env_file_path=str(temp_env_file),
            allow_overwrite_keys=["GSHEET_CLIENT_SECRET", "GSHEET_REFRESH_TOKEN"],
        )
        client_secret = {
            "installed": {
                "client_id": "test_client_id",
                "client_secret": "test_secret",
                "redirect_uris": ["http://localhost"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        mock_secret.set("GSHEET_CLIENT_SECRET", json.dumps(client_secret))

        with patch("smrlib.google_sheet_client.Credentials") as mock_creds:
            with patch("smrlib.google_sheet_client.InstalledAppFlow") as mock_flow:
                with patch("smrlib.google_sheet_client.gspread.authorize") as mock_authorize:
                    mock_creds_instance = MagicMock()
                    mock_creds_instance.valid = True
                    mock_creds.from_authorized_user_info.return_value = mock_creds_instance

                    mock_flow_instance = MagicMock()
                    mock_flow_instance.run_local_server.return_value = mock_creds_instance
                    mock_flow.from_client_config.return_value = mock_flow_instance

                    client = GoogleSheetsClient(scopes=custom_scopes, secret_core=mock_secret)

                    assert client.scopes == custom_scopes

        print("Confirmed: GoogleSheetsClient initializes with custom scopes")

    def test_authentication_with_existing_token(self, temp_env_file):
        """Test: 既存のトークンで認証することを確認"""
        print("Testing authentication with existing valid token")

        mock_secret = SecretCore.initialize(
            env_file_path=str(temp_env_file),
            allow_overwrite_keys=["GSHEET_CLIENT_SECRET", "GSHEET_REFRESH_TOKEN"],
        )
        client_secret = {
            "installed": {
                "client_id": "test_client_id",
                "client_secret": "test_secret",
                "redirect_uris": ["http://localhost"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        mock_secret.set("GSHEET_CLIENT_SECRET", json.dumps(client_secret))
        mock_secret.set("GSHEET_REFRESH_TOKEN", '{"token": "test_token", "refresh_token": "refresh"}')

        with patch("smrlib.google_sheet_client.Credentials") as mock_creds:
            with patch("smrlib.google_sheet_client.gspread.authorize") as mock_authorize:
                mock_creds_instance = MagicMock()
                mock_creds_instance.valid = True
                mock_creds.from_authorized_user_info.return_value = mock_creds_instance

                client = GoogleSheetsClient(secret_core=mock_secret)

                assert client.creds is not None
                mock_creds.from_authorized_user_info.assert_called_once()

        print("Confirmed: Authentication works with existing token")

    def test_get_worksheet_data(self, temp_env_file):
        """Test: シートデータの取得を確認"""
        print("Testing get_worksheet_data method")

        mock_secret = SecretCore.initialize(
            env_file_path=str(temp_env_file),
            allow_overwrite_keys=["GSHEET_CLIENT_SECRET", "GSHEET_REFRESH_TOKEN"],
        )
        client_secret = {
            "installed": {
                "client_id": "test_client_id",
                "client_secret": "test_secret",
                "redirect_uris": ["http://localhost"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        mock_secret.set("GSHEET_CLIENT_SECRET", json.dumps(client_secret))
        mock_secret.set("GSHEET_REFRESH_TOKEN", '{"token": "test_token", "refresh_token": "refresh"}')

        with patch("smrlib.google_sheet_client.Credentials") as mock_creds:
            with patch("smrlib.google_sheet_client.gspread.authorize") as mock_authorize:
                mock_creds_instance = MagicMock()
                mock_creds_instance.valid = True
                mock_creds.from_authorized_user_info.return_value = mock_creds_instance

                mock_gc = MagicMock()
                mock_spreadsheet = MagicMock()
                mock_worksheet = MagicMock()
                mock_worksheet.get_all_values.return_value = [
                    ["Header1", "Header2"],
                    ["Value1", "Value2"],
                ]
                mock_spreadsheet.worksheet.return_value = mock_worksheet
                mock_gc.open_by_key.return_value = mock_spreadsheet
                mock_authorize.return_value = mock_gc

                client = GoogleSheetsClient(secret_core=mock_secret)
                data = client.get_worksheet_data("test_id", "Sheet1")

                assert data is not None
                assert len(data) == 2
                assert data[0] == ["Header1", "Header2"]
                mock_gc.open_by_key.assert_called_once_with("test_id")

        print("Confirmed: Worksheet data retrieval works correctly")

    def test_connection_error_handling(self, temp_env_file):
        """Test: 接続エラーの処理を確認"""
        print("Testing connection error handling")

        mock_secret = SecretCore.initialize(
            env_file_path=str(temp_env_file),
            allow_overwrite_keys=["GSHEET_CLIENT_SECRET", "GSHEET_REFRESH_TOKEN"],
        )
        client_secret = {
            "installed": {
                "client_id": "test_client_id",
                "client_secret": "test_secret",
                "redirect_uris": ["http://localhost"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        mock_secret.set("GSHEET_CLIENT_SECRET", json.dumps(client_secret))
        mock_secret.set("GSHEET_REFRESH_TOKEN", '{"token": "test_token", "refresh_token": "refresh"}')

        with patch("smrlib.google_sheet_client.Credentials") as mock_creds:
            with patch("smrlib.google_sheet_client.gspread.authorize") as mock_authorize:
                mock_creds_instance = MagicMock()
                mock_creds_instance.valid = True
                mock_creds.from_authorized_user_info.return_value = mock_creds_instance

                mock_gc = MagicMock()
                # Simulate connection error
                from requests.exceptions import (
                    ConnectionError as RequestsConnectionError,
                )

                mock_gc.open_by_key.side_effect = RequestsConnectionError("Network error")
                mock_authorize.return_value = mock_gc

                client = GoogleSheetsClient(secret_core=mock_secret)

                with pytest.raises(ConnectionError):
                    client.get_worksheet_data("test_id")

        print("Confirmed: Connection errors are properly raised")

    def test_auto_save_token_enabled(self, temp_env_file):
        """Test: トークン自動保存が有効であることを確認"""
        print("Testing auto_save_token is enabled by default")

        mock_secret = SecretCore.initialize(
            env_file_path=str(temp_env_file),
            allow_overwrite_keys=["GSHEET_CLIENT_SECRET", "GSHEET_REFRESH_TOKEN"],
        )
        client_secret = {
            "installed": {
                "client_id": "test_client_id",
                "client_secret": "test_secret",
                "redirect_uris": ["http://localhost"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        mock_secret.set("GSHEET_CLIENT_SECRET", json.dumps(client_secret))
        mock_secret.set("GSHEET_REFRESH_TOKEN", '{"token": "test_token", "refresh_token": "refresh"}')

        with patch("smrlib.google_sheet_client.Credentials") as mock_creds:
            with patch("smrlib.google_sheet_client.gspread.authorize") as mock_authorize:
                mock_creds_instance = MagicMock()
                mock_creds_instance.valid = True
                mock_creds.from_authorized_user_info.return_value = mock_creds_instance

                client = GoogleSheetsClient(secret_core=mock_secret)

                assert client.auto_save_token is True

        print("Confirmed: auto_save_token is enabled by default")

    def test_auto_save_token_disabled(self, temp_env_file):
        """Test: トークン自動保存を無効にできることを確認"""
        print("Testing auto_save_token can be disabled")

        mock_secret = SecretCore.initialize(
            env_file_path=str(temp_env_file),
            allow_overwrite_keys=["GSHEET_CLIENT_SECRET", "GSHEET_REFRESH_TOKEN"],
        )
        client_secret = {
            "installed": {
                "client_id": "test_client_id",
                "client_secret": "test_secret",
                "redirect_uris": ["http://localhost"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        mock_secret.set("GSHEET_CLIENT_SECRET", json.dumps(client_secret))
        mock_secret.set("GSHEET_REFRESH_TOKEN", '{"token": "test_token", "refresh_token": "refresh"}')

        with patch("smrlib.google_sheet_client.Credentials") as mock_creds:
            with patch("smrlib.google_sheet_client.gspread.authorize") as mock_authorize:
                mock_creds_instance = MagicMock()
                mock_creds_instance.valid = True
                mock_creds.from_authorized_user_info.return_value = mock_creds_instance

                client = GoogleSheetsClient(secret_core=mock_secret, auto_save_token=False)

                assert client.auto_save_token is False

        print("Confirmed: auto_save_token can be disabled")

        print("Confirmed: auto_save_token can be disabled")
