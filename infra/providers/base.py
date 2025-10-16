from dataclasses import dataclass

class ProviderConfigError(RuntimeError):
    pass

@dataclass
class ProviderConfig:
    provider: str                 # "OpenAI" | "Azure OpenAI"
    api_key: str = ""
    model: str = ""              # OpenAI model or Azure deployment name
    azure_api_base: str = ""
    azure_api_version: str = ""