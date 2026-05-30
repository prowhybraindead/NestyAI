from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.embeddings import EmbeddingResult


class BaseEmbeddingProvider(ABC):
    provider_name: str

    @abstractmethod
    async def embed_text(self, text: str, model: str) -> EmbeddingResult:
        raise NotImplementedError

    async def embed_batch(self, texts: list[str], model: str) -> list[EmbeddingResult]:
        results: list[EmbeddingResult] = []
        for text in texts:
            results.append(await self.embed_text(text=text, model=model))
        return results
