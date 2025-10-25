import chromadb
from chromadb.utils import embedding_functions
from config.settings import settings
from typing import Any, Dict, List

# Lưu cục bộ vào ./.chroma (bạn có thể đổi đường dẫn)
chroma_client = chromadb.PersistentClient(path="./.chroma")

# Tên collection cố định theo project; có thể thêm tiền tố theo repo name nếu muốn
CHROMA_COLLECTION = "code_heroes"

def build_embedding_fn():
    return embedding_functions.OpenAIEmbeddingFunction(
        api_key="sk-KGeQv7GAbxrP7Nb_juXtrg",
        api_base=settings.AZURE_OPENAI_API_BASE,
        model_name="text-embedding-3-small"
    )

def get_collection(collection_name, embedding_fn):
    try:
        return chroma_client.get_collection(name=collection_name)
    except Exception:
        return chroma_client.create_collection(name=collection_name, embedding_function=embedding_fn)
