# retriever/pinecone_retriever.py
from typing import List
from langchain_openai import AzureOpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec
from langchain_community.document_loaders import TextLoader

from config.env import settings

from .base import BaseRuleRetriever, RuleSnippet, RuleSearchResult


class PineconeRuleRetriever(BaseRuleRetriever):
    """Simple Pinecone + LangChain retriever using language filter."""
    
    def __init__(self, index_name: str):
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        if index_name not in [index["name"] for index in pc.list_indexes()]:
            pc.create_index(
            name=index_name,
            dimension=1536,
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"),
            )
        self.index = pc.Index(index_name)
        self.embedding = AzureOpenAIEmbeddings(
                azure_endpoint=settings.AZURE_OPENAI_EMBEDDING_ENDPOINT,
                api_key=settings.AZURE_OPENAI_EMBEDDING_API_KEY,
                model=settings.AZURE_OPENAI_EMBED_MODEL,
                api_version=settings.AZURE_OPENAI_EMBEDDING_VERSION,
        )

    def search(self, query: str, language: str, k: int = 5, score_threshold: float = 0.25) -> RuleSearchResult:
        vs = PineconeVectorStore(
            index=self.index,
            embedding=self.embedding,
            text_key="text"
        )
        results = vs.similarity_search_with_score(
            query=query,
            k=k,
            filter={"language": {"$eq": language}}
        )
        snippets: List[RuleSnippet] = []
        for doc, score in results:
            if score < score_threshold:
                continue
            summary = (doc.page_content or "").strip()
            snippets.append(
                RuleSnippet(
                    summary=summary,
                    source_path=doc.metadata.get("source_path", "unknown"),
                    score=round(float(score), 4)
                )
            )
        return RuleSearchResult(hits=len(snippets), snippets=snippets)
    
    def import_rules_from_txt(
        self,
        file_path: str,
        *,
        language: str,
        source_path: str | None = None,
        chunk_size: int = 200,
        chunk_overlap: int = 20,
    ) -> int:
        """
        Ingest .txt into Pinecone via LangChain:
        - Load file (UTF-8)
        - Split (RecursiveCharacterTextSplitter) → cân bằng độ chính xác/độ trễ
        - Attach metadata: language (lowercase), source_path
        - Upsert bằng VectorStore (batch nội bộ)
        - Trả về số chunk đã ingest
        """
        lang = (language or "").strip().lower()
        loader = TextLoader(file_path, encoding="utf-8")
        docs = loader.load()

        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = splitter.split_documents(docs)

        src = source_path or file_path
        for d in chunks:
            d.metadata["language"] = lang
            d.metadata["source_path"] = src

            # làm sạch nhẹ nội dung
            if d.page_content:
                d.page_content = d.page_content.strip()

        # loại bỏ chunk rỗng
        chunks = [c for c in chunks if c.page_content]

        if not chunks:
            return 0

        vs = PineconeVectorStore(index=self.index, embedding=self.embedding, text_key="text")
        vs.add_documents(chunks)
        return len(chunks)
    

