"""
Configuration management using Pydantic Settings.
Supports environment-specific configurations for Power BI ETL pipelines.
"""

from pathlib import Path
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection settings."""
    host: str = "localhost"
    port: int = 5432
    username: str = "etl_user"
    password: str = ""
    database: str = "powerbi_etl"
    pool_size: int = 5
    max_overflow: int = 10

    @property
    def url(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class SharePointSettings(BaseSettings):
    """SharePoint/OneDrive settings for Power BI data sources."""
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    site_url: str = ""
    drive_id: str = ""
    folder_path: str = "Documents/PowerBI/DataSources"


class Dynamics365Settings(BaseSettings):
    """Microsoft Dynamics 365 OData integration settings."""
    base_url: str = ""  # e.g., https://org.crm.dynamics.com
    client_id: str = ""
    client_secret: str = ""
    tenant_id: str = ""
    api_version: str = "v9.2"
    entities: List[str] = Field(default_factory=lambda: ["accounts", "contacts", "opportunities", "invoices"])


class PowerBISettings(BaseSettings):
    """Power BI Service integration settings."""
    workspace_id: str = ""
    dataset_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    tenant_id: str = ""


class PipelineSettings(BaseSettings):
    """ETL Pipeline execution settings."""
    default_chunk_size: int = 10000
    max_workers: int = 4
    timeout_seconds: int = 300
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    enable_incremental: bool = True
    watermark_column: str = "modifiedon"


class LoggingSettings(BaseSettings):
    """Structured logging configuration."""
    level: str = "INFO"
    format: str = "json"  # json or console
    output_file: Optional[str] = None


class Settings(BaseSettings):
    """Main application settings."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )

    # Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Paths
    project_root: Path = Path(__file__).parent.parent.parent.parent
    data_dir: Path = Path("data")
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    output_dir: Path = Path("data/output")
    config_dir: Path = Path("config")

    # Sub-settings
    database: DatabaseSettings = DatabaseSettings()
    sharepoint: SharePointSettings = SharePointSettings()
    dynamics365: Dynamics365Settings = Dynamics365Settings()
    powerbi: PowerBISettings = PowerBISettings()
    pipeline: PipelineSettings = PipelineSettings()
    logging: LoggingSettings = LoggingSettings()

    # Pipeline defaults
    default_source_type: str = "excel"  # excel, csv, sharepoint, dynamics365, odata

    @field_validator("data_dir", "raw_dir", "processed_dir", "output_dir", "config_dir", mode="before")
    @classmethod
    def resolve_paths(cls, v):
        if isinstance(v, str):
            return Path(v)
        return v


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
