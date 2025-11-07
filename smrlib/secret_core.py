"""Secret management core with pluggable storage backends."""

import os
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, load_dotenv, set_key


class SecretStorageType(Enum):
    """Secret storage backend types."""

    DOTENV = "dotenv"
    # Future: DATABASE = "database", VAULT = "vault", etc.


class SecretStorage(ABC):
    """Abstract base class for secret storage backends."""

    @abstractmethod
    def load(self, key: str) -> str | None:
        """Load secret value by key."""
        pass

    @abstractmethod
    def save(self, key: str, value: str) -> None:
        """Save secret value by key."""
        pass

    @abstractmethod
    def load_all(self) -> dict[str, str]:
        """Load all secrets."""
        pass


class DotEnvStorage(SecretStorage):
    """DotEnv file-based secret storage."""

    def __init__(self, env_file_path: str = ".env"):
        """Initialize DotEnv storage.

        Args:
            env_file_path: Path to .env file
        """
        self.env_file_path = Path(env_file_path)
        # Ensure .env file exists
        if not self.env_file_path.exists():
            self.env_file_path.touch()

        # Load .env into environment variables
        load_dotenv(self.env_file_path)

    def load(self, key: str) -> str | None:
        """Load secret from environment variables.

        Args:
            key: Secret key name

        Returns:
            Secret value or None if not found
        """
        return os.getenv(key)

    def save(self, key: str, value: str) -> None:
        """Save secret to .env file.

        Args:
            key: Secret key name
            value: Secret value
        """
        set_key(self.env_file_path, key, value)
        # Reload environment variables to reflect changes
        load_dotenv(self.env_file_path, override=True)

    def load_all(self) -> dict[str, str]:
        """Load all secrets from .env file.

        Returns:
            Dictionary of all key-value pairs from .env (None values excluded)
        """
        raw_values = dotenv_values(self.env_file_path)
        # Filter out None values to ensure type safety
        return {k: v for k, v in raw_values.items() if v is not None}


class SecretCore:
    """Core secret management with pluggable storage backends (Singleton)."""

    _instance: "SecretCore | None" = None
    _initialized: bool = False

    def __new__(cls) -> "SecretCore":
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize SecretCore (only once)."""
        # Prevent re-initialization
        if self._initialized:
            return

        self.storage_type: SecretStorageType = SecretStorageType.DOTENV
        self.storage: SecretStorage | None = None
        self._allow_overwrite_keys: set[str] = set()
        self._initialized = True

    @classmethod
    def initialize(
        cls,
        storage_type: SecretStorageType = SecretStorageType.DOTENV,
        allow_overwrite_keys: list[str] | None = None,
        **kwargs: Any,
    ) -> "SecretCore":
        """Initialize SecretCore singleton with specified configuration.

        Args:
            storage_type: Type of storage backend to use
            allow_overwrite_keys: List of keys that can be overwritten at runtime
            **kwargs: Additional arguments passed to storage backend

        Returns:
            SecretCore instance
        """
        instance = cls()
        if instance.storage is None:  # Only initialize once
            instance.storage_type = storage_type
            instance.storage = instance._create_storage(storage_type, **kwargs)
            instance._allow_overwrite_keys = set(allow_overwrite_keys or [])
        return instance

    @classmethod
    def get_instance(cls) -> "SecretCore":
        """Get SecretCore instance.

        Returns:
            SecretCore instance

        Raises:
            RuntimeError: If SecretCore has not been initialized
        """
        if cls._instance is None or cls._instance.storage is None:
            raise RuntimeError("SecretCore must be initialized first using SecretCore.initialize()")
        return cls._instance

    def _create_storage(self, storage_type: SecretStorageType, **kwargs: Any) -> SecretStorage:
        """Create storage backend instance.

        Args:
            storage_type: Type of storage backend
            **kwargs: Additional arguments for storage backend

        Returns:
            Storage backend instance

        Raises:
            ValueError: If storage type is not supported
        """
        if storage_type == SecretStorageType.DOTENV:
            return DotEnvStorage(**kwargs)
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")

    def get(self, key: str) -> str | None:
        """Get secret value by key.

        Args:
            key: Secret key name

        Returns:
            Secret value or None if not found
        """
        if not self.storage:
            raise RuntimeError("SecretCore not initialized")
        return self.storage.load(key)

    def set(self, key: str, value: str) -> None:
        """Set secret value by key.

        Args:
            key: Secret key name
            value: Secret value

        Raises:
            ValueError: If key is not allowed to be overwritten
        """
        if not self.storage:
            raise RuntimeError("SecretCore not initialized")

        # Check if overwrite is allowed for runtime updates
        existing_value = self.storage.load(key)
        if existing_value is not None and key not in self._allow_overwrite_keys:
            raise ValueError(f"Key '{key}' is not allowed to be overwritten at runtime")

        self.storage.save(key, value)

    def get_all(self) -> dict[str, str]:
        """Get all secrets.

        Returns:
            Dictionary of all secrets
        """
        if not self.storage:
            raise RuntimeError("SecretCore not initialized")
        return self.storage.load_all()

    def has(self, key: str) -> bool:
        """Check if secret key exists.

        Args:
            key: Secret key name

        Returns:
            True if key exists, False otherwise
        """
        return self.get(key) is not None

    def require(self, key: str) -> str:
        """Get required secret value.

        Args:
            key: Secret key name

        Returns:
            Secret value

        Raises:
            ValueError: If secret key is not found
        """
        value = self.get(key)
        if value is None:
            raise ValueError(f"Required secret '{key}' not found")
        return value
