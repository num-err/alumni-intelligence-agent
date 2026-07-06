"""Shared data structures for search results.

Kept separate from `tavily_client.py` so both the client and the cache
service (which serializes results to/from JSON) can depend on it without
importing each other.
"""

from dataclasses import asdict, dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    score: float
    source_query: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SearchResult":
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            content=data.get("content", ""),
            score=float(data.get("score", 0.0)),
            source_query=data.get("source_query", ""),
        )
