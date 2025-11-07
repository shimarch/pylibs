"""Generic Google Chat API client for webhook-based messaging."""

import json
import os
from typing import Any

from httplib2 import Http

from smrlib.structured_logger import LoggerContext


class GoogleChatClient:
    """Generic Google Chat client using Webhook API.

    This class provides low-level functionality for sending messages to Google Chat
    spaces via webhooks. It handles authentication and basic message sending.
    """

    def __init__(self):
        """Initialize the Google Chat client."""
        self.logger = LoggerContext.get_logger()

    def get_webhook_url(self, space_name: str) -> str | None:
        """Get webhook URL from environment variable.

        Args:
            space_name: Name of the space (e.g., 'space1')

        Returns:
            Webhook URL or None if not found

        Example:
            >>> client = GoogleChatClient()
            >>> url = client.get_webhook_url("space1")
            >>> # Looks for GCHAT_WEBHOOK_SPACE1 environment variable
        """
        env_key = f"GCHAT_WEBHOOK_{space_name.upper()}"
        url = os.getenv(env_key)

        if not url:
            self.logger.error("Webhook URL not found in environment", {"env_key": env_key})
            return None

        return url

    def send_message(self, space_name: str, payload: dict[str, Any]) -> bool:
        """Send a message payload to Google Chat.

        Args:
            space_name: Name of the space (e.g., 'space1')
            payload: JSON payload to send (dict will be converted to JSON)

        Returns:
            True if successful, False otherwise

        Example:
            >>> client = GoogleChatClient()
            >>> payload = {"text": "Hello, world!"}
            >>> success = client.send_message("space1", payload)
        """
        url = self.get_webhook_url(space_name)
        if not url:
            return False

        headers = {"Content-Type": "application/json; charset=UTF-8"}

        try:
            http_obj = Http()
            response, content = http_obj.request(uri=url, method="POST", headers=headers, body=json.dumps(payload))

            self.logger.debug(
                "Google Chat message sent",
                {
                    "space": space_name,
                    "status_code": response.status if hasattr(response, "status") else "unknown",
                    "payload_size": len(json.dumps(payload)),
                },
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to send Google Chat message: {e}", {"space": space_name, "error": str(e)})
            return False

    def send_text_message(self, space_name: str, title: str, message: str) -> bool:
        """Send a simple text message to Google Chat.

        Args:
            space_name: Name of the space (e.g., 'space1')
            title: Message title
            message: Message content

        Returns:
            True if successful, False otherwise

        Example:
            >>> client = GoogleChatClient()
            >>> success = client.send_text_message("space1", "Alert", "System is down")
        """
        payload = {"text": f"*{title}*\n{message}"}

        result = self.send_message(space_name, payload)

        if result:
            self.logger.info("Text message sent to Google Chat", {"title": title, "space": space_name})

        return result
