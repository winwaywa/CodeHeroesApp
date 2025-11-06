# retriever/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

@dataclass
class RuleSnippet:
    summary: str
    source_path: str
    score: float

@dataclass
class RuleSearchResult:
    hits: int
    snippets: List[RuleSnippet]

class BaseRuleRetriever(ABC):
    @abstractmethod
    def search(self, query: str, language: str) -> RuleSearchResult:
        """Retrieve related rule snippets by query and language."""
        raise NotImplementedError
