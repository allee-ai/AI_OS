"""
Core Configuration
------------------
Application settings using pydantic-settings.
No Nola imports to avoid circular dependencies.
"""

from pydantic_settings import BaseSettings
from typing import List, Union
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file."""
    
    app_name: str = "Nola AI OS"
    cors_origins: Union[str, List[str]] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173", 
        "http://localhost:3000"
    ]
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    class Config:
        env_file = ".env"


settings = Settings()
