"""Search provider abstraction.

Adding a provider means implementing `SearchProvider` and registering it in
`registry.build_search_router` — nothing else in the system changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse


@dataclass(slots=True)
class SearchResult:
    url: str
    title: str
    snippet: str
    provider: str
    published_at: datetime | None = None
    raw_score: float = 0.0
    extra: dict = field(default_factory=dict)

    @property
    def domain(self) -> str:
        host = (urlparse(self.url).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host


class SearchProvider(ABC):
    name: str = "unknown"

    @property
    @abstractmethod
    def configured(self) -> bool: ...

    @abstractmethod
    async def search(self, query: str, *, limit: int) -> list[SearchResult]: ...
