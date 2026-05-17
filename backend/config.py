from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://ppe_user:ppe_password@localhost:5433/ppe_system"

    # JWT
    secret_key: str = "supersecretkey_change_in_production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # App
    backend_url: str = "http://localhost:8000"
    saved_violations_dir: str = "./saved_violations"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
