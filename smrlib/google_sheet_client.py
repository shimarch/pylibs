import json

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

        try:
            # Authorize and open spreadsheet
            client = gspread.authorize(self.creds)
            spreadsheet = client.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            return worksheet.get_all_values()

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
            raise ValueError(
                f"❌ Spreadsheet not found: ID '{spreadsheet_id}'\n"
                f"   Please check:\n"
                f"   1. The spreadsheet ID in GSHEET_SPREADSHEET_ID is correct\n"
                f"   2. The spreadsheet is shared with your Google account\n"
                f"   3. Your account has read permission"
            ) from None

        except gspread.exceptions.WorksheetNotFound:
            raise ValueError(
                f"❌ Worksheet not found: Sheet '{sheet_name}'\n"
                f"   Please check the sheet name in your spreadsheet.\n"
                f"   Available sheets can be checked in the Google Spreadsheet."
            ) from None

        except gspread.exceptions.APIError as e:
            raise RuntimeError(
                f"❌ Google Sheets API error: {e.response.status_code}\n"
                f"   Error message: {e.response.json().get('error', {}).get('message', 'Unknown error')}\n"
                f"   This may be a temporary issue. Please try again later."
            ) from e

        except RequestException as e:
            raise RuntimeError(
                f"❌ HTTP request error: {type(e).__name__}\n"
                f"   Error: {e}\n"
                f"   This may be a temporary network issue. Please try again."
            ) from e

        except Exception as e:
            raise RuntimeError(
                f"❌ Unexpected error while accessing Google Sheets:\n"
                f"   {type(e).__name__}: {e}\n"
                f"   Please check your configuration and try again."
            ) from e
