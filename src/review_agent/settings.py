from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    github_token: str = ""
    webhook_secret: str = ""
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5-coder:7b"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    return Settings()
