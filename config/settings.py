from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Provider ---
    PROVIDER: str = "OpenAI"  # hoặc "AzureOpenAI"

    # --- OpenAI ---
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4"

    # --- Azure OpenAI ---
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_BASE: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # --- Common model parameters ---
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0.3
    TOP_P: float = 1.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
