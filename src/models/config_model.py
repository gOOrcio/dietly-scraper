import json
from pathlib import Path
from typing import List, Optional, Type, TypeVar

import yaml
from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


def load_configuration_from_file(model: Type[T], file_path: str) -> T:
    """Load configuration from YAML or JSON file.
    
    Args:
        model: Pydantic model class to validate configuration
        file_path: Path to configuration file (.yaml, .yml, or .json)
        
    Returns:
        Validated configuration model instance
        
    Raises:
        FileNotFoundError: If configuration file doesn't exist
        ValueError: If file format is unsupported
    """
    config_path = Path(file_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    if config_path.suffix in [".yaml", ".yml"]:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    elif config_path.suffix == ".json":
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        raise ValueError(f"Unsupported configuration file format: {config_path.suffix}. Use .json or .yaml/.yml")

    return model.model_validate(data)


class SiteConfiguration(BaseModel):
    """Configuration for a single site/service."""
    base_url: Optional[str] = Field(default=None, description="Base URL of the service")
    login_url: Optional[str] = Field(default=None, description="Login endpoint URL")
    api_url: Optional[str] = Field(default=None, description="API base URL")


class SitesConfiguration(BaseModel):
    """Configuration for all sites/services."""
    dietly: SiteConfiguration = Field(description="Dietly service configuration")
    fitatu: SiteConfiguration = Field(description="Fitatu service configuration")

    @classmethod
    def load_from_file(cls, file_path: str = "config/sites.yaml") -> "SitesConfiguration":
        """Load sites configuration from file.
        
        Args:
            file_path: Path to sites configuration file
            
        Returns:
            Validated sites configuration
        """
        return load_configuration_from_file(cls, file_path)


class DietlyCredentials(BaseModel):
    """Credentials for Dietly service."""
    email: str = Field(description="Dietly account email")
    password: str = Field(description="Dietly account password")


class FitatuCredentials(BaseModel):
    """Credentials for Fitatu service."""
    email: str = Field(description="Fitatu account email")
    password: str = Field(description="Fitatu account password")
    api_secret: str = Field(description="Fitatu API secret key")


class UserConfiguration(BaseModel):
    """Configuration for a single user."""
    name: str = Field(description="User display name")
    dietly_credentials: DietlyCredentials = Field(description="Dietly login credentials")
    fitatu_credentials: FitatuCredentials = Field(description="Fitatu login credentials")


class UsersConfiguration(BaseModel):
    """Configuration for all users."""
    users: List[UserConfiguration] = Field(description="List of user configurations")

    @classmethod
    def load_from_file(cls, file_path: str = "config/users.yaml") -> "UsersConfiguration":
        """Load users configuration from file.
        
        Args:
            file_path: Path to users configuration file
            
        Returns:
            Validated users configuration
        """
        return load_configuration_from_file(cls, file_path)
