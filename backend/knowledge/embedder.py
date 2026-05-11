import logging
from typing import List

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Singleton embedding service using text2vec-large-chinese (1024-dim)."""

    _instance = None

    def __init__(self):
        self._model = None

    @property
    def model(self):
        if self._model is None:
            logger.info("Loading text2vec-large-chinese model (this may take 10-30s on first run)...")
            from text2vec import SentenceModel
            self._model = SentenceModel("shibing624/text2vec-large-chinese")
            logger.info("text2vec-large-chinese model loaded successfully.")
        return self._model

    @property
    def dimension(self) -> int:
        return 1024

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        vectors = self.model.encode(texts)
        return vectors.tolist()

    def embed_query(self, query: str) -> List[float]:
        return self.embed_texts([query])[0]


_embedding_service: EmbeddingService = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
