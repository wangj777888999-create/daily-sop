import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class BM25Index:
    """BM25 memory index, rebuilt from knowledge_chunks.json at startup."""

    def __init__(self):
        self._chunks: List[dict] = []
        self._index = None

    def build(self, chunks: List[dict]):
        import jieba
        from rank_bm25 import BM25Okapi

        self._chunks = chunks
        if not chunks:
            self._index = None
            return
        tokenized = [list(jieba.cut(c.get("text", ""))) for c in chunks]
        self._index = BM25Okapi(tokenized)
        logger.info(f"BM25 index built: {len(chunks)} chunks")

    def search(self, query: str, top_k: int = 5,
               doc_ids: Optional[List[str]] = None) -> List[dict]:
        if not self._index or not self._chunks:
            return []

        import jieba
        tokens = list(jieba.cut(query))
        raw_scores = self._index.get_scores(tokens)
        max_score = max(raw_scores) if max(raw_scores) > 0 else 1

        results = []
        for chunk, raw in zip(self._chunks, raw_scores):
            if raw == 0:
                continue
            if doc_ids and chunk.get("doc_id") not in doc_ids:
                continue
            results.append({**chunk, "score": round(raw / max_score, 4)})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def add_chunks(self, new_chunks: List[dict]):
        self._chunks.extend(new_chunks)
        self.build(self._chunks)

    def remove_doc(self, doc_id: str):
        self._chunks = [c for c in self._chunks if c.get("doc_id") != doc_id]
        if self._chunks:
            self.build(self._chunks)
        else:
            self._index = None

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)
