"""ChromaDB 向量存储 — 每个分类一个 collection"""
import logging
import os
from typing import List, Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")

# 分类 → collection 名
COLLECTION_NAMES = {
    "policy":   "kb_policy",
    "activity": "kb_activity",
    "data":     "kb_data",
}


class VectorStore:
    """ChromaDB 向量库封装，每个分类独立 collection，共享 embedding function。"""

    def __init__(self, embed_fn):
        os.makedirs(CHROMA_DIR, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        self._embed_fn = embed_fn
        self._collections: dict = {}
        for category, col_name in COLLECTION_NAMES.items():
            self._collections[category] = self._client.get_or_create_collection(
                name=col_name,
                metadata={"hnsw:space": "cosine"},
            )
        logger.info("ChromaDB collections ready: %s", list(COLLECTION_NAMES.values()))

    def _col(self, category: str):
        if category not in self._collections:
            raise ValueError(f"Unknown category: {category}. Must be one of {list(COLLECTION_NAMES)}")
        return self._collections[category]

    # ── 写入 ──

    def add_chunks(self, category: str, chunks: List[dict]) -> None:
        """将 chunks 写入对应分类的 collection。"""
        if not chunks:
            return
        col = self._col(category)
        texts = [c["text"] for c in chunks]
        ids = [c["id"] for c in chunks]
        metas = [
            {
                "doc_id": c.get("doc_id", ""),
                "doc_name": c.get("doc_name", ""),
                "chunk_index": c.get("chunk_index", 0),
                "chunk_type": c.get("chunk_type", "paragraph"),
                "heading_path": c.get("heading_path", ""),
                "page": c.get("page", 0),
            }
            for c in chunks
        ]
        embeddings = self._embed_fn(texts)
        col.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metas)
        logger.info("VectorStore: upserted %d chunks → %s", len(chunks), category)

    def remove_doc(self, category: str, doc_id: str) -> None:
        """删除某文档在对应分类中的所有 chunk。"""
        col = self._col(category)
        results = col.get(where={"doc_id": doc_id})
        ids_to_delete = results.get("ids", [])
        if ids_to_delete:
            col.delete(ids=ids_to_delete)
            logger.info("VectorStore: deleted %d chunks for doc %s", len(ids_to_delete), doc_id)

    # ── 检索 ──

    def search(
        self,
        query: str,
        category: str,
        top_k: int = 20,
        doc_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        """向量检索，返回带排名的 chunk 列表。"""
        col = self._col(category)
        if col.count() == 0:
            return []

        query_embedding = self._embed_fn([query])[0]
        where = {"doc_id": {"$in": doc_ids}} if doc_ids else None

        kwargs = dict(
            query_embeddings=[query_embedding],
            n_results=min(top_k, col.count()),
            include=["documents", "metadatas", "distances"],
        )
        if where:
            kwargs["where"] = where

        res = col.query(**kwargs)

        results = []
        docs_list = res.get("documents", [[]])[0]
        metas_list = res.get("metadatas", [[]])[0]
        dists_list = res.get("distances", [[]])[0]

        for text, meta, dist in zip(docs_list, metas_list, dists_list):
            # ChromaDB cosine distance: 0=identical, 2=opposite → score=1-dist/2
            score = round(1.0 - dist / 2.0, 4)
            results.append({
                "text": text,
                "doc_id": meta.get("doc_id", ""),
                "doc_name": meta.get("doc_name", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "chunk_type": meta.get("chunk_type", "paragraph"),
                "heading_path": meta.get("heading_path", ""),
                "page": meta.get("page", 0),
                "vector_score": score,
            })
        return results

    def search_multi_category(
        self,
        query: str,
        top_k: int = 20,
        doc_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        """跨所有分类检索，合并结果。"""
        all_results = []
        for category in COLLECTION_NAMES:
            results = self.search(query, category, top_k=top_k, doc_ids=doc_ids)
            for r in results:
                r["category"] = category
            all_results.extend(results)
        all_results.sort(key=lambda x: x["vector_score"], reverse=True)
        return all_results[:top_k]

    # ── 统计 ──

    def count(self, category: Optional[str] = None) -> int:
        if category:
            return self._col(category).count()
        return sum(col.count() for col in self._collections.values())
