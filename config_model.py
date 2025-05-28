from typing import List, Optional, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

def load_config(model: Type[T], path: str) -> T:
    from pathlib import Path
    import yaml, json
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
    return model.model_validate(data)

class Site(BaseModel):
    base_url: Optional[str] = None
    login_url: Optional[str] = None
    api_url: Optional[str] = None

class SitesConfig(BaseModel):
    dietly: Site
    fitatu: Site

    @staticmethod
    def load(path: str = "sites.yaml") -> "SitesConfig":
        return load_config(SitesConfig, path)

class DietlyCredentials(BaseModel):
    email: str
    password: str

class FitatuCredentials(BaseModel):
    email: str
    password: str
    api_secret: str
    user_id: str

class User(BaseModel):
    name: str
    dietly_credentials: DietlyCredentials
    fitatu_credentials: FitatuCredentials

class UsersConfig(BaseModel):
    users: List[User]

    @staticmethod
    def load(path: str = "users.yaml") -> "UsersConfig":
        return load_config(UsersConfig, path)
