"""Tests for secret_core module."""

import os
from pathlib import Path

import pytest

from smrlib.secret_core import DotEnvStorage, SecretCore, SecretStorageType


class TestDotEnvStorage:
    """Test DotEnvStorage class."""

    def test_initialization_creates_file(self, temp_dir):
        """Test: DotEnvStorageの初期化でファイルが作成されることを確認"""
        print("Testing DotEnvStorage creates .env file on initialization")

        env_file = temp_dir / "test.env"
        storage = DotEnvStorage(str(env_file))

        assert env_file.exists()

        print("Confirmed: .env file is created during initialization")

    def test_save_and_load(self, temp_env_file):
        """Test: 秘密情報の保存と読み込みを確認"""
        print("Testing DotEnvStorage save and load operations")

        storage = DotEnvStorage(str(temp_env_file))

        # Save
        storage.save("TEST_KEY", "test_value")

        # Load
        value = storage.load("TEST_KEY")
        assert value == "test_value"

        print("Confirmed: Save and load operations work correctly")

    def test_load_nonexistent_key(self, temp_env_file):
        """Test: 存在しないキーの読み込みがNoneを返すことを確認"""
        print("Testing DotEnvStorage returns None for nonexistent key")

        storage = DotEnvStorage(str(temp_env_file))
        value = storage.load("NONEXISTENT_KEY")

        assert value is None

        print("Confirmed: Returns None for nonexistent key")

    def test_load_all(self, temp_env_file):
        """Test: すべての秘密情報の読み込みを確認"""
        print("Testing DotEnvStorage load_all operation")

        storage = DotEnvStorage(str(temp_env_file))

        # Save multiple values
        storage.save("KEY1", "value1")
        storage.save("KEY2", "value2")
        storage.save("KEY3", "value3")

        # Load all
        all_secrets = storage.load_all()

        assert all_secrets["KEY1"] == "value1"
        assert all_secrets["KEY2"] == "value2"
        assert all_secrets["KEY3"] == "value3"

        print("Confirmed: load_all returns all stored secrets")

    def test_overwrite_value(self, temp_env_file):
        """Test: 既存の値の上書きを確認"""
        print("Testing DotEnvStorage overwrites existing values")

        storage = DotEnvStorage(str(temp_env_file))

        storage.save("KEY", "old_value")
        storage.save("KEY", "new_value")

        value = storage.load("KEY")
        assert value == "new_value"

        print("Confirmed: Existing values can be overwritten")


class TestSecretCore:
    """Test SecretCore class."""

    def setup_method(self):
        """Reset SecretCore singleton before each test."""
        print("Resetting SecretCore singleton")
        SecretCore._instance = None
        SecretCore._initialized = False

    def test_singleton_pattern(self, temp_env_file):
        """Test: SecretCoreのシングルトンパターンを確認"""
        print("Testing SecretCore singleton pattern")

        core1 = SecretCore.initialize(env_file_path=str(temp_env_file))
        core2 = SecretCore.get_instance()

        assert core1 is core2

        print("Confirmed: SecretCore follows singleton pattern")

    def test_initialization(self, temp_env_file):
        """Test: SecretCoreの初期化を確認"""
        print("Testing SecretCore initialization")

        core = SecretCore.initialize(
            storage_type=SecretStorageType.DOTENV,
            env_file_path=str(temp_env_file),
        )

        assert core is not None
        assert core.storage is not None
        assert core.storage_type == SecretStorageType.DOTENV

        print("Confirmed: SecretCore initializes correctly")

    def test_get_instance_before_initialization(self):
        """Test: 初期化前のget_instanceがエラーを出すことを確認"""
        print("Testing SecretCore.get_instance() before initialization")

        with pytest.raises(RuntimeError, match="SecretCore must be initialized first"):
            SecretCore.get_instance()

        print("Confirmed: Raises error when not initialized")

    def test_get_and_set(self, temp_env_file):
        """Test: get/setメソッドを確認"""
        print("Testing SecretCore get and set methods")

        core = SecretCore.initialize(env_file_path=str(temp_env_file))

        # Set
        core.set("API_KEY", "secret123")

        # Get
        value = core.get("API_KEY")
        assert value == "secret123"

        print("Confirmed: get and set methods work correctly")

    def test_require_existing_key(self, temp_env_file):
        """Test: requireメソッドが既存のキーを取得できることを確認"""
        print("Testing SecretCore.require() with existing key")

        core = SecretCore.initialize(env_file_path=str(temp_env_file))
        core.set("REQUIRED_KEY", "required_value")

        value = core.require("REQUIRED_KEY")
        assert value == "required_value"

        print("Confirmed: require() returns value for existing key")

    def test_require_missing_key(self, temp_env_file):
        """Test: requireメソッドが存在しないキーでエラーを出すことを確認"""
        print("Testing SecretCore.require() with missing key")

        core = SecretCore.initialize(env_file_path=str(temp_env_file))

        with pytest.raises(ValueError, match="Required secret 'MISSING_KEY' not found"):
            core.require("MISSING_KEY")

        print("Confirmed: require() raises error for missing key")

    def test_get_all(self, temp_env_file):
        """Test: get_allメソッドを確認"""
        print("Testing SecretCore.get_all() method")

        core = SecretCore.initialize(
            env_file_path=str(temp_env_file),
            allow_overwrite_keys=["KEY1", "KEY2"],
        )

        core.set("KEY1", "value1")
        core.set("KEY2", "value2")

        all_secrets = core.get_all()

        assert all_secrets["KEY1"] == "value1"
        assert all_secrets["KEY2"] == "value2"

        print("Confirmed: get_all() returns all secrets")

    def test_allow_overwrite_keys(self, temp_env_file):
        """Test: allow_overwrite_keysの機能を確認"""
        print("Testing SecretCore allow_overwrite_keys feature")

        core = SecretCore.initialize(
            env_file_path=str(temp_env_file),
            allow_overwrite_keys=["OVERWRITABLE_KEY"],
        )

        # First set
        core.set("OVERWRITABLE_KEY", "value1")

        # Overwrite should succeed (because it's in allow_overwrite_keys)
        core.set("OVERWRITABLE_KEY", "value2")

        value = core.get("OVERWRITABLE_KEY")
        assert value == "value2"

        print("Confirmed: Keys in allow_overwrite_keys can be overwritten")

    def test_prevent_overwrite_by_default(self, temp_env_file):
        """Test: デフォルトで上書きが禁止されていることを確認"""
        print("Testing SecretCore prevents overwrite by default")

        core = SecretCore.initialize(env_file_path=str(temp_env_file))

        core.set("PROTECTED_KEY", "original")

        # Second set should fail because PROTECTED_KEY is not in allow_overwrite_keys
        with pytest.raises(ValueError, match="not allowed to be overwritten"):
            core.set("PROTECTED_KEY", "new_value")

        print("Confirmed: Overwrites are prevented by default")


class TestSecretStorageType:
    """Test SecretStorageType enum."""

    def test_enum_values(self):
        """Test: SecretStorageTypeの値を確認"""
        print("Testing SecretStorageType enum values")

        assert SecretStorageType.DOTENV.value == "dotenv"

        print("Confirmed: SecretStorageType enum has correct values")
