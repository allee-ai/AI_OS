from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    app_name: str = "React Chat Backend"
    cors_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]
    demo_agent_path: str = "../demo-integration"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()