from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Provider ---
    PROVIDER: str = "AzureOpenAI"  # hoặc "OpenAI"

    # --- OpenAI ---
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4"

    # --- Azure OpenAI ---
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_BASE: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    AZURE_OPENAI_EMBED_MODEL: str = "text-embedding-3-small"
    AZURE_OPENAI_EMBEDDING_ENDPOINT: str = ""
    AZURE_OPENAI_EMBEDDING_API_KEY: str = ""
    AZURE_OPENAI_EMBEDDING_VERSION: str = "2024-07-01-preview"

    PINECONE_API_KEY: str = ""
    

    # --- Common model parameters ---
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0
    TOP_P: float = 1.0
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
