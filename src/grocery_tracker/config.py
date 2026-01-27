"""Configuration management for Grocery Tracker."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DataConfig:
    """Data storage configuration."""

    storage_dir: Path
    backup_enabled: bool = True
    backup_interval_days: int = 7


@dataclass
class DefaultsConfig:
    """Default values configuration."""

    store: str = "Giant"
    category: str = "Other"


@dataclass
class BudgetConfig:
    """Budget configuration."""

    monthly_limit: float = 500.0
    alert_threshold: float = 0.9


@dataclass
class Config:
    """Complete application configuration."""

    data: DataConfig
    defaults: DefaultsConfig
    budget: BudgetConfig
    stores: dict[str, Any] = field(default_factory=dict)
    users: dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """Manages application configuration from TOML files."""

    def __init__(self, config_path: Path | None = None):
        """Initialize configuration manager.

        Args:
            config_path: Optional explicit path to config file.
                        If not provided, searches standard locations.
        """
        self.config_path = config_path or self._find_config()
        self._config = self._load_config()

    @property
    def data(self) -> DataConfig:
        """Get data configuration."""
        return self._config.data

    @property
    def defaults(self) -> DefaultsConfig:
        """Get defaults configuration."""
        return self._config.defaults

    @property
    def budget(self) -> BudgetConfig:
        """Get budget configuration."""
        return self._config.budget

    @property
    def stores(self) -> dict[str, Any]:
        """Get stores configuration."""
        return self._config.stores

    @property
    def users(self) -> dict[str, Any]:
        """Get users configuration."""
        return self._config.users

    def _find_config(self) -> Path:
        """Find config file in standard locations."""
        locations = [
            Path.cwd() / "config.toml",
            Path.home() / ".config" / "grocery-tracker" / "config.toml",
            Path.home() / ".grocery-tracker" / "config.toml",
        ]

        for loc in locations:
            if loc.exists():
                return loc

        # Return default location if none found
        return Path.home() / ".config" / "grocery-tracker" / "config.toml"

    def _load_config(self) -> Config:
        """Load configuration from TOML file."""
        if not self.config_path.exists():
            return self._default_config()

        with open(self.config_path, "rb") as f:
            data = tomllib.load(f)

        return Config(
            data=DataConfig(
                storage_dir=Path(
                    data.get("data", {}).get("storage_dir", "~/grocery-tracker/data")
                ).expanduser(),
                backup_enabled=data.get("data", {}).get("backup_enabled", True),
                backup_interval_days=data.get("data", {}).get("backup_interval_days", 7),
            ),
            defaults=DefaultsConfig(
                store=data.get("defaults", {}).get("store", "Giant"),
                category=data.get("defaults", {}).get("category", "Other"),
            ),
            budget=BudgetConfig(
                monthly_limit=data.get("budget", {}).get("monthly_limit", 500.0),
                alert_threshold=data.get("budget", {}).get("alert_threshold", 0.9),
            ),
            stores=data.get("stores", {}),
            users=data.get("users", {}),
        )

    def _default_config(self) -> Config:
        """Return default configuration."""
        return Config(
            data=DataConfig(storage_dir=Path.home() / "grocery-tracker" / "data"),
            defaults=DefaultsConfig(),
            budget=BudgetConfig(),
            stores={},
            users={},
        )

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get config value by dot-notation path.

        Args:
            key_path: Dot-separated path like 'data.storage_dir'
            default: Default value if path not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split(".")
        value: Any = self._config

        for key in keys:
            if hasattr(value, key):
                value = getattr(value, key)
            elif isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default
