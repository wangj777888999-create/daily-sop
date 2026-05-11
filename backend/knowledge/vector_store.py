import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB wrapper for knowledge chunk storage and similarity search."""

    def __init__(self, persist_dir: str):
        os.makedirs(persist_dir, exist_ok=True)
        import chromadb
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="knowledge_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"VectorStore initialized at {persist_dir}, "
                     f"collection size: {self.collection.count()}")

    def add_chunks(self, doc_id: str, doc_name: str, chunks: List[dict],
                   embeddings: List[List[float]]):
        if not chunks:
            return

        ids = [f"{doc_id}_{c['chunk_index']}" for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "doc_name": doc_name,
                "chunk_index": c["chunk_index"],
                "chunk_type": c.get("chunk_type", "paragraph"),
                "heading_path": c.get("heading_path", ""),
                "page": c.get("page", 0),
            }
            for c in chunks
        ]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(self, query_embedding: List[float], top_k: int = 5,
               doc_ids: Optional[List[str]] = None) -> List[dict]:
        where = None
        if doc_ids:
            where = {"doc_id": {"$in": doc_ids}}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"][0] else {}
                distance = results["distances"][0][i] if results["distances"][0] else 1.0
                score = 1.0 / (1.0 + distance) if distance is not None else 0.0

                output.append({
                    "chunk_id": chunk_id,
                    "doc_id": meta.get("doc_id", ""),
                    "doc_name": meta.get("doc_name", ""),
                    "chunk_text": results["documents"][0][i] if results["documents"][0] else "",
                    "chunk_type": meta.get("chunk_type", "paragraph"),
                    "heading_path": meta.get("heading_path", ""),
                    "page": meta.get("page", 0),
                    "score": round(score, 4),
                })

        return output

    def delete_doc(self, doc_id: str):
        try:
            results = self.collection.get(where={"doc_id": doc_id})
            if results and results["ids"]:
                self.collection.delete(ids=results["ids"])
                logger.info(f"Deleted {len(results['ids'])} chunks for doc {doc_id}")
        except Exception as e:
            logger.warning(f"Error deleting chunks for doc {doc_id}: {e}")

    def count(self) -> int:
        return self.collection.count()
