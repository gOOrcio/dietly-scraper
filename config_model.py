from typing import List, Optional
from pydantic import BaseModel

class Site(BaseModel):
    base_url: Optional[str] = None
    login_url: Optional[str] = None
    api_url: Optional[str] = None

class SitesConfig(BaseModel):
    dietly: Site
    fitatu: Site

class DietlyCredentials(BaseModel):
    email: str
    password: str

class FitatuCredentials(BaseModel):
    email: str
    password: str
    api_secret: str

class User(BaseModel):
    name: str
    dietly_credentials: DietlyCredentials
    fitatu_credentials: FitatuCredentials

class Config(BaseModel):
    sites: SitesConfig
    users: List[User]

    @staticmethod
    def load(path: str = "config.yaml") -> "Config":
        """Load configuration from a YAML or JSON file."""
        from pathlib import Path
        import yaml
        import json
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        if config_path.suffix in [".yaml", ".yml"]:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        elif config_path.suffix == ".json":
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            raise ValueError("Unsupported config file format. Use .json or .yaml/.yml")
        return Config.model_validate(data)
