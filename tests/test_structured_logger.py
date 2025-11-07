"""Tests for structured_logger module."""

import logging
from pathlib import Path

import pytest

from smrlib.structured_logger import (
    LogConfig,
    LoggerContext,
    LogItem,
    LogLevel,
    StructuredError,
    StructuredLogger,
    detect_log_config,
)


class TestLogConfig:
    """Test LogConfig class."""

    def test_default_config(self):
        """Test: LogConfigのデフォルト設定を確認"""
        print("Testing LogConfig default configuration")

        config = LogConfig()

        assert config.level == logging.INFO
        assert config.log_file is None
        assert config.dry_run is False
        assert config.log_file_max_bytes == 1 * 1024 * 1024
        assert config.log_file_backup_count == 1

        print("Confirmed: Default LogConfig settings are correct")

    def test_custom_config(self):
        """Test: LogConfigのカスタム設定を確認"""
        print("Testing LogConfig custom configuration")

        config = LogConfig(
            level=logging.DEBUG,
            log_file=Path("test.log"),
            dry_run=True,
            log_file_max_bytes=2048,
            log_file_backup_count=3,
        )

        assert config.level == logging.DEBUG
        assert config.log_file == Path("test.log")
        assert config.dry_run is True
        assert config.log_file_max_bytes == 2048
        assert config.log_file_backup_count == 3

        print("Confirmed: Custom LogConfig settings are applied correctly")


class TestLogLevel:
    """Test LogLevel enum."""

    def test_log_levels(self):
        """Test: LogLevelの各レベルが正しく定義されているか確認"""
        print("Testing LogLevel enum values")

        assert LogLevel.SUCCESS == 0
        assert LogLevel.ERROR == 1
        assert LogLevel.WARNING == 5
        assert LogLevel.INFO == 10
        assert LogLevel.NOTICE == 15
        assert LogLevel.DEBUG == 100

        print("Confirmed: All LogLevel values are correctly defined")

    def test_log_level_ordering(self):
        """Test: LogLevelの順序が正しいか確認"""
        print("Testing LogLevel ordering")

        assert LogLevel.SUCCESS < LogLevel.ERROR
        assert LogLevel.ERROR < LogLevel.WARNING
        assert LogLevel.WARNING < LogLevel.INFO
        assert LogLevel.INFO < LogLevel.NOTICE
        assert LogLevel.NOTICE < LogLevel.DEBUG

        print("Confirmed: LogLevel ordering is correct")


class TestLogItem:
    """Test LogItem class."""

    def test_factory_methods(self):
        """Test: LogItemのファクトリメソッドを確認"""
        print("Testing LogItem factory methods")

        success_item = LogItem.success("Success message")
        assert success_item.level == LogLevel.SUCCESS
        assert success_item.message == "Success message"

        error_item = LogItem.error("Error message", {"code": 500})
        assert error_item.level == LogLevel.ERROR
        assert error_item.message == "Error message"
        assert error_item.context == {"code": 500}

        warning_item = LogItem.warning("Warning message")
        assert warning_item.level == LogLevel.WARNING

        info_item = LogItem.info("Info message")
        assert info_item.level == LogLevel.INFO

        notice_item = LogItem.notice("Notice message")
        assert notice_item.level == LogLevel.NOTICE

        debug_item = LogItem.debug("Debug message")
        assert debug_item.level == LogLevel.DEBUG

        print("Confirmed: All factory methods create LogItems with correct levels")

    def test_format_console_simple(self):
        """Test: コンソール出力フォーマット（単純なメッセージ）を確認"""
        print("Testing LogItem console format for simple messages")

        item = LogItem("Simple message")
        assert item.format_console() == "Simple message"

        item_with_str = LogItem("Message", "context")
        assert item_with_str.format_console() == "Message: context"

        item_with_int = LogItem("Count", 42)
        assert item_with_int.format_console() == "Count: 42"

        print("Confirmed: Simple console formatting works correctly")

    def test_format_console_dict(self):
        """Test: コンソール出力フォーマット（辞書）を確認"""
        print("Testing LogItem console format for dict context")

        # Single item dict
        item_single = LogItem("Config", {"key": "value"})
        formatted = item_single.format_console()
        assert "Config:" in formatted
        assert "key='value'" in formatted

        # Multiple items dict
        item_multi = LogItem("Config", {"key1": "value1", "key2": 123})
        formatted_multi = item_multi.format_console()
        assert "Config:" in formatted_multi
        assert "key1='value1'" in formatted_multi
        assert "key2=123" in formatted_multi

        print("Confirmed: Dict console formatting works correctly")

    def test_format_file(self):
        """Test: ファイル出力フォーマットを確認"""
        print("Testing LogItem file format")

        item = LogItem("Message", {"key": "value", "num": 42})
        formatted = item.format_file()
        assert "Message, " in formatted
        assert "key='value'" in formatted
        assert "num=42" in formatted

        print("Confirmed: File formatting works correctly")

    def test_str_method(self):
        """Test: __str__メソッドを確認"""
        print("Testing LogItem __str__ method")

        item = LogItem("Test message")
        assert str(item) == "Test message"

        print("Confirmed: __str__ returns console format")


class TestStructuredLogger:
    """Test StructuredLogger class."""

    def test_logger_initialization(self):
        """Test: StructuredLoggerの初期化を確認"""
        print("Testing StructuredLogger initialization")

        logger = StructuredLogger("test_logger", config=LogConfig(level=logging.DEBUG))

        assert logger is not None
        assert logger.logger.level == logging.DEBUG

        print("Confirmed: StructuredLogger initializes correctly")

    def test_logger_with_file(self, temp_dir):
        """Test: ファイル出力付きStructuredLoggerを確認"""
        print("Testing StructuredLogger with file output")

        log_file = temp_dir / "test.log"
        logger = StructuredLogger("test_file_logger", log_file_path=log_file, config=LogConfig(level=logging.INFO))

        logger.info("Test message")

        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "Test message" in content

        # Explicitly close to test the close() method and release file lock
        logger.close()

        print("Confirmed: File logging works correctly")

    def test_logger_auto_cleanup(self, temp_dir):
        """Test: StructuredLoggerが自動的にリソースを解放することを確認"""
        print("Testing StructuredLogger automatic resource cleanup")

        log_file = temp_dir / "auto_cleanup.log"

        # Create logger in a scope and let it go out of scope
        logger = StructuredLogger("test_auto_cleanup", log_file_path=log_file, config=LogConfig(level=logging.INFO))
        logger.info("Test auto cleanup")

        # Delete the logger to trigger __del__
        del logger

        # Force garbage collection to ensure __del__ is called
        import gc

        gc.collect()

        # File should be accessible now (not locked on Windows)
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "Test auto cleanup" in content

        print("Confirmed: Auto cleanup releases file resources")

    def test_log_methods(self):
        """Test: 各種ログメソッドを確認"""
        print("Testing various log methods")

        logger = StructuredLogger("test_methods", config=LogConfig(level=logging.DEBUG))

        # These should not raise exceptions
        logger.debug("Debug message")
        logger.notice("Notice message")
        logger.info("Info message")
        logger.success("Success message")
        logger.warning("Warning message")
        logger.error("Error message")

        print("Confirmed: All log methods execute without errors")

    def test_log_with_context(self):
        """Test: コンテキスト付きログを確認"""
        print("Testing log with context")

        logger = StructuredLogger("test_context", config=LogConfig(level=logging.INFO))

        # Should not raise exception
        logger.info("Message with context", {"key": "value"})

        print("Confirmed: Logging with context works correctly")


class TestLoggerContext:
    """Test LoggerContext class."""

    def test_singleton_pattern(self):
        """Test: LoggerContextのシングルトンパターンを確認"""
        print("Testing LoggerContext singleton pattern")

        # Initialize
        test_logger = StructuredLogger("test_singleton")
        LoggerContext.initialize(test_logger)
        logger1 = LoggerContext.get_logger()
        logger2 = LoggerContext.get_logger()

        assert logger1 is logger2

        print("Confirmed: LoggerContext returns same instance (singleton)")

    def test_initialization_required(self):
        """Test: 初期化前のget_loggerがエラーを出すか確認"""
        print("Testing LoggerContext requires initialization")

        # Reset the singleton
        LoggerContext._logger = None

        with pytest.raises(RuntimeError, match="LoggerContext not initialized"):
            LoggerContext.get_logger()

        print("Confirmed: get_logger raises error before initialization")

        # Re-initialize for other tests
        LoggerContext.initialize()


class TestStructuredError:
    """Test StructuredError exception."""

    def test_error_with_string(self):
        """Test: 文字列からStructuredErrorを生成"""
        print("Testing StructuredError with string message")

        error = StructuredError("Error message")
        assert str(error) == "Error message"
        assert error.log_item.message == "Error message"
        assert error.log_item.level == LogLevel.ERROR

        print("Confirmed: StructuredError works with string message")

    def test_error_with_log_item(self):
        """Test: LogItemからStructuredErrorを生成"""
        print("Testing StructuredError with LogItem")

        log_item = LogItem.error("Custom error", {"code": 404})
        error = StructuredError(log_item)

        assert error.log_item is log_item
        assert "Custom error" in str(error)

        print("Confirmed: StructuredError works with LogItem")


class TestDetectLogConfig:
    """Test detect_log_config function."""

    def test_default_config(self):
        """Test: デフォルト設定の検出を確認"""
        print("Testing detect_log_config with default arguments")

        config = detect_log_config([])
        assert config.level is None  # No --log-level argument means None
        assert config.log_file is None
        assert config.dry_run is False  # Default value from LogConfig

        print("Confirmed: Default config detection works")

    def test_log_level_flag(self):
        """Test: --log-levelフラグの検出を確認"""
        print("Testing detect_log_config with --log-level flag")

        config = detect_log_config(["--log-level", "10"])
        assert config.level == 10

        print("Confirmed: --log-level flag is detected correctly")

    def test_log_file_flag(self):
        """Test: --log-fileフラグの検出を確認"""
        print("Testing detect_log_config with --log-file flag")

        config = detect_log_config(["--log-file", "test.log"])
        assert config.log_file == Path("test.log")

        print("Confirmed: --log-file flag is detected correctly")
