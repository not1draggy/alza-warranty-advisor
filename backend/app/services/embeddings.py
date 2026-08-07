"""Embedding generation for the RAG store."""

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger

logger = get_logger(__name__)

_MAX_BATCH = 64


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        api_key = settings.secret(settings.openai_api_key)
        self._model = settings.embedding_model
        self._dimensions = settings.embedding_dimensions
        self._client = (
            AsyncOpenAI(api_key=api_key, timeout=settings.llm_timeout_seconds, max_retries=2)
            if api_key
            else None
        )

    @property
    def configured(self) -> bool:
        return self._client is not None

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns an empty list when unconfigured."""
        if self._client is None or not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _MAX_BATCH):
            batch = [text[:8000] for text in texts[start : start + _MAX_BATCH]]
            try:
                response = await self._client.embeddings.create(
                    model=self._model, input=batch, dimensions=self._dimensions
                )
            except RateLimitError as exc:
                raise ProviderUnavailable("Embedding provider is rate limited.") from exc
            except (APIConnectionError, APIStatusError) as exc:
                logger.warning("embedding_request_failed", error=str(exc))
                raise ProviderUnavailable("Embedding provider could not be reached.") from exc
            vectors.extend(item.embedding for item in response.data)
        return vectors

    async def embed_one(self, text: str) -> list[float] | None:
        vectors = await self.embed([text])
        return vectors[0] if vectors else None
