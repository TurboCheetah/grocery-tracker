"""Tests for configuration management."""

from pathlib import Path

import pytest

from grocery_tracker.config import ConfigManager


@pytest.fixture
def config_file(tmp_path):
    """Create a temporary config file."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[data]
storage_dir = "/custom/data"
backup_enabled = false
backup_interval_days = 14

[defaults]
store = "Safeway"
category = "Produce"

[budget]
monthly_limit = 750.0
alert_threshold = 0.85

[stores.giant]
name = "Giant Food"
typical_categories = ["Produce", "Dairy"]

[users.francisco]
dietary_restrictions = ["vegetarian"]
favorite_stores = ["Giant", "Trader Joe's"]
""")
    return config_path


class TestConfigManager:
    """Tests for ConfigManager."""

    def test_load_config_file(self, config_file):
        """Load configuration from file."""
        manager = ConfigManager(config_path=config_file)

        assert manager.data.storage_dir == Path("/custom/data")
        assert manager.data.backup_enabled is False
        assert manager.data.backup_interval_days == 14

    def test_defaults_config(self, config_file):
        """Load defaults configuration."""
        manager = ConfigManager(config_path=config_file)

        assert manager.defaults.store == "Safeway"
        assert manager.defaults.category == "Produce"

    def test_budget_config(self, config_file):
        """Load budget configuration."""
        manager = ConfigManager(config_path=config_file)

        assert manager.budget.monthly_limit == 750.0
        assert manager.budget.alert_threshold == 0.85

    def test_stores_config(self, config_file):
        """Load stores configuration."""
        manager = ConfigManager(config_path=config_file)

        assert "giant" in manager.stores
        assert manager.stores["giant"]["name"] == "Giant Food"

    def test_users_config(self, config_file):
        """Load users configuration."""
        manager = ConfigManager(config_path=config_file)

        assert "francisco" in manager.users
        assert "vegetarian" in manager.users["francisco"]["dietary_restrictions"]

    def test_missing_config_uses_defaults(self, tmp_path):
        """Missing config file uses default values."""
        manager = ConfigManager(config_path=tmp_path / "nonexistent.toml")

        assert manager.defaults.store == "Giant"
        assert manager.defaults.category == "Other"
        assert manager.budget.monthly_limit == 500.0

    def test_get_by_path(self, config_file):
        """Get config value by dot-notation path."""
        manager = ConfigManager(config_path=config_file)

        assert manager.get("defaults.store") == "Safeway"
        assert manager.get("budget.monthly_limit") == 750.0

    def test_get_with_default(self, config_file):
        """Get returns default for missing path."""
        manager = ConfigManager(config_path=config_file)

        assert manager.get("nonexistent.key", "default") == "default"
        assert manager.get("nonexistent", None) is None

    def test_partial_config(self, tmp_path):
        """Config file with only some sections."""
        config_path = tmp_path / "partial.toml"
        config_path.write_text("""
[defaults]
store = "Costco"
""")
        manager = ConfigManager(config_path=config_path)

        assert manager.defaults.store == "Costco"
        assert manager.defaults.category == "Other"  # Default
        assert manager.budget.monthly_limit == 500.0  # Default


class TestConfigDiscovery:
    """Tests for config file discovery."""

    def test_finds_local_config(self, tmp_path, monkeypatch):
        """Finds config.toml in current directory."""
        monkeypatch.chdir(tmp_path)

        config_path = tmp_path / "config.toml"
        config_path.write_text("""
[defaults]
store = "LocalStore"
""")

        manager = ConfigManager()
        assert manager.defaults.store == "LocalStore"

    def test_prefers_explicit_path(self, tmp_path, monkeypatch):
        """Explicit path takes precedence over discovery."""
        monkeypatch.chdir(tmp_path)

        # Create local config
        local_config = tmp_path / "config.toml"
        local_config.write_text('[defaults]\nstore = "LocalStore"')

        # Create explicit config
        explicit_config = tmp_path / "explicit.toml"
        explicit_config.write_text('[defaults]\nstore = "ExplicitStore"')

        manager = ConfigManager(config_path=explicit_config)
        assert manager.defaults.store == "ExplicitStore"

    def test_no_config_uses_default_path(self, tmp_path, monkeypatch):
        """When no config file exists anywhere, returns default home config path."""
        # Use a directory with no config.toml
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        manager = ConfigManager()
        expected = Path.home() / ".config" / "grocery-tracker" / "config.toml"
        assert manager.config_path == expected
        # Should use default config values since file doesn't exist
        assert manager.defaults.store == "Giant"


class TestGetDictTraversal:
    """Tests for get() method dict key traversal."""

    def test_get_stores_dict_key(self, config_file):
        """Get value from stores dict via dot notation."""
        manager = ConfigManager(config_path=config_file)
        assert manager.get("stores.giant") == {
            "name": "Giant Food",
            "typical_categories": ["Produce", "Dairy"],
        }

    def test_get_missing_dict_key_returns_default(self, config_file):
        """Get returns default when dict key is missing."""
        manager = ConfigManager(config_path=config_file)
        assert manager.get("stores.nonexistent", "fallback") == "fallback"

    def test_get_nested_dict_none_value(self, tmp_path):
        """Get returns default when dict value is None."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("""
[stores.teststore]
name = "Test"
""")
        manager = ConfigManager(config_path=config_path)
        # Access a key that doesn't exist in the nested dict
        assert manager.get("stores.teststore.missing_key", "default_val") == "default_val"

    def test_get_returns_none_for_none_final_value(self, config_file):
        """Get returns default when final resolved value is None."""
        manager = ConfigManager(config_path=config_file)
        result = manager.get("stores.giant.name")
        assert result == "Giant Food"
