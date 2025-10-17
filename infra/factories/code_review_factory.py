from infra.providers.base import ProviderConfig
from infra.providers.openai_client import OpenAIClient
from infra.providers.azure_client import AzureOpenAIClient
from domain.application.code_review_service import CodeReviewService


def build_code_review_service(provider: str, api_key: str, model: str,
                              azure_api_base: str = "", azure_api_version: str = "") -> CodeReviewService:
    cfg = ProviderConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        azure_api_base=azure_api_base,
        azure_api_version=azure_api_version,
    )
    if provider == "OpenAI":
        client = OpenAIClient(cfg)
    else:
        client = AzureOpenAIClient(cfg)
    return CodeReviewService(client, default_model=model)