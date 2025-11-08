"""smrlib - Personal utility library for Python projects.

Documentation: https://github.com/shimarch/pylibs/blob/main/README.md
"""

from smrlib.google_chat_client import GoogleChatClient
from smrlib.google_sheet_client import GoogleSheetsClient
from smrlib.secret_core import SecretCore, SecretStorageType
from smrlib.structured_logger import LogConfig, LoggerContext, StructuredLogger

__version__ = "0.1.0"
__doc_url__ = "https://github.com/shimarch/pylibs/blob/main/README.md"

__all__ = [
    "GoogleChatClient",
    "GoogleSheetsClient",
    "SecretCore",
    "SecretStorageType",
    "LogConfig",
    "LoggerContext",
    "StructuredLogger",
]
