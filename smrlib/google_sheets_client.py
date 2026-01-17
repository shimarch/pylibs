import json
from contextlib import contextmanager
from typing import Any

import google.auth.transport.requests
import gspread
from google.auth.exceptions import RefreshError, TransportError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import RequestException
from requests.exceptions import Timeout as RequestsTimeout

from smrlib.secret_core import SecretCore
from smrlib.structured_logger import LoggerContext


class GoogleSheetsClient:
    def __init__(
        self,
        scopes: list[str] | None = None,
        secret_core: SecretCore | None = None,
        auto_save_token: bool = True,
    ):
        if scopes is None:
            scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

        # Use provided SecretCore or get singleton instance
        self.secrets = secret_core or SecretCore.get_instance()
        self.auto_save_token = auto_save_token
        self.logger = LoggerContext.get_logger()

        # 秘密情報を SecretCore から取得
        self.client_secret_json = self.secrets.require("GSHEET_CLIENT_SECRET")
        self.token_json = self.secrets.get("GSHEET_REFRESH_TOKEN")

        self.scopes = scopes
        self.creds = None

        self._authenticate()

    def _authenticate(self):
        # トークンが存在する場合は読み込み
        if self.token_json:
            try:
                token_data = json.loads(self.token_json)
                self.creds = Credentials.from_authorized_user_info(token_data, self.scopes)
            except (json.JSONDecodeError, KeyError):
                pass

        # トークンが期限切れ、または存在しない場合に再認証
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(google.auth.transport.requests.Request())
            else:
                if not self.client_secret_json:
                    raise ValueError("GSHEET_CLIENT_SECRET is required for authentication")
                client_secret_data = json.loads(self.client_secret_json)
                flow = InstalledAppFlow.from_client_config(client_secret_data, self.scopes)
                self.creds = flow.run_local_server(port=0)

            # 新しいトークンを取得したら、メモリに保存し、必要に応じて永続化
            new_token = self.creds.to_json()
            self.token_json = new_token

            # 自動保存が有効で、トークンが更新された場合に永続化
            if self.auto_save_token:
                try:
                    self.secrets.set("GSHEET_REFRESH_TOKEN", new_token)
                    self.logger.success("Refresh token saved to storage")
                except ValueError as e:
                    # 保存が許可されていない場合はワーニングログのみ
                    self.logger.warning(f"Cannot persist refresh token: {e}")
                except Exception as e:
                    # その他のエラーもログに記録
                    self.logger.error(f"Failed to save refresh token: {e}")

    @contextmanager
    def _api_error_handler(self, spreadsheet_id=None, sheet_name=None):
        """Context manager for handling Google Sheets API errors consistently."""
        try:
            yield
        except (RequestsConnectionError, RequestsTimeout, TimeoutError) as e:
            raise ConnectionError(
                f"❌ Network connection error: Failed to connect to Google Sheets API\n"
                f"   Please check your internet connection.\n"
                f"   Error: {type(e).__name__}: {e}"
            ) from e

        except (RefreshError, TransportError) as e:
            raise ValueError(
                f"❌ Authentication error: Failed to refresh credentials\n"
                f"   Your access token may have expired or been revoked.\n"
                f"   Please re-authenticate by setting GSHEET_REFRESH_TOKEN.\n"
                f"   Error: {type(e).__name__}: {e}"
            ) from e

        except gspread.exceptions.SpreadsheetNotFound:
            msg = "Spreadsheet not found"
            if spreadsheet_id:
                msg += f": ID '{spreadsheet_id}'"

            raise ValueError(
                f"❌ {msg}\n"
                f"   Please check:\n"
                f"   1. The spreadsheet ID is correct\n"
                f"   2. The spreadsheet is shared with your Google account\n"
                f"   3. Your account has read permission"
            ) from None

        except gspread.exceptions.WorksheetNotFound:
            msg = "Worksheet not found"
            if sheet_name:
                msg += f": Sheet '{sheet_name}'"

            raise ValueError(
                f"❌ {msg}\n"
                f"   Please check the sheet name in your spreadsheet.\n"
                f"   Available sheets can be checked in the Google Spreadsheet."
            ) from None

        except gspread.exceptions.APIError as e:
            error_details = "Unknown error"
            try:
                if hasattr(e, "response") and e.response:
                    error_details = e.response.json().get("error", {}).get("message", "Unknown error")
            except Exception as parse_error:
                self.logger.debug(f"Failed to parse error details: {parse_error}")

            raise RuntimeError(
                f"❌ Google Sheets API error: {getattr(e, 'code', 'Unknown code')}\n"
                f"   Error message: {error_details}\n"
                f"   This may be a temporary issue. Please try again later."
            ) from e

        except RequestException as e:
            raise RuntimeError(
                f"❌ HTTP request error: {type(e).__name__}\n"
                f"   Error: {e}\n"
                f"   This may be a temporary network issue. Please try again."
            ) from e

        except Exception as e:
            # Re-raise already transformed errors
            if isinstance(e, (ConnectionError, ValueError, RuntimeError)):
                raise

            raise RuntimeError(
                f"❌ Unexpected error while accessing Google Sheets:\n"
                f"   {type(e).__name__}: {e}\n"
                f"   Please check your configuration and try again."
            ) from e

    def get_worksheet_data(self, spreadsheet_id, sheet_name="Sheet1"):
        """Get worksheet data with improved error handling.

        Args:
            spreadsheet_id: Google Spreadsheet ID
            sheet_name: Sheet name to retrieve

        Returns:
            List of rows from the worksheet

        Raises:
            ValueError: Authentication or configuration error
            ConnectionError: Network connection error
            TimeoutError: Request timeout
            RuntimeError: Other Google API errors
        """
        if not self.creds:
            raise ValueError("❌ Authentication credentials not available")

        with self._api_error_handler(spreadsheet_id, sheet_name):
            # Authorize and open spreadsheet
            client = gspread.authorize(self.creds)
            spreadsheet = client.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            return worksheet.get_all_values()

    def _safe_serialize(self, value: object) -> str | int | float | bool:
        """Serialize value to be safe for Google Sheets API."""
        if value is None:
            return ""
        if isinstance(value, (str, int, float, bool)):
            return value

        # Try to serialize list/dict to valid JSON string
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                pass

        # Convert objects (datetime, Decimal, etc.) to string
        return str(value)

    def update_worksheet_data(
        self, spreadsheet_id: str, data: list[dict[str, object]] | str, sheet_name: str = "Sheet1"
    ):
        """Update worksheet data from a list of dictionaries or a JSON string.

        This method clears the worksheet and writes the new data starting from cell A1.
        Keys of the first dictionary are used as headers.

        Args:
            spreadsheet_id: Google Spreadsheet ID
            data: List of dictionaries or JSON string representing list of dictionaries
            sheet_name: Sheet name to update

        Raises:
            ValueError: Authentication error, configuration error, or invalid JSON
            ConnectionError: Network connection error
            RuntimeError: Other Google API errors
        """
        if not self.creds:
            raise ValueError("❌ Authentication credentials not available")

        if not data:
            self.logger.warning("No data provided to update_worksheet_data. Skipping update.")
            return

        # Parse JSON string if provided
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                raise ValueError(f"❌ Invalid JSON string provided: {e}") from e

        if not isinstance(data, list):
            raise ValueError("❌ Data must be a list of dictionaries (or a JSON array)")

        if not data:
            self.logger.warning("Empty data list provided. Skipping update.")
            return

        with self._api_error_handler(spreadsheet_id, sheet_name):
            client = gspread.authorize(self.creds)
            spreadsheet = client.open_by_key(spreadsheet_id)

            try:
                worksheet = spreadsheet.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                # シートが存在しない場合は作成
                self.logger.info(f"Worksheet '{sheet_name}' not found. Creating new worksheet.")
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=26)

            # Transform list of dicts to list of lists
            headers = list(data[0].keys())
            values: list[list[Any]] = [headers]
            for row in data:
                # Ensure order matches headers; fill missing keys with None or empty string
                # And serialize values safely
                values.append([self._safe_serialize(row.get(h)) for h in headers])

            worksheet.clear()
            worksheet.update(values)

            self.logger.success(f"Successfully updated sheet '{sheet_name}' with {len(data)} rows.")
