"""Tests for google_chat_client module."""

import os
from unittest.mock import MagicMock, patch

import pytest

from smrlib.google_chat_client import GoogleChatClient
from smrlib.structured_logger import LoggerContext, StructuredLogger


class TestGoogleChatClient:
    """Test GoogleChatClient class."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        print("Setting up GoogleChatClient tests")
        # Initialize logger for GoogleChatClient
        LoggerContext.initialize(StructuredLogger("test_chat_client"))

    def test_initialization(self):
        """Test: GoogleChatClientの初期化を確認"""
        print("Testing GoogleChatClient initialization")

        client = GoogleChatClient()

        assert client is not None
        assert client.logger is not None

        print("Confirmed: GoogleChatClient initializes correctly")

    def test_get_webhook_url_success(self):
        """Test: Webhook URLの取得が成功することを確認"""
        print("Testing get_webhook_url with existing environment variable")

        client = GoogleChatClient()

        with patch.dict(os.environ, {"GCHAT_WEBHOOK_TESTSPACE": "https://chat.googleapis.com/v1/spaces/test"}):
            url = client.get_webhook_url("testspace")

            assert url == "https://chat.googleapis.com/v1/spaces/test"

        print("Confirmed: Webhook URL retrieved successfully")

    def test_get_webhook_url_not_found(self):
        """Test: Webhook URLが見つからない場合にNoneを返すことを確認"""
        print("Testing get_webhook_url with missing environment variable")

        client = GoogleChatClient()

        # Ensure the env var does not exist
        with patch.dict(os.environ, {}, clear=False):
            url = client.get_webhook_url("nonexistent")

            assert url is None

        print("Confirmed: Returns None when webhook URL not found")

    def test_send_message_success(self):
        """Test: メッセージ送信が成功することを確認"""
        print("Testing send_message with successful HTTP request")

        client = GoogleChatClient()

        # Mock the Http object
        mock_response = MagicMock()
        mock_response.status = 200

        with patch.dict(os.environ, {"GCHAT_WEBHOOK_TESTSPACE": "https://test.url"}):
            with patch("smrlib.google_chat_client.Http") as mock_http:
                mock_http_instance = MagicMock()
                mock_http_instance.request.return_value = (mock_response, b'{"success": true}')
                mock_http.return_value = mock_http_instance

                payload = {"text": "Test message"}
                result = client.send_message("testspace", payload)

                assert result is True
                mock_http_instance.request.assert_called_once()

        print("Confirmed: Message sent successfully")

    def test_send_message_webhook_not_found(self):
        """Test: Webhook URLが見つからない場合にFalseを返すことを確認"""
        print("Testing send_message when webhook URL not found")

        client = GoogleChatClient()

        with patch.dict(os.environ, {}, clear=False):
            result = client.send_message("nonexistent", {"text": "Test"})

            assert result is False

        print("Confirmed: Returns False when webhook URL not found")

    def test_send_message_http_error(self):
        """Test: HTTP送信エラーが発生した場合にFalseを返すことを確認"""
        print("Testing send_message with HTTP error")

        client = GoogleChatClient()

        with patch.dict(os.environ, {"GCHAT_WEBHOOK_TESTSPACE": "https://test.url"}):
            with patch("smrlib.google_chat_client.Http") as mock_http:
                mock_http_instance = MagicMock()
                mock_http_instance.request.side_effect = Exception("Network error")
                mock_http.return_value = mock_http_instance

                result = client.send_message("testspace", {"text": "Test"})

                assert result is False

        print("Confirmed: Returns False on HTTP error")

    def test_send_text_message_success(self):
        """Test: テキストメッセージ送信が成功することを確認"""
        print("Testing send_text_message")

        client = GoogleChatClient()

        mock_response = MagicMock()
        mock_response.status = 200

        with patch.dict(os.environ, {"GCHAT_WEBHOOK_TESTSPACE": "https://test.url"}):
            with patch("smrlib.google_chat_client.Http") as mock_http:
                mock_http_instance = MagicMock()
                mock_http_instance.request.return_value = (mock_response, b'{"success": true}')
                mock_http.return_value = mock_http_instance

                result = client.send_text_message("testspace", "Test Title", "Test message content")

                assert result is True

        print("Confirmed: Text message sent successfully")

    def test_send_text_message_formats_correctly(self):
        """Test: テキストメッセージが正しくフォーマットされることを確認"""
        print("Testing send_text_message formats message correctly")

        client = GoogleChatClient()

        mock_response = MagicMock()
        mock_response.status = 200

        with patch.dict(os.environ, {"GCHAT_WEBHOOK_TESTSPACE": "https://test.url"}):
            with patch("smrlib.google_chat_client.Http") as mock_http:
                mock_http_instance = MagicMock()
                mock_http_instance.request.return_value = (mock_response, b'{"success": true}')
                mock_http.return_value = mock_http_instance

                client.send_text_message("testspace", "Title", "Content")

                # Check that request was called with formatted payload
                call_args = mock_http_instance.request.call_args
                import json

                body = json.loads(call_args.kwargs["body"])
                assert body["text"] == "*Title*\nContent"

        print("Confirmed: Message is formatted with title and content")
