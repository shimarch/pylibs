"""Structured logging with emoji and context support.

This module provides a structured logging system with:
- Emoji-based log levels for visual clarity
- Context-aware formatting (console vs file)
- Type-safe log items with factory methods
- Color support via colorama
- Log rotation (1MB max, keep 3 backup files)

Usage Recommendation:
    Use LoggerContext to manage the logger instance globally across your application.
    This avoids circular imports and dependency injection complexity.

    Example:
        # In your app initialization (e.g., app_context.py)
        from smrlib.structured_logger import LoggerContext
        LoggerContext.initialize()

        # In any module (e.g., lib/playwright_core.py)
        from smrlib.structured_logger import LoggerContext

        class MyClass:
            def __init__(self):
                self.logger = LoggerContext.get_logger()

            def do_something(self):
                self.logger.info("Task started", {"id": 123})
                self.logger.success("Task completed")

"""

from __future__ import annotations

import argparse
import getpass
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colorama import Fore, Style
from colorama import init as colorama_init

if TYPE_CHECKING:
    pass

colorama_init(autoreset=True)


@dataclass(slots=True)
class LogConfig:
    """Configuration object describing how logging should behave."""

    level: int = logging.INFO
    log_file: Path | None = None
    dry_run: bool = False
    log_file_max_bytes: int = 1 * 1024 * 1024  # 1MB
    log_file_backup_count: int = 1  # current + .1
    log_file_encoding: str = "utf-8"


# _level_to_emoji = {
#     logging.DEBUG: "🛠️",
#     logging.INFO: "ℹ️",
#     logging.WARNING: "⚠️",
#     logging.ERROR: "❌",
#     logging.CRITICAL: "🔥",
# }

# if _colorama_available:  # pragma: no branch - constant at runtime
#     _level_to_color = {
#         logging.DEBUG: Fore.BLUE,
#         logging.INFO: Fore.GREEN,
#         logging.WARNING: Fore.YELLOW,
#         logging.ERROR: Fore.RED,
#         logging.CRITICAL: Fore.MAGENTA,
#     }
# else:
#     _level_to_color = {level: "" for level in _level_to_emoji}


class LogLevel(IntEnum):
    """Log level enumeration matching custom level scheme.

    This enum defines the logging levels used throughout the application.
    Lower values have higher priority (will be logged more often).

    Attributes:
        SUCCESS: Success messages (level 0)
        ERROR: Error messages (level 1)
        WARNING: Warning messages (level 5)
        INFO: Informational messages (level 10)
        NOTICE: Notice messages (level 15)
        DEBUG: Debug messages (level 100)
    """

    SUCCESS = 0
    ERROR = 1
    WARNING = 5
    INFO = 10
    NOTICE = 15
    DEBUG = 100


# ファイル出力時のレベルマッピング（LogLevel → logging level）
_FILE_LOG_LEVEL_MAP = {
    LogLevel.SUCCESS: logging.INFO,
    LogLevel.NOTICE: logging.INFO,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARNING: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
    LogLevel.DEBUG: logging.DEBUG,
}


@dataclass
class LogItem:
    """構造化ログ情報を保持し、フォーマットも担当するクラス"""

    message: str
    context: Any = None
    level: LogLevel = LogLevel.INFO

    # ファクトリメソッド（レベル別の生成）
    @classmethod
    def success(cls, message: str, context: Any = None) -> LogItem:
        """成功レベルの LogItem を生成"""
        return cls(message, context, LogLevel.SUCCESS)

    @classmethod
    def error(cls, message: str, context: Any = None) -> LogItem:
        """エラーレベルの LogItem を生成"""
        return cls(message, context, LogLevel.ERROR)

    @classmethod
    def warning(cls, message: str, context: Any = None) -> LogItem:
        """警告レベルの LogItem を生成"""
        return cls(message, context, LogLevel.WARNING)

    @classmethod
    def info(cls, message: str, context: Any = None) -> LogItem:
        """情報レベルの LogItem を生成"""
        return cls(message, context, LogLevel.INFO)

    @classmethod
    def notice(cls, message: str, context: Any = None) -> LogItem:
        """通知レベルの LogItem を生成"""
        return cls(message, context, LogLevel.NOTICE)

    @classmethod
    def debug(cls, message: str, context: Any = None) -> LogItem:
        """デバッグレベルの LogItem を生成"""
        return cls(message, context, LogLevel.DEBUG)

    def format_console(self) -> str:
        """コンソール出力用のフォーマット（ユーザーフレンドリー）"""
        if self.context is None:
            return self.message

        if isinstance(self.context, (str, int, float)):
            return f"{self.message}: {self.context}"

        # dict_items などのビューオブジェクトや dict を処理
        if isinstance(self.context, dict) or hasattr(self.context, "__iter__"):
            try:
                # イテレート可能で、(key, value) のペアを持つ場合
                result: str = self._format_dict_like_console(self.message, self.context)  # type: ignore[arg-type]
                return result
            except (TypeError, ValueError, AttributeError):
                # イテレートできない、または想定外の形式
                pass

        return f"{self.message}: {self.context}"  # type: ignore[str-bytes-safe]

    def format_file(self) -> str:
        """ファイル出力用のフォーマット（詳細ログ）"""
        if self.context is None:
            return self.message

        if isinstance(self.context, (str, int, float)):
            return f"{self.message}, {self.context}"

        # dict_items などのビューオブジェクトや dict を処理
        if isinstance(self.context, dict) or hasattr(self.context, "__iter__"):
            try:
                # イテレート可能で、(key, value) のペアを持つ場合
                serialised: str = self._serialise_dict_like(self.context)  # type: ignore[arg-type]
                return f"{self.message}, {serialised}"
            except (TypeError, ValueError, AttributeError):
                # イテレートできない、または想定外の形式
                pass

        return f"{self.message}, {self.context}"  # type: ignore[str-bytes-safe]

    def _format_dict_like_console(self, title: str, data: Any) -> str:
        """辞書ライクなオブジェクト（dict, dict_items等）をコンソール用にフォーマット（複数行対応）"""

        def _format_value(value: Any) -> str:
            if isinstance(value, str):
                return f"'{value}'"
            return str(value)

        # dictの場合は直接items()を使用
        if isinstance(data, dict):
            items_iter: Any = data.items()  # type: ignore[var-annotated]
            data_len: int = len(data)  # type: ignore[arg-type]
        else:
            # dict_itemsなどのイテラブル - リスト化して長さを取得
            items_list: list[Any] = list(data)
            items_iter = iter(items_list)
            data_len = len(items_list)

        if data_len == 0:
            return title

        # 単一項目: 1行で表示
        if data_len == 1:
            key: Any
            value: Any
            key, value = next(iter(items_iter))
            return f"{title}: {key}={_format_value(value)}"

        # 複数項目: 複数行で表示
        lines = [f"{title}:"]
        for key, value in items_iter:
            lines.append(f"  - {key}={_format_value(value)}")
        return "\n".join(lines)

    def _serialise_dict_like(self, data: Any) -> str:
        """辞書ライクなオブジェクト（dict, dict_items等）をファイル用にシリアライズ（1行形式）"""

        def _format_value(value: Any) -> str:
            if isinstance(value, str):
                return f"'{value}'"
            return str(value)

        # dictの場合は直接items()を使用
        if isinstance(data, dict):
            items_iter: Any = data.items()  # type: ignore[var-annotated]
        else:
            # dict_itemsなどのイテラブルはそのまま使用
            items_iter = data

        formatted_items: list[str] = [f"{key}={_format_value(value)}" for key, value in items_iter]
        return ", ".join(formatted_items)

    def _format_dict_console(self, title: str, data: dict[str, Any]) -> str:
        """辞書をコンソール用にフォーマット（複数行対応）

        Note: 後方互換性のため残しているが、_format_dict_like_console() を推奨
        """
        return self._format_dict_like_console(title, data)

    def _serialise_dict(self, data: dict[str, Any]) -> str:
        """辞書をファイル用にシリアライズ（1行形式）

        Note: 後方互換性のため残しているが、_serialise_dict_like() を推奨
        """
        return self._serialise_dict_like(data)

    def __str__(self) -> str:
        """文字列化（Exception など汎用用途）"""
        return self.format_console()


class _BaseFormatter(logging.Formatter):
    """Formatter with ISO-8601 timestamps, resilient to Windows' strftime."""

    _micro_placeholder = "__MICROSECOND__"

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        dt = datetime.fromtimestamp(record.created)
        if not datefmt:
            return dt.isoformat(timespec="milliseconds")

        fmt = datefmt
        if "%f" in fmt:
            fmt = fmt.replace("%f", self._micro_placeholder)
            rendered = dt.strftime(fmt)
            return rendered.replace(self._micro_placeholder, f"{dt.microsecond:06d}")
        return dt.strftime(fmt)


# class _EmojiFormatter(_BaseFormatter):
#     """Custom formatter that injects emoji, color, and title/data handling."""

#     def format(self, record: logging.LogRecord) -> str:
#         base = super().format(record)
#         emoji = _level_to_emoji.get(record.levelno, "")
#         color = _level_to_color.get(record.levelno, "")
#         reset = Style.RESET_ALL if _colorama_available else ""
#         if color:
#             return f"{color}{emoji} {base}{reset}" if emoji else f"{color}{base}{reset}"
#         return f"{emoji} {base}" if emoji else base


# class _ConsoleFormatter(logging.Formatter):
#     """User-friendly console formatter with emoji and color, without timestamps."""

#     def format(self, record: logging.LogRecord) -> str:
#         message = record.getMessage()
#         emoji = _level_to_emoji.get(record.levelno, "")
#         color = _level_to_color.get(record.levelno, "")
#         reset = Style.RESET_ALL if _colorama_available else ""

#         if color and emoji:
#             return f"{color}{emoji}  {message}{reset}"
#         elif emoji:
#             return f"{emoji}  {message}"
#         else:
#             return message


class StructuredLogger:
    """Wrapper around :mod:`logging` with emoji, optional colour, and helpers."""

    def __init__(
        self,
        name: str | None = "filetoolkit",
        log_file_path: Path | None = None,
        *,
        config: LogConfig | None = None,
    ) -> None:
        # 通常 name は Path(__file__).stem から生成
        self.config = config or LogConfig()

        if self.config.log_file is None and log_file_path:
            try:
                # 親ディレクトリが存在しない場合は作成
                if log_file_path.parent != Path():
                    log_file_path.parent.mkdir(parents=True, exist_ok=True)
                self.config.log_file = log_file_path
            except (ValueError, OSError) as exc:
                raise ValueError(f"Invalid log file name from '{log_file_path}': {exc}") from exc

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        self._handlers: list[logging.Handler] = []
        self._message_prefix = "[DRY-RUN] " if self.config.dry_run else ""

        if not self.logger.handlers:
            self._install_handlers()

        if log_file_path is None:
            self.info("Logger initialised without log file", {"name": name})

        self.debug(
            "Logger initialised",
            {
                "level": self._resolve_level(),
                "log_file": str(self.config.log_file) if self.config.log_file else None,
                "dry_run": self.config.dry_run,
            },
        )

    def _install_handlers(self) -> None:
        message_format = "%(asctime)s, %(message)s"

        # No console handler - we use print() for console output
        installed_handlers: list[logging.Handler] = []

        if self.config.log_file:
            # Use RotatingFileHandler with configurable max size and backup count
            file_handler = RotatingFileHandler(
                self.config.log_file,
                maxBytes=self.config.log_file_max_bytes,
                backupCount=self.config.log_file_backup_count,
                encoding=self.config.log_file_encoding,
            )
            # datefmt=None でミリ秒(3桁)のISO-8601形式を使用
            file_handler.setFormatter(_BaseFormatter(fmt=message_format, datefmt=None))
            self.logger.addHandler(file_handler)
            installed_handlers.append(file_handler)

        self._handlers.extend(installed_handlers)

    def _resolve_level(self) -> int:
        return self.config.level

    def _should_log(self, threshold: int) -> bool:
        resolved = self._resolve_level()
        if resolved <= 0:
            return False
        return resolved >= threshold

    def set_level(self, level: LogLevel) -> None:
        """Dynamically adjust the log level.

        Args:
            level: The log level to set (must be a LogLevel enum value)

        Example:
            >>> logger.set_level(LogLevel.DEBUG)
            >>> logger.set_level(LogLevel.INFO)
        """
        self.config.level = int(level)

    #
    # Console output methods (user-friendly, no timestamp) ----------------
    def _log(self, log_item: LogItem, *, console: bool = True) -> None:
        """Internal logging with optional console output.

        Args:
            log_item: The log item to output
            console: If True, output to console; if False, only to log file
        """
        if console:
            match log_item.level:
                case LogLevel.SUCCESS:
                    self._output_console(log_item, "✅", Fore.GREEN)
                case LogLevel.NOTICE:
                    self._output_console(log_item, "ℹ️", "")
                case LogLevel.ERROR:
                    self._output_console(log_item, "❌", Fore.RED)
                case LogLevel.WARNING:
                    self._output_console(log_item, "⚠️", Fore.YELLOW)
                case LogLevel.INFO:
                    self._output_console(log_item, "", "")
                case LogLevel.DEBUG:
                    self._output_console(log_item, "🛠️", Fore.BLUE)

        if self.config.log_file:
            message = self._add_prefix(log_item.format_file())
            file_level = _FILE_LOG_LEVEL_MAP[log_item.level]
            self.logger.log(file_level, message)

    def log(self, log_item: LogItem) -> None:
        """Log to both console and file."""
        self._log(log_item, console=True)

    def info(self, title: str, data: object | None = None) -> None:
        """Console info message with emoji."""
        self.log(LogItem.info(title, data))

    def notice(self, title: str, data: object | None = None) -> None:
        """Console notice message with emoji."""
        self.log(LogItem.notice(title, data))

    def warning(self, title: str, data: object | None = None) -> None:
        """Console warning message with emoji."""
        self.log(LogItem.warning(title, data))

    def error(self, title: str, data: object | None = None) -> None:
        """Console error message with emoji."""
        self.log(LogItem.error(title, data))

    def success(self, title: str, data: object | None = None) -> None:
        """Console success message with emoji."""
        self.log(LogItem.success(title, data))

    def debug(self, title: str, data: object | None = None) -> None:
        """Console debug message with emoji (only if level >= 100)."""
        if not self._should_log(100):
            return

        self.log(LogItem(title, data, LogLevel.DEBUG))

    def _output_console(self, log_item: LogItem, emoji: str, color: str) -> None:
        """コンソールに LogItem を出力"""
        message = log_item.format_console()

        if self._message_prefix:
            message = f"{self._message_prefix}{message}"
        print(f"{color}{emoji} {message}{Style.RESET_ALL}")

    def _add_prefix(self, message: str) -> str:
        """ドライラン用プレフィックスを追加"""
        return f"{self._message_prefix}{message}" if self._message_prefix else message

    def close(self) -> None:
        """Flush and detach all handlers installed by this logger."""

        for handler in getattr(self, "_handlers", []):
            handler.flush()
            handler.close()
            self.logger.removeHandler(handler)
        self._handlers = []

    def __del__(self) -> None:
        """Ensure resources are released when the logger is garbage collected."""
        try:
            self.close()
        except Exception:  # noqa: S110
            # Ignore errors during cleanup to avoid issues during interpreter shutdown
            pass

    # Context-manager convenience ---------------------------------------
    def __enter__(self) -> StructuredLogger:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    # Utilities -------------------------------------------------------------
    def ask(self, prompt: str, *, password: bool = False) -> str:
        """Prompt the user and log both prompt and response (masked for passwords)."""

        self.info("User input requested", prompt)
        if password:
            response = getpass.getpass(f"🔐 {prompt}: ")
            masked = "*" * len(response)
            self.debug("User input captured", {"prompt": prompt, "value": masked})
        else:
            response = input(f"❓ {prompt}: ")
            self.debug("User input captured", {"prompt": prompt, "value": response})
        return response

    def confirm(self, prompt: str, *, default: bool = False) -> bool:
        """Ask user for yes/no confirmation and return True/False.

        Args:
            prompt: Question to ask the user
            default: Default value if user just presses Enter (False = No, True = Yes)

        Returns:
            True if user confirmed (y/yes), False otherwise

        Example:
            >>> if logger.confirm("このディレクトリで処理を実行しますか？"):
            ...     process_directory()
        """
        suffix = " (Y/n)" if default else " (y/N)"
        self.info("User confirmation requested", prompt)

        response = input(f"❓ {prompt}{suffix}: ").strip().lower()

        # Empty response uses default
        if not response:
            result = default
        else:
            result = response in ("y", "Y")

        self.debug("User confirmation captured", {"prompt": prompt, "response": response, "result": result})
        return result

    def summary(
        self,
        title: str,
        items: dict[str, dict[str, int | str]],
        *,
        total_key: str | None = None,
    ) -> None:
        """Display summary table with colors and log structured data.

        Args:
            title: Title of the summary (with emoji if desired)
            items: Dictionary of {label: {"value": int, "color": str}}
                   color should be colorama Fore.* constant (e.g., Fore.GREEN) or empty string
            total_key: Optional key for total row (will be separated with a line)

        Example:
            logger.summary(
                "📊 処理結果サマリー",
                {
                    "Converted": {"value": 27, "color": Fore.GREEN},
                    "No Need": {"value": 2, "color": Fore.YELLOW},
                    "Skipped": {"value": 1, "color": Fore.CYAN},
                    "Failed": {"value": 0, "color": Fore.RED},
                    "Total": {"value": 30, "color": ""},
                },
                total_key="Total",
            )
        """
        # コンソールに表形式で表示
        separator = "=" * 50
        print(f"\n{separator}")
        print(title)
        print(separator)

        for label, data in items.items():
            value = data["value"]
            color = data.get("color", "")

            # Total行の前に区切り線
            if total_key and label == total_key:
                print(f"  {'-' * 44}")

            # 色付きで表示
            if color:
                print(f"  {color}{label:9s}{Style.RESET_ALL} : {value:3d} 件")
            else:
                print(f"  {label:9s} : {value:3d} 件")

        print(f"{separator}\n")

        # ログファイルにのみ構造化データとして記録（コンソール出力なし）
        log_data = {label: data["value"] for label, data in items.items()}
        log_item = LogItem.info(title, log_data)
        self._log(log_item, console=False)


def detect_log_config(argv: Iterable[str] | None = None) -> LogConfig:
    """Derive :class:`LogConfig` from command line arguments."""

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--log-level",
        dest="log_level",
        type=int,
        choices=[0, 1, 10, 100],
        default=None,
        help="Logging detail level (0=silent, 1=normal, 10=verbose, 100=debug)",
    )
    parser.add_argument(
        "--log-file",
        dest="log_file",
        type=Path,
        default=None,
        help="Path to an optional log file destination.",
    )

    known_args, _ = parser.parse_known_args(list(argv) if argv is not None else None)

    return LogConfig(
        level=known_args.log_level,
        log_file=known_args.log_file,
    )


"""Logger context for managing shared logger instance."""


class LoggerContext:
    """Singleton context for managing the application logger."""

    _logger: StructuredLogger | None = None

    @classmethod
    def initialize(cls, logger: StructuredLogger | None = None) -> StructuredLogger:
        """Initialize the global logger.

        Args:
            logger: Optional logger instance. If None, creates a default logger.

        Returns:
            The initialized logger instance
        """
        if logger is None:
            cls._logger = StructuredLogger()
        else:
            cls._logger = logger
        return cls._logger

    @classmethod
    def get_logger(cls) -> StructuredLogger:
        """Get the logger instance.

        Returns:
            StructuredLogger: The logger instance

        Raises:
            RuntimeError: If logger is not initialized
        """
        if cls._logger is None:
            raise RuntimeError("LoggerContext not initialized. Call LoggerContext.initialize() first.")
        return cls._logger

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if logger is initialized.

        Returns:
            True if logger is initialized, False otherwise
        """
        return cls._logger is not None

    @classmethod
    def reset(cls) -> None:
        """Reset the logger instance.

        This method clears the current logger instance, allowing it to be reinitialized.
        Useful for testing or when you need to reconfigure the logger.
        """
        cls._logger = None


class StructuredError(Exception):
    """全プロジェクト共通の基底例外クラス（LogItem 統一処理）

    この基底クラスを継承することで、すべての例外が LogItem を統一的に扱えます。

    Attributes:
        log_item: ログ情報を保持する LogItem インスタンス

    Example:
        >>> from .structured_logger import LogItem, LogLevel
        >>> log_item = LogItem("エラー発生", {"file": "test.zip"}, LogLevel.ERROR)
        >>> raise ComponentError(log_item)

        >>> raise ComponentError("簡単なエラーメッセージ")  # 文字列も可
    """

    def __init__(self, log_item: LogItem | str) -> None:
        """
        Args:
            log_item: LogItem インスタンスまたは文字列メッセージ
                     文字列の場合は自動的に LogItem(message, level=ERROR) に変換
        """
        if isinstance(log_item, str):
            # 遅延インポートで循環依存を回避
            from smrlib.structured_logger import LogItem, LogLevel  # noqa: PLC0415

            log_item = LogItem(log_item, level=LogLevel.ERROR)

        self.log_item = log_item
        super().__init__(str(log_item))
