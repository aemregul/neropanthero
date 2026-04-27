"""
Uygulama konfigürasyonu.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Uygulama ayarları."""
    
    # Uygulama
    APP_NAME: str = "Nero Panthero AI Studio"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # API
    API_PREFIX: str = "/api/v1"
    
    # URL'ler
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
    
    # Veritabanı
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pepperroot"
    
    # Güvenlik
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 gün (beni hatırla için)
    
    # AI APIs
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None  # ChatGPT/GPT-4
    FAL_KEY: Optional[str] = None
    SERPAPI_KEY: Optional[str] = None  # Web search for images
    GEMINI_API_KEY: Optional[str] = None  # Google Gemini (image editing)
    
    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    
    # Storage
    STORAGE_TYPE: str = "local"
    STORAGE_PATH: str = "./uploads"
    
    # Redis — REDIS_URL varsa otomatik aktif olur
    REDIS_URL: Optional[str] = None
    USE_REDIS: bool = False  # REDIS_URL set edilirse otomatik True olur
    
    @property
    def redis_enabled(self) -> bool:
        """Redis aktif mi? REDIS_URL varsa veya USE_REDIS=true ise aktif."""
        return self.USE_REDIS or bool(self.REDIS_URL)
    
    # Pinecone Semantic Search
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_INDEX_NAME: str = "neropanthero"
    PINECONE_ENVIRONMENT: str = "us-east-1"
    USE_PINECONE: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
