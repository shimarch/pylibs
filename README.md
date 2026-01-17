# smrlib

Personal utility library for Python projects.

## Table of Contents

- [Table of Contents](#table-of-contents)
- [Installation](#installation)
  - [Using uv](#using-uv)
  - [Using pip](#using-pip)
- [Update](#update)
  - [Using uv](#using-uv-1)
  - [Using pip](#using-pip-1)
- [Modules](#modules)
- [API Reference](#api-reference)
  - [structured_logger](#structured_logger)
    - [LoggerContext](#loggercontext)

## Installation

### Using uv

```bash
uv add git+https://github.com/shimarch/pylibs.git
```

### Using pip

```bash
pip install git+https://github.com/shimarch/pylibs.git
```

## Update

### Using uv

Git dependencies are heavily cached by `uv`. Use the following commands to ensure you get the latest version:

```bash
uv cache clean
uv sync
```

### Using pip

```bash
pip install --upgrade git+https://github.com/shimarch/pylibs.git
```

## Modules

- `structured_logger` - Structured logging with emoji and context support
- `secret_core` - Secret management with pluggable storage backends
- `google_chat_client` - Google Chat API client for webhook-based messaging
- `google_sheet_client` - Google Sheets API client

## API Reference

### structured_logger

#### LoggerContext

Global singleton context for managing the application logger.

**Methods:**

- `initialize(logger: StructuredLogger | None = None) -> StructuredLogger`
  - Initialize the global logger
  - Args:
    - `logger`: Optional logger instance. If None, creates a default logger.
  - Returns: The initialized logger instance

- `get_logger() -> StructuredLogger`
  - Get the logger instance
  - Returns: The logger instance
  - Raises: `RuntimeError` if logger is not initialized

- `is_initialized() -> bool`
  - Check if logger is initialized
  - Returns: True if logger is initialized, False otherwise

- `reset() -> None`
  - Reset the logger instance
  - This clears the current logger instance, allowing it to be reinitialized
  - Useful for testing or when you need to reconfigure the logger

**Example:**

```python
from smrlib.structured_logger import LoggerContext

# Initialize logger
LoggerContext.initialize()

# Use logger in any module
class MyClass:
    def __init__(self):
        self.logger = LoggerContext.get_logger()

    def do_something(self):
        self.logger.info("Task started", {"id": 123})
        self.logger.success("Task completed")

# Reset logger (e.g., for testing)
LoggerContext.reset()
```
